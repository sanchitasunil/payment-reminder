"""Update dispatch rule to include room_config.agents for instant auto-dispatch.

When LiveKit creates the room via dispatchRuleIndividual, it will automatically
dispatch 'payment-agent' — no polling delay needed.  This cuts ~1s of ringback.
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
OLD_RULE_ID = "SDR_PYeVsNUb4hwc"  # payment-agent-individual (without room_config)


async def main() -> None:
    lk = api.LiveKitAPI(
        url=os.environ["LIVEKIT_URL"],
        api_key=os.environ["LIVEKIT_API_KEY"],
        api_secret=os.environ["LIVEKIT_API_SECRET"],
    )

    # Delete old rule
    try:
        await lk.sip.delete_sip_dispatch_rule(
            api.DeleteSIPDispatchRuleRequest(sip_dispatch_rule_id=OLD_RULE_ID)
        )
        print(f"Deleted: {OLD_RULE_ID}")
    except Exception as e:
        print(f"Could not delete {OLD_RULE_ID}: {e}")

    # Create rule with room_config.agents for automatic dispatch
    req = api.CreateSIPDispatchRuleRequest(
        name="payment-agent-auto",
        trunk_ids=[TRUNK_ID],
        rule=sip_proto.SIPDispatchRule(
            dispatch_rule_individual=sip_proto.SIPDispatchRuleIndividual(
                room_prefix="payment-",
            )
        ),
    )
    req.room_config.agents.add().agent_name = "payment-agent"

    new_rule = await lk.sip.create_sip_dispatch_rule(req)
    print(f"Created: {new_rule.sip_dispatch_rule_id}")
    print(f"  Name:     {new_rule.name}")
    print(f"  TrunkIDs: {list(new_rule.trunk_ids)}")
    print(f"  Rule:     {new_rule.rule}")
    print(f"  Agents:   {[a.agent_name for a in new_rule.room_config.agents]}")

    await lk.aclose()


asyncio.run(main())
