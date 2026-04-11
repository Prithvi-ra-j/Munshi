# Munshi — Tasks Spec (Build Order)

## How to use this file with Kiro
Open each task in order. Do NOT skip ahead. Each task builds on the previous.
When you complete a task, mark it ✅ and move to the next.

Estimated total: ~10 hours across 2 weekends

---

## PHASE 1: Foundation (Weekend 1, Day 1 — ~3 hours)

### Task 1.1 — Project Setup ⬜
**Prompt to Kiro:** "Set up the Munshi project structure exactly as defined in the design spec folder structure. Create all files and directories. Create requirements.txt with all dependencies. Create .env.example. Initialize SQLite DB with the tasks and reminders tables from the design spec."

Dependencies: None

Expected output:
- Full folder structure created
- requirements.txt with: fastapi, uvicorn, langgraph, langsmith, chromadb, sentence-transformers, groq, python-dotenv, apscheduler, spacy, pydantic, httpx, aiosqlite
- .env.example with all required variables
- db/sqlite_client.py with init_db() function
- SQLite tables created on startup

---

### Task 1.2 — WAHA Setup ⬜
**Prompt to Kiro:** "Create the WAHA docker-compose.yml from the design spec. Create a waha_client.py in app/ that wraps WAHA's REST API with async Python methods: send_text_message(phone, text), download_media(media_url), get_session_status(). Use httpx for HTTP calls."

Dependencies: Task 1.1

Expected output:
- waha/docker-compose.yml
- app/waha_client.py with 3 methods
- Error handling for WAHA connection failures

---

### Task 1.3 — FastAPI Skeleton ⬜
**Prompt to Kiro:** "Create app/main.py with FastAPI app. Add /health endpoint that checks WAHA connection and SQLite connection. Add /webhook POST endpoint that accepts WAHAWebhookPayload from models.py, returns 200 immediately, and queues processing as a background task. Add /tasks/{phone} GET endpoint. Add /eval/run POST endpoint stub. Include CORS middleware."

Dependencies: Task 1.2

Expected output:
- app/main.py with 4 endpoints
- Background task queue for webhook processing
- Health check that actually pings WAHA and SQLite
- app/models.py with all Pydantic models from design spec

---

## PHASE 2: Core Agents (Weekend 1, Day 2 — ~4 hours)

### Task 2.1 — LLM Client + LangSmith ⬜
**Prompt to Kiro:** "Create app/llm_client.py that wraps Groq API. It should have: call_llm(prompt, system_prompt, model='llama-3.3-70b-versatile', max_tokens=500) async function. Integrate LangSmith tracing so every call is traced with input/output/latency/tokens. Create a get_tracer() function. Add retry logic: if Groq fails, wait 2 seconds and retry once. If retry fails, return a fallback response."

Dependencies: Task 1.3

Expected output:
- app/llm_client.py
- LangSmith traces visible on every call
- Retry + fallback logic

---

### Task 2.2 — Transcription Agent ⬜
**Prompt to Kiro:** "Create app/agents/transcription.py. The transcription_agent(state: MunshiState) function should: check if message_type is 'audio', download audio from state.audio_url using waha_client, call Groq Whisper API (whisper-large-v3) to transcribe, set state.transcribed_text and state.processed_text, delete the local audio file, return updated state. If message_type is 'text', just set processed_text = raw_message and return."

Dependencies: Task 2.1

Expected output:
- app/agents/transcription.py
- Handles both text and audio message types
- Audio file cleanup after transcription
- LangSmith trace on Whisper call

---

### Task 2.3 — Intent Classifier Agent ⬜
**Prompt to Kiro:** "Create app/agents/intent_classifier.py. The intent_classifier_agent(state: MunshiState) function should: use the intent classifier prompt from the design spec, call llm_client.call_llm(), parse the JSON response, set state.intent and state.intent_confidence, detect language (English/Hindi/Hinglish) and set state.language, return updated state. Handle JSON parse errors gracefully by setting intent to UNKNOWN."

Dependencies: Task 2.2

