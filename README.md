# 🧾 Munshi — AI-Powered WhatsApp Business Assistant

> *Munshi* (मुंशी) — Sanskrit/Urdu for a personal secretary or business record-keeper.

A **production-grade, multi-agent AI system** that acts as an always-on business assistant over WhatsApp — managing tasks, tracking payments, drafting replies, and conversing fluently in Hindi, English, and Hinglish. Built with a fully async LangGraph architecture and persistent per-user memory.

---

## What It Does

A small business owner in India can simply WhatsApp:

> *"Sharma ji ka 50k pending hai 2 mahine se"* → Task + reminder auto-created  
> *"Ravi ne pay kar diya"* → Task fuzzy-matched and marked done, reminder cancelled  
> *"Draft reply to Priya about the GST invoice"* → Professional draft generated, awaits confirmation  
> *"Snooze reminder 1 ghante ke liye"* → APScheduler job rescheduled, DB updated  
> *"Kya pending hai?"* → Status report of all open tasks  

No app to install. No training needed. Just WhatsApp.

---

## Architecture

### Multi-Agent DAG (LangGraph)

```
Webhook → [reset_state]
             ↓
        [transcribe]  ← Groq Whisper (voice note support)
             ↓
        [classify]    ← Few-shot LLM intent classifier (9 classes)
             ↓
        [extract]     ← spaCy NER + Groq LLM entity extraction
             ↓
        [memory]      ← ChromaDB RAG for contact context
             ↓
    ┌────────┴──────────────────────────────────┐
    │        Intent-Based Routing               │
    ├────────────┬───────────┬──────────────────┤
  [task]    [reply]     [report]   [task_complete]
    ↓           ↓           ↓        [reminder_control]
[reminder]  [confirm?]  [respond]    [confirm]
    ↓           ↓           ↓            ↓
    └───────────┴───────────┴────────────┘
                         ↓
                   [respond]  ← WAHA WhatsApp API
                         ↓
                  [save_history] → AsyncSqliteSaver checkpoint
                         ↓
                        END
```

**Every conversation is a thread.** The LangGraph `AsyncSqliteSaver` checkpointer persists the entire agent state — conversation history, extracted entities, onboarding progress — per user phone number. No session state is held in memory.

---

## Agent Roster

| Agent | Intent(s) Handled | Key Capability |
|---|---|---|
| `intent_classifier` | All | Few-shot LLM classification (9 classes), LLM-based language detection |
| `entity_extractor` | All | spaCy NER + Groq extraction; pronoun resolution via `last_entities` |
| `memory_agent` | All | ChromaDB RAG — retrieves stored notes about contacts |
| `task_agent` | `TASK`, `FOLLOW_UP`, `STORE_INFO` | Creates SQLite task records |
| `reminder_agent` | — | Schedules APScheduler one-shot jobs; persists to DB for crash recovery |
| `task_completion_agent` | `TASK_COMPLETE` | Honorific-aware fuzzy matching ("Sharma ji" ↔ "Sharma"); auto-cancels reminders |
| `reminder_control_agent` | `REMINDER_CONTROL` | Regex + NL duration parsing; reschedules or cancels APScheduler jobs |
| `reply_drafter` | `REPLY_DRAFT`, `UNKNOWN` | Context-aware draft; saves pending confirmation to DB |
| `confirmation_agent` | `CONFIRMATION` | Handles haan/nahi; delivers approved draft to user for forwarding |
| `report_agent` | `STATUS_QUERY` | Queries SQLite and formats pending task summary |
| `transcription_agent` | Voice messages | Groq Whisper transcription |
| `onboarding_agent` | First-time users | 3-step state machine using `graph.aupdate_state()` |

---

## Key Technical Design Decisions

### 1. Persistent Memory via LangGraph Checkpointing
Rather than storing conversation history in a custom table, the **entire LangGraph state is checkpointed per user** using `AsyncSqliteSaver`. This means cross-turn context (conversation history, last extracted entities, onboarding progress) is fully restored on any new message without application-layer session management.

```python
# Every user gets their own isolated thread in checkpoints.sqlite
config = {"configurable": {"thread_id": phone_number}}
await graph.ainvoke(initial_state, config=config)
```

### 2. Pronoun Resolution via `last_entities`
When a user says *"Draft a reply to him"* after discussing Ravi, the entity extractor falls back to `state["last_entities"]` from the previous checkpoint to resolve "him" → Ravi. This cross-turn entity memory is propagated through all agents.

### 3. Few-Shot Intent Classification at Temperature=0
The intent classifier uses one labelled example per class in-prompt and runs at `temperature=0` for **deterministic, reproducible** results. This replaced a brittle keyword-based language detector and handles code-switched Hinglish natively.

