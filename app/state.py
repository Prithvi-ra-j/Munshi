from typing import TypedDict, Optional, List
from app.models import IntentType


class MunshiState(TypedDict):
    # Input
    phone: str
    raw_message: str
    message_type: str          # "text" | "audio" | "image"
    audio_url: Optional[str]
    timestamp: str

    # Processing
    transcribed_text: Optional[str]
    processed_text: str
    intent: Optional[IntentType]
    intent_confidence: Optional[float]
    entities: dict             # {names: [], dates: [], amounts: [], action: ""}
    contact_context: Optional[str]

    # Output
    tasks_created: List[int]
    reminder_scheduled: Optional[str]
    draft_reply: Optional[str]
    status_report: Optional[str]
    final_response: str
    language: str              # "en" | "hi" | "hinglish"

    # Cross-turn memory (persisted via LangGraph AsyncSqliteSaver checkpointer)
    # NOTE: These are intentionally NOT set in initial_state in webhook.py so the
    # checkpointer's restored values are used. On the very first message (no checkpoint),
    # they will simply be absent from the dict — all agents use .get() with safe defaults.
    conversation_history: Optional[str]   # Formatted string of last ~6 turns
    last_entities: Optional[dict]         # Entities from the previous turn for pronoun resolution
    onboarding_step: Optional[str]        # None | 'ask_name' | 'ask_business' | 'ask_language'
    pending_confirmation_id: Optional[int] # DB id of pending "Bhejun kya?" confirmation

    # Observability
    trace_id: str
    agent_errors: List[str]
