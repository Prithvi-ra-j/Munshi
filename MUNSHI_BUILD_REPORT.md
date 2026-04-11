# Munshi — Build Report v3
**Last Updated:** April 4, 2026
**Status:** LIVE — End-to-End Verified on Real WhatsApp
**Hackathon:** Gen AI Academy APAC Edition (Hack2skill / Google) — Deadline April 8, 2026

---

## Current System Status

| Component | Status | Notes |
|---|---|---|
| FastAPI backend | LIVE | uvicorn on port 8000, dotenv loaded |
| WAHA container | LIVE | NOWEB engine, session `default` WORKING |
| WhatsApp session | CONNECTED | Linked to +91 77958 44029 |
| SQLite DB | CONNECTED | Tasks writing correctly under real phone numbers |
| ChromaDB | RUNNING | Contact memory persisting to ./chroma_db |
| APScheduler | RUNNING | Reminder jobs loading on startup |
| LangSmith | ACTIVE | All LLM calls traced |
| Groq API | ACTIVE | llama-3.3-70b-versatile + whisper-large-v3 |
| Webhook pipeline | VERIFIED | Real messages flowing, replies landing on phone |

---

## What Was Built (Complete)

### Core Pipeline
- FastAPI webhook receives WAHA events, returns 200 immediately, processes async
- LangGraph StateGraph with 8 agent nodes + conditional routing
- MunshiState TypedDict flows through every agent, accumulates results
- Final response sent back via WAHA to the sender's real phone number

### Agents
- `transcription_agent` — Groq Whisper for voice notes, temp file cleanup
- `intent_classifier_agent` — 5-intent classification + keyword language detection (EN/HI/Hinglish)
- `entity_extractor_agent` — spaCy NER + Groq hybrid for names, dates, amounts
- `memory_rag_agent` — ChromaDB contact context retrieval + upsert per interaction
- `task_agent` — SQLite task creation with multilingual confirmation
- `reply_drafter_agent` — Groq reply drafting using contact context
- `report_agent` — Pending tasks summary with contact name + amount + due date
- `reminder_agent` — APScheduler DateTrigger, persists to SQLite, restart-resilient

### Data Layer
- SQLite: `tasks` + `reminders` tables, async via aiosqlite
- ChromaDB: `contacts` collection, sentence-transformers embeddings, scoped per user
- All tasks stored under real international phone number (e.g. `919844155242`)

### Infrastructure
- WAHA NOWEB engine (no Chromium, stable on Docker)
- `host.docker.internal` for container-to-host communication
- `X-Api-Key` auth on all WAHA API calls
- LID-to-real-phone extraction via `_data.key.remoteJidAlt`
- `load_dotenv()` in `main.py` ensures env vars available at runtime

---

## Bugs Fixed During Deployment

| Bug | Root Cause | Fix |
|---|---|---|
| spaCy build failure | Python 3.13 incompatibility | Relaxed to `spacy>=3.8.7` |
| langgraph + langsmith version conflict | Pinned versions incompatible | Relaxed all to `>=` |
| Docker daemon not connecting | Docker Desktop not running | Started Docker Desktop |
| WAHA session name rejected | Core only supports `default` | Changed everywhere to `default` |
| WEBJS `window is not defined` | Puppeteer fails on Docker | Switched to NOWEB engine |
| Webhook `ENOTFOUND munshi-backend` | Container can't resolve host service | Changed to `host.docker.internal` |
| Session STOPPED after recreate | `--force-recreate` wipes state | Manually restart session via API |
| Webhook config null on session | Env var not persisting to session | PUT webhook config explicitly via API |
| `from` field is LID not phone | NOWEB uses LID addressing mode | Extract real phone from `_data.key.remoteJidAlt` |
| GROQ_API_KEY not found at runtime | uvicorn doesn't auto-load .env | Added `load_dotenv()` to `main.py` |
| WAHA send returning 401 | API key not sent with requests | Added `X-Api-Key` header to all WAHA calls |
| Reply going to LID not real number | send_text_message used raw `from` field | Normalize phone from remoteJidAlt before sending |
| Status report missing contact + amount | report_agent only showed description | Updated format to include contact name + amount + due date |

