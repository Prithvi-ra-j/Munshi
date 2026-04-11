from datetime import datetime, timedelta
from app.state import MunshiState
from app.db.sqlite_client import insert_reminder
from app.scheduler import schedule_reminder


async def reminder_agent(state: MunshiState) -> MunshiState:
    """Schedule reminders for tasks that have a due date."""
    tasks_created = state.get("tasks_created", [])
    entities = state.get("entities", {})
    dates = entities.get("dates", [])
    action = entities.get("action") or state.get("processed_text", "")[:100]
    phone = state["phone"]

    if not tasks_created or not dates:
        return state

    task_id = tasks_created[-1]
    due_date_str = dates[0]

    try:
        # Try to parse the date
        due_dt = datetime.fromisoformat(due_date_str)
    except ValueError:
        try:
            due_dt = datetime.strptime(due_date_str, "%Y-%m-%d")
        except ValueError:
            return state

    # Schedule reminder 1 hour before due date
    remind_at = due_dt - timedelta(hours=1)
    if remind_at < datetime.utcnow():
        remind_at = due_dt  # fallback to exact time if already past

    reminder_id = await insert_reminder(
        task_id=task_id,
        user_phone=phone,
        message=action,
        scheduled_at=remind_at,
    )

    schedule_reminder(
        job_id=f"reminder_{reminder_id}",
        run_at=remind_at,
        phone=phone,
        message=action,
    )

    state["reminder_scheduled"] = remind_at.isoformat()
    return state
