# Munshi — Project Steering

## What is Munshi
Munshi is a WhatsApp-native AI Chief of Staff for Indian MSME owners, freelancers, and solopreneurs. It sits inside WhatsApp — the one app Indian business owners use all day — and acts as their personal business memory. It extracts tasks, tracks follow-ups, transcribes voice notes, and sends proactive reminders from unstructured Hinglish conversations.

**Tagline:** *Apna Munshi — jo WhatsApp pe sab yaad rakhta hai*

## Problem Being Solved
Indian business owners run their entire business on WhatsApp. Every pending payment, client promise, supplier commitment, and deadline lives in their head and in 47 WhatsApp threads. There is no system. Things fall through. Money is lost. Relationships are damaged. Munshi gives them a second brain inside WhatsApp without asking them to change any behavior.

## Hackathon Context
This project is submitted to Gen AI Academy APAC Edition (Hack2skill / Google).
Problem statement: "Build a multi-agent AI system that helps users manage tasks, schedules, and information by interacting with multiple tools and data sources."
Deadline: April 8, 2026, 11:59 PM IST

## Tech Stack — STRICT, DO NOT DEVIATE
- **WhatsApp interface**: WAHA (Docker, unofficial API via whatsapp-web.js wrapper)
- **LLM**: Groq API (llama-3.3-70b-versatile) — free tier
- **Voice transcription**: Groq Whisper API — free tier
- **Agent orchestration**: LangGraph (Python)
- **Vector DB / memory**: ChromaDB (local)
- **Embeddings**: sentence-transformers (all-MiniLM-L6-v2, CPU)
- **Structured DB**: SQLite (tasks, reminders, contacts)
- **Observability**: LangSmith (free tier)
- **Backend**: FastAPI
- **Scheduler**: APScheduler
- **Deployment**: Render (free tier)
- **NLP**: spaCy (en_core_web_sm) for entity extraction

## Cost Constraint
Total monthly cost must be ₹0. Use only free tiers. No paid APIs.

## Language Handling
- Accept messages in English, Hindi, Hinglish
- Respond in the same language the user wrote in
- Never force English on a user who writes in Hindi

## Architecture: Multi-Agent System (LangGraph)
```
User WhatsApp Message
        ↓
[FastAPI Webhook] ← WAHA sends events here
        ↓
[Orchestrator Agent] — primary coordinator
        ├── [Intent Classifier Agent] — what does user want?
        ├── [Transcription Agent] — voice note → text (Groq Whisper)
        ├── [Entity Extractor Agent] — spaCy: names, dates, amounts
        ├── [Task Agent] — create/update tasks in SQLite
        ├── [Memory RAG Agent] — ChromaDB: who is this contact?
        ├── [Reply Drafter Agent] — draft WhatsApp reply in user's language
        ├── [Reminder Agent] — APScheduler: schedule future nudges
        └── [Report Agent] — "what's pending?" summary
        ↓
[Response] → WAHA → User's WhatsApp
```

## Intent Types (V1 Only)
1. `TASK` — "remind me to call Sharma ji"
2. `FOLLOW_UP` — "Ravi ka payment pending hai"
3. `REPLY_DRAFT` — "draft a reply for this"
4. `STATUS_QUERY` — "what's pending today?"
5. `STORE_INFO` — "Priya's number is 98xxxxxxxx"

## V1 Scope (STRICT — DO NOT ADD FEATURES)
✅ Text message intake
✅ Voice note transcription
✅ Intent classification (5 intents above)
✅ Task creation + storage (SQLite)
✅ Contact memory (ChromaDB)
✅ Reply drafting
✅ "What's pending?" report
✅ Basic reminder scheduling (APScheduler)
✅ LangSmith tracing on every agent call

❌ Image/document reading (V2)
❌ Google Calendar integration (V2)
❌ Multi-user support (V2)
❌ Proactive daily briefing (V2)
❌ Payment tracking (V2)

## Database Schema

### SQLite — tasks table
```sql
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_phone TEXT NOT NULL,
    description TEXT NOT NULL,
    contact_name TEXT,
    amount REAL,
    due_date TEXT,
    status TEXT DEFAULT 'pending',
    intent_type TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### SQLite — reminders table
```sql
CREATE TABLE reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER,
    user_phone TEXT NOT NULL,
    message TEXT NOT NULL,
    scheduled_at TIMESTAMP NOT NULL,
    sent INTEGER DEFAULT 0,
    FOREIGN KEY(task_id) REFERENCES tasks(id)
);
```

### ChromaDB — contacts collection
```
collection: "contacts"
document: "{contact_name} - {context}"
metadata: {user_phone, contact_name, last_interaction, pending_count}
```

## Eval Metrics (document these in README)
- Intent classification accuracy (test on 50 messages)
- Entity extraction precision (names, dates, amounts)
- Response latency P50 and P95
- Voice transcription accuracy on Hinglish samples

## Code Style
- Python 3.11+
- Type hints everywhere
- Pydantic models for all request/response schemas
- Async FastAPI endpoints
- Each agent is a separate Python function in agents/ directory
- All LLM calls go through a single llm_client.py wrapper
- Environment variables via python-dotenv, never hardcode keys
- Every agent call must have LangSmith trace decorator

## Folder Structure
```
munshi/
├── .kiro/
│   ├── steering/
│   │   └── project.md          ← this file
│   └── specs/
│       ├── requirements.md
│       ├── design.md
│       └── tasks.md
├── app/
│   ├── main.py                 ← FastAPI app
│   ├── webhook.py              ← WAHA webhook handler
│   ├── agents/
│   │   ├── orchestrator.py     ← LangGraph graph definition
│   │   ├── intent_classifier.py
│   │   ├── transcription.py
│   │   ├── entity_extractor.py
│   │   ├── task_agent.py
│   │   ├── memory_agent.py
│   │   ├── reply_drafter.py
│   │   ├── reminder_agent.py
│   │   └── report_agent.py
│   ├── db/
│   │   ├── sqlite_client.py
│   │   └── chroma_client.py
│   ├── llm_client.py           ← Groq wrapper
│   ├── scheduler.py            ← APScheduler setup
│   └── models.py               ← Pydantic schemas
├── waha/
│   └── docker-compose.yml      ← WAHA container
├── eval/
│   ├── test_messages.json      ← 50 test conversations
│   └── run_eval.py             ← eval script
├── .env.example
├── requirements.txt
├── Dockerfile
├── render.yaml                 ← Render deployment config
└── README.md
```

## Environment Variables Required
```
GROQ_API_KEY=
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=munshi-prod
WAHA_API_URL=http://localhost:3000
WAHA_SESSION=munshi
DATABASE_URL=sqlite:///./munshi.db
CHROMA_PERSIST_DIR=./chroma_db
```

## Non-Negotiables
1. Every agent call MUST have LangSmith tracing
2. Every LLM call MUST have a fallback if Groq fails
3. SQLite MUST be initialized on startup if tables don't exist
4. WAHA webhook MUST return 200 within 5 seconds (async processing)
5. Voice notes MUST be downloaded, transcribed, then deleted locally
6. README MUST have architecture diagram, setup steps, and eval results
