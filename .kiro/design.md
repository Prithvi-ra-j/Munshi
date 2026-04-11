# Munshi — Design Spec

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    User's WhatsApp                       │
└──────────────────────┬──────────────────────────────────┘
                       │ sends message
                       ▼
┌─────────────────────────────────────────────────────────┐
│                  WAHA Container (Docker)                  │
│         whatsapp-web.js REST API wrapper                  │
│         Port 3000 | Webhook → FastAPI                    │
└──────────────────────┬──────────────────────────────────┘
                       │ POST /webhook
                       ▼
┌─────────────────────────────────────────────────────────┐
│              FastAPI Backend (app/main.py)               │
│                                                          │
│  /health    /webhook    /tasks/{phone}    /eval          │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│           Orchestrator Agent (LangGraph)                 │
│                                                          │
│  State: {phone, message, intent, entities,               │
│           tasks, draft, response, trace_id}              │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐  │
│  │Transcribe│  │ Classify │  │  Extract Entities    │  │
│  │  Agent   │→ │  Intent  │→ │  (spaCy + Groq)      │  │
│  └──────────┘  └──────────┘  └──────────────────────┘  │
│                                        │                 │
│              ┌─────────────────────────┤                 │
│              │                         │                 │
│         ┌────▼────┐              ┌─────▼─────┐          │
│         │  Task   │              │  Memory   │          │
│         │  Agent  │              │ RAG Agent │          │
│         └────┬────┘              └─────┬─────┘          │
│              │                         │                 │
│         ┌────▼─────────────────────────▼────┐           │
│         │         Reply / Report Agent       │           │
│         └────────────────┬──────────────────┘           │
│                          │                               │
│                   ┌──────▼──────┐                        │
│                   │  Reminder   │                        │
│                   │   Agent     │                        │
│                   └─────────────┘                        │
└──────────────────────┬──────────────────────────────────┘
                       │
         ┌─────────────┴──────────────┐
         │                            │
┌────────▼────────┐        ┌──────────▼──────────┐
│   SQLite DB     │        │    ChromaDB          │
│                 │        │                      │
│ - tasks         │        │ - contacts           │
│ - reminders     │        │   collection         │
└─────────────────┘        └─────────────────────┘
         │
┌────────▼────────┐        ┌─────────────────────┐
│  APScheduler    │        │    LangSmith         │
│  (reminders)    │        │  (all traces)        │
└─────────────────┘        └─────────────────────┘
         │
┌────────▼────────┐        ┌─────────────────────┐
│   Groq API      │        │  sentence-           │
│ - llama-3.3-70b │        │  transformers        │
│ - whisper-large │        │  (embeddings)        │
└─────────────────┘        └─────────────────────┘
```

## LangGraph State Definition

```python
from typing import TypedDict, Optional, List
from enum import Enum

class IntentType(str, Enum):
    TASK = "TASK"
    FOLLOW_UP = "FOLLOW_UP"
    REPLY_DRAFT = "REPLY_DRAFT"
    STATUS_QUERY = "STATUS_QUERY"
    STORE_INFO = "STORE_INFO"
    UNKNOWN = "UNKNOWN"

class MunshiState(TypedDict):
    # Input
    phone: str
    raw_message: str
    message_type: str          # "text" | "audio" | "image"
    audio_url: Optional[str]
    timestamp: str

    # Processing
    transcribed_text: Optional[str]
    processed_text: str        # final text after transcription
    intent: Optional[IntentType]
    intent_confidence: Optional[float]
    entities: dict             # {names: [], dates: [], amounts: []}
    contact_context: Optional[str]

    # Output
    tasks_created: List[int]   # SQLite task IDs
    reminder_scheduled: Optional[str]
    draft_reply: Optional[str]
    status_report: Optional[str]
    final_response: str
    language: str              # "en" | "hi" | "hinglish"

    # Observability
    trace_id: str
    agent_errors: List[str]
```

## LangGraph Graph Definition

```python
from langgraph.graph import StateGraph, END

def build_munshi_graph():
    graph = StateGraph(MunshiState)

    # Add nodes
    graph.add_node("transcribe", transcription_agent)
    graph.add_node("classify", intent_classifier_agent)
    graph.add_node("extract", entity_extractor_agent)
    graph.add_node("memory", memory_rag_agent)
    graph.add_node("task", task_agent)
    graph.add_node("reply", reply_drafter_agent)
    graph.add_node("report", report_agent)
    graph.add_node("reminder", reminder_agent)
    graph.add_node("respond", response_formatter)

    # Entry point
    graph.set_entry_point("transcribe")

    # Edges
    graph.add_edge("transcribe", "classify")
    graph.add_edge("classify", "extract")
    graph.add_edge("extract", "memory")

    # Conditional routing based on intent
    graph.add_conditional_edges(
        "memory",
        route_by_intent,
        {
            "TASK": "task",
            "FOLLOW_UP": "task",
            "REPLY_DRAFT": "reply",
            "STATUS_QUERY": "report",
            "STORE_INFO": "task",
            "UNKNOWN": "reply",
        }
    )

    graph.add_edge("task", "reminder")
    graph.add_edge("reminder", "respond")
    graph.add_edge("reply", "respond")
    graph.add_edge("report", "respond")
    graph.add_edge("respond", END)

    return graph.compile()
