# Call flow:
# Phone call → Twilio number → TwiML Bin → LiveKit SIP URI
# → SIP inbound trunk → dispatch rule → clinic-agent worker
# → AgentSession (STT(Deepgram or gpt-realtime-whisper) → LLM → TTS(Murf Falcon))  [LLM_PROVIDER=gemini/opencode/openai]

from __future__ import annotations

import asyncio
import logging
import time

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentSession,
    AutoSubscribe,
    JobContext,
    JobProcess,
    WorkerOptions,
    cli,
)
from livekit.agents.llm import ChatContext
from livekit.agents import tts as agents_tts
from livekit.agents.tts import AudioEmitter
from livekit.agents.types import APIConnectOptions
from livekit.agents.utils import http_context as _http_ctx
from livekit.plugins import deepgram, google, openai, silero
from livekit.plugins import murf

import config  # validates required env vars at import time
from prompts.system_prompt import build_system_prompt
from tools.handoff import transfer_to_human
from tools.transcript import (
    CallSession,
    infer_intent_from_turns,
    register_call_session,
    save_transcript,
    unregister_call_session,
)
from livekit.agents.voice.events import ConversationItemAddedEvent, UserInputTranscribedEvent

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("clinic-agent")
logger.setLevel(logging.INFO)

# Suppress HTTP/2 frame-level debug noise from Supabase client
logging.getLogger("hpack").setLevel(logging.WARNING)
logging.getLogger("hpack.table").setLevel(logging.WARNING)
logging.getLogger("h2").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

OPENING_LINE = (
    "Hello, thank you for calling The Clinic. I'm Matthew, your AI receptionist. "
    "How may I help you today?"
)


def _opening_line_for_patient(patient_memory: dict | None) -> str:
    if patient_memory and patient_memory.get("name"):
        name = patient_memory["name"]
        return (
            f"Hello {name}, welcome back to The Clinic. I'm Matthew, your AI receptionist. "
            f"How can I help you today?"
        )
    return OPENING_LINE


def _sip_caller_phone(participant: rtc.RemoteParticipant) -> str | None:
    if participant.kind != rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
        return None
    return participant.attributes.get("sip.phoneNumber") or participant.identity


async def _resolve_caller_phone(ctx: JobContext, is_phone: bool) -> str | None:
    if not is_phone:
        return None

    for participant in ctx.room.remote_participants.values():
        phone = _sip_caller_phone(participant)
        if phone:
            return phone

    try:
        participant = await asyncio.wait_for(ctx.wait_for_participant(), timeout=10.0)
        return _sip_caller_phone(participant)
    except asyncio.TimeoutError:
        return None


# ── Pre-synthesized greeting cache ────────────────────────────────────────────

class _CachedChunkedStream(agents_tts.ChunkedStream):
    """Replays pre-synthesized PCM frames without calling the TTS API."""

    def __init__(
        self,
        *,
        tts_instance: agents_tts.TTS,
        input_text: str,
        frames: list[rtc.AudioFrame],
        conn_options: APIConnectOptions,
    ) -> None:
        super().__init__(tts=tts_instance, input_text=input_text, conn_options=conn_options)
        self._frames = frames

    async def _run(self, output_emitter: AudioEmitter) -> None:
        if not self._frames:
            return
        first = self._frames[0]
        output_emitter.initialize(
            request_id="cached-greeting",
            sample_rate=first.sample_rate,
            num_channels=first.num_channels,
            mime_type="audio/pcm",
        )
        for frame in self._frames:
            output_emitter.push(bytes(frame.data))


class CachedGreetingTTS(agents_tts.TTS):
    """Wraps a TTS and plays pre-cached audio for the opening greeting call."""

    def __init__(
        self,
        inner: agents_tts.TTS,
        greeting_text: str,
        greeting_frames: list[rtc.AudioFrame],
    ) -> None:
        super().__init__(
            capabilities=inner.capabilities,
            sample_rate=inner.sample_rate,
            num_channels=inner.num_channels,
        )
        self._inner = inner
        self._greeting_text = greeting_text
        self._greeting_frames = greeting_frames
        self._greeting_used = False

    def synthesize(
        self,
        text: str,
        *,
        conn_options: APIConnectOptions = APIConnectOptions(),
    ) -> agents_tts.ChunkedStream:
        if not self._greeting_used and self._greeting_frames and text == self._greeting_text:
            self._greeting_used = True
            logger.info("Serving pre-cached greeting (no TTS API call)")
            return _CachedChunkedStream(
                tts_instance=self,
                input_text=text,
                frames=self._greeting_frames,
                conn_options=conn_options,
            )
        return self._inner.synthesize(text, conn_options=conn_options)

    def stream(
        self,
        *,
        conn_options: APIConnectOptions = APIConnectOptions(),
    ) -> agents_tts.SynthesizeStream:
        return self._inner.stream(conn_options=conn_options)

    async def aclose(self) -> None:
        await self._inner.aclose()


# ── Agent ──────────────────────────────────────────────────────────────────────

class ClinicAgent(Agent):
    def __init__(self, instructions: str, opening_line: str) -> None:
        chat_ctx = ChatContext()
        chat_ctx.add_message(role="assistant", content=opening_line)
        super().__init__(
            instructions=instructions,
            chat_ctx=chat_ctx,
            tools=[
                transfer_to_human,
            ],
        )


