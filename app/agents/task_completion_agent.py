from app.state import MunshiState
from app.db.sqlite_client import get_all_pending_tasks, update_task_status, get_reminders_for_task, delete_reminder
from app.scheduler import cancel_reminder

DONE_MSGS = {
    "en": "✅ Marked as done: {tasks}\n{reminder_note}",
    "hi": "✅ Done kar diya: {tasks}\n{reminder_note}",
    "hinglish": "✅ Done kar diya: {tasks}\n{reminder_note}",
}
NO_MATCH_MSGS = {
    "en": "Hmm, I couldn't find a pending task for '{name}'. Type 'kya pending hai?' to see all tasks.",
    "hi": "'{name}' ke naam pe koi pending task nahi mila.",
    "hinglish": "'{name}' ke naam pe koi pending task nahi mila.",
}


def _fuzzy_match(extracted: str, task_contact: str) -> bool:
    """
    Lightweight fuzzy match without external libraries.
    Returns True if the extracted name meaningfully overlaps with the task contact.
    Strategy:
    - Normalize both strings (lowercase, strip honorifics like 'ji', 'bhai', 'didi')
    - Check if one is a substring of the other
    - Check if any word in extracted appears in task_contact
    """
    HONORIFICS = {" ji", " bhai", " didi", " sir", " madam", " seth", " sahab"}

    def normalize(s: str) -> str:
        s = s.lower().strip()
        for h in HONORIFICS:
            s = s.replace(h, "")
        return s.strip()

    ext = normalize(extracted)
    tct = normalize(task_contact)

    if not ext or not tct:
        return False

    # Substring match (Ravi ↔ Ravi Sharma, Sharma ji ↔ Sharma)
    if ext in tct or tct in ext:
        return True

    # Word-level match — at least one word overlapping
    ext_words = set(ext.split())
    tct_words = set(tct.split())
    return bool(ext_words & tct_words)


async def task_completion_agent(state: MunshiState) -> MunshiState:
    """
    Handles TASK_COMPLETE intent.
    Fuzzy-matches the contact name to pending tasks, marks them done,
    and cancels any linked APScheduler reminders.
    """
    entities = state.get("entities", {})
    names = entities.get("names", [])

    # Fall back to last_entities if no name extracted in current turn
    if not names:
        last = state.get("last_entities") or {}
        names = last.get("names", [])

    language = state.get("language", "en")
    phone = state["phone"]

    if not names:
        state["final_response"] = NO_MATCH_MSGS.get(language, NO_MATCH_MSGS["en"]).format(name="?")
        return state

    contact_name = names[0]
    all_tasks = await get_all_pending_tasks(phone)

    matched = [t for t in all_tasks if t.get("contact_name") and _fuzzy_match(contact_name, t["contact_name"])]

    if not matched:
        state["final_response"] = NO_MATCH_MSGS.get(language, NO_MATCH_MSGS["en"]).format(name=contact_name)
        return state

    # Mark all matched tasks as done
    for task in matched:
        await update_task_status(task["id"], "done")

        # Cancel linked reminders in APScheduler + DB
        reminders = await get_reminders_for_task(task["id"])
        for reminder in reminders:
            cancel_reminder(f"reminder_{reminder['id']}")
            await delete_reminder(reminder["id"])

    # Build response
    task_lines = []
    for t in matched:
        line = t["description"]
        if t.get("amount"):
            line += f" (₹{int(t['amount'])})"
        task_lines.append(line)

    reminder_note = "⏰ Linked reminder(s) cancelled too." if any(True for t in matched) else ""
    template = DONE_MSGS.get(language, DONE_MSGS["en"])
    state["final_response"] = template.format(
        tasks="\n".join(f"• {l}" for l in task_lines),
        reminder_note=reminder_note,
    ).strip()

    return state
