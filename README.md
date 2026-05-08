# 🧾 Munshi — Production multi-agent WhatsApp assistant — LangGraph · FastAPI · SQLite · Docker

> *Munshi* (मुंशी) — Sanskrit/Urdu for a personal secretary or business record-keeper.

WhatsApp-native AI assistant for Indian small business owners. Tracks payments, creates tasks, drafts replies, and sends reminders — all from unstructured Hinglish conversations. No app to install. No training needed. Just WhatsApp.

---

## Eval Results

Tested against **65 labeled messages** across 9 intent classes in English, Hindi, and Hinglish.

```
Intent Accuracy     92%   (60/65 correct)
Entity Precision    94%
P50 Latency         4.2s  (Groq free tier)
P95 Latency         5.5s
```

Per-intent breakdown:

```
TASK               13/13  █████████████
CONFIRMATION        5/5   █████
REMINDER_CONTROL    5/5   █████
STATUS_QUERY        9/9   █████████
TASK_COMPLETE       5/5   █████
FOLLOW_UP          11/12  ████████████░
REPLY_DRAFT         9/10  █████████░
STORE_INFO          8/9   ████████░
```

```bash
python eval/run_eval.py
```

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        WhatsApp User                        │
└──────────────────────────┬──────────────────────────────────┘
                           │  message / voice note
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    WAHA (Docker)                            │
│          whatsapp-web.js HTTP wrapper, NOWEB engine         │
└──────────────────────────┬──────────────────────────────────┘
                           │  POST /webhook
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                  FastAPI  (app/webhook.py)                  │
│   • Returns 200 immediately                                 │
│   • Filters: fromMe, group chats, stickers, reactions       │
│   • Spawns async background task                            │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              LangGraph StateGraph  (orchestrator.py)        │
│                                                             │
│  [reset_state]                                              │
│       ↓                                                     │
│  [transcribe] ──── Groq Whisper (voice notes only)          │
│       ↓                                                     │
│  [classify] ─────── Groq LLM, few-shot, temp=0, 9 classes  │
│       ↓                                                     │
│  [extract] ──────── spaCy NER + Groq hybrid                 │
│       ↓                                                     │
│  [memory] ───────── ChromaDB RAG (contact context)          │
│       ↓                                                     │
│  ┌────┴──────────────────────────────────────────────┐      │
│  │           Conditional routing on intent           │      │
│  └──┬──────┬──────┬──────┬──────┬──────┬────────────┘      │
│     │      │      │      │      │      │                    │
│  [task] [reply] [report] [task_  [reminder [confirm]        │
│     │   [draft]    │    complete]  _control]    │           │
│  [remind]   │      │       │          │         │           │
│     │    [confirm?]│       │          │         │           │
│     └──────┴───────┴───────┴──────────┴─────────┘          │
│                           ↓                                 │
│                      [respond]                              │
│                           ↓                                 │
│                   [save_history] ── AsyncSqliteSaver        │
└──────────────────────────┬──────────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
   ┌─────────────────┐       ┌─────────────────────┐
   │  SQLite (async) │       │  ChromaDB + embeddings│
   │  tasks          │       │  contact memory       │
   │  reminders      │       │  sentence-transformers│
   │  users          │       └─────────────────────┘
   │  confirmations  │
   │  checkpoints    │
   └─────────────────┘
              │
              ▼
   ┌─────────────────┐
   │   APScheduler   │
   │  reminder jobs  │
   │  crash-resilient│
   └─────────────────┘
              │
              ▼
   ┌─────────────────┐
   │  WAHA send API  │  → WhatsApp reply delivered
   └─────────────────┘
