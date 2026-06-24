"""
Call transcript collection and storage.
Accumulates turns during a call, writes to Supabase on call end.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from supabase import create_client

import config

logger = logging.getLogger(__name__)

_active_sessions: dict[str, CallSession] = {}


@dataclass
class Turn:
    role: Literal["agent", "user"]
    text: str
    ts: float = 0.0


@dataclass
class CallSession:
    """
    Holds transcript state for one call. One instance per active call,
    stored on the AgentSession or passed through context.
    """

    phone: str
    started_at: float = field(default_factory=time.time)
    turns: list[Turn] = field(default_factory=list)
    booking_id: str | None = None
    intent: str = "unknown"
    call_outcome: str = "unknown"

    def add_turn(self, role: Literal["agent", "user"], text: str) -> None:
        """Append a turn with timestamp relative to call start."""
        cleaned = text.strip()
        if not cleaned:
            return
        if self.turns and self.turns[-1].role == role and self.turns[-1].text == cleaned:
            return
        relative_ts = round(time.time() - self.started_at, 2)
        self.turns.append(Turn(role=role, text=cleaned, ts=relative_ts))

    def set_outcome(
        self,
        intent: str,
        outcome: str,
        booking_id: str | None = None,
    ) -> None:
        self.intent = intent
        self.call_outcome = outcome
        if booking_id:
            self.booking_id = booking_id

    def to_transcript_json(self) -> list[dict]:
        return [{"role": t.role, "text": t.text, "ts": t.ts} for t in self.turns]

    def duration_seconds(self) -> int:
        return int(time.time() - self.started_at)


def register_call_session(room_name: str, session: CallSession) -> None:
    _active_sessions[room_name] = session


def unregister_call_session(room_name: str) -> CallSession | None:
    return _active_sessions.pop(room_name, None)


def get_call_session(room_name: str) -> CallSession | None:
    return _active_sessions.get(room_name)


def infer_intent_from_turns(session: CallSession) -> None:
    """Set intent from transcript keywords when not set explicitly."""
    if session.intent != "unknown":
        return

    all_text = " ".join(t.text.lower() for t in session.turns)
    if any(w in all_text for w in ("book", "appointment", "schedule")):
        session.intent = "booking"
    elif any(w in all_text for w in ("cancel", "cancellation")):
        session.intent = "cancellation"
    elif any(w in all_text for w in ("reschedule", "change", "move")):
        session.intent = "reschedule"
    elif session.turns:
        session.intent = "faq"


async def save_transcript(session: CallSession) -> bool:
    """
    Write the completed call session to Supabase call_logs.
    Called once at the end of every call. Never raises.
    Returns True on success, False on error.
    """

    def _save() -> bool:
        try:
            client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
            ended = datetime.now(timezone.utc)
            started = datetime.fromtimestamp(session.started_at, tz=timezone.utc)

            client.table("call_logs").insert(
                {
                    "phone": session.phone,
                    "started_at": started.isoformat(),
                    "ended_at": ended.isoformat(),
                    "duration_seconds": session.duration_seconds(),
                    "transcript": session.to_transcript_json(),
                    "booking_id": session.booking_id,
                    "intent": session.intent,
                    "call_outcome": session.call_outcome,
                }
            ).execute()

            logger.info(
                "Transcript saved: %d turns, %ss, outcome=%s",
                len(session.turns),
                session.duration_seconds(),
                session.call_outcome,
            )
            return True
        except Exception as exc:
            logger.error("Transcript save failed: %s", exc)
            return False

    try:
        return await asyncio.to_thread(_save)
    except Exception as exc:
        logger.error("Transcript save failed: %s", exc)
        return False