---

## Verified End-to-End Flow

**Message sent:** `"Sharma ji ka payment 50 k pending hai"`
**Pipeline:** webhook → transcribe → classify (FOLLOW_UP, hinglish) → extract (Sharma ji, ₹50000) → memory (ChromaDB upsert) → task (SQLite insert) → reminder (no date, skip) → respond (✅ Note kar liya)
**SQLite result:** `contact_name: Sharma ji, amount: 50000, intent_type: FOLLOW_UP, status: pending`
**Reply on phone:** ✅ confirmed delivered

**Message sent:** `"What's pending?"`
**Pipeline:** webhook → classify (STATUS_QUERY) → report (SQLite query) → respond
**Reply on phone:** `📋 Aapke 1 pending kaam hain: 1. Sharma ji (₹50000) — Payment is pending`
**Reply on phone:** ✅ confirmed delivered

---

## Eval Results

```
Intent Accuracy:    96.0%   (48/50 correct)
Entity Precision:   94.0%
P50 Latency:        4573.7 ms   (Groq free tier)
P95 Latency:        5143.2 ms
Total Messages:     50
```

---

## V2 Vision — Munshi as a Service

### The Problem with V1
Right now Munshi is tied to one personal WhatsApp number. The person who set it up IS the agent — their number is the Munshi number. This means:
- You can't give it to someone else to use
- The owner's personal number is exposed
- There's no onboarding, no setup flow, no isolation between users
- It only works while your laptop is running

### The V2 Vision
Munshi should be a **dedicated WhatsApp number** — a proper AI agent account — that any business owner can message and immediately start using. Like messaging a service, not a person.

```
User messages +91 XXXXX XXXXX (Munshi's dedicated number)
       ↓
Munshi onboards them in 30 seconds
       ↓
They use it forever — tasks, reminders, drafts, memory
       ↓
Their data is isolated, private, theirs
```

---

## V2 Roadmap

### 1. Dedicated Agent Number (Most Important)
Move from personal WhatsApp to a dedicated Munshi number. Options:
- **WAHA PLUS** — supports multiple sessions, can run a dedicated number
- **Meta Business API** — official, scalable, but requires business verification and policy compliance
- **JioMart / Airtel WhatsApp Business** — Indian BSP (Business Solution Provider) route

The dedicated number is what makes Munshi a product, not a personal tool.

### 2. Self-Onboarding Flow
When a new user messages Munshi for the first time, it should walk them through setup:
```
User: Hi
Munshi: Namaste! Main Munshi hoon — aapka WhatsApp business assistant.
        Aapka naam kya hai aur aap kya kaam karte hain?
User: Main Prithviraj hoon, kapde ka business hai
Munshi: Perfect Prithviraj ji! Ab se main aapke saare pending kaam,
        payments aur follow-ups track karunga. Shuru karte hain?
```
Stores user profile in SQLite/ChromaDB on first interaction.

### 3. Multi-User Isolation
Each user's data is already scoped by phone number in SQLite and ChromaDB. But need:
- User profile table (name, business type, language preference, timezone)
- Per-user settings (reminder time, language override, notification preferences)
- Admin dashboard to see all users and their activity

### 4. Conversation Memory (Turn-by-Turn Context)
Right now each message is stateless — Munshi forgets what was said 10 seconds ago. V2 needs:
- Short-term conversation buffer (last 5 messages per user)
- "To whom?" follow-up questions that remember the previous message
- Confirmation flows: user says "haan" → Munshi knows what to confirm

### 5. Send Confirmation Flow
```
User: Draft a reply to Sharma ji about the payment
Munshi: 📝 Draft: "Sharma ji, payment ke baare mein baat karni thi..."
        Bhejun kya? (Reply haan/nahi)
User: haan
Munshi: ✅ Sharma ji ko message bhej diya
```
Requires conversation state tracking per user.

