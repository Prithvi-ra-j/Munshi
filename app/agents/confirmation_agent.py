from app.state import MunshiState
from app.db.sqlite_client import get_pending_confirmation, delete_confirmation

# Words that mean "yes, send it"
YES_WORDS = {"haan", "ha", "yes", "ok", "okay", "send", "bhej do", "bhejo", "kar do", "sure", "han"}
# Words that mean "no, don't send"
NO_WORDS = {"nahi", "no", "nope", "cancel", "mat bhejo", "mat karo", "ruk", "chod do", "band karo"}


async def confirmation_agent(state: MunshiState) -> MunshiState:
    """
    Handles CONFIRMATION intent — user responds haan/nahi to a pending 'Bhejun kya?' prompt.

    Option 1 behavior (user choice): Munshi sends the formatted draft back to the
    USER to forward manually. It does NOT send directly to the contact.
    """
    phone = state["phone"]
    language = state.get("language", "en")
    text = state.get("processed_text", "").lower().strip()

    confirmation = await get_pending_confirmation(phone)

    if not confirmation:
        msgs = {
            "en": "No pending draft found. Send a new reply request first.",
            "hi": "Koi pending draft nahi hai. Pehle draft banwao.",
            "hinglish": "Koi pending draft nahi hai. Pehle draft banwao.",
        }
        state["final_response"] = msgs.get(language, msgs["en"])
        return state

    user_said_yes = any(w in text.split() for w in YES_WORDS) or any(w in text for w in YES_WORDS)
    user_said_no = any(w in text.split() for w in NO_WORDS) or any(w in text for w in NO_WORDS)

    if user_said_no and not user_said_yes:
        await delete_confirmation(confirmation["id"])
        msgs = {
            "en": "Okay, draft cancelled. 👍",
            "hi": "Theek hai, draft cancel kar diya. 👍",
            "hinglish": "Theek hai, draft cancel kar diya. 👍",
        }
        state["final_response"] = msgs.get(language, msgs["en"])
        # Clear pending confirmation from state
        state["pending_confirmation_id"] = None
        return state

    if user_said_yes:
        draft = confirmation["draft"]
        contact_name = confirmation.get("contact_name") or "the contact"
        await delete_confirmation(confirmation["id"])

        # Option 1: Send formatted draft back to user for manual forwarding
        msgs = {
            "en": f"📋 Forward this to *{contact_name}*:\n\n{draft}",
            "hi": f"📋 Yeh message *{contact_name}* ko forward karo:\n\n{draft}",
            "hinglish": f"📋 Yeh message *{contact_name}* ko forward karo:\n\n{draft}",
        }
        state["final_response"] = msgs.get(language, msgs["en"])
        state["pending_confirmation_id"] = None
        return state

    # Ambiguous response — ask again
    state["final_response"] = "Haan ya nahi? (Reply 'haan' to confirm, 'nahi' to cancel)"
    return state
