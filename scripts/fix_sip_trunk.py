"""Update the inbound SIP trunk to allow connections from all addresses (0.0.0.0/0)."""
import asyncio
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

from livekit import api
from livekit.protocol import sip as sip_proto, models as models_proto


TRUNK_ID = "ST_Yo7YC6VngvcW"


async def main() -> None:
    lk = api.LiveKitAPI(
        url=os.environ["LIVEKIT_URL"],
        api_key=os.environ["LIVEKIT_API_KEY"],
        api_secret=os.environ["LIVEKIT_API_SECRET"],
    )

    req = api.UpdateSIPInboundTrunkRequest(
        sip_trunk_id=TRUNK_ID,
        update=sip_proto.SIPInboundTrunkUpdate(
            allowed_addresses=models_proto.ListUpdate(**{"set": ["0.0.0.0/0"]}),
        ),
    )
    updated = await lk.sip.update_sip_inbound_trunk(req)
    print(f"Updated trunk: {updated.sip_trunk_id}")
    print(f"Allowed addresses: {list(updated.allowed_addresses)}")
    await lk.aclose()


asyncio.run(main())
