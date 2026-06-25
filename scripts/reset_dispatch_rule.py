"""Delete the current dispatchRuleDirect and create a dispatchRuleIndividual.

dispatchRuleIndividual accepts the SIP INVITE immediately (no 486) and creates
a new room named  payment-<uuid>.  trigger_call.py then polls for that room
and dispatches the agent explicitly.
"""
import asyncio
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

from livekit import api
from livekit.protocol import sip as sip_proto

TRUNK_ID = "ST_Yo7YC6VngvcW"
OLD_RULE_ID = "SDR_niFEyH282Xn8"  # payment-agent-direct (dispatchRuleDirect)


async def main() -> None:
    lk = api.LiveKitAPI(
        url=os.environ["LIVEKIT_URL"],
        api_key=os.environ["LIVEKIT_API_KEY"],
        api_secret=os.environ["LIVEKIT_API_SECRET"],
    )

    # Delete old direct rule
    try:
        await lk.sip.delete_sip_dispatch_rule(
            api.DeleteSIPDispatchRuleRequest(sip_dispatch_rule_id=OLD_RULE_ID)
        )
        print(f"Deleted old rule: {OLD_RULE_ID}")
    except Exception as e:
        print(f"Could not delete {OLD_RULE_ID}: {e}")

    # Create new individual rule
    new_rule = await lk.sip.create_sip_dispatch_rule(
        api.CreateSIPDispatchRuleRequest(
            name="payment-agent-individual",
            trunk_ids=[TRUNK_ID],
            rule=sip_proto.SIPDispatchRule(
                dispatch_rule_individual=sip_proto.SIPDispatchRuleIndividual(
                    room_prefix="payment-",
                )
            ),
        )
    )
    print(f"Created new rule: {new_rule.sip_dispatch_rule_id}")
    print(f"  Name:       {new_rule.name}")
    print(f"  TrunkIDs:   {list(new_rule.trunk_ids)}")
    print(f"  Rule:       {new_rule.rule}")

    await lk.aclose()


asyncio.run(main())
