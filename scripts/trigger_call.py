"""
Trigger an outbound payment reminder call via Twilio → LiveKit.

HOW IT WORKS
  1. This script writes the chosen scenario to scenario_config.json.
  2. It calls Twilio's REST API to dial your phone number.
  3. When you answer, Twilio connects the call to a LiveKit SIP inbound trunk.
  4. LiveKit creates a room named  payment-<id>  and dispatches it to your
     running  agent.py  worker.
  5. Asha (the payment agent) speaks to you in real time.

ONE-TIME SETUP (do this before the first call — already done if dispatch-rule.json exists)
  LiveKit Cloud dashboard → SIP:
    a) Create an inbound SIP trunk — copy the SIP URI into .env as LIVEKIT_SIP_URI
    b) Create a dispatch rule:
         Room prefix:  payment-
         Agent name:   payment-agent

  Twilio console.twilio.com:
    a) Buy a phone number with Voice capability
    b) No webhook needed — TwiML is generated inline by this script

REQUIRED in .env
  LIVEKIT_SIP_URI          e.g.  abc123.sip.livekit.cloud
  TWILIO_ACCOUNT_SID       ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
  TWILIO_AUTH_TOKEN        xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
  TWILIO_PHONE_NUMBER      +919876500000

USAGE
  python scripts/trigger_call.py --to +919876543210
  python scripts/trigger_call.py --to +919876543210 --scenario hardship
  python scripts/trigger_call.py --to +919876543210 --scenario already_paid
  python scripts/trigger_call.py --to +919876543210 --scenario wrong_person
  python scripts/trigger_call.py --to +919876543210 --scenario grievance_pending
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid

# ── Project root on sys.path ──────────────────────────────────────────────────
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Load .env from the project root explicitly so the script works regardless
# of which directory the user runs it from.
from dotenv import load_dotenv

load_dotenv(os.path.join(_PROJECT_ROOT, ".env"), override=False)

VALID_SCENARIOS = [
    "normal_reminder",
    "already_paid",
    "hardship",
    "wrong_person",
    "grievance_pending",
]

_CONFIG_PATH = os.path.join(_PROJECT_ROOT, "scenario_config.json")


# ── Env helpers ───────────────────────────────────────────────────────────────

def _getenv(*names: str) -> str | None:
    """Return the first non-empty value found among the given env var names."""
    for name in names:
        v = os.getenv(name, "").strip()
        if v:
            return v
    return None


def _check_env() -> list[str]:
    """Return a list of human-readable error strings for missing vars."""
    checks = [
        (
            ["LIVEKIT_SIP_URI"],
            "LiveKit SIP URI — Cloud dashboard → SIP → Trunks → your inbound trunk\n"
            "      (looks like  abc123.sip.livekit.cloud  — no  sip:  prefix)",
        ),
        (
            ["TWILIO_ACCOUNT_SID", "TWILLIO_ACCOUNT_SID"],
            "Twilio Account SID — console.twilio.com → Account Info (starts with AC)",
        ),
        (
            ["TWILIO_AUTH_TOKEN", "TWILLIO_AUTH_TOKEN"],
            "Twilio Auth Token — console.twilio.com → Account Info",
        ),
        (
            ["TWILIO_PHONE_NUMBER", "TWILLIO_PHONE_NUMBER"],
            "Your Twilio phone number in E.164 format, e.g. +911234567890",
        ),
    ]
    missing = []
    for names, hint in checks:
        if not _getenv(*names):
            primary = names[0]
            missing.append(f"  {primary}\n      {hint}")
    return missing


# ── Config helpers ────────────────────────────────────────────────────────────

def _load_config() -> dict:
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def _set_scenario(scenario: str) -> None:
    cfg = _load_config()
    cfg["scenario"] = scenario
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Trigger an outbound payment reminder call",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--to",
        required=True,
        metavar="PHONE",
        help="Borrower phone number in E.164 format, e.g. +919876543210",
    )
    parser.add_argument(
        "--scenario",
        choices=VALID_SCENARIOS,
        default=None,
        metavar="SCENARIO",
        help=f"One of: {', '.join(VALID_SCENARIOS)}  (updates scenario_config.json)",
    )
    args = parser.parse_args()

    print()
    print("=" * 62)
    print("  PAYMENT REMINDER — OUTBOUND CALL TRIGGER")
    print("=" * 62)

    # ── Env check ────────────────────────────────────────────────────────────
    missing = _check_env()
    if missing:
        print("\n[ERROR] Missing required environment variables:\n")
        for m in missing:
            print(m)
        print(f"\nCheck your .env at:  {os.path.join(_PROJECT_ROOT, '.env')}")
        sys.exit(1)

    # ── Scenario update ───────────────────────────────────────────────────────
    if args.scenario:
        _set_scenario(args.scenario)
        print(f"\n  Scenario set to '{args.scenario}' in scenario_config.json")

    cfg = _load_config()
    scenario = cfg["scenario"]

    # ── Pre-call guardrail check ──────────────────────────────────────────────
    from guardrails import GuardrailEngine

    can_proceed, block_reason = GuardrailEngine().check_pre_call(scenario)
    if not can_proceed:
        print(f"\n[BLOCKED] {block_reason}")
        print(f"  Scenario '{scenario}' prevents call initiation.")
        print("  The agent worker will also block this scenario when dispatched.")
        sys.exit(1)

    # ── Build call parameters ─────────────────────────────────────────────────
    call_id = uuid.uuid4().hex[:8]
    room_name = f"payment-{call_id}"

    sip_host = _getenv("LIVEKIT_SIP_URI", "").strip().lstrip("sip:")  # type: ignore[arg-type]
    sip_address = f"sip:{room_name}@{sip_host};transport=tcp"

    twilio_sid   = _getenv("TWILIO_ACCOUNT_SID",  "TWILLIO_ACCOUNT_SID")
    twilio_token = _getenv("TWILIO_AUTH_TOKEN",    "TWILLIO_AUTH_TOKEN")
    twilio_from  = _getenv("TWILIO_PHONE_NUMBER",  "TWILLIO_PHONE_NUMBER")

    # Inline TwiML — Twilio executes this when the callee answers
    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        "<Dial>"
        f"<Sip>{sip_address}</Sip>"
        "</Dial>"
        "</Response>"
    )

    print()
    print(f"  Calling:   {args.to}")
    print(f"  From:      {twilio_from}")
    print(f"  Scenario:  {scenario}")
    print(f"  Customer:  {cfg.get('customerName', '?')}")
    print(f"  Amount:    {cfg.get('amountDueFormatted', '?')} due {cfg.get('dueDate', '?')}")
    print(f"  Room:      {room_name}")
    print(f"  SIP:       {sip_address}")

    # ── Twilio call ───────────────────────────────────────────────────────────
    # Place the Twilio call FIRST so the SIP INVITE creates the room via
    # dispatchRuleDirect. Pre-creating the room via the API causes LiveKit to
    # return 486 Busy — it won't add a SIP participant to a room it didn't create.
    print("\n  Initiating call...")
    try:
        from twilio.rest import Client

        call = Client(twilio_sid, twilio_token).calls.create(
            to=args.to,
            from_=twilio_from,
            twiml=twiml,
            timeout=30,
        )

        print()
        print("  [OK] Call placed")
        print(f"  Call SID:  {call.sid}")
        print(f"  Status:    {call.status}")
        print()
        print("  Your phone will ring. Answer it — then:")
        print("  LiveKit SIP will create the room and we'll dispatch the agent.")
        print()

    except ImportError:
        print("\n[ERROR] twilio package not installed.  Run: pip install twilio")
        sys.exit(1)
    except Exception as exc:
        print(f"\n[ERROR] Twilio call failed: {exc}")
        sys.exit(1)

    # ── Wait for SIP to create the room, then dispatch agent ─────────────────
    # dispatchRuleIndividual accepts the SIP INVITE and creates a new room named
    # payment-<uuid>.  We snapshot existing payment-* rooms before the call,
    # then poll until a NEW one appears, and dispatch the agent to it.
    print("  Waiting for LiveKit to create a payment room (answer your phone)...")
    try:
        from livekit import api as lk_api

        async def _poll_and_dispatch() -> None:
            lk = lk_api.LiveKitAPI(
                url=os.environ["LIVEKIT_URL"],
                api_key=os.environ["LIVEKIT_API_KEY"],
                api_secret=os.environ["LIVEKIT_API_SECRET"],
            )
            # Snapshot rooms that exist right now so we only trigger on NEW ones.
            existing = await lk.room.list_rooms(lk_api.ListRoomsRequest())
            existing_names = {r.name for r in existing.rooms}

            for i in range(30):
                await asyncio.sleep(1)
                current = await lk.room.list_rooms(lk_api.ListRoomsRequest())
                new_rooms = [
                    r for r in current.rooms
                    if r.name not in existing_names and r.name.startswith("payment-")
                    and not r.name.startswith("payment-test-")
                ]
                if new_rooms:
                    created_room = new_rooms[0].name
                    dispatch = await lk.agent_dispatch.create_dispatch(
                        lk_api.CreateAgentDispatchRequest(
                            agent_name="payment-agent",
                            room=created_room,
                        )
                    )
                    print(f"  New room after {i+1}s: {created_room}")
                    print(f"  Agent dispatched: {dispatch.id}")
                    print()
                    print(f"  Watch the agent.py terminal for room: {created_room}")
                    print("  Outcome log -> logs/ when the call ends.")
                    await lk.aclose()
                    return
                if i % 5 == 4:
                    print(f"  Still waiting... ({i+1}s)")
            print("\n  [WARNING] No new payment room found within 30s — call may have failed")
            await lk.aclose()

        asyncio.run(_poll_and_dispatch())
    except Exception as exc:
        print(f"\n[ERROR] LiveKit dispatch failed: {exc}")
        sys.exit(1)

    print()
    print("=" * 62)


if __name__ == "__main__":
    main()
