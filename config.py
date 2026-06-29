from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(
            f"Required environment variable '{name}' is not set. "
            "Copy .env.example to .env and fill in your credentials."
        )
    return value


def _optional(name: str) -> str | None:
    return os.getenv(name) or None


def _normalize_sip_uri(uri: str) -> str:
    value = uri.strip()
    if value.lower().startswith("sip:"):
        value = value[4:]
    return value


# ── LiveKit (required) ─────────────────────────────────────────────────────────
LIVEKIT_URL: str = _require("LIVEKIT_URL")
LIVEKIT_API_KEY: str = _require("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET: str = _require("LIVEKIT_API_SECRET")

# Only needed for SIP transfer (human handoff over PSTN)
LIVEKIT_SIP_URI: str | None = _optional("LIVEKIT_SIP_URI")

# ── STT provider: "deepgram" (default) or "openai" ────────────────────────────
STT_PROVIDER: str = os.getenv("STT_PROVIDER", "deepgram")
DEEPGRAM_API_KEY: str | None = _optional("DEEPGRAM_API_KEY")
OPENAI_API_KEY: str | None = _optional("OPENAI_API_KEY")

if STT_PROVIDER == "deepgram" and not DEEPGRAM_API_KEY:
    raise ValueError("DEEPGRAM_API_KEY is required when STT_PROVIDER=deepgram")
if STT_PROVIDER == "openai" and not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is required when STT_PROVIDER=openai")

# ── LLM provider: "gemini" (default) | "openai" | "opencode" ─────────────────
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini")
GOOGLE_API_KEY: str | None = _optional("GOOGLE_API_KEY")
OPENCODE_API_KEY: str | None = _optional("OPENCODE_API_KEY")

if LLM_PROVIDER == "gemini" and not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY is required when LLM_PROVIDER=gemini")
if LLM_PROVIDER == "opencode" and not OPENCODE_API_KEY:
    raise ValueError("OPENCODE_API_KEY is required when LLM_PROVIDER=opencode")
if LLM_PROVIDER == "openai" and not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")

# ── Murf TTS (required) ───────────────────────────────────────────────────────
MURF_API_KEY: str = _require("MURF_API_KEY")

# ── Supabase — transcript persistence (optional) ──────────────────────────────
# If not set, call transcripts are logged locally but not persisted to a database.
SUPABASE_URL: str | None = _optional("SUPABASE_URL")
SUPABASE_KEY: str | None = _optional("SUPABASE_KEY")


def supabase_enabled() -> bool:
    return bool(SUPABASE_URL and SUPABASE_KEY)


# ── Human handoff — SIP transfer to human agent (optional) ────────────────────
# Set HUMAN_TRANSFER_NUMBER to enable live SIP transfers when the agent escalates.
HUMAN_TRANSFER_NUMBER: str | None = _optional("HUMAN_TRANSFER_NUMBER")


def handoff_enabled() -> bool:
    return bool(HUMAN_TRANSFER_NUMBER and LIVEKIT_SIP_URI)


# ── Twilio — SIP trunk setup + post-call WhatsApp (optional at agent runtime) ─
TWILIO_ACCOUNT_SID: str | None = _optional("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN: str | None = _optional("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER: str | None = _optional("TWILIO_PHONE_NUMBER")
TWILIO_WHATSAPP_FROM: str | None = _optional("TWILIO_WHATSAPP_FROM")


def whatsapp_enabled() -> bool:
    return bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_WHATSAPP_FROM)
