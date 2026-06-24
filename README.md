# Reception Agent - an AI Phone Receptionist

A fully autonomous voice agent designed to handle inbound clinic calls, schedule appointments, and manage patient FAQs without human intervention. It’s configured for a medical clinic, but swap the system prompt and local knowledge base, and it can be adapted for any business front desk.

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://python.org)
[![LiveKit](https://img.shields.io/badge/Transport-LiveKit%20Agents-002cf2)](https://docs.livekit.io/agents)
![STT](https://img.shields.io/badge/STT-%20OpenAI%20Whisper%20%7C%20Deepgram%20-13EF93?logoColor=black)
[![Murf](https://img.shields.io/badge/TTS-Murf%20Falcon-6366F1)](https://murf.ai/api)
[![Twilio](https://img.shields.io/badge/Phone-Twilio%20SIP-F22F46?logo=twilio&logoColor=white)](https://twilio.com)
[![Supabase](https://img.shields.io/badge/Database-Supabase-3ECF8E?logo=supabase&logoColor=white)](https://supabase.com)

---

## What it does

- **Answers inbound calls** via Twilio, speaks with Murf Falcon TTS 
- **Books, cancels, and reschedules** appointments against a live Supabase slot table
- **Greets returning callers by name** — looks up caller memory on every call, no need to re-introduce yourself
- **Answers FAQs** using semantic search over a local knowledge base (LanceDB + all-MiniLM-L6-v2)
- **Sends WhatsApp confirmations** after every booking via Twilio
- **Transfers calls to a human** via SIP REFER when asked
- **Mirrors bookings to Google Calendar** for clinic staff (write-only, optional)
- **Logs full transcripts** with intent and outcome labels to Supabase after every call

---

## Architecture

![Architecture](images/architecture.png)

---

## Contents

1. [Quick start](#1-quick-start)
2. [LLM and STT providers](#2-llm-and-stt-providers)
3. [Telephony, WhatsApp, and call handoff](#3-telephony-whatsapp-and-call-handoff)
4. [Database, memory, and slots](#4-database-memory-and-slots)
5. [Google Calendar](#5-google-calendar)
6. [Transcript logging](#6-transcript-logging)
7. [Knowledge base](#7-knowledge-base)
8. [Adapting for your use case](#9-adapting-for-your-use-case)
9. [Common errors](#10-common-errors)
10. [Resources](#11-resources)

---

## 1. Quick start

### Clone

```bash
git clone <repo-url>
cd reception-agent
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

Open `.env` and fill in every value. The table below shows where to find each one. You will come back to add Supabase and Twilio values in later sections.

**Required**

| Variable | Where to get it |
|---|---|
| `LIVEKIT_URL` | [LiveKit Cloud](https://cloud.livekit.io) dashboard, your project |
| `LIVEKIT_API_KEY` | LiveKit Cloud > Settings > API Keys |
| `LIVEKIT_API_SECRET` | Same page as API key |
| `LIVEKIT_SIP_URI` | LiveKit Cloud > Telephony > SIP URI (hostname only, no `sip:` prefix) |
| `STT_PROVIDER` | `deepgram` or `openai` — see [LLM and STT providers](#2-llm-and-stt-providers) |
| `DEEPGRAM_API_KEY` | [console.deepgram.com](https://console.deepgram.com) — required if `STT_PROVIDER=deepgram` |
| `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com) — required if `STT_PROVIDER=openai` or `LLM_PROVIDER=openai` |
| `LLM_PROVIDER` | `opencode`, `openai`, or `gemini` — see [LLM and STT providers](#2-llm-and-stt-providers) |
| `OPENCODE_API_KEY` | [opencode.ai](https://opencode.ai) — required if `LLM_PROVIDER=opencode` |
| `GOOGLE_API_KEY` | [aistudio.google.com](https://aistudio.google.com) — required if `LLM_PROVIDER=gemini` |
| `MURF_API_KEY` | [murf.ai](https://murf.ai/api/dashboard) > Settings > API |
| `TWILIO_ACCOUNT_SID` | [console.twilio.com](https://console.twilio.com) > Account Info |
| `TWILIO_AUTH_TOKEN` | Same page as SID |
| `TWILIO_PHONE_NUMBER` | Your Twilio number in E.164 format (e.g. `+12015551234`) |
| `TWILIO_WHATSAPP_FROM` | `whatsapp:+14155238886` for sandbox testing |
| `SUPABASE_URL` | Supabase > Settings > API > Project URL |
| `SUPABASE_KEY` | Supabase > Settings > API > anon / public key |

**Optional** (agent works without these)

| Variable | What it enables |
|---|---|
| `CLINIC_PHONE_NUMBER` | Live call transfer to a real staff phone |
| `GOOGLE_CALENDAR_CREDENTIALS_JSON` | Mirror bookings to Google Calendar |
| `GOOGLE_CALENDAR_ID_SARAH` | Calendar ID for Dr. Sarah Lin |
| `GOOGLE_CALENDAR_ID_JAMES` | Calendar ID for Dr. James Cole |

### Download models

```bash
python agent.py download-files
```

Downloads Silero VAD and the FAQ embedding model (`all-MiniLM-L6-v2`, ~80 MB on first run) and builds the LanceDB index. Watch for `FAQ index built: N chunks` in the output.

### Run the agent

```bash
# Browser testing - no phone needed
python agent.py dev
```

```bash
# Phone testing - stable, no file-watcher restarts
python agent.py start
```

For `dev` mode, open the [LiveKit Agents Playground](https://agents-playground.livekit.io/), connect with your LiveKit URL, API key, and secret, and talk to the agent with your microphone.

### Check all API connections

Run this before starting the agent for the first time. It pings every service and prints a clear OK or FAIL.

```bash
python scripts/check_apis.py
```

Fix any failures before continuing.

---

## 2. LLM and STT providers

The LLM and STT are configurable via `.env` — no code changes needed to switch.

### LLM

Set `LLM_PROVIDER` in `.env`:

| Value | Model | API key needed | Notes |
|---|---|---|---|
| `opencode` | `kimi-k2.5` | `OPENCODE_API_KEY` | Default |
| `openai` | `gpt-4o-mini` | `OPENAI_API_KEY` | |
| `gemini` | `gemini-2.5-flash` | `GOOGLE_API_KEY` | |

```env
LLM_PROVIDER=opencode
OPENCODE_API_KEY=...

# or
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...

# or
LLM_PROVIDER=gemini
GOOGLE_API_KEY=AIza...
```

### STT

Set `STT_PROVIDER` in `.env`:

| Value | Model | API key needed | Notes |
|---|---|---|---|
| `deepgram` | `nova-3` | `DEEPGRAM_API_KEY` | Low latency |
| `openai` | `gpt-realtime-whisper` | `OPENAI_API_KEY` | Whisper via OpenAI Realtime API, word-by-word streaming |

```env
STT_PROVIDER=deepgram
DEEPGRAM_API_KEY=...

# or
STT_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

### Verify before starting

```bash
python scripts/check_apis.py
```

This automatically tests whichever providers are configured and prints OK or FAIL for each.

---

## 3. Telephony, WhatsApp, and Call handoff

Everything call-related: routing real phone calls to the agent, sending WhatsApp confirmations, and transferring to a human.

### How the routing works

```
Caller dials Twilio number
  -> TwiML Bin forwards the call to LiveKit SIP URI
    -> LiveKit inbound SIP trunk receives it
      -> Dispatch rule routes it to the clinic-agent worker
        -> Agent picks up
```

### Step 1 — Twilio phone number

Log into [console.twilio.com](https://console.twilio.com). Copy your **Account SID**, **Auth Token**, and **phone number** from the account dashboard and add them to `.env`.

### Step 2 — LiveKit SIP trunk

The SIP trunk is the bridge that receives calls from Twilio.

1. Go to [LiveKit Cloud](https://cloud.livekit.io) > Telephony > SIP Trunks
2. Click **New trunk** > **Inbound**
3. Set a **trunk name** (e.g. `clinic-inbound`)
4. Add your Twilio number to **Numbers** in E.164 format (e.g. `+12015551234`)
5. Set **Allowed addresses** to `0.0.0.0/0`
6. Save and copy the **SIP URI** shown at the top (e.g. `abc123.sip.livekit.cloud`)

### Step 3 — Twilio TwiML Bin

The TwiML Bin tells Twilio where to forward incoming calls.

1. Twilio Console > Develop > TwiML Bins > **Create new TwiML Bin**
2. Give it a name (e.g. `clinic`) and paste the content below, replacing the SIP URI:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Dial>
    <Sip>sip:<phone_number>@<sip_uri>;transport=tcp</Sip>
  </Dial>
</Response>
```
Replace <phone_number> and <sip_uri> with your Twilio phone number and your SIP URI.
For example: `sip:1234567@abcd1234.sip.livekit.cloud;transport=tcp`

3. Save and confirm it shows **Valid Voice TwiML**
4. Go to **Products&Services > Numbers&Senders > Overview > Your Number > Edit Details**
5. Set **Configure with** to **TwiML Bin** and select the bin you created

### Step 4 — LiveKit dispatch rule

The dispatch rule tells LiveKit which agent worker handles each call.

1. LiveKit Cloud > Telephony > Dispatch Rules > **Create new rule**
2. Set:
   - **Rule name:** `clinic-dispatch`
   - **Rule type:** Individual
   - **Room prefix:** `clinic-`
   - **Agent name:** `clinic-agent`
3. Switch to the **JSON editor** and confirm it looks exactly like this:

```json
{
  "name": "clinic-dispatch",
  "rule": {
    "dispatchRuleIndividual": {
      "roomPrefix": "clinic-"
    }
  },
  "roomConfig": {
    "agents": [
      { "agentName": "clinic-agent" }
    ]
  }
}
```

> The `agentName` must match exactly. A rule without the `agents` block will answer the call but stay completely silent.

### Step 5 — Run the agent and call it

```bash
# For phone testing - stable, no file-watcher restarts
python agent.py start

# For development with verbose logs
python agent.py dev
```

Call your Twilio number. The agent should answer within 2-3 rings.

To watch calls arrive and leave in real time:

```bash
python scripts/watch_calls.py
```

To verify your SIP trunk and dispatch rule are wired up correctly:

```bash
python scripts/diagnose_telephony.py
```

Prefer a script over the dashboard? This sets up the SIP trunk and dispatch rule automatically from your `.env` values:

```bash
python scripts/setup_twilio_sip.py
```

### WhatsApp Confirmations

After every booking the agent sends a WhatsApp message to the patient. 

**Sandbox setup (free, for testing):**

1. Go to [Twilio Console > Messaging > Try WhatsApp](https://www.twilio.com/console/sms/whatsapp/sandbox)
2. From the patient's phone, send `join <keyword>` to `+1 415 523 8886`
3. Confirm `.env` has `TWILIO_WHATSAPP_FROM=whatsapp:+14155238886`

Each recipient must opt in once. It resets every 24 hours, so every recepient must resend the join message once every 24 hours when using the sandbox. For production, apply for a WhatsApp Business number through Twilio and update `TWILIO_WHATSAPP_FROM`.

**Test without making a call:**

```bash
python scripts/test_whatsapp_confirmation.py --phone +919876543210
python scripts/test_whatsapp_confirmation.py --phone +919876543210 --dry-run
```

The confirmation should arrive within 5-10 seconds of a booking. Check logs for the Twilio message SID on success, or an error line on failure.

### Call Handoff

When a caller asks to speak to a human, the agent cold-transfers the live call to a real phone via SIP REFER.

Add to `.env`:

```env
CLINIC_PHONE_NUMBER=+918041234567
```

Also enable **SIP REFER** in Twilio: Elastic SIP Trunking > your trunk > **General** tab > **Call Transfer (SIP REFER)** toggle. It is off by default.

If `CLINIC_PHONE_NUMBER` is unset, the agent reads the number aloud instead of transferring. If it is set but SIP REFER is not enabled, the transfer fails gracefully and the agent reads the number.

**Test:**

```bash
python scripts/test_handoff.py status
python scripts/test_handoff.py dry-run
python scripts/test_handoff.py messages
```

During a live call - get real room and identity values from `rooms` first:

```bash
python scripts/test_handoff.py rooms
python scripts/test_handoff.py refer --room clinic-XXXX --identity sip-XXXX
```

### Telephony Troubleshooting

| Symptom | Fix |
|---|---|
| Call drops immediately | Confirm the TwiML Bin URL is reachable and the `<Sip>` URI ends with `;transport=tcp` |
| Agent does not answer | Run `python scripts/diagnose_telephony.py`. Check `agent.py` is running and the dispatch rule has `agentName: clinic-agent` in the `agents` block |
| Agent answers but stays silent | The dispatch rule is missing the `agents` block. Edit it in LiveKit Cloud and add `agentName: clinic-agent` to `roomConfig.agents` |
| Call drops mid-greeting | Use `python agent.py start` for phone testing. The `dev` mode restarts on every file save, which drops active calls |
| Audio cuts out | Run `python agent.py download-files` to re-verify Silero VAD |

---

## 4. Database, memory, and slots

All persistent data lives in Supabase: caller memory, appointment slots, booking records, and call transcripts.

### Set up the database

1. Create a free account at [supabase.com](https://supabase.com) (500 MB, no expiry)
2. Create a new project and wait for it to finish provisioning
3. Go to **Settings > API** and copy:
   - **Project URL** (e.g. `https://abcdefghijk.supabase.co`)
   - **anon / public key** (the longer of the two keys shown)
4. Add both to `.env` as `SUPABASE_URL` and `SUPABASE_KEY`
5. Go to **SQL Editor**, paste the full contents of `sql/create_tables.sql`, select all (Ctrl+A), and click **Run**

The script creates all four tables, adds indexes, and seeds 14 days of available slots so the agent can take bookings immediately. It is safe to re-run.

### Tables

| Table | What it stores |
|---|---|
| `customers` | Caller name, preferred doctor, visit history, call count |
| `slots` | Every 30-minute time slot - available or booked, with doctor, date, and time |
| `appointments` | Booking audit log with confirmed / cancelled / rescheduled status |
| `call_logs` | Full call transcript, intent label, and outcome label for every call |

### Caller memory

On every inbound call the agent looks up the caller's phone number from the SIP metadata. If a match exists in `customers`, their name and last booking details are injected into the system prompt before the call starts. The agent greets them by name and skips asking for their number again.

After a successful booking, `customers` and `appointments` are upserted automatically.

**Test before making a call:**

```bash
python scripts/test_memory.py lookup --phone 9876543210   # same lookup the agent runs on every call
python scripts/test_memory.py call   --phone 9876543210   # simulate call start
python scripts/test_memory.py book   --phone 9876543210   # simulate post-booking write
python scripts/test_memory.py prompt --phone 9876543210   # preview the greeting the agent would use
python scripts/test_memory.py flow   --phone 9876543210   # run all of the above in sequence
```

What to verify:
- **First call:** `customers` and `appointments` rows appear in Supabase after a booking
- **Second call (same number):** agent greets by name, `call_count` increments
- **Supabase down:** agent treats the caller as a first-timer and continues normally

### Slot seeding

The initial seed in `sql/create_tables.sql` covers 14 days. A Supabase Edge Function keeps slots topped up automatically every Sunday at midnight IST.

**Deploy the Edge Function:**

1. Install the Supabase CLI:

   ```bash
   npm install -g supabase
   ```

2. Link to your project.

   Your **project ref** is the subdomain in your Supabase project URL. For `https://abcdefghijk.supabase.co` it is `abcdefghijk`. Also at Settings > General > Reference ID.

   ```bash
   supabase login
   supabase link --project-ref YOUR_PROJECT_REF
   ```

3. Deploy:

   ```bash
   supabase functions deploy seed-slots --no-verify-jwt
   ```

4. Enable `pg_cron` under **Database > Extensions**, then schedule the weekly run in the SQL editor:

   Your **service role key** is at Settings > API > Project API keys > `service_role`. It has full database access — keep it out of version control.

   ```sql
   select cron.schedule(
     'seed-slots-weekly',
     '30 18 * * 0',   -- Sunday 18:30 UTC = midnight IST
     $$
     select net.http_post(
       url := 'https://YOUR_PROJECT_REF.supabase.co/functions/v1/seed-slots',
       headers := jsonb_build_object(
         'Content-Type', 'application/json',
         'Authorization', 'Bearer YOUR_SERVICE_ROLE_KEY'
       ),
       body := '{}'::jsonb
     )
     $$
   );
   ```

**Test the Edge Function manually** before relying on the cron.

macOS / Linux:

```bash
curl -sS -X POST "https://YOUR_PROJECT_REF.supabase.co/functions/v1/seed-slots" \
  -H "Authorization: Bearer YOUR_SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  -d "{}"
```

Windows (PowerShell):

```powershell
curl.exe -sS -X POST "https://YOUR_PROJECT_REF.supabase.co/functions/v1/seed-slots" `
  -H "Authorization: Bearer YOUR_SERVICE_ROLE_KEY" `
  -H "Content-Type: application/json" `
  -d "{}"
```

Expected responses:

```json
{"message": "Seeded N slots from YYYY-MM-DD to YYYY-MM-DD"}
```

```json
{"message": "Slots OK - N days ahead. No seeding needed."}
```

Local test (requires Docker and `supabase start`):

```bash
supabase functions serve seed-slots --no-verify-jwt
# In a second terminal:
curl -sS -X POST "http://127.0.0.1:54321/functions/v1/seed-slots" \
  -H "Authorization: Bearer YOUR_SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  -d "{}"
```

**Manual seed (fallback)** — run in the Supabase SQL editor:

```sql
INSERT INTO slots (doctor, iso_date, iso_time, status)
SELECT
    doctor,
    date_val::DATE,
    slot_start::TIME,
    'available'
FROM
    UNNEST(ARRAY['Dr. Sarah Lin', 'Dr. James Cole']) AS doctor,
    generate_series(
        CURRENT_DATE,
        CURRENT_DATE + INTERVAL '60 days',
        INTERVAL '1 day'
    ) AS date_val,
    UNNEST(ARRAY[
        '09:00','09:30','10:00','10:30','11:00','11:30','12:00','12:30',
        '17:00','17:30','18:00','18:30','19:00','19:30'
    ]) AS slot_start
WHERE EXTRACT(ISODOW FROM date_val::DATE) BETWEEN 1 AND 6
ON CONFLICT (doctor, iso_date, iso_time) DO NOTHING;
```

**Check slot coverage at any time:**

```sql
SELECT
    MIN(iso_date)                                AS earliest_slot,
    MAX(iso_date)                                AS latest_slot,
    COUNT(*) FILTER (WHERE status = 'available') AS available_slots,
    COUNT(*) FILTER (WHERE status = 'booked')    AS booked_slots,
    MAX(iso_date)::date - CURRENT_DATE           AS days_of_coverage
FROM slots
WHERE iso_date >= CURRENT_DATE;
```

The agent logs `SLOT COVERAGE: N days ahead - OK` on startup. To test the low-coverage warning, delete far-future slots and restart:

```sql
DELETE FROM slots WHERE iso_date > CURRENT_DATE + INTERVAL '10 days';
```

Run the manual seed above to restore.

**Verify the cron job:**

```sql
SELECT * FROM cron.job WHERE jobname = 'seed-slots-weekly';

SELECT * FROM cron.job_run_details
WHERE jobid = (SELECT jobid FROM cron.job WHERE jobname = 'seed-slots-weekly')
ORDER BY start_time DESC LIMIT 5;
```

---

## 5. Google Calendar

Supabase `slots` is the source of truth. Google Calendar is a write-only mirror for clinic staff. The agent never reads from it.

1. Go to [console.cloud.google.com](https://console.cloud.google.com) and create a project
2. Enable the **Google Calendar API**
3. Go to **IAM > Service Accounts > Create** (no project-level role needed at this step)
4. Open the service account > **Keys > Add Key > JSON** — save the file as `service-account.json` in the project root (already gitignored)
5. Open [Google Calendar](https://calendar.google.com) and create one calendar per doctor
6. For each calendar: **Settings > Share with specific people** > add the service account email > **Make changes to events**
7. For each calendar: **Settings > Integrate calendar > Calendar ID** — copy the ID (e.g. `abc123@group.calendar.google.com`)
8. Add to `.env`:

```env
GOOGLE_CALENDAR_CREDENTIALS_JSON=./service-account.json
GOOGLE_CALENDAR_ID_SARAH=abc123@group.calendar.google.com
GOOGLE_CALENDAR_ID_JAMES=xyz456@group.calendar.google.com
```

**Test:**

```bash
python scripts/test_calendar.py status
python scripts/test_calendar.py create --dry-run
python scripts/test_calendar.py create --doctor "Dr. Sarah Lin"
```

Without Calendar configured, logs show `Calendar mirror disabled - skipping` and bookings work normally. If credentials are misconfigured, the agent logs an error but the booking and WhatsApp confirmation still go through.

---

## 6. Transcript logging

Every call produces one row in `call_logs` (created by `sql/create_tables.sql`).

The `transcript` column is a JSONB array of turns:

```json
[
  {"role": "agent", "text": "Hello, I'm Aria...", "ts": 0.0},
  {"role": "user",  "text": "Hi, I want to book an appointment", "ts": 3.2}
]
```

| Field | Values |
|---|---|
| `intent` | `booking`, `faq`, `cancellation`, `reschedule`, `unknown` |
| `call_outcome` | `booked`, `cancelled`, `rescheduled`, `answered_faq`, `transferred`, `abandoned`, `unknown` |

View a transcript: Supabase dashboard > `call_logs` > expand the `transcript` cell. After a booking you should see `intent = booking` and `call_outcome = booked`.

**Privacy note:** Transcripts may contain caller names and visit reasons. Treat `call_logs` as sensitive personal data in production.

---

## 7. RAG

![RAG](images/RAG.png)

The agent answers factual questions by searching `knowledge/clinic_faq.md`. It does not guess. If the FAQ has no useful answer it says so and offers a callback.

**To update the knowledge base:**

1. Edit `knowledge/clinic_faq.md`
2. Restart the agent — the index rebuilds automatically

**Structure:** one `##` heading per topic. Each heading becomes one searchable chunk.

```markdown
## Clinic hours

We are open Monday to Saturday, 9 am to 1 pm and 5 pm to 8 pm.
Closed Sundays and public holidays.

## Consultation fees

A general consultation is 500 rupees. A follow-up within two weeks is 350 rupees.
```

**Index details**

| Detail | Value |
|---|---|
| Index location | `.lancedb/` (gitignored, rebuilt on every startup) |
| Embedding model | `all-MiniLM-L6-v2` (~80 MB, downloaded once) |
| Retrieval | Top-3 nearest chunks by cosine similarity |

More on the models: [all-MiniLM-L6-v2 on HuggingFace](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) — [LanceDB docs](https://docs.lancedb.com/)


---

## 9. Adapting for your use case

The clinic persona is a thin configuration layer on top of a general-purpose call agent. The voice pipeline, slot system, memory, WhatsApp, and transcripts are all business-agnostic. Here is what to change.

### Configuration map

| What to change | File | What to update |
|---|---|---|
| Agent name and persona | `prompts/system_prompt.py` | Identity block and opening line |
| Staff / provider names | `sql/create_tables.sql` | `slots_doctor_check` constraint |
| Booking flow | `prompts/system_prompt.py` | Booking intent section |
| Business hours and slot schedule | `sql/create_tables.sql` + `supabase/functions/seed-slots/index.ts` | Seed times and weekdays |
| FAQ content | `knowledge/clinic_faq.md` | Replace entirely, keep the `##` heading structure |
| Calendar names | `.env` | `GOOGLE_CALENDAR_ID_*` values |
| Handoff number | `.env` | `CLINIC_PHONE_NUMBER` |
| Voice | `agent.py` | Murf voice ID — see [murf.ai/voices](https://murf.ai/api/dashboard) |

### Example prompts

**Hair salon**

```
You are Zara, the AI receptionist for Curl & Cut salon, Indiranagar, Bangalore.
Opening line: Hello, thanks for calling Curl & Cut. I'm Zara, your AI assistant. How can I help?
```

Booking flow: service type (haircut / colour / blowout), stylist preference, date, time.

`sql/create_tables.sql` — update the provider constraint:

```sql
constraint slots_stylist_check check (doctor in ('Aisha', 'Priya', 'Riya'))
```

Replace `knowledge/clinic_faq.md` with your services, pricing, and cancellation policy.

**Legal intake**

```
You are Alex, the AI intake assistant for Mehta & Associates. Collect: caller name,
contact number, matter type (civil / criminal / family / property), and a brief description.
Then schedule a callback with a solicitor.
```

For callback-only intake, replace `book_appointment` with a lighter tool that logs the inquiry and records a preferred callback time. Memory, transcripts, and WhatsApp all still work as-is.

**Restaurant reservations**

```
You are Anaya, an AI receptionist who takes reservations for The Spice Room. Collect: guest name, contact number,
date, time, party size, and any dietary requirements.
```

The `slots` table works naturally for table-time pairs. Update the provider constraint to table names:

```sql
constraint slots_table_check check (doctor in ('Table 1', 'Table 2', 'Table 3', 'Terrace'))
```

Update `supabase/functions/seed-slots/index.ts` for your opening hours, days, and booking interval.

---

## 10. Common errors

| Error | Cause | Fix |
|---|---|---|
| `Required environment variable 'X' is not set` | Missing `.env` value | Copy `.env.example` to `.env` and fill in the variable |
| Agent answers but stays silent | Dispatch rule has no `agents` block | Edit the rule in LiveKit Cloud — add `agentName: clinic-agent` to `roomConfig.agents` |
| `DuplexClosed` in logs, call drops mid-greeting | `dev` mode restarts on file save | Use `python agent.py start` for all phone testing |
| Call drops immediately | TwiML Bin not reachable, or `<Sip>` URI missing `;transport=tcp` | Check the URI in the TwiML Bin and add `;transport=tcp` at the end |
| `ERROR: relation "slots" does not exist` | Ran only part of `create_tables.sql` | Select the full file (Ctrl+A) and run it again from the top |
| `Table "slots" is missing` at seed time | Same as above | Same fix — the seed block at the bottom requires the tables above it |
| `401` or `403` from Murf or Deepgram | Wrong or expired API key | Re-check `MURF_API_KEY` and `DEEPGRAM_API_KEY` in `.env` |
| WhatsApp message not delivered | Recipient has not joined the sandbox | Send `join <keyword>` from the recipient's WhatsApp to the sandbox number |
| Calendar events not appearing | Service account not shared with the calendar | Go to each calendar's settings and share it with edit permissions to the service account email |
| Slot coverage warning on startup | Fewer than 14 days of available slots ahead | Run the manual seed SQL or POST to the Edge Function URL |

---

## 11. Resources

**Services**

- [LiveKit Cloud](https://cloud.livekit.io) — agent hosting and SIP telephony
- [LiveKit Agents Playground](https://agents-playground.livekit.io/) — browser-based testing, no phone needed
- [LiveKit docs: Accepting inbound Twilio calls](https://docs.livekit.io/telephony/accepting-calls/inbound-twilio/)
- [Deepgram console](https://console.deepgram.com)
- [Murf AI](https://murf.ai/api/dashboard) 
- [Twilio console](https://console.twilio.com)
- [Twilio WhatsApp sandbox](https://www.twilio.com/console/sms/whatsapp/sandbox)
- [Supabase](https://supabase.com)
- [Google Cloud Console](https://console.cloud.google.com) — service accounts for Calendar

**Libraries and models**

- [LanceDB](https://docs.lancedb.com/) — vector store for FAQ search
- [all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) — FAQ embedding model
- [Silero VAD](https://github.com/snakers4/silero-vad) — voice activity detection
