"""
Trigger an outbound payment reminder call.

HOW IT WORKS
  1. Creates a LiveKit room named  payment-<id>.
  2. Dispatches the payment-agent worker to that room, passing the target
     phone number as job metadata.
  3. The agent starts fully (session ready), then calls  create_sip_participant
     to dial your phone via the LiveKit outbound SIP trunk → Twilio → PSTN.
  4. Your phone rings.  When you answer, the agent speaks immediately —
     no ringback, no delay.

ONE-TIME SETUP (run scripts/setup_outbound_trunk.py once, then add to .env)
  Twilio console.twilio.com → Elastic SIP Trunking:
    a) Create a trunk → Termination → note the SIP URI, e.g. mytrunk.pstn.twilio.com
    b) Termination → Credential Lists → create username/password

  LiveKit:
    python scripts/setup_outbound_trunk.py  (reads TWILIO_SIP_* vars from .env)
    → prints  LIVEKIT_SIP_OUTBOUND_TRUNK_ID=ST_xxx  — add to .env

REQUIRED in .env
  LIVEKIT_URL                wss://...
  LIVEKIT_API_KEY            APIxxx
  LIVEKIT_API_SECRET         xxx
  LIVEKIT_SIP_OUTBOUND_TRUNK_ID  ST_xxx   (from setup_outbound_trunk.py)

USAGE
  python scripts/trigger_call.py --to +919876543210
  python scripts/trigger_call.py --to +919876543210 --scenario hardship
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

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


def _getenv(*names: str) -> str | None:
    for name in names:
        v = os.getenv(name, "").strip()
        if v:
            return v
    return None


def _check_env() -> list[str]:
    checks = [
        (["LIVEKIT_URL"],        "LiveKit server URL — wss://your-project.livekit.cloud"),
        (["LIVEKIT_API_KEY"],    "LiveKit API key — from your project dashboard"),
        (["LIVEKIT_API_SECRET"], "LiveKit API secret — from your project dashboard"),
        (
            ["LIVEKIT_SIP_OUTBOUND_TRUNK_ID"],
            "LiveKit SIP outbound trunk ID — run  scripts/setup_outbound_trunk.py  first",
        ),
    ]
    missing = []
    for names, hint in checks:
        if not _getenv(*names):
            missing.append(f"  {names[0]}\n      {hint}")
    return missing


def _load_config() -> dict:
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def _set_scenario(scenario: str) -> None:
    cfg = _load_config()
    cfg["scenario"] = scenario
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Trigger an outbound payment reminder call")
    parser.add_argument("--to", required=True, metavar="PHONE",
                        help="Target phone number in E.164 format, e.g. +919876543210")
    parser.add_argument("--scenario", choices=VALID_SCENARIOS, default=None, metavar="SCENARIO",
                        help=f"One of: {', '.join(VALID_SCENARIOS)}")
    args = parser.parse_args()

    print()
    print("=" * 62)
    print("  PAYMENT REMINDER — OUTBOUND CALL TRIGGER")
    print("=" * 62)

    missing = _check_env()
    if missing:
        print("\n[ERROR] Missing required environment variables:\n")
        for m in missing:
            print(m)
        sys.exit(1)

    if args.scenario:
        _set_scenario(args.scenario)
        print(f"\n  Scenario set to '{args.scenario}'")

    cfg = _load_config()
    scenario = cfg["scenario"]

    from guardrails import GuardrailEngine
    can_proceed, block_reason = GuardrailEngine().check_pre_call(scenario)
    if not can_proceed:
        print(f"\n[BLOCKED] {block_reason}")
        sys.exit(1)

    call_id   = uuid.uuid4().hex[:8]
    room_name = f"payment-{call_id}"
    trunk_id  = _getenv("LIVEKIT_SIP_OUTBOUND_TRUNK_ID")

    print()
    print(f"  Calling:   {args.to}")
    print(f"  Scenario:  {scenario}")
    print(f"  Customer:  {cfg.get('customerName', '?')}")
    print(f"  Amount:    {cfg.get('amountDueFormatted', '?')} due {cfg.get('dueDate', '?')}")
    print(f"  Room:      {room_name}")
    print(f"  Trunk:     {trunk_id}")

    metadata = json.dumps({"phone_number": args.to, "scenario": scenario})

    async def _dispatch() -> None:
        from livekit import api as lk_api
        lk = lk_api.LiveKitAPI(
            url=os.environ["LIVEKIT_URL"],
            api_key=os.environ["LIVEKIT_API_KEY"],
            api_secret=os.environ["LIVEKIT_API_SECRET"],
        )
        await lk.room.create_room(lk_api.CreateRoomRequest(name=room_name))
        dispatch = await lk.agent_dispatch.create_dispatch(
            lk_api.CreateAgentDispatchRequest(
                agent_name="payment-agent",
                room=room_name,
                metadata=metadata,
            )
        )
        print(f"\n  Agent dispatched: {dispatch.id}")
        print(f"  The agent will dial {args.to} once its session is ready.")
        print(f"  Your phone will ring in ~3-5s. Answer it — Asha speaks immediately.")
        print()
        print(f"  Watch agent.py terminal for room: {room_name}")
        print("  Outcome log -> logs/ when the call ends.")
        await lk.aclose()

    print("\n  Dispatching agent...")
    try:
        asyncio.run(_dispatch())
    except Exception as exc:
        print(f"\n[ERROR] Dispatch failed: {exc}")
        sys.exit(1)

    print()
    print("=" * 62)


if __name__ == "__main__":
    main()
