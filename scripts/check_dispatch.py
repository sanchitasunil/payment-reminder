"""Print all SIP dispatch rules and inbound trunks configured in LiveKit Cloud."""
import asyncio
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

from livekit import api


async def main() -> None:
    lk = api.LiveKitAPI(
        url=os.environ["LIVEKIT_URL"],
        api_key=os.environ["LIVEKIT_API_KEY"],
        api_secret=os.environ["LIVEKIT_API_SECRET"],
    )

    print("=== SIP Inbound Trunks ===\n")
    trunks = await lk.sip.list_sip_inbound_trunk(api.ListSIPInboundTrunkRequest())
    if not trunks.items:
        print("  NO inbound trunks found.\n")
    else:
        for t in trunks.items:
            print(f"  ID:               {t.sip_trunk_id}")
            print(f"  Name:             {t.name}")
            print(f"  Allowed Numbers:  {list(t.numbers)}")
            print(f"  Allowed Addrs:    {list(t.allowed_addresses)}")
            print()

    print("=== SIP Dispatch Rules ===\n")
    rules = await lk.sip.list_sip_dispatch_rule(api.ListSIPDispatchRuleRequest())
    if not rules.items:
        print("  NO dispatch rules found.\n")
    else:
        for r in rules.items:
            print(f"  ID:         {r.sip_dispatch_rule_id}")
            print(f"  Name:       {r.name}")
            print(f"  TrunkIDs:   {list(r.trunk_ids)}")
            print(f"  Rule:       {r.rule}")
            print(f"  RoomConfig: {r.room_config}")
            print()

    print("=== .env SIP URI ===\n")
    sip_uri = os.getenv("LIVEKIT_SIP_URI", "(not set)")
    twilio_num = os.getenv("TWILIO_PHONE_NUMBER", "(not set)")
    print(f"  LIVEKIT_SIP_URI:      {sip_uri}")
    print(f"  TWILIO_PHONE_NUMBER:  {twilio_num}")

    await lk.aclose()


asyncio.run(main())
