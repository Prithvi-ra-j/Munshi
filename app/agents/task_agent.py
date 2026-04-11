from app.state import MunshiState
from app.db.sqlite_client import insert_task

CONFIRMATIONS = {
    "en": "✅ Got it — {action}",
    "hi": "✅ Note kar liya — {action}",
    "hinglish": "✅ Note kar liya — {action}",
}


async def task_agent(state: MunshiState) -> MunshiState:
    """Create tasks in SQLite for TASK, FOLLOW_UP, and STORE_INFO intents."""
    entities = state.get("entities", {})
    action = entities.get("action") or state.get("processed_text", "")[:100]
    contact_name = entities.get("names", [None])[0] if entities.get("names") else None
    amounts = entities.get("amounts", [])
    amount = float(amounts[0]) if amounts else None
    dates = entities.get("dates", [])
    due_date = dates[0] if dates else None
    language = state.get("language", "en")

    task_id = await insert_task(
        user_phone=state["phone"],
        description=action,
        contact_name=contact_name,
        amount=amount,
        due_date=due_date,
        intent_type=state.get("intent", "TASK"),
    )

    state["tasks_created"] = state.get("tasks_created", []) + [task_id]

    template = CONFIRMATIONS.get(language, CONFIRMATIONS["en"])
    state["final_response"] = template.format(action=action)

    return state
