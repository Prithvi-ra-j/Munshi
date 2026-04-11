import re
from datetime import datetime, timedelta
from app.state import MunshiState
from app.db.sqlite_client import get_latest_reminder_for_user, delete_reminder, update_reminder_time
from app.scheduler import cancel_reminder, reschedule_reminder

# Keywords for action detection
CANCEL_WORDS = {"cancel", "hatao", "band karo", "remove", "delete", "mat bhejo", "cancel karo"}
SNOOZE_WORDS = {"snooze", "baad mein", "later", "thodi der baad", "remind later", "1 hour", "1 ghante"}


def _parse_snooze_duration(text: str) -> timedelta:
    """
    Parse natural language snooze duration from message text.
    Returns a timedelta. Default is 1 hour if nothing is recognised.
    """
    text_lower = text.lower()

    # Look for patterns like "2 hours", "30 minutes", "1 din"
    hour_match = re.search(r'(\d+)\s*(hour|hr|ghante|ghanta)', text_lower)
    min_match = re.search(r'(\d+)\s*(minute|min|mins)', text_lower)
    day_match = re.search(r'(\d+)\s*(day|din)', text_lower)

    if hour_match:
        return timedelta(hours=int(hour_match.group(1)))
    if min_match:
        return timedelta(minutes=int(min_match.group(1)))
    if day_match:
        return timedelta(days=int(day_match.group(1)))

    # Natural language fallbacks
    if "kal" in text_lower or "tomorrow" in text_lower:
        return timedelta(days=1)
    if "shaam" in text_lower or "evening" in text_lower:
        now = datetime.utcnow()
        evening = now.replace(hour=14, minute=0, second=0)  # 7:30pm IST = 14:00 UTC
        if evening > now:
            return evening - now
        return timedelta(hours=5)

    # Default: 1 hour
    return timedelta(hours=1)


async def reminder_control_agent(state: MunshiState) -> MunshiState:
    """
    Handles REMINDER_CONTROL intent (snooze / cancel a reminder).
    Finds the user's most imminent pending reminder and acts on it.
    """
    phone = state["phone"]
    language = state.get("language", "en")
    text = state.get("processed_text", "").lower()

    reminder = await get_latest_reminder_for_user(phone)
    if not reminder:
        msgs = {
            "en": "No active reminders found to modify.",
            "hi": "Koi active reminder nahi mila.",
            "hinglish": "Koi active reminder nahi mila.",
        }
        state["final_response"] = msgs.get(language, msgs["en"])
        return state

    reminder_id = reminder["id"]
    job_id = f"reminder_{reminder_id}"

    # Determine action: cancel or snooze
    is_cancel = any(w in text for w in CANCEL_WORDS)

    if is_cancel:
        cancel_reminder(job_id)
        await delete_reminder(reminder_id)
        msgs = {
            "en": f"✅ Reminder cancelled: \"{reminder['message']}\"",
            "hi": f"✅ Reminder cancel kar diya: \"{reminder['message']}\"",
            "hinglish": f"✅ Reminder cancel kar diya: \"{reminder['message']}\"",
        }
        state["final_response"] = msgs.get(language, msgs["en"])
    else:
        # Snooze: compute new time
        delta = _parse_snooze_duration(state.get("processed_text", ""))
        new_time = datetime.utcnow() + delta

        success = reschedule_reminder(job_id, new_time)
        if success:
            await update_reminder_time(reminder_id, new_time)
            # Format delta for display
            hours = int(delta.total_seconds() // 3600)
            mins = int((delta.total_seconds() % 3600) // 60)
            if hours:
                duration_str = f"{hours} ghante" if language != "en" else f"{hours} hour(s)"
            else:
                duration_str = f"{mins} minute" if language != "en" else f"{mins} minute(s)"

            msgs = {
                "en": f"⏰ Snoozed for {duration_str}: \"{reminder['message']}\"",
                "hi": f"⏰ {duration_str} ke liye snooze kar diya: \"{reminder['message']}\"",
                "hinglish": f"⏰ {duration_str} ke liye snooze kar diya: \"{reminder['message']}\"",
            }
            state["final_response"] = msgs.get(language, msgs["en"])
        else:
            # Job not found in scheduler (e.g. after server restart it wasn't reloaded)
            # Re-schedule it fresh
            from app.scheduler import schedule_reminder
            schedule_reminder(job_id, new_time, phone, reminder["message"])
            await update_reminder_time(reminder_id, new_time)
            state["final_response"] = f"⏰ Reminder rescheduled: \"{reminder['message']}\""

    return state