```

## API Endpoints

### POST /webhook
Receives WAHA events. Must return 200 within 5 seconds.
```python
{
  "event": "message",
  "session": "munshi",
  "payload": {
    "id": "msg_id",
    "from": "919876543210@c.us",
    "body": "message text",
    "hasMedia": false,
    "timestamp": 1234567890,
    "type": "chat"  # or "audio"
  }
}
```

### GET /health
```json
{
  "status": "ok",
  "waha": "connected",
  "db": "connected",
  "scheduler": "running",
  "version": "1.0.0"
}
```

### GET /tasks/{phone}
```json
{
  "phone": "919876543210",
  "pending_count": 3,
  "tasks": [
    {
      "id": 1,
      "description": "Call Sharma ji about GST docs",
      "contact_name": "Sharma ji",
      "due_date": "2026-04-05",
      "status": "pending",
      "created_at": "2026-04-03T10:00:00"
    }
  ]
}
```

### POST /eval/run
Triggers eval run against test_messages.json
```json
{
  "results": {
    "intent_accuracy": 0.87,
    "entity_precision": 0.82,
    "p50_latency_ms": 1240,
    "p95_latency_ms": 3100,
    "total_messages": 50
  }
}
```

## Pydantic Models

```python
# models.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class WAHAWebhookPayload(BaseModel):
    event: str
    session: str
    payload: dict

class TaskCreate(BaseModel):
    user_phone: str
    description: str
    contact_name: Optional[str] = None
    amount: Optional[float] = None
    due_date: Optional[str] = None
    intent_type: str

class TaskResponse(BaseModel):
    id: int
    description: str
    contact_name: Optional[str]
    due_date: Optional[str]
    status: str
    created_at: datetime

class EvalResult(BaseModel):
    intent_accuracy: float
    entity_precision: float
    p50_latency_ms: float
    p95_latency_ms: float
    total_messages: int
```

## LLM Prompt Templates

### Intent Classifier Prompt
```
You are Munshi, an AI assistant for Indian business owners.
Classify the following message into exactly one intent:
- TASK: user wants to create a reminder or to-do
- FOLLOW_UP: user is flagging something pending with someone
- REPLY_DRAFT: user wants you to draft a WhatsApp reply
- STATUS_QUERY: user wants to know what tasks are pending
- STORE_INFO: user is saving contact info or a note

Message: {message}

Respond in JSON only: {{"intent": "INTENT_TYPE", "confidence": 0.95}}
```

### Entity Extractor Prompt
```
Extract entities from this message. Return JSON only.
Message: {message}

Extract:
- names: list of person/company names mentioned
- dates: list of dates/times (normalize to YYYY-MM-DD if possible)
- amounts: list of monetary amounts in INR
- action: the main action/task described in one line

JSON format:
{{
  "names": [],
  "dates": [],
  "amounts": [],
  "action": ""
}}
```

### Reply Drafter Prompt
```
You are Munshi, drafting a WhatsApp reply for an Indian business owner.

Context about {contact_name}: {contact_context}
User's message: {user_message}
User's language: {language}

Write a brief, professional WhatsApp reply in the SAME language as the user's message.
Keep it under 3 sentences. Sound natural and human, not robotic.
Do NOT add emojis unless the user typically uses them.
```

## WAHA Docker Compose

```yaml
version: '3.8'
services:
  waha:
    image: devlikeapro/waha:latest
    ports:
      - "3000:3000"
    environment:
      - WHATSAPP_DEFAULT_ENGINE=WEBJS
      - WHATSAPP_HOOK_URL=http://munshi-backend:8000/webhook
      - WHATSAPP_HOOK_EVENTS=message
    volumes:
      - waha_sessions:/app/.sessions
    restart: unless-stopped

  munshi:
    build: .
    ports:
      - "8000:8000"
    environment:
      - WAHA_API_URL=http://waha:3000
    env_file:
      - .env
    depends_on:
      - waha
    volumes:
      - ./munshi.db:/app/munshi.db
      - ./chroma_db:/app/chroma_db
    restart: unless-stopped

volumes:
  waha_sessions:
```

## Eval Framework Design

```python
# eval/run_eval.py
# Test messages format (eval/test_messages.json):
[
  {
    "id": 1,
    "message": "Sharma ji ka payment 50k pending hai",
    "language": "hinglish",
    "expected_intent": "FOLLOW_UP",
    "expected_entities": {
      "names": ["Sharma ji"],
      "amounts": [50000]
    }
  },
  ...
]
```

## Key Design Decisions

1. **Why WAHA over official Meta API**: Meta's official API bans general-purpose AI bots (Jan 2026 policy). WAHA allows free-form AI responses needed for Munshi's use case. For production, migrate to official API with task-specific framing.

2. **Why SQLite over PostgreSQL**: Render free tier has no managed DB. SQLite runs in container. Good enough for V1 with <100 users.

3. **Why ChromaDB for contacts**: Vector similarity search lets Munshi find relevant past context even when user mentions a contact by nickname, first name only, or partial name.

4. **Why Groq**: Fastest free LLM inference available. P99 latency <2s on llama-3.3-70b. Critical for WhatsApp UX where users expect fast replies.

5. **Why LangGraph over LangChain**: LangGraph gives explicit control over agent flow with state machine approach. Easier to debug, trace, and extend. LangSmith integration is first-class.

6. **Why spaCy for entities**: Groq is used for creative/language tasks. spaCy handles structured extraction faster and cheaper (no tokens used). Hybrid approach = best of both.
