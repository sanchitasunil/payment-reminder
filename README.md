# Payment Reminder Agent

An outbound AI voice agent that calls borrowers, verifies their identity, presents payment context, and handles disputes, hardship, and human handoff — all within a strict compliance guardrail layer.

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://python.org)
[![LiveKit](https://img.shields.io/badge/Transport-LiveKit%20Agents-002cf2)](https://docs.livekit.io/agents)
![STT](https://img.shields.io/badge/STT-Deepgram%20%7C%20OpenAI%20Whisper-13EF93)
[![Murf](https://img.shields.io/badge/TTS-Murf%20Falcon-6366F1)](https://murf.ai/api)
[![Twilio](https://img.shields.io/badge/Phone-Twilio%20SIP-F22F46?logo=twilio&logoColor=white)](https://twilio.com)

---

## What it does

- **Dials outbound** via Twilio PSTN → LiveKit SIP outbound trunk, speaks with Murf Falcon TTS
- **Pre-synthesizes the opening greeting** during worker startup so the borrower hears audio the instant they pick up — no TTS latency on the first line
- **Verifies borrower identity** using the last four digits of their registered mobile number before disclosing any account details
- **Presents payment context** — amount due, due date, and a payment link sent to their registered number
- **Records a promise to pay** with a commitment date when the borrower agrees
- **Stops the payment flow immediately** if the borrower disputes, reports hardship, asks to stop being called, or requests a human — guardrails fire before the LLM can respond
- **Blocks the call entirely** when the account has an active grievance ticket
- **Logs a structured outcome file** (`logs/`) after every call — identity verified, dispute detected, ticket ID, outcome label, etc.
- **Persists call transcripts** to Supabase when configured
- **Transfers to a human agent** via SIP REFER when escalation is needed

---

## Call flow

```
trigger_call.py
  -> LiveKit: create room + create dispatch (phone number in metadata)
    -> agent worker: prewarm (VAD + greeting pre-synthesis)
      -> entrypoint: session.start()
        -> create_sip_participant (outbound trunk -> Twilio -> PSTN)
          -> borrower's phone rings
            -> borrower answers -> 200 OK
              -> agent greets immediately (cached audio, no TTS delay)
```

### State machine

```
PRE_CALL_CHECK
  -> OPENING_DISCLOSURE       (agent introduces itself, asks "Am I speaking with <name>?")
    -> IDENTITY_VERIFICATION  (last four digits of registered mobile)
      -> PAYMENT_CONTEXT      (amount, due date, offer payment link)
        -> INTENT_CLASSIFICATION
          -> SEND_PAYMENT_LINK  -> PROMISE_TO_PAY  -> CALL_SUMMARY
          -> DISPUTE_INTAKE     -> HUMAN_HANDOFF
          -> HARDSHIP_ESCALATION -> HUMAN_HANDOFF
  -> WRONG_PERSON_END         (any state — triggered by guardrail)
  -> HUMAN_HANDOFF            (any state — triggered by guardrail)
```

Guardrails run on every user utterance and override the LLM routing decision: dispute phrases → `DISPUTE_INTAKE`, hardship phrases → `HARDSHIP_ESCALATION`, "stop calling" or human request → `HUMAN_HANDOFF`, wrong person → `WRONG_PERSON_END`. The agent never discloses account details to an unverified or wrong-person caller.

---

## Contents

1. [Quick start](#1-quick-start)
2. [Environment variables](#2-environment-variables)
3. [LLM and STT providers](#3-llm-and-stt-providers)
4. [Telephony setup](#4-telephony-setup)
5. [Scenarios](#5-scenarios)
6. [Testing without a phone](#6-testing-without-a-phone)
7. [Triggering a real call](#7-triggering-a-real-call)
8. [Transcript logging and outcome files](#8-transcript-logging-and-outcome-files)
9. [Adapting for your use case](#9-adapting-for-your-use-case)
10. [Common errors](#10-common-errors)

---

## 1. Quick start

### Clone

```bash
git clone <repo-url>
cd payment-reminder
```

### Create a virtual environment

```bash
python -m venv venv
```

```bash
# macOS / Linux
source venv/bin/activate
```

```powershell
# Windows
venv\Scripts\Activate.ps1
```

### Install dependencies

```bash
pip install -r requirements.txt
```

### Configure environment variables

```bash
# macOS / Linux
cp .env.example .env
```

```powershell
# Windows
Copy-Item .env.example .env
```

Fill in `.env`. See [Environment variables](#2-environment-variables) for where to find each value.

### Download VAD model

```bash
python agent.py download-files
```

Downloads Silero VAD weights. Watch for the confirmation line in the output.

### Run the agent worker

```bash
# Browser / playground testing — no phone needed
python agent.py dev

# Phone testing — stable, no file-watcher restarts
python agent.py start
```

### Trigger a call (separate terminal)

```bash
python scripts/trigger_call.py --to +919876543210
```

The agent dials the number, your phone rings in ~3–5 s. When you answer, Asha speaks immediately.

---

## 2. Environment variables

**Required**

| Variable | Where to get it |
|---|---|
| `LIVEKIT_URL` | [LiveKit Cloud](https://cloud.livekit.io) dashboard > your project |
| `LIVEKIT_API_KEY` | LiveKit Cloud > Settings > API Keys |
| `LIVEKIT_API_SECRET` | Same page as API key |
| `MURF_API_KEY` | [murf.ai/api/dashboard](https://murf.ai/api/dashboard) > Settings > API |
| `STT_PROVIDER` | `deepgram` (default) or `openai` — see [LLM and STT providers](#3-llm-and-stt-providers) |
| `DEEPGRAM_API_KEY` | [console.deepgram.com](https://console.deepgram.com) — required if `STT_PROVIDER=deepgram` |
| `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com) — required if `STT_PROVIDER=openai` or `LLM_PROVIDER=openai` |
| `LLM_PROVIDER` | `gemini` (default), `openai`, or `opencode` — see [LLM and STT providers](#3-llm-and-stt-providers) |
| `GOOGLE_API_KEY` | [aistudio.google.com](https://aistudio.google.com) — required if `LLM_PROVIDER=gemini` |
| `OPENCODE_API_KEY` | [opencode.ai](https://opencode.ai) — required if `LLM_PROVIDER=opencode` |
| `LIVEKIT_SIP_OUTBOUND_TRUNK_ID` | Run `python scripts/setup_outbound_trunk.py` once — see [Telephony setup](#4-telephony-setup) |

**Optional**

| Variable | What it enables |
|---|---|
| `LIVEKIT_SIP_URI` | SIP REFER transfers to a human agent (human handoff over PSTN) |
| `HUMAN_TRANSFER_NUMBER` | Phone number to transfer to when the agent escalates |
| `SUPABASE_URL` | Persist call transcripts to Supabase |
| `SUPABASE_KEY` | Same — anon/public key from Supabase > Settings > API |
| `TWILIO_ACCOUNT_SID` | Needed for `setup_outbound_trunk.py` and call monitoring scripts |
| `TWILIO_AUTH_TOKEN` | Same |
| `TWILIO_PHONE_NUMBER` | Your Twilio number in E.164 format (e.g. `+12015551234`) |

---

## 3. LLM and STT providers

Both are configurable via `.env` with no code changes.

### LLM

Set `LLM_PROVIDER` in `.env`:

| Value | Model | API key needed |
|---|---|---|
| `gemini` | `gemini-2.5-flash` | `GOOGLE_API_KEY` |
| `openai` | `gpt-4o-mini` | `OPENAI_API_KEY` |
| `opencode` | `kimi-k2.5` | `OPENCODE_API_KEY` |

### STT

Set `STT_PROVIDER` in `.env`:

| Value | Model | API key needed | Notes |
|---|---|---|---|
| `deepgram` | `nova-3` | `DEEPGRAM_API_KEY` | Default, low latency |
| `openai` | `gpt-realtime-whisper` | `OPENAI_API_KEY` | Word-by-word streaming via OpenAI Realtime API |

---

## 4. Telephony setup

The agent makes outbound calls via a LiveKit SIP outbound trunk backed by a Twilio Elastic SIP trunk.

### Step 1 — Twilio Elastic SIP trunk

1. [console.twilio.com](https://console.twilio.com) > Elastic SIP Trunking > Trunks > **Create new trunk**
2. Give it a name and click **Create**
3. Open the trunk > **Termination** > note the **Termination SIP URI** (e.g. `mytrunk.pstn.twilio.com`)
4. Termination > **Credential Lists** > create a username and password

Add to `.env`:

```env
TWILIO_SIP_TRUNK_URI=mytrunk.pstn.twilio.com
TWILIO_SIP_USERNAME=your-username
TWILIO_SIP_PASSWORD=your-password
TWILIO_PHONE_NUMBER=+12015551234
```

### Step 2 — LiveKit outbound SIP trunk

```bash
python scripts/setup_outbound_trunk.py
```

This reads the `TWILIO_SIP_*` vars from `.env`, creates the LiveKit outbound SIP trunk, and prints:

```
LIVEKIT_SIP_OUTBOUND_TRUNK_ID=ST_xxxxxxxxxxxxxxxxx
```

Add that value to `.env`.

### Step 3 — LiveKit dispatch rule

The dispatch rule tells LiveKit which agent worker handles each room.

1. [LiveKit Cloud](https://cloud.livekit.io) > Telephony > Dispatch Rules > **Create new rule**
2. Switch to the JSON editor and paste:

```json
{
  "name": "payment-dispatch",
  "rule": {
    "dispatchRuleIndividual": {
      "roomPrefix": "payment-"
    }
  },
  "roomConfig": {
    "agents": [
      { "agentName": "payment-agent" }
    ]
  }
}
```

> The `agentName` must match exactly. A rule without the `agents` block will receive the dispatch but the agent will never start.

### Step 4 — Human handoff (optional)

To enable live SIP transfers when the agent escalates:

1. Add to `.env`:

```env
LIVEKIT_SIP_URI=abc123.sip.livekit.cloud
HUMAN_TRANSFER_NUMBER=+918041234567
```

2. Enable **SIP REFER** in Twilio: Elastic SIP Trunking > your trunk > General > **Call Transfer (SIP REFER)** toggle.

If `HUMAN_TRANSFER_NUMBER` is unset, the agent reads the number aloud instead of transferring.

### Diagnosis scripts

```bash
python scripts/check_dispatch.py       # verify dispatch rule is wired correctly
python scripts/check_twilio_calls.py   # view recent Twilio call logs
python scripts/fix_sip_trunk.py        # update SIP trunk credentials if they change
```

---

## 5. Scenarios

Scenarios are set in `scenario_config.json`. The `trigger_call.py` script can switch the scenario before each call.

| Scenario | What happens |
|---|---|
| `normal_reminder` | Identity verified → amount disclosed → payment link sent → promise to pay recorded |
| `already_paid` | Borrower says "I already paid" → guardrail fires → dispute ticket created → human handoff |
| `hardship` | Borrower says "I lost my job" → guardrail fires → account flagged → human callback arranged |
| `wrong_person` | Someone else answers → guardrail fires → call ends, amount never disclosed |
| `grievance_pending` | Active grievance on file → call blocked before it starts |

Trigger a specific scenario:

```bash
python scripts/trigger_call.py --to +919876543210 --scenario hardship
```

Edit `scenario_config.json` directly to change customer name, amount, due date, or account details. The agent worker reads this file fresh on every call — no restart needed.

---

## 6. Testing without a phone

Preview what the agent would do for any scenario — no LiveKit connection, no phone, no API calls:

```bash
python scripts/run_scenario.py --scenario normal_reminder
python scripts/run_scenario.py --scenario already_paid
python scripts/run_scenario.py --scenario hardship
python scripts/run_scenario.py --scenario wrong_person
python scripts/run_scenario.py --scenario grievance_pending
```

Output includes: config values, pre-call check result, expected state machine path, opening line, initial system prompt, sample exchange, and expected outcome log.

Other unit-level tests:

```bash
python scripts/test_state_machine.py   # all state transitions and terminal states
python scripts/test_guardrails.py      # dispute / hardship / wrong person / prohibited language detection
python scripts/test_tools.py           # payment tools (verify identity, send link, log PTP, etc.)
python scripts/test_prompt.py          # system prompt rendering for each state
python scripts/test_foundation.py      # env vars and config load
python scripts/test_murf_voice.py      # Murf TTS API connectivity
python scripts/test_dispatch.py        # LiveKit dispatch rule check
```

For browser-based voice testing (no phone needed):

```bash
python agent.py dev
```

Open the [LiveKit Agents Playground](https://agents-playground.livekit.io/), connect with your LiveKit URL, API key, and secret, and speak to the agent with your microphone.

---

## 7. Triggering a real call

```bash
# Normal payment reminder
python scripts/trigger_call.py --to +919876543210

# With a specific scenario
python scripts/trigger_call.py --to +919876543210 --scenario already_paid
```

The script:
1. Checks required env vars are set
2. Optionally updates `scenario_config.json` to the requested scenario
3. Runs the pre-call guardrail check (prints `[BLOCKED]` and exits for `grievance_pending`)
4. Creates a LiveKit room named `payment-<id>`
5. Dispatches `payment-agent` to that room with the phone number in job metadata
6. The agent dials the number — your phone rings in ~3–5 s

Watch the agent terminal for the room name and call progress. Outcome log is written to `logs/` when the call ends.

---

## 8. Transcript logging and outcome files

### Outcome log

Every call writes a JSON file to `logs/<scenario>_<timestamp>.json`:

```json
{
  "scenario": "normal_reminder",
  "call_started": true,
  "recording_disclosure_played": true,
  "identity_verified": true,
  "amount_disclosed": true,
  "payment_link_sent": true,
  "promise_to_pay_date": "June 25, 2026",
  "dispute_detected": false,
  "payment_reminder_stopped": false,
  "ticket_created": false,
  "ticket_id": null,
  "future_automated_reminders_paused": false,
  "hardship_detected": false,
  "human_callback_requested": false,
  "human_handoff_required": false,
  "outcome": "promise_to_pay"
}
```

Possible `outcome` values: `promise_to_pay`, `payment_dispute`, `hardship_detected`, `identity_mismatch`, `call_blocked`, `unknown`.

### Transcript persistence (Supabase)

When `SUPABASE_URL` and `SUPABASE_KEY` are set, the full call transcript is saved to Supabase after the call ends. Without them, the agent logs locally only — the call still works normally.

---

## 9. Adapting for your use case

The payment collection workflow is a thin layer on top of the voice pipeline. The state machine, guardrails, tools, and transcript logging are all configurable.

| What to change | File | What to update |
|---|---|---|
| Company name, agent name, voice | `scenario_config.json` | `companyName`, `agentName`, `agentVoice` |
| System prompt and call script | `prompts/payment_prompt.py` | Prompt per state |
| Guardrail phrases | `guardrails.py` | Dispute, hardship, wrong person phrase lists |
| Call states and allowed transitions | `state_machine.py` | `CallState`, `VALID_TRANSITIONS`, `ALLOWED_ACTIONS` |
| Payment tools | `tools/payment_tools.py` | Replace mock implementations with real API calls |
| Voice | `scenario_config.json` | `agentVoice` — see [murf.ai/voices](https://murf.ai/api/dashboard) |

To hook into a real loan management system, replace the mock functions in `tools/payment_tools.py` with actual API calls. The tool contracts (function signatures and return strings) stay the same.

---

## 10. Common errors

| Error | Cause | Fix |
|---|---|---|
| `Required environment variable 'X' is not set` | Missing `.env` value | Copy `.env.example` to `.env` and fill in the variable |
| `LIVEKIT_SIP_OUTBOUND_TRUNK_ID not set — cannot dial outbound` | Trunk not created | Run `python scripts/setup_outbound_trunk.py` and add the printed ID to `.env` |
| Phone rings but agent stays silent | Dispatch rule has no `agents` block | Edit the rule in LiveKit Cloud — add `agentName: payment-agent` to `roomConfig.agents` |
| `DuplexClosed` in logs, call drops mid-greeting | `dev` mode restarts on file save | Use `python agent.py start` for all phone testing |
| Agent answers but immediately says goodbye | `grievance_pending` scenario is active | Change `scenario` in `scenario_config.json` or pass `--scenario normal_reminder` to `trigger_call.py` |
| `401` or `403` from Murf or Deepgram | Wrong or expired API key | Re-check the relevant key in `.env` |
| `No caller in payment-xxx after 20s` | Outbound SIP trunk misconfigured | Run `python scripts/check_dispatch.py` and verify the trunk SIP URI and credentials |
