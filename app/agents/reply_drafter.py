from app.state import MunshiState
from app.llm_client import call_llm
from app.db.sqlite_client import save_confirmation

REPLY_PROMPT = """You are Munshi, drafting a WhatsApp reply for an Indian business owner.

Recent conversation with this user (for tone and context):
{history}

Context about {contact_name}: {contact_context}
User's latest message: {user_message}
User's language: {language}

Write a brief, professional WhatsApp reply in the SAME language as the user's message.
Keep it under 3 sentences. Sound natural and human, not robotic.
Do NOT contradict anything in the conversation history above.
Do NOT add emojis unless the user typically uses them."""

CLARIFY = {
    "en": "Could you clarify what you'd like me to help with?",
    "hi": "Kya aap thoda aur batayenge ki aap kya chahte hain?",
    "hinglish": "Kya aap thoda aur batayenge ki aap kya chahte hain?",
}

CONFIRM_PROMPT = {
    "en": "📝 Draft for *{contact_name}*:\n\n{draft}\n\n*Bhejun kya? (Reply haan/nahi)*",
    "hi": "📝 *{contact_name}* ke liye draft:\n\n{draft}\n\n*Bhejun kya? (haan/nahi likho)*",
    "hinglish": "📝 *{contact_name}* ke liye draft:\n\n{draft}\n\n*Bhejun kya? (haan/nahi likho)*",
}


async def reply_drafter_agent(state: MunshiState) -> MunshiState:
    """Draft a WhatsApp reply or ask a clarifying question for UNKNOWN intent.
    After drafting, saves to pending_confirmations and asks user 'Bhejun kya?'
    """
    from app.models import IntentType

    intent = state.get("intent")
    language = state.get("language", "en")

    if intent == IntentType.UNKNOWN:
        state["final_response"] = CLARIFY.get(language, CLARIFY["en"])
        return state

    entities = state.get("entities", {})
    names = entities.get("names", [])

    # Resolve pronoun if no name in current turn — fall back to last_entities
    if not names:
        last = state.get("last_entities") or {}
        names = last.get("names", [])

    contact_name = names[0] if names else "the contact"
    contact_context = state.get("contact_context") or "No prior context available."
    history = state.get("conversation_history") or "(no prior conversation)"

    prompt = REPLY_PROMPT.format(
        contact_name=contact_name,
        contact_context=contact_context,
        user_message=state.get("processed_text", ""),
        language=language,
        history=history,
    )

    draft = await call_llm(prompt, max_tokens=200)
    state["draft_reply"] = draft

    # Save draft to pending_confirmations and ask for confirmation
    conf_id = await save_confirmation(
        user_phone=state["phone"],
        draft=draft,
        contact_name=contact_name if contact_name != "the contact" else None,
    )
    state["pending_confirmation_id"] = conf_id

    template = CONFIRM_PROMPT.get(language, CONFIRM_PROMPT["hinglish"])
    state["final_response"] = template.format(
        contact_name=contact_name,
        draft=draft,
    )
    return state