def prewarm(proc: JobProcess) -> None:
    """Load VAD weights and pre-synthesize the opening greeting before first call."""
    proc.userdata["vad"] = silero.VAD.load()

    # tts_for_calls is kept clean (no asyncio.run() event-loop state).
    tts_for_calls = murf.TTS(voice="en-US-matthew", locale="en-US")

    async def _synthesise_greeting() -> list[rtc.AudioFrame]:
        # Throwaway instance: used only here so tts_for_calls stays uncontaminated.
        tts_tmp = murf.TTS(voice="en-US-matthew", locale="en-US")
        frames: list[rtc.AudioFrame] = []
        async with _http_ctx.open():
            async for audio in tts_tmp.synthesize(OPENING_LINE):
                frames.append(audio.frame)
        return frames

    try:
        greeting_frames = asyncio.run(_synthesise_greeting())
        total_s = sum(f.duration for f in greeting_frames)
        logger.info(
            "Greeting pre-synthesized: %d frames, %.1fs audio", len(greeting_frames), total_s
        )
        proc.userdata["tts"] = CachedGreetingTTS(tts_for_calls, OPENING_LINE, greeting_frames)
    except Exception:
        logger.exception("Greeting pre-synthesis failed, will synthesize on first call")
        proc.userdata["tts"] = tts_for_calls


def _is_phone_room(room_name: str) -> bool:
    return room_name.startswith("clinic-") and not room_name.startswith("clinic-test-")


async def _greet_phone_caller(
    ctx: JobContext,
    session: AgentSession,
    t0: float,
    opening_line: str,
) -> None:
    """Play opening greeting; TTS is fired immediately to overlap with participant-join wait."""
    handle = session.say(opening_line, allow_interruptions=False)
    logger.info("Greeting started at %.1fs", time.monotonic() - t0)

    participant: rtc.RemoteParticipant | None = None
    for p in ctx.room.remote_participants.values():
        participant = p
        logger.info(
            "Caller already in room: %s (%s)",
            p.identity,
            rtc.ParticipantKind.Name(p.kind),
        )
        break

    if participant is None:
        try:
            participant = await asyncio.wait_for(ctx.wait_for_participant(), timeout=20.0)
            logger.info(
                "Caller joined: %s (%s) at %.1fs",
                participant.identity,
                rtc.ParticipantKind.Name(participant.kind),
                time.monotonic() - t0,
            )
        except asyncio.TimeoutError:
            logger.error(
                "No caller in %s after 20s — remote=%s",
                ctx.room.name,
                list(ctx.room.remote_participants.keys()),
            )
            return

    session.room_io.set_participant(participant.identity)

    await asyncio.wait_for(handle.wait_for_playout(), timeout=60.0)
    logger.info("Opening greeting played at %.1fs", time.monotonic() - t0)


async def entrypoint(ctx: JobContext) -> None:
    t0 = time.monotonic()
    is_phone = _is_phone_room(ctx.room.name)

    await ctx.connect(
        auto_subscribe=AutoSubscribe.AUDIO_ONLY if is_phone else AutoSubscribe.SUBSCRIBE_ALL,
    )
    logger.info("Connected to %s (%.1fs)", ctx.room.name, time.monotonic() - t0)

    tts_instance = ctx.proc.userdata.get("tts") or murf.TTS(voice="en-US-matthew", locale="en-US")

    session = AgentSession(
        stt=openai.STT(model="gpt-realtime-whisper", use_realtime=True, language="en", api_key=config.OPENAI_API_KEY) if config.STT_PROVIDER == "openai"
        else deepgram.STT(model="nova-3", language="en-IN"),
        llm=google.LLM(model="gemini-2.5-flash") if config.LLM_PROVIDER == "gemini"
        else openai.LLM(model="gpt-4o-mini", api_key=config.OPENAI_API_KEY) if config.LLM_PROVIDER == "openai"
        else openai.LLM(model="kimi-k2.5", base_url="https://opencode.ai/zen/go/v1", api_key=config.OPENCODE_API_KEY),
        tts=tts_instance,
        vad=ctx.proc.userdata["vad"],
    )

    caller_phone = await _resolve_caller_phone(ctx, is_phone)

    prompt = build_system_prompt()
    opening_line = _opening_line_for_patient(None)

    log_phone = caller_phone.strip() if caller_phone else "unknown"
    call_session = CallSession(phone=log_phone)
    register_call_session(ctx.room.name, call_session)
    transcript_saved = False

    async def _finalize_transcript() -> None:
        nonlocal transcript_saved
        if transcript_saved:
            return
        transcript_saved = True
        infer_intent_from_turns(call_session)
        await save_transcript(call_session)
        unregister_call_session(ctx.room.name)

    def _on_room_disconnected(*_args: object) -> None:
        asyncio.create_task(_finalize_transcript())

    ctx.room.on("disconnected", _on_room_disconnected)

    @session.on("user_input_transcribed")
    def on_user_input_transcribed(event: UserInputTranscribedEvent) -> None:
        if event.is_final and event.transcript:
            call_session.add_turn("user", event.transcript)

    @session.on("conversation_item_added")
    def on_conversation_item_added(event: ConversationItemAddedEvent) -> None:
        item = event.item
        if item.type == "message" and item.role == "assistant":
            text = item.text_content
            if text:
                call_session.add_turn("agent", text)

    await session.start(ClinicAgent(prompt, opening_line), room=ctx.room)
    logger.info("Session started (%.1fs)", time.monotonic() - t0)

    if is_phone:
        try:
            await _greet_phone_caller(ctx, session, t0, opening_line)
        except asyncio.TimeoutError:
            logger.error("Phone greeting timed out — call may have dropped")
        except Exception:
            logger.exception("Phone greeting failed")
    while ctx.room.isconnected():
        await asyncio.sleep(0.25)

    await _finalize_transcript()
    logger.info("Room %s disconnected", ctx.room.name)


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
            agent_name="clinic-agent",
            num_idle_processes=1,
        )
    )
