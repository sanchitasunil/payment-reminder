"""Diagnostic: test both HTTP and WebSocket Murf endpoints."""
import asyncio
import base64
import json
import os
import aiohttp
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ["MURF_API_KEY"]
BASE_URL = "https://global.api.murf.ai"
VOICE = "en-IN-anisha"
LOCALE = "en-IN"
MODEL = "FALCON"
STYLE = "Conversation"
SAMPLE_RATE = 24000

TEXT = "Hello, this is a test of the payment reminder agent."


async def test_http(session: aiohttp.ClientSession) -> None:
    print("--- HTTP /v1/speech/stream ---")
    async with session.post(
        f"{BASE_URL}/v1/speech/stream",
        headers={"api-key": API_KEY},
        json={
            "text": TEXT,
            "model": MODEL,
            "multiNativeLocale": LOCALE,
            "voice_id": VOICE,
            "style": STYLE,
            "format": "pcm",
            "sample_rate": SAMPLE_RATE,
        },
    ) as resp:
        if resp.status == 200:
            body = await resp.read()
            print(f"  OK — {len(body)} bytes")
        else:
            body = await resp.text()
            print(f"  {resp.status} ERROR: {body[:500]}")


async def test_websocket(session: aiohttp.ClientSession) -> None:
    print("--- WebSocket /v1/speech/stream-input ---")
    url = (
        f"wss://global.api.murf.ai/v1/speech/stream-input"
        f"?api-key={API_KEY}&sample_rate={SAMPLE_RATE}&format=pcm&model={MODEL}"
    )
    try:
        ws = await session.ws_connect(url)
        print("  WebSocket connected")

        pkt = {
            "voice_config": {
                "voice_id": VOICE,
                "style": STYLE,
                "multi_native_locale": LOCALE,
            },
            "min_buffer_size": 3,
            "max_buffer_delay_in_ms": 0,
            "context_id": "test-ctx",
            "text": TEXT,
        }
        await ws.send_str(json.dumps(pkt))

        end_pkt = {"context_id": "test-ctx", "end": True}
        await ws.send_str(json.dumps(end_pkt))

        audio_bytes = 0
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                if data.get("audio"):
                    audio_bytes += len(base64.b64decode(data["audio"]))
                elif data.get("final"):
                    print(f"  OK — received final, {audio_bytes} audio bytes total")
                    break
                elif "error" in data or "error_message" in data:
                    print(f"  ERROR: {data}")
                    break
            elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                print(f"  WebSocket closed/error: {msg}")
                break
        await ws.close()
    except Exception as e:
        print(f"  EXCEPTION: {e}")


async def main() -> None:
    async with aiohttp.ClientSession() as session:
        await test_http(session)
        await test_websocket(session)


asyncio.run(main())
