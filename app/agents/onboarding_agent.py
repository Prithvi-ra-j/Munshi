"""
Onboarding agent — handles first-time users via a 3-step state machine.

Called from webhook.py BEFORE the main LangGraph graph is invoked.
Uses graph.aget_state() to read the current onboarding_step from the checkpoint,
and graph.aupdate_state() to advance the step without running the full pipeline.
"""
from app.db.sqlite_client import get_user, upsert_user
from app.waha_client import send_text_message

WELCOME_MSG = """👋 Namaste! Main *Munshi* hoon — aapka WhatsApp business assistant.

Main aapke liye:
• 📝 Tasks aur reminders track kar sakta hoon
• 💰 Pending payments yaad rakh sakta hoon  
• 📨 WhatsApp replies draft kar sakta hoon
• 📋 Daily summary bhej sakta hoon

Shuru karte hain! Aapka naam kya hai?"""

WELCOME_EN = """👋 Hi! I'm *Munshi* — your WhatsApp business assistant.

I can help you:
• 📝 Track tasks and reminders
• 💰 Remember pending payments
• 📨 Draft WhatsApp replies
• 📋 Send daily summaries

Let's get started! What's your name?"""

READY_MSG = {
    "en": "🎉 All set, {name}! You can now send me tasks, payments, or just say 'kya pending hai?' to see your pending items. I'm here 24/7.",
    "hi": "🎉 Sab set hai, {name} ji! Ab aap mujhe tasks, payments bhej sakte ho ya 'kya pending hai?' bol ke apna status dekh sakte ho.",
    "hinglish": "🎉 Sab set hai, {name} ji! Ab aap mujhe tasks, payments bhej sakte ho ya 'kya pending hai?' bol ke apna status dekh sakte ho.",
}


async def handle_onboarding_turn(
    phone: str,
    body: str,
    onboarding_step: str | None,
    graph,
    config: dict,
) -> None:
    """
    Process one turn of the onboarding flow.
    Sends WAHA messages directly and updates checkpoint state via graph.aupdate_state().
    """
    if onboarding_step is None:
        # First ever message — greet and ask for name
        await upsert_user(phone, onboarded=False)
        # Detect language from greeting to choose message language
        greet_lower = body.lower()
        if any(w in greet_lower for w in ["hi", "hello", "hey", "namaste", "haha"]):
            msg = WELCOME_MSG
        else:
            msg = WELCOME_MSG  # default to Hinglish welcome

        await send_text_message(phone, msg)
        await graph.aupdate_state(config, {"onboarding_step": "ask_name"})
        return

    if onboarding_step == "ask_name":
        name = body.strip()[:50]  # cap at 50 chars
        await upsert_user(phone, name=name)
        await send_text_message(
            phone,
            f"Nice to meet you, *{name}* ji! 🙏\n\nAapka kaam kya hai? (e.g., kapde ka business, catering, electronics, real estate)"
        )
        await graph.aupdate_state(config, {"onboarding_step": "ask_business"})
        return

    if onboarding_step == "ask_business":
        business = body.strip()[:100]
        await upsert_user(phone, business_type=business)
        await send_text_message(
            phone,
            "Perfect! 👍\n\nMain aapko kaunsi language mein reply karun?\n1️⃣ Hinglish (mix of Hindi + English) — recommended\n2️⃣ Hindi\n3️⃣ English\n\n(Reply 1, 2, or 3)"
        )
        await graph.aupdate_state(config, {"onboarding_step": "ask_language"})
        return

    if onboarding_step == "ask_language":
        lang_map = {
            "1": "hinglish", "hinglish": "hinglish",
            "2": "hi", "hindi": "hi",
            "3": "en", "english": "en",
        }
        chosen = lang_map.get(body.strip().lower(), "hinglish")
        await upsert_user(phone, language_pref=chosen, onboarded=True)

        # Get name for welcome message
        user = await get_user(phone)
        name = (user or {}).get("name", "aap")
        msg = READY_MSG.get(chosen, READY_MSG["hinglish"]).format(name=name)
        await send_text_message(phone, msg)

        # Clear onboarding_step — user is fully onboarded
        await graph.aupdate_state(config, {
            "onboarding_step": None,
            "language": chosen,
        })
        return