```

---

## What It Does

A small business owner can simply WhatsApp:

> *"Sharma ji ka 50k pending hai 2 mahine se"* → Task + reminder auto-created  
> *"Ravi ne pay kar diya"* → Task fuzzy-matched and marked done, reminder cancelled  
> *"Draft reply to Priya about the GST invoice"* → Professional draft generated, awaits confirmation  
> *"Snooze reminder 1 ghante ke liye"* → APScheduler job rescheduled, DB updated  
> *"Kya pending hai?"* → Status report of all open tasks  

---

## Decision Log

### Why LangGraph over alternatives

The core problem: a WhatsApp message can mean 9 different things, each requiring a different sequence of agents, and the system must maintain per-user state across turns without any session infrastructure.

**LangGraph** was chosen over the alternatives below:

| Alternative | Why rejected |
|---|---|
| Plain Python functions | No built-in state persistence, conditional routing becomes a mess of if/else, no checkpointing |
| LangChain AgentExecutor | Tool-calling loop is non-deterministic — bad for a system where "draft a reply" must never accidentally create a task |
| CrewAI | Role-based multi-agent, not DAG-based. No native per-user thread checkpointing. Overkill for a linear pipeline with branching |
| Custom FSM | Would have to reimplement checkpointing, state serialization, and async execution from scratch |
| AutoGen | Conversational agent framework — designed for agent-to-agent dialogue, not user-facing pipelines with strict routing |

LangGraph gives three things nothing else does cleanly together:

1. **Deterministic DAG routing** — `classify → extract → memory → [branch]` is explicit. The graph cannot hallucinate a path.
2. **Native per-user checkpointing** — `AsyncSqliteSaver` with `thread_id=phone_number` means every user's full state (conversation history, last entities, onboarding progress) is restored on any new message. Zero application-layer session management.
3. **`aupdate_state()`** — The onboarding flow injects state mid-graph without re-running the full pipeline. This is not possible in a simple function chain.

The tradeoff: LangGraph adds ~200ms overhead per invocation and the graph definition is verbose. Acceptable given the architectural benefits.

---

## Agent Roster

| Agent | Intent(s) | Key capability |
|---|---|---|
| `intent_classifier` | All | Few-shot LLM, 9 classes, temp=0, language detection |
| `entity_extractor` | All | spaCy NER + Groq; pronoun resolution via `last_entities` |
| `memory_agent` | All | ChromaDB RAG — contact context retrieval + upsert |
| `task_agent` | TASK, FOLLOW_UP, STORE_INFO | SQLite task creation |
| `reminder_agent` | — | APScheduler DateTrigger, DB-persisted for crash recovery |
| `task_completion_agent` | TASK_COMPLETE | Honorific-aware fuzzy match; auto-cancels reminders |
| `reminder_control_agent` | REMINDER_CONTROL | Regex + NL duration parsing; reschedule or cancel |
| `reply_drafter` | REPLY_DRAFT, UNKNOWN | Context-aware draft; saves to `pending_confirmations` |
| `confirmation_agent` | CONFIRMATION | haan/nahi handler; delivers approved draft |
| `report_agent` | STATUS_QUERY | SQLite query → formatted pending task summary |
| `transcription_agent` | Voice messages | Groq Whisper; temp file deleted after transcription |
| `onboarding_agent` | First-time users | 3-step state machine via `graph.aupdate_state()` |

---

## Key Design Decisions

**Persistent state via LangGraph checkpointing** — The entire graph state is checkpointed per user in SQLite. Cross-turn context (conversation history, last entities, onboarding progress) is fully restored on every new message.

```python
config = {"configurable": {"thread_id": phone_number}}
await graph.ainvoke(initial_state, config=config)
```

**Pronoun resolution via `last_entities`** — "Draft a reply to him" after discussing Ravi resolves "him" → Ravi via the previous checkpoint's `last_entities`. No separate coreference model needed.

**Few-shot intent classification at temp=0** — One labeled example per class in-prompt, deterministic output. Handles code-switched Hinglish natively.

**Honorific normalization for fuzzy task completion** — "Sharma ji" matches "Sharma" matches "Sharma bhai" via a lightweight word-overlap algorithm. No third-party fuzzy library.

```python
HONORIFICS = {" ji", " bhai", " didi", " sir", " seth", " sahab"}
```

**Crash-safe reminders** — APScheduler state is ephemeral. On startup, `load_pending_reminders()` replays all unsent reminders from SQLite. The DB is the source of truth.

**Confirmation flow via DB** — After drafting a reply, the draft is saved to `pending_confirmations`. The next turn's `CONFIRMATION` intent retrieves and delivers it. True multi-turn dialogue without polling.

---

## Tech Stack

| Layer | Technology |
|---|---|
| AI orchestration | LangGraph (DAG + AsyncSqliteSaver checkpointing) |
| LLM inference | Groq — Llama 3.3 70B (128k context, free tier) |
| Voice transcription | Groq Whisper Large v3 |
| NLP / NER | spaCy `en_core_web_sm` |
| Vector memory | ChromaDB + `sentence-transformers` (all-MiniLM-L6-v2, CPU) |
| Structured DB | SQLite via `aiosqlite` |
| Scheduling | APScheduler |
| WhatsApp | WAHA (self-hosted, NOWEB engine) |
| API framework | FastAPI + Uvicorn |
| Observability | LangSmith (`@traceable` on every LLM call) |
| Deployment | Docker + Render |

Total monthly cost: ₹0. All free tiers.

---

## Project Structure

```
munshi/
├── app/
│   ├── agents/
│   │   ├── orchestrator.py           # LangGraph DAG: nodes, edges, routing
│   │   ├── intent_classifier.py      # Few-shot LLM classifier (9 intents)
│   │   ├── entity_extractor.py       # spaCy + Groq entity extraction
│   │   ├── memory_agent.py           # ChromaDB RAG
│   │   ├── task_agent.py             # Task creation
│   │   ├── task_completion_agent.py  # Fuzzy task completion
│   │   ├── reminder_agent.py         # APScheduler integration
│   │   ├── reminder_control_agent.py # Snooze / cancel reminders
│   │   ├── reply_drafter.py          # Draft + confirmation flow
│   │   ├── confirmation_agent.py     # haan/nahi handler
│   │   ├── report_agent.py           # Pending task status reports
│   │   ├── onboarding_agent.py       # First-time user flow
│   │   └── transcription.py          # Groq Whisper
│   ├── db/
│   │   └── sqlite_client.py          # Async SQLite: tasks, reminders, users, confirmations
│   ├── state.py                      # MunshiState TypedDict
│   ├── models.py                     # IntentType enum, Pydantic models
│   ├── llm_client.py                 # Groq client with retry + LangSmith tracing
│   ├── waha_client.py                # WhatsApp send API
│   ├── webhook.py                    # Inbound handler + edge case filters
│   ├── scheduler.py                  # APScheduler helpers
│   └── main.py                       # FastAPI app + lifespan init
├── eval/
│   ├── run_eval.py                   # Evaluation harness (65 test cases)
│   └── test_messages.json            # Labeled dataset (EN + HI + Hinglish)
├── Dockerfile
├── render.yaml
└── requirements.txt
```

---

## Edge Cases Handled

| Scenario | Handling |
|---|---|
| Bot sends to itself | `fromMe: true` filter |
| Group chat message | `@g.us` JID filter |
| Stickers / reactions / call logs | `IGNORABLE_TYPES` filter |
| Pronoun in follow-up turn | `last_entities` cross-turn resolution |
| "Cancel" ambiguity | LLM disambiguation rule in classifier prompt |
| Scheduler restart | DB-driven replay on startup |
| First-time user | Onboarding state machine via `graph.aupdate_state()` |
| Groq API failure | Retry with 2s backoff, user-facing error in their language |
| Honorifics in names | Normalization: "Sharma ji" ↔ "Sharma" ↔ "Sharma bhai" |

---

## Quick Start

### Prerequisites
- Docker + Docker Compose
- [Groq API key](https://console.groq.com) (free)
- A WhatsApp account for the bot

### 1. Clone & configure

```bash
git clone https://github.com/your-username/munshi
cd munshi
cp .env.example .env
# Fill in GROQ_API_KEY and WAHA_API_URL
```

### 2. Start WAHA

```bash
cd waha
docker compose up -d
# Visit http://localhost:3000, add a session named "default", scan the QR code
```

### 3. Run Munshi

```bash
docker build -t munshi .
docker run -p 8000:8000 --env-file .env munshi
```

### 4. Wire up the webhook

In the WAHA dashboard, set the webhook URL to `http://your-host:8000/webhook` for the `message` event.

