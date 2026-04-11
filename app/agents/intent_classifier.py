import json
import re
from app.state import MunshiState
from app.models import IntentType
from app.llm_client import call_llm

# ── Few-shot examples ─────────────────────────────────────────────────────────
# One representative example per intent, covering both English and Hinglish.
# Research shows few-shot prompting with 1-2 examples per class typically yields
# 5-10% accuracy gains on multi-class text classification tasks.
FEW_SHOT_EXAMPLES = """
Examples of each intent (format: INTENT_NAME : example message):

TASK           : "Remind me to call Priya tomorrow at 10am"
TASK           : "Kal subah 9 baje Sharma ji ko call karna hai"
FOLLOW_UP      : "Raju bhai ka 50,000 pending hai 2 mahine se"
FOLLOW_UP      : "Follow up with Patel ji about the invoice next week"
REPLY_DRAFT    : "Draft a reply to Meena about the order delay"
REPLY_DRAFT    : "Gupta ji ko reply karo ki payment kal tak ho jayega"
STATUS_QUERY   : "What tasks are pending today?"
STATUS_QUERY   : "Aaj kya karna hai? / Pending kaam batao"
STORE_INFO     : "Save Amit's number: 9876543210"
STORE_INFO     : "Harish bhai ka GST number 29ABCDE1234F1Z5 hai"
TASK_COMPLETE  : "Ravi ne pay kar diya" (payment received from Ravi)
TASK_COMPLETE  : "Vijay bhai settled the dues" / "invoice clear ho gaya"
REMINDER_CONTROL : "Snooze the reminder for 1 hour" / "Reminder cancel karo"
REMINDER_CONTROL : "Baad mein yaad dilao" / "Remind me later" / "1 ghante baad"
CONFIRMATION   : "Haan" / "Nahi" / "Yes send it" / "No cancel" / "Bhej do" / "Mat bhejo"
"""

INTENT_PROMPT = """You are Munshi's intent classifier for an Indian business WhatsApp assistant.

{few_shot}

─── RECENT CONVERSATION (most recent last) ───
{history}
─────────────────────────────────────────────

Classify the latest message into exactly ONE of these intents:

| Intent           | When to use |
|------------------|-------------|
| TASK             | User wants to SET a future reminder, to-do, or deadline |
| FOLLOW_UP        | User is LOGGING that someone owes them money or promised something |
| REPLY_DRAFT      | User wants Munshi to WRITE a WhatsApp message to send to someone |
| STATUS_QUERY     | User wants to SEE their pending tasks/payments list |
| STORE_INFO       | User is SAVING a contact detail, note, address, GST number, etc. |
| TASK_COMPLETE    | User says a task/payment is DONE or RECEIVED ("ne diya", "ho gaya", "settled") |
| REMINDER_CONTROL | User wants to SNOOZE or CANCEL an existing reminder |
| CONFIRMATION     | User is saying HAAN/NAHI to Munshi's previous question — check history! |
| UNKNOWN          | Cannot be classified into any of the above |

─── DISAMBIGUATION RULES ───
- FOLLOW_UP vs TASK_COMPLETE: FOLLOW_UP = "X ka payment PENDING hai" | TASK_COMPLETE = "X ne payment KAR DIYA"
- CONFIRMATION vs REMINDER_CONTROL: "cancel" alone → check history; if Munshi asked "Bhejun kya?" → CONFIRMATION; if there's a reminder context → REMINDER_CONTROL
- TASK vs FOLLOW_UP: TASK = user needs to DO something | FOLLOW_UP = user is noting someone ELSE owes/promised
- Very short messages ("haan", "ok", "nahi", "yes") after Munshi showed a draft → always CONFIRMATION

Latest message to classify: "{message}"

Respond ONLY with valid JSON on one line:
{{"intent": "INTENT_TYPE", "confidence": 0.0-1.0, "language": "en|hi|hinglish", "reasoning": "1 sentence"}}"""


async def intent_classifier_agent(state: MunshiState) -> MunshiState:
    """
    Classify intent and detect language using few-shot LLM classification.
    Uses temperature=0 for deterministic, reproducible results.
    """
    text = state.get("processed_text", "")
    if not text:
        state["intent"] = IntentType.UNKNOWN
        state["intent_confidence"] = 0.0
        state["language"] = state.get("language", "en")
        return state

    history = state.get("conversation_history") or "(no prior conversation)"
    prompt = INTENT_PROMPT.format(
        message=text,
        history=history,
        few_shot=FEW_SHOT_EXAMPLES,
    )

    # temperature=0 for deterministic output — critical for classification accuracy
    response = await call_llm(prompt, max_tokens=150, temperature=0)

    try:
        match = re.search(r'\{.*\}', response, re.DOTALL)
        if match:
            data = json.loads(match.group())
            intent_str = data.get("intent", "UNKNOWN").upper()
            state["intent"] = (
                IntentType(intent_str) if intent_str in IntentType.__members__
                else IntentType.UNKNOWN
            )
            state["intent_confidence"] = float(data.get("confidence", 0.5))

            # LLM-based language detection (replaces keyword detector)
            lang = data.get("language", "").lower()
            state["language"] = lang if lang in ("en", "hi", "hinglish") else "hinglish"
        else:
            state["intent"] = IntentType.UNKNOWN
            state["intent_confidence"] = 0.0
    except Exception as e:
        state["intent"] = IntentType.UNKNOWN
        state["intent_confidence"] = 0.0
        state["agent_errors"].append(f"intent_classifier error: {e}")

    return state