### 4. Fuzzy Task Completion with Honorific Normalization
```python
HONORIFICS = {" ji", " bhai", " didi", " sir", " seth", " sahab"}
# "Sharma ji" correctly matches task for "Sharma"
# "Raju bhai" correctly matches task for "Raj"
```
No third-party fuzzy library — a lightweight word-overlap algorithm handles the long tail of Indian naming conventions.

### 5. Confirmation Flow via Persistent DB State
After drafting a reply, the draft is saved to `pending_confirmations` (SQLite) and the `CONFIRMATION` intent handles the haan/nahi response in the *next turn*. This is true multi-turn, stateful dialogue without polling.

### 6. Crash-Safe Reminders
On startup, `load_pending_reminders()` reloads all unsent reminders from SQLite back into APScheduler. The scheduler state is ephemeral; the DB is the source of truth.

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| **AI Orchestration** | [LangGraph](https://github.com/langchain-ai/langgraph) | Deterministic DAG with conditional routing; native checkpointing |
| **LLM Inference** | [Groq](https://groq.com) (Llama 3.3 70B) | 128k context, sub-5s latency, free tier for prototyping |
| **Voice Transcription** | Groq Whisper Large v3 | Same API, no extra key |
| **NLP / NER** | [spaCy](https://spacy.io) | Fast entity extraction for names, dates, amounts |
| **Vector Memory** | [ChromaDB](https://www.trychroma.com/) + `sentence-transformers` | Semantic contact/note retrieval |
| **Persistence** | SQLite via `aiosqlite` | Tasks, reminders, users, confirmations — async, zero-config |
| **State Checkpointing** | `langgraph-checkpoint-sqlite` | Full state persistence per user thread |
| **Scheduling** | [APScheduler](https://apscheduler.readthedocs.io/) | In-process async job scheduler for reminders |
| **WhatsApp** | [WAHA](https://waha.devlike.pro/) | Self-hosted WhatsApp HTTP API; no Meta approval needed for dev |
| **API Framework** | FastAPI + Uvicorn | Async-first, production-ready |
| **Observability** | [LangSmith](https://smith.langchain.com/) | Full LLM trace visibility |
| **Deployment** | Docker + [Render](https://render.com) | Containerized, one-command deploy |

---

##  Evaluation

An automated eval suite runs intent classification and entity extraction against **65 labeled test messages** covering all 9 intent classes and 3 languages (English, Hindi, Hinglish).

```
=== Munshi Eval Results ===
Intent Accuracy:    92%
Entity Precision:   94%
P50 Latency:        ~4.5s
Total Messages:     65
==========================

--- Per-Intent Accuracy ---
  CONFIRMATION          5/5  #####
  FOLLOW_UP            11/12 ###########.
  REMINDER_CONTROL      5/5  #####
  REPLY_DRAFT           9/10 #########.
  STATUS_QUERY          9/9  #########
  STORE_INFO            8/9  ########.
  TASK                 13/13 #############
  TASK_COMPLETE         5/5  #####
```

**Run it yourself:**
```bash
python eval/run_eval.py
```

---

## Project Structure

```
munshi/
├── app/
│   ├── agents/
│   │   ├── orchestrator.py          # LangGraph DAG: nodes, edges, conditional routing
│   │   ├── intent_classifier.py     # Few-shot LLM classifier (9 intents)
│   │   ├── entity_extractor.py      # spaCy + Groq entity extraction
│   │   ├── memory_agent.py          # ChromaDB RAG
│   │   ├── task_agent.py            # Task creation
│   │   ├── task_completion_agent.py # Fuzzy task completion
│   │   ├── reminder_agent.py        # APScheduler integration
│   │   ├── reminder_control_agent.py# Snooze/cancel reminders
│   │   ├── reply_drafter.py         # Draft + confirmation flow
│   │   ├── confirmation_agent.py    # haan/nahi handler
│   │   ├── report_agent.py          # Pending task status reports
│   │   ├── onboarding_agent.py      # First-time user flow
│   │   └── transcription.py         # Groq Whisper
│   ├── db/
│   │   └── sqlite_client.py         # Async SQLite: tasks, reminders, users, confirmations
│   ├── state.py                     # MunshiState TypedDict (typed graph state)
│   ├── models.py                    # IntentType enum, Pydantic models
│   ├── llm_client.py                # Groq client with retry + LangSmith tracing
│   ├── waha_client.py               # WhatsApp send API
│   ├── webhook.py                   # Inbound message handler + edge case filters
│   ├── scheduler.py                 # APScheduler helpers
│   └── main.py                      # FastAPI app + lifespan init
├── eval/
│   ├── run_eval.py                  # Evaluation harness (65 test cases)
│   └── test_messages.json           # Labeled eval dataset (EN + HI + Hinglish)
├── Dockerfile
├── render.yaml
└── requirements.txt
```

---

##  Edge Cases Handled

| Scenario | Handling |
|---|---|
| Bot sends message to itself | `fromMe: true` filter in webhook |
| Group chat message | `@g.us` JID filter |
| Stickers / reactions / call logs | `IGNORABLE_TYPES` filter |
| Empty audio message | `has_media + body` guard |
| Pronoun in follow-up turn | `last_entities` cross-turn resolution |
| "Cancel" ambiguity (CONFIRMATION vs REMINDER_CONTROL) | LLM disambiguation rule in prompt |
| Scheduler restart (lost jobs) | DB-driven replay on startup |
| First-time user | Onboarding state machine via `graph.aupdate_state()` |
| User wants to wipe memory | `reset` / `clear` keyword handler |
| Groq API failure | Retry with 2s backoff, user-facing error in their language |
| Honorifics in contact names | Normalization: "Sharma ji" ↔ "Sharma" ↔ "Sharma bhai" |

---

##  Quick Start

### Prerequisites
- Docker + Docker Compose  
- A [Groq API key](https://console.groq.com) (free)  
- WAHA running locally or on a VPS (`docker compose up`)  
- A WhatsApp account for the bot

### 1. Clone & Configure

```bash
git clone https://github.com/your-username/munshi
cd munshi
cp .env.example .env
# Fill in GROQ_API_KEY and WAHA_API_URL
```

### 2. Start WAHA (WhatsApp API)

```bash
cd waha
docker compose up -d
# Visit http://localhost:3000 and scan the QR code to link WhatsApp
```

### 3. Run Munshi

```bash
docker build -t munshi .
docker run -p 8000:8000 --env-file .env munshi
```

### 4. Wire up the Webhook

Configure WAHA to POST to `http://your-host:8000/webhook` for the `message` event.

---

## 🛠️ Detailed Setup & Tracing Guide

### 1. LangSmith Tracing (Observability)
To see Munshi's internal thoughts and agent traces:
1.  Create an account at [smith.langchain.com](https://smith.langchain.com/).
2.  Create a new API Key in **Settings**.
3.  Add `LANGCHAIN_TRACING_V2=true` and your key to `.env`.
4.  Munshi uses the `@traceable` decorator in `app/llm_client.py` to automatically ship logs to your dashboard.

### 2. WhatsApp Integration (WAHA)
Munshi uses **WAHA (WhatsApp HTTP API)** to interact with WhatsApp without the official Business API's restrictions.
1.  Run WAHA via Docker: `docker compose up -d` (in the `waha/` folder).
2.  Open `http://localhost:3000`, click **Add Session**, and name it `default`.
3.  Scan the QR code with your phone (WhatsApp → Linked Devices).
4.  Set the **Webhook URL** in the WAHA dashboard to your local Munshi endpoint: `http://localhost:8000/webhook`.

### 3. Running for Development
```bash
# Install dependencies
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# Launch the API
uvicorn app.main:app --reload
```

---

## 🌍 Environment Variables

| Variable | Description |
|---|---|
| `GROQ_API_KEY` | Groq API key (LLM + Whisper) |
| `WAHA_API_URL` | Base URL of your WAHA instance |
| `WAHA_SESSION` | WAHA session name (default: `default`) |
| `DATABASE_URL` | SQLite path (default: `sqlite:///./munshi.db`) |
| `CHECKPOINT_DB` | Checkpoint SQLite path (default: `./checkpoints.sqlite`) |
| `LANGCHAIN_TRACING_V2` | Set to `true` to enable LangSmith tracing |
| `LANGSMITH_API_KEY` | Your LangSmith API Key |
| `LANGSMITH_PROJECT` | Your LangSmith project name |
| `CHROMA_DB_PATH` | ChromaDB storage directory |

---

##  Roadmap

- [ ] **Summarization node** — Periodically condense old `conversation_history` to manage context window growth  
- [ ] **Image / invoice processing** — Groq vision API for receipt parsing  
- [ ] **Proactive morning briefings** — 9 AM daily summary cron job  
- [ ] **Meta Business API migration** — Move from WAHA to official WhatsApp Cloud API for multi-tenancy  
- [ ] **Multi-tenant SaaS** — Per-business isolated SQLite instances on a managed backend  

---

##  Design Philosophy

> "The best interface is the one people already use."

Munshi is built on the belief that AI agents are most valuable when they fit into existing workflows — not when they demand users adopt new tools. WhatsApp has 500M+ users in India. A business assistant that lives there, speaks their language, and handles the informal, code-switched way people actually communicate is worth more than a polished but unused app.

Every technical choice reinforces this: async throughout for real-world latency, stateful memory so the agent never "forgets," and fuzzy matching that handles the messy reality of Indian names and honorifics.

---

##  Author

Built as a personal productivity tool and AI engineering portfolio project.

- LangGraph multi-agent orchestration
- Persistent state management with SQLite checkpoint
- Production WhatsApp integration (webhook, edge cases, filters)
- Async Python (FastAPI + aiosqlite + APScheduler)
- Eval-driven development with labeled multi-language dataset

---

*Munshi handles your business. You handle your business.*