### Development (no Docker)

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
uvicorn app.main:app --reload
```

---

## Environment Variables

| Variable | Description |
|---|---|
| `GROQ_API_KEY` | Groq API key (LLM + Whisper) |
| `WAHA_API_URL` | Base URL of your WAHA instance |
| `WAHA_SESSION` | WAHA session name (default: `default`) |
| `WAHA_API_KEY` | WAHA auth header value |
| `DATABASE_URL` | SQLite path (default: `sqlite:///./munshi.db`) |
| `CHECKPOINT_DB` | Checkpoint SQLite path (default: `./checkpoints.sqlite`) |
| `LANGCHAIN_TRACING_V2` | Set to `true` to enable LangSmith |
| `LANGSMITH_API_KEY` | LangSmith API key |
| `LANGSMITH_PROJECT` | LangSmith project name |
| `CHROMA_PERSIST_DIR` | ChromaDB storage directory |

---

## Roadmap

- [ ] Summarization node — condense old `conversation_history` to manage context window growth
- [ ] Image / invoice processing — Groq vision API for receipt parsing
- [ ] Proactive morning briefings — 9 AM daily summary cron
- [ ] Multi-tenant SaaS — per-business isolated SQLite on managed backend
- [ ] Meta Business API migration — move from WAHA to official WhatsApp Cloud API

---

## Design Philosophy

> "The best interface is the one people already use."

WhatsApp has 500M+ users in India. A business assistant that lives there, speaks their language, and handles the informal, code-switched way people actually communicate is worth more than a polished but unused app. Every technical choice reinforces this: async throughout for real-world latency, stateful memory so the agent never forgets, and fuzzy matching that handles the messy reality of Indian names and honorifics.

---

*Munshi handles your business. You handle your business.*
