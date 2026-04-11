from app.state import MunshiState
from app.db.sqlite_client import get_pending_tasks

EMPTY_STATE = {
    "en": "🎉 No pending tasks right now!",
    "hi": "🎉 Abhi koi pending kaam nahi hai!",
    "hinglish": "🎉 Abhi koi pending kaam nahi hai!",
}


async def report_agent(state: MunshiState) -> MunshiState:
    """Generate a pending tasks summary for STATUS_QUERY intent."""
    phone = state["phone"]
    language = state.get("language", "en")

    tasks = await get_pending_tasks(phone, limit=5)

    if not tasks:
        state["final_response"] = EMPTY_STATE.get(language, EMPTY_STATE["en"])
        return state

    count = len(tasks)
    if language == "en":
        header = f"📋 You have {count} pending task(s):\n"
    else:
        header = f"📋 Aapke {count} pending kaam hain:\n"

    lines = []
    for i, task in enumerate(tasks, 1):
        desc = task["description"]
        contact = f" — {task['contact_name']}" if task.get("contact_name") else ""
        amount = f" (₹{int(task['amount'])})" if task.get("amount") else ""
        due = f" [due: {task['due_date']}]" if task.get("due_date") else ""
        lines.append(f"{i}.{contact}{amount} — {desc}{due}")

    state["status_report"] = header + "\n".join(lines)
    state["final_response"] = state["status_report"]
    return state