Expected output:
- app/agents/intent_classifier.py
- Returns IntentType enum value
- Language detection working
- Confidence score in state

---

### Task 2.4 — Entity Extractor Agent ⬜
**Prompt to Kiro:** "Create app/agents/entity_extractor.py. Use a hybrid approach: first run spaCy (en_core_web_sm) to extract PERSON entities and DATE entities, then call Groq with the entity extractor prompt from design spec to extract amounts and the action summary. Merge both results into state.entities dict with keys: names, dates, amounts, action. Return updated state."

Dependencies: Task 2.3

Expected output:
- app/agents/entity_extractor.py
- spaCy for NER
- Groq for amounts + action
- Merged entities dict

---

### Task 2.5 — ChromaDB Memory Agent ⬜
**Prompt to Kiro:** "Create app/db/chroma_client.py with ChromaDB setup: get_or_create_collection('contacts'), upsert_contact(user_phone, contact_name, context), search_contact(user_phone, query, n_results=3). Create app/agents/memory_agent.py: memory_rag_agent(state) that takes names from state.entities.names, searches ChromaDB for each, sets state.contact_context with relevant past context, and upserts any new contact mentions. Use sentence-transformers for embeddings."

Dependencies: Task 2.4

Expected output:
- app/db/chroma_client.py
- app/agents/memory_agent.py
- ChromaDB persisting to ./chroma_db directory

---

## PHASE 3: Action Agents (Weekend 2, Day 1 — ~4 hours)

### Task 3.1 — Task Agent ⬜
**Prompt to Kiro:** "Create app/agents/task_agent.py. The task_agent(state) function handles TASK, FOLLOW_UP, and STORE_INFO intents. It should: create a TaskCreate object from state.entities, call sqlite_client to insert into tasks table, set state.tasks_created with the new task ID, build a confirmation message in state.language (e.g., '✅ Note kar liya — {action}'), set state.final_response. Return updated state."

Dependencies: Task 2.5

Expected output:
- app/agents/task_agent.py
- SQLite task insertion working
- Multilingual confirmation messages

---

### Task 3.2 — Reply Drafter Agent ⬜
**Prompt to Kiro:** "Create app/agents/reply_drafter.py. The reply_drafter_agent(state) function handles REPLY_DRAFT and UNKNOWN intents. It should: use contact_context from state, call Groq with the reply drafter prompt from design spec, prefix response with '📝 Draft:\n', set state.final_response. For UNKNOWN intent, ask one clarifying question in user's language. Return updated state."

Dependencies: Task 3.1

Expected output:
- app/agents/reply_drafter.py
- Draft formatted with prefix
- Clarifying question for UNKNOWN intent

---

### Task 3.3 — Report Agent ⬜
**Prompt to Kiro:** "Create app/agents/report_agent.py. The report_agent(state) handles STATUS_QUERY intent. It should: query SQLite for all pending tasks where user_phone = state.phone, order by created_at desc, limit 5, format a summary message in state.language, set state.final_response. Empty state message: '🎉 Abhi koi pending kaam nahi hai!'. Non-empty: show count + list of top 5 with checkboxes."

Dependencies: Task 3.2

Expected output:
- app/agents/report_agent.py
- SQLite query for pending tasks
- Formatted WhatsApp-friendly summary

---

### Task 3.4 — Reminder Agent ⬜
**Prompt to Kiro:** "Create app/scheduler.py with APScheduler AsyncIOScheduler. Create app/agents/reminder_agent.py. The reminder_agent(state) should: check if any task in state.tasks_created has a due_date, if yes, schedule a reminder job via APScheduler at due_date - 1 hour, store reminder in SQLite reminders table, the job should call waha_client.send_text_message with reminder text. On app startup, load all unsent reminders from SQLite and reschedule them."

Dependencies: Task 3.3

Expected output:
- app/scheduler.py
- app/agents/reminder_agent.py
- Reminders persist across restarts
- Reminder fires via WAHA

---

## PHASE 4: Orchestrator + Integration (Weekend 2, Day 2 — ~2 hours)

