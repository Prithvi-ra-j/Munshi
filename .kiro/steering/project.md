---
inclusion: always
---

# Munshi — Project Steering

## What is Munshi
Munshi is a WhatsApp-native AI Chief of Staff for Indian MSME owners, freelancers, and solopreneurs. It sits inside WhatsApp and acts as their personal business memory. It extracts tasks, tracks follow-ups, transcribes voice notes, and sends proactive reminders from unstructured Hinglish conversations.

## Tech Stack — STRICT, DO NOT DEVIATE
- WhatsApp interface: WAHA (Docker, unofficial API via whatsapp-web.js wrapper)
- LLM: Groq API (llama-3.3-70b-versatile) — free tier
- Voice transcription: Groq Whisper API — free tier
- Agent orchestration: LangGraph (Python)
- Vector DB / memory: ChromaDB (local)
- Embeddings: sentence-transformers (all-MiniLM-L6-v2, CPU)
- Structured DB: SQLite (tasks, reminders, contacts)
- Observability: LangSmith (free tier)
- Backend: FastAPI
- Scheduler: APScheduler
- Deployment: Render (free tier)
- NLP: spaCy (en_core_web_sm) for entity extraction

## Code Style
- Python 3.11+
- Type hints everywhere
- Pydantic models for all request/response schemas
- Async FastAPI endpoints
- Each agent is a separate Python function in agents/ directory
- All LLM calls go through a single llm_client.py wrapper
- Environment variables via python-dotenv, never hardcode keys
- Every agent call must have LangSmith trace decorator

## Non-Negotiables
1. Every agent call MUST have LangSmith tracing
2. Every LLM call MUST have a fallback if Groq fails
3. SQLite MUST be initialized on startup if tables don't exist
4. WAHA webhook MUST return 200 within 5 seconds (async processing)
5. Voice notes MUST be downloaded, transcribed, then deleted locally

## Cost Constraint
Total monthly cost must be ₹0. Use only free tiers. No paid APIs.

## Language Handling
- Accept messages in English, Hindi, Hinglish
- Respond in the same language the user wrote in
- Never force English on a user who writes in Hindi
