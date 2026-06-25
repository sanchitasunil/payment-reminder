"""Directly dispatch a job to the payment-agent worker, bypassing Twilio/SIP.
Run this while agent.py start is running in another terminal.
You should see the agent's entrypoint logs appear immediately.
"""
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

    room_name = "payment-test-dispatch"
    print(f"Creating room: {room_name}")

    await lk.room.create_room(api.CreateRoomRequest(name=room_name))

    print("Dispatching job to payment-agent...")
    dispatch = await lk.agent_dispatch.create_dispatch(
        api.CreateAgentDispatchRequest(
            agent_name="payment-agent",
            room=room_name,
        )
    )
    print(f"Dispatch created: {dispatch.id}")
    print("Check agent.py terminal — entrypoint should have fired.")
    print(f"Room: {room_name}")

    await lk.aclose()


asyncio.run(main())
