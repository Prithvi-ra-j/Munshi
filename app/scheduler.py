from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from datetime import datetime
from typing import Optional

_scheduler: Optional[AsyncIOScheduler] = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


def schedule_reminder(job_id: str, run_at: datetime, phone: str, message: str) -> None:
    """Schedule a one-time reminder job."""
    scheduler = get_scheduler()

    async def send_reminder():
        from app.waha_client import send_text_message
        from app.db.sqlite_client import mark_reminder_sent
        await send_text_message(phone, f"⏰ Reminder: {message}")
        # Extract reminder_id from job_id
        try:
            reminder_id = int(job_id.split("_")[-1])
            await mark_reminder_sent(reminder_id)
        except Exception:
            pass

    scheduler.add_job(
        send_reminder,
        trigger=DateTrigger(run_date=run_at),
        id=job_id,
        replace_existing=True,
    )


def cancel_reminder(job_id: str) -> bool:
    """Remove a scheduled reminder job. Returns True if found and removed."""
    scheduler = get_scheduler()
    try:
        scheduler.remove_job(job_id)
        return True
    except Exception:
        return False


def reschedule_reminder(job_id: str, new_run_at: datetime) -> bool:
    """Reschedule an existing reminder job to a new time. Returns True if successful."""
    scheduler = get_scheduler()
    try:
        scheduler.reschedule_job(job_id, trigger=DateTrigger(run_date=new_run_at))
        return True
    except Exception:
        return False


async def load_pending_reminders() -> None:
    """On startup, reload all unsent reminders from SQLite."""
    from app.db.sqlite_client import get_pending_reminders
    reminders = await get_pending_reminders()
    now = datetime.utcnow()
    for r in reminders:
        try:
            scheduled_at = datetime.fromisoformat(r["scheduled_at"])
            if scheduled_at > now:
                schedule_reminder(
                    job_id=f"reminder_{r['id']}",
                    run_at=scheduled_at,
                    phone=r["user_phone"],
                    message=r["message"],
                )
        except Exception:
            pass
