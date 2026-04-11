# Munshi — Requirements Spec

## Overview
Munshi is a WhatsApp-native multi-agent AI system for Indian MSME owners. It processes WhatsApp messages (text + voice), understands intent, extracts structured information, stores it, and responds intelligently.

## User Stories (EARS Format)

### US-01: Text Message Intake
**WHEN** a user sends a text message to the Munshi WhatsApp number
**THE SYSTEM SHALL** receive it via WAHA webhook within 2 seconds
**AND** route it to the orchestrator agent for processing

**Acceptance Criteria:**
- [ ] WAHA webhook endpoint returns HTTP 200 within 5 seconds
- [ ] Message content, sender phone, timestamp stored in processing queue
- [ ] Supports English, Hindi, Hinglish text

---

### US-02: Voice Note Transcription
**WHEN** a user sends a voice note to Munshi
**THE SYSTEM SHALL** download the audio file from WAHA
**AND** transcribe it using Groq Whisper
**AND** process the transcription as if it were a text message
**AND** delete the local audio file after transcription

**Acceptance Criteria:**
- [ ] Audio downloaded from WAHA media endpoint
- [ ] Groq Whisper transcription returns within 10 seconds
- [ ] Hinglish voice notes transcribed with >80% accuracy
- [ ] Local audio file deleted post-transcription
- [ ] If transcription fails, user receives: "Voice note ki samajh nahi aaya, please text karein"

---

### US-03: Intent Classification
**WHEN** a message (text or transcribed voice) enters the system
**THE SYSTEM SHALL** classify it into one of 5 intents:
- TASK — user wants to create a reminder or to-do
- FOLLOW_UP — user is flagging something pending with someone
- REPLY_DRAFT — user wants Munshi to draft a reply
- STATUS_QUERY — user wants to know what's pending
- STORE_INFO — user is saving contact or info for later

**Acceptance Criteria:**
- [ ] Intent classified within 3 seconds
- [ ] Confidence score logged to LangSmith
- [ ] Ambiguous messages ask ONE clarifying question
- [ ] Intent classification accuracy ≥ 85% on eval set

---

### US-04: Task Creation
**WHEN** intent is TASK or FOLLOW_UP
**THE SYSTEM SHALL** extract: description, contact name (if any), amount (if any), due date (if any)
**AND** store in SQLite tasks table
**AND** confirm to user in their language

**Acceptance Criteria:**
- [ ] Task stored with all extracted fields
- [ ] User gets confirmation: "✅ Note kar liya — [task description]"
- [ ] If due date detected, reminder automatically scheduled
- [ ] Duplicate detection: if same task exists, ask user to confirm

---

### US-05: Reply Drafting
**WHEN** intent is REPLY_DRAFT
**THE SYSTEM SHALL** check ChromaDB for context about the mentioned contact
**AND** draft a reply in the user's language and tone
**AND** send the draft prefixed with "📝 Draft:"
**AND** ask "Bhejun kya?" (Shall I send it?)

**Acceptance Criteria:**
- [ ] Draft generated within 5 seconds
- [ ] Draft matches user's language (Hindi user gets Hindi draft)
- [ ] Draft is contextually relevant to past interactions with that contact
- [ ] User can say "haan" / "yes" / "send" to confirm (V2 feature — just draft in V1)

---

### US-06: Status Query
**WHEN** intent is STATUS_QUERY
**THE SYSTEM SHALL** query SQLite for all pending tasks for that user
**AND** format a clean summary
**AND** return it within 5 seconds

**Acceptance Criteria:**
- [ ] Summary shows: pending count, top 3 urgent items, any overdue items
- [ ] Response in same language as query
- [ ] Empty state: "Abhi koi pending kaam nahi hai 🎉"
- [ ] Max 5 items shown to avoid WhatsApp wall of text

---

### US-07: Contact Memory
**WHEN** any message mentions a person's name
**THE SYSTEM SHALL** store/update that contact in ChromaDB
**WITH** context of the interaction

**Acceptance Criteria:**
- [ ] Contact upserted in ChromaDB with latest interaction context
- [ ] When same contact mentioned later, past context retrieved
- [ ] Contact memory used to make reply drafts more contextual

---

### US-08: Reminder Scheduling
**WHEN** a task has a due date or user says "remind me [time]"
**THE SYSTEM SHALL** schedule a reminder via APScheduler
**AND** send the reminder message via WAHA at the scheduled time

**Acceptance Criteria:**
- [ ] Reminder fires within 60 seconds of scheduled time
- [ ] Reminder message: "⏰ Reminder: [task description]"
- [ ] If app restarts, pending reminders restored from SQLite
- [ ] User can cancel reminder by replying "cancel" to reminder message (V2)

---

### US-09: LangSmith Observability
**FOR EVERY** agent invocation
**THE SYSTEM SHALL** log a LangSmith trace with:
- Agent name
- Input
- Output
- Latency
- Token count

**Acceptance Criteria:**
- [ ] 100% of LLM calls traced in LangSmith
- [ ] Traces visible in LangSmith dashboard
- [ ] P95 latency tracked per agent type
- [ ] Error traces flagged separately

---

### US-10: API Deployment
**THE SYSTEM SHALL** be deployable as a single Docker container
**AND** expose a FastAPI backend with documented endpoints
**AND** run on Render free tier

**Acceptance Criteria:**
- [ ] `docker-compose up` starts both WAHA and Munshi backend
- [ ] `/health` endpoint returns 200 with system status
- [ ] `/webhook` endpoint receives WAHA events
- [ ] `/tasks/{phone}` returns all tasks for a user
- [ ] Render deployment config (render.yaml) included
- [ ] Public URL accessible for WAHA webhook configuration

## Non-Functional Requirements
- Response time: < 5 seconds for text, < 15 seconds for voice
- Availability: best-effort on free tier (Render sleep after inactivity acceptable for demo)
- Data: all data local (SQLite + ChromaDB), no external data storage
- Cost: ₹0/month total
- Languages: English, Hindi, Hinglish