### 6. Task Completion
```
User: Sharma ji ne pay kar diya
Munshi: ✅ Sharma ji ka task complete mark kar diya (₹50,000)
```
Fuzzy match incoming message against open tasks, mark as done.

### 7. Proactive Daily Briefing
Every morning at 9am (per user's timezone), Munshi sends unprompted:
```
☀️ Good morning Prithviraj ji!
Aaj ke pending kaam:
1. Sharma ji — ₹50,000 payment (3 din se pending)
2. Ravi ko call karna tha
3. GST filing — kal deadline hai
```
APScheduler cron job, already have the infrastructure.

### 8. Render / Cloud Deployment
Move from local laptop to always-on cloud:
- `render.yaml` already in repo
- Push to GitHub → connect to Render → auto-deploy
- Persistent disk for SQLite + ChromaDB
- No more "it only works when my laptop is on"

### 9. Image / Document Reading
User sends a photo of an invoice, contract, or visiting card:
- Groq vision model extracts text
- Processed as normal message
- Invoice → FOLLOW_UP task with amount
- Visiting card → STORE_INFO with contact details

### 10. Google Calendar Sync
When a task has a due date, create a Google Calendar event automatically. OAuth2 flow on first use.

### 11. Payment Tracking Dashboard
Simple web UI (FastAPI + Jinja2 or React):
- All pending payments with amounts and days overdue
- Total receivables
- Contact-wise breakdown
- Accessible at `https://munshi.yourdomain.com/dashboard/{phone}`

### 12. WhatsApp Group Support
Add Munshi to a business WhatsApp group. It listens passively and:
- Extracts action items from group conversations
- Tags the right person for each task
- Sends a daily summary of group commitments

### 13. Reminder Cancellation + Snooze
```
User receives: ⏰ Reminder: Call Sharma ji
User replies: snooze 1 hour
Munshi: ✅ Reminder snoozed — 1 ghante baad yaad dilaaunga
```

### 14. Export + Reporting
```
User: Send me all pending payments as a list
Munshi: [sends formatted text or PDF attachment]
```

### 15. Migrate to Meta Official API (Production Scale)
For serious scale (1000+ users), move to Meta's official WhatsApp Business API:
- Requires business verification
- No ban risk
- Supports proper message templates
- Works with Indian BSPs like Gupshup, Kaleyra, Interakt

---

## How to Run (Current)

```bash
# Dependencies
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# Configure
cp .env.example .env
# Fill: GROQ_API_KEY, LANGSMITH_API_KEY, WAHA_API_KEY=munshi-secret

# Start backend
uvicorn app.main:app --reload

# Start WAHA (separate terminal)
docker-compose -f waha/docker-compose.yml up -d

# Start WAHA session
Invoke-RestMethod -Uri "http://localhost:3000/api/sessions/default/start" -Method POST -Headers @{"X-Api-Key"="munshi-secret"}

# Get QR code
$qr = Invoke-RestMethod -Uri "http://localhost:3000/api/default/auth/qr" -Headers @{"X-Api-Key"="munshi-secret"; "Accept"="application/json"}
$bytes = [Convert]::FromBase64String($qr.data)
[IO.File]::WriteAllBytes("$PWD\qr.png", $bytes)
Start-Process "$PWD\qr.png"
# Scan QR with WhatsApp

# Run eval
python eval/run_eval.py
```

## Environment Variables

| Variable | Value | Purpose |
|---|---|---|
| `GROQ_API_KEY` | your key | LLM + Whisper |
| `LANGSMITH_API_KEY` | your key | Tracing |
| `LANGSMITH_PROJECT` | munshi-prod | LangSmith project |
| `WAHA_API_URL` | http://localhost:3000 | WAHA container |
| `WAHA_SESSION` | default | WAHA session name |
| `WAHA_API_KEY` | munshi-secret | WAHA auth header |
| `DATABASE_URL` | sqlite:///./munshi.db | SQLite path |
| `CHROMA_PERSIST_DIR` | ./chroma_db | ChromaDB storage |