### Task 4.1 — LangGraph Orchestrator ⬜
**Prompt to Kiro:** "Create app/agents/orchestrator.py. Build the full LangGraph graph exactly as defined in the design spec. Implement the route_by_intent() conditional edge function. Implement response_formatter node that sends state.final_response via waha_client.send_text_message(). Wire all agents in correct order. Export a compiled_graph = build_munshi_graph() that can be imported and invoked."

Dependencies: Tasks 2.1-3.4

Expected output:
- app/agents/orchestrator.py
- Full LangGraph graph compiles without errors
- route_by_intent working for all 5 intents
- Response sent back via WAHA

---

### Task 4.2 — Webhook Integration ⬜
**Prompt to Kiro:** "Update app/webhook.py to: parse incoming WAHA webhook payload, build initial MunshiState from the payload (phone from 'from' field, strip @c.us suffix, extract message body, detect if audio message), invoke compiled_graph from orchestrator, handle errors gracefully (if graph fails, send 'Kuch technical issue hai, thodi der mein try karein'). The webhook handler must be async."

Dependencies: Task 4.1

Expected output:
- app/webhook.py fully integrated with orchestrator
- End-to-end flow working: WhatsApp message → response
- Error handling with user-friendly fallback

---

## PHASE 5: Eval + Deploy (Final push)

### Task 5.1 — Eval Framework ⬜
**Prompt to Kiro:** "Create eval/test_messages.json with 50 test messages covering all 5 intents, in English, Hindi, and Hinglish. Include expected_intent and expected_entities for each. Create eval/run_eval.py that: loads test_messages.json, runs each through the intent_classifier_agent and entity_extractor_agent directly (not via WhatsApp), calculates intent_accuracy, entity_precision, p50_latency_ms, p95_latency_ms, saves results to eval/results.json, prints summary table."

Dependencies: Task 4.2

Expected output:
- eval/test_messages.json (50 messages)
- eval/run_eval.py
- eval/results.json generated on run

---

### Task 5.2 — Dockerfile + Render Config ⬜
**Prompt to Kiro:** "Create Dockerfile for the Munshi FastAPI app. Create render.yaml for Render deployment. The Dockerfile should: use python:3.11-slim, install spaCy model (en_core_web_sm), install requirements.txt, copy app code, run uvicorn on port 8000. render.yaml should define a web service pointing to the Dockerfile. Add startup script that initializes SQLite tables and loads pending reminders."

Dependencies: Task 5.1

Expected output:
- Dockerfile
- render.yaml
- Startup initialization script

---

### Task 5.3 — README ⬜
**Prompt to Kiro:** "Create a production-quality README.md for Munshi. Include: project tagline, problem statement (1 paragraph), architecture diagram (Mermaid), quick start (docker-compose up), environment variables table, API endpoints table, agent descriptions table, eval results table (use placeholder numbers), tech stack badges, demo GIF placeholder, and a section on 'Why Munshi exists' with India MSME context. Make it look like a serious open source project."

Dependencies: Task 5.2

Expected output:
- README.md that would impress any recruiter
- Mermaid architecture diagram
- All sections complete

---

## Kiro Credit Budget (50 credits total)

| Phase | Tasks | Estimated Credits |
|---|---|---|
| Phase 1: Foundation | 1.1, 1.2, 1.3 | 8 |
| Phase 2: Core Agents | 2.1-2.5 | 15 |
| Phase 3: Action Agents | 3.1-3.4 | 12 |
| Phase 4: Orchestrator | 4.1, 4.2 | 8 |
| Phase 5: Eval + Deploy | 5.1-5.3 | 7 |
| **Total** | **13 tasks** | **50** |

## Tips for Using Kiro Efficiently
1. Always reference this tasks.md when prompting — "Do Task 2.3 from tasks.md"
2. After each task, run the code and fix errors BEFORE moving to next task
3. Use Kiro's steering rules — it reads project.md automatically
4. If Kiro goes off-spec, paste the relevant section from design.md and say "follow this exactly"
5. Save credits by handling small fixes manually — only use Kiro for new agent creation
