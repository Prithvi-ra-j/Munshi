import logging
import uuid
from datetime import datetime
from typing import Optional
from app.models import WAHAWebhookPayload
from app.state import MunshiState
from app.agents.orchestrator import get_compiled_graph
from app.waha_client import send_text_message

# Keywords that trigger a conversation history reset
RESET_TRIGGERS = {"reset", "clear", "start over", "naya shuru", "bhool jao", "/reset", "/clear"}

# Message types from WhatsApp that carry no text and should be silently ignored
IGNORABLE_TYPES = {"reaction", "revoked", "ephemeralSetting", "call_log", "e2e_notification"}


async def handle_webhook(payload: WAHAWebhookPayload) -> None:
    """Process incoming WAHA webhook event through the LangGraph orchestrator."""
    logging.warning(f"MUNSHI RAW PAYLOAD: {payload.payload}")
    if payload.event != "message":
        return

    msg = payload.payload

    # ── Edge Case 1: Ignore messages sent BY the bot (prevents infinite loops) ──
    if msg.get("fromMe", False):
        return

    # ── Edge Case 2: Ignore group messages (JID ends with @g.us) ──
    raw_from: str = msg.get("from", "")
    if raw_from.endswith("@g.us"):
        return

    # ── Edge Case 3: Ignore empty/ignorable message types ──
    msg_type: str = msg.get("type", "chat")
    if msg_type in IGNORABLE_TYPES:
        return

    has_media: bool = msg.get("hasMedia", False)
    body: str = msg.get("body", "")
    is_audio: bool = msg_type in ("audio", "ptt") and has_media

    if not body and not is_audio:
        return

    # ── Phone extraction ──
    real_jid: str = msg.get("_data", {}).get("key", {}).get("remoteJidAlt", "")
    if real_jid:
        phone = real_jid.replace("@s.whatsapp.net", "").replace("@c.us", "")
    else:
        phone = raw_from.replace("@c.us", "").replace("@lid", "")

    if not phone:
        logging.warning("MUNSHI: Could not extract phone number, dropping message")
        return

    timestamp: str = str(msg.get("timestamp", datetime.utcnow().isoformat()))
    audio_url: Optional[str] = msg.get("mediaUrl") if is_audio else None

    graph = get_compiled_graph()
    config = {"configurable": {"thread_id": phone}}

    # ── Edge Case 4: Conversation reset command ──
    if body.strip().lower() in RESET_TRIGGERS:
        await send_text_message(phone, "✅ Memory cleared! Fresh start 🙏")
        clean_state: MunshiState = {
            "phone": phone, "raw_message": "", "message_type": "text",
            "audio_url": None, "timestamp": timestamp, "transcribed_text": None,
            "processed_text": "reset", "intent": None, "intent_confidence": None,
            "entities": {}, "contact_context": None, "tasks_created": [],
            "reminder_scheduled": None, "draft_reply": None, "status_report": None,
            "final_response": "✅ Memory cleared! Fresh start 🙏", "language": "en",
            "conversation_history": "", "last_entities": {},
            "onboarding_step": None, "pending_confirmation_id": None,
            "trace_id": str(uuid.uuid4()), "agent_errors": [],
        }
        try:
            await graph.ainvoke(clean_state, config=config)
        except Exception as e:
            logging.exception(f"MUNSHI: Reset invoke error for {phone}: {e}")
        return

    # ── Onboarding pre-check ──
    # Read onboarding_step from the checkpoint (if it exists) to see if user is mid-onboarding
    from app.db.sqlite_client import get_user
    from app.agents.onboarding_agent import handle_onboarding_turn

    user = await get_user(phone)
    onboarding_step = None

    try:
        state_snapshot = await graph.aget_state(config)
        if state_snapshot and state_snapshot.values:
            onboarding_step = state_snapshot.values.get("onboarding_step")
    except Exception:
        pass

    # New user (not in DB) OR user not yet onboarded OR mid-onboarding flow
    if user is None or not user.get("onboarded") or onboarding_step:
        await handle_onboarding_turn(phone, body, onboarding_step, graph, config)
        return  # Don't run main graph during onboarding

    # ── Build initial state for this turn ──
    # Cross-turn fields (conversation_history, last_entities, onboarding_step,
    # pending_confirmation_id, language) are intentionally NOT set here so the
    # checkpointer's restored values carry forward automatically.
    initial_state: MunshiState = {
        "phone": phone,
        "raw_message": body,
        "message_type": "audio" if is_audio else "text",
        "audio_url": audio_url,
        "timestamp": timestamp,
        "transcribed_text": None,
        "processed_text": body,
        "intent": None,
        "intent_confidence": None,
        "entities": {},
        "contact_context": None,
        "tasks_created": [],
        "reminder_scheduled": None,
        "draft_reply": None,
        "status_report": None,
        "final_response": "",
        "trace_id": str(uuid.uuid4()),
        "agent_errors": [],
    }

    try:
        await graph.ainvoke(initial_state, config=config)
    except Exception as e:
        logging.exception(f"MUNSHI: Graph error for {phone}: {e}")
        await send_text_message(phone, "Kuch technical issue hai, thodi der mein try karein.")
