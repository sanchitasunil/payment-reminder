"""
SIP call transfer — forwards the live call to the clinic's real phone number.
Uses LiveKit SIP REFER (cold transfer).
Called when patient requests a human or Aria cannot resolve the query.
"""

from __future__ import annotations

import logging
from typing import Annotated

from livekit import api, rtc
from livekit.agents import RunContext, function_tool, get_job_context
from pydantic import Field

import config
from tools.transcript import get_call_session

logger = logging.getLogger(__name__)

CLINIC_FALLBACK = "080-41234567"


def _normalize_tel(number: str) -> str:
    """E.164 for tel: URI."""
    cleaned = number.strip().replace(" ", "").replace("-", "")
    if cleaned.startswith("tel:"):
        cleaned = cleaned[4:]
    if not cleaned.startswith("+"):
        if cleaned.startswith("0"):
            cleaned = f"+91{cleaned[1:]}"
        elif len(cleaned) == 10 and cleaned.isdigit():
            cleaned = f"+91{cleaned}"
        else:
            cleaned = f"+{cleaned}"
    return f"tel:{cleaned}"


def _find_sip_participant_identity(room: rtc.Room) -> str | None:
    for participant in room.remote_participants.values():
        if participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
            return participant.identity
    return None


async def transfer_call(
    room_name: str,
    sip_participant_identity: str,
    reason: str = "patient request",
) -> bool:
    """
    Transfer the active SIP call to the clinic's real phone number.
    Returns True on success, False on any failure. Never raises.
    """
    if not config.handoff_enabled():
        logger.debug("Handoff disabled — skipping SIP REFER")
        return False

    if not config.CLINIC_PHONE_NUMBER:
        return False

    transfer_to = _normalize_tel(config.CLINIC_PHONE_NUMBER)

    try:
        async with api.LiveKitAPI(
            url=config.LIVEKIT_URL,
            api_key=config.LIVEKIT_API_KEY,
            api_secret=config.LIVEKIT_API_SECRET,
        ) as lk_api:
            await lk_api.sip.transfer_sip_participant(
                api.TransferSIPParticipantRequest(
                    room_name=room_name,
                    participant_identity=sip_participant_identity,
                    transfer_to=transfer_to,
                    play_dialtone=False,
                )
            )

        logger.info(
            "Call transferred to %s, reason=%s",
            config.CLINIC_PHONE_NUMBER,
            reason,
        )
        return True
    except Exception as exc:
        logger.error("SIP transfer failed: %s", exc)
        return False


@function_tool()
async def transfer_to_human(
    reason: Annotated[
        str,
        Field(
            description=(
                "Why the patient needs a human. e.g. 'patient requested', "
                "'medical question outside scope', 'complaint'"
            )
        ),
    ],
    context: RunContext,
) -> str:
    """
    Transfer the call to a human at the clinic.
    Call this when:
    - The patient explicitly asks to speak to a doctor or human
    - The patient is distressed and needs immediate human support
    - The query is a medical question Aria cannot answer
    - The patient has complained or is frustrated after two attempts
    - The patient has asked for something outside Aria's scope after one redirect
    Do NOT call this for routine bookings, FAQs, or cancellations Aria can handle.
    reason: brief description of why the transfer is needed.
    """
    _ = context  # required for tool injection

    job_ctx = get_job_context(required=False)
    if not job_ctx:
        logger.warning("Transfer requested but no job context")
        return (
            "I wasn't able to connect the transfer. "
            f"Please call us directly on {CLINIC_FALLBACK}."
        )

    sip_identity = _find_sip_participant_identity(job_ctx.room)
    if not sip_identity:
        logger.warning("Transfer requested but no SIP participant found")
        return (
            "I wasn't able to connect the transfer. "
            f"Please call us directly on {CLINIC_FALLBACK}."
        )

    if not config.handoff_enabled():
        logger.info("Handoff disabled — no CLINIC_PHONE_NUMBER configured")
        return (
            f"Please call us directly on {CLINIC_FALLBACK} and our team will help you."
        )

    success = await transfer_call(
        room_name=job_ctx.room.name,
        sip_participant_identity=sip_identity,
        reason=reason,
    )

    if success:
        cs = get_call_session(job_ctx.room.name)
        if cs:
            cs.set_outcome(intent=cs.intent, outcome="transferred")

        return (
            "I'm transferring you to our team right now. "
            "Please hold for just a moment."
        )

    return (
        "I wasn't able to connect the transfer right now. "
        f"Please call us directly on {CLINIC_FALLBACK}."
    )
