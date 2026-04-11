import aiosqlite
import os
from typing import Optional, List
from datetime import datetime

DB_PATH = os.getenv("DATABASE_URL", "sqlite:///./munshi.db").replace("sqlite:///", "")


async def init_db() -> None:
    """Initialize SQLite database with required tables."""
    async with aiosqlite.connect(DB_PATH) as db:
        # --- Original tables ---
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_phone TEXT NOT NULL,
                description TEXT NOT NULL,
                contact_name TEXT,
                amount REAL,
                due_date TEXT,
                status TEXT DEFAULT 'pending',
                intent_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER,
                user_phone TEXT NOT NULL,
                message TEXT NOT NULL,
                scheduled_at TIMESTAMP NOT NULL,
                sent INTEGER DEFAULT 0,
                FOREIGN KEY(task_id) REFERENCES tasks(id)
            )
        """)
        # --- New: user profiles for onboarding ---
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                phone TEXT PRIMARY KEY,
                name TEXT,
                business_type TEXT,
                language_pref TEXT DEFAULT 'en',
                onboarded INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # --- New: pending confirmations for "Bhejun kya?" flow ---
        await db.execute("""
            CREATE TABLE IF NOT EXISTS pending_confirmations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_phone TEXT NOT NULL,
                confirmation_type TEXT NOT NULL,
                draft TEXT NOT NULL,
                contact_name TEXT,
                contact_phone TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()


# ─── Task CRUD ────────────────────────────────────────────────────────────────

async def insert_task(
    user_phone: str,
    description: str,
    contact_name: Optional[str] = None,
    amount: Optional[float] = None,
    due_date: Optional[str] = None,
    intent_type: Optional[str] = None,
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO tasks (user_phone, description, contact_name, amount, due_date, intent_type)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_phone, description, contact_name, amount, due_date, intent_type),
        )
        await db.commit()
        return cursor.lastrowid


async def get_pending_tasks(user_phone: str, limit: int = 5) -> List[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT * FROM tasks WHERE user_phone = ? AND status = 'pending'
               ORDER BY created_at DESC LIMIT ?""",
            (user_phone, limit),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_all_pending_tasks(user_phone: str) -> List[dict]:
    """Return ALL pending tasks for a user — used for fuzzy matching in task_completion_agent."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM tasks WHERE user_phone = ? AND status = 'pending' ORDER BY created_at DESC",
            (user_phone,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def update_task_status(task_id: int, status: str) -> None:
    """Mark a task as 'done', 'cancelled', or any other status."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE tasks SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, task_id),
        )
        await db.commit()


# ─── Reminders CRUD ───────────────────────────────────────────────────────────

async def insert_reminder(
    task_id: Optional[int],
    user_phone: str,
    message: str,
    scheduled_at: datetime,
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO reminders (task_id, user_phone, message, scheduled_at)
               VALUES (?, ?, ?, ?)""",
            (task_id, user_phone, message, scheduled_at.isoformat()),
        )
        await db.commit()
        return cursor.lastrowid


async def get_pending_reminders() -> List[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM reminders WHERE sent = 0 ORDER BY scheduled_at ASC"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_latest_reminder_for_user(user_phone: str) -> Optional[dict]:
    """Get the most recently scheduled unsent reminder for this user."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT * FROM reminders WHERE user_phone = ? AND sent = 0
               ORDER BY scheduled_at ASC LIMIT 1""",
            (user_phone,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_reminders_for_task(task_id: int) -> List[dict]:
    """Get all unsent reminders linked to a task (for cancellation on task completion)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM reminders WHERE task_id = ? AND sent = 0",
            (task_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def mark_reminder_sent(reminder_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE reminders SET sent = 1 WHERE id = ?", (reminder_id,))
        await db.commit()


async def delete_reminder(reminder_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
        await db.commit()


async def update_reminder_time(reminder_id: int, new_scheduled_at: datetime) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE reminders SET scheduled_at = ? WHERE id = ?",
            (new_scheduled_at.isoformat(), reminder_id),
        )
        await db.commit()


# ─── Users / Onboarding ───────────────────────────────────────────────────────

async def get_user(phone: str) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE phone = ?", (phone,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def upsert_user(
    phone: str,
    name: Optional[str] = None,
    business_type: Optional[str] = None,
    language_pref: Optional[str] = None,
    onboarded: bool = False,
) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO users (phone, name, business_type, language_pref, onboarded)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(phone) DO UPDATE SET
                   name = COALESCE(excluded.name, users.name),
                   business_type = COALESCE(excluded.business_type, users.business_type),
                   language_pref = COALESCE(excluded.language_pref, users.language_pref),
                   onboarded = excluded.onboarded""",
            (phone, name, business_type, language_pref or "en", 1 if onboarded else 0),
        )
        await db.commit()


# ─── Pending Confirmations ────────────────────────────────────────────────────

async def save_confirmation(
    user_phone: str,
    draft: str,
    contact_name: Optional[str] = None,
    contact_phone: Optional[str] = None,
) -> int:
    """Save a pending confirmation (draft waiting for haan/nahi). Replaces any existing one."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Delete any previous pending confirmation for this user first
        await db.execute(
            "DELETE FROM pending_confirmations WHERE user_phone = ?", (user_phone,)
        )
        cursor = await db.execute(
            """INSERT INTO pending_confirmations
               (user_phone, confirmation_type, draft, contact_name, contact_phone)
               VALUES (?, 'send_reply', ?, ?, ?)""",
            (user_phone, draft, contact_name, contact_phone),
        )
        await db.commit()
        return cursor.lastrowid


async def get_pending_confirmation(user_phone: str) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM pending_confirmations WHERE user_phone = ? ORDER BY created_at DESC LIMIT 1",
            (user_phone,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def delete_confirmation(confirmation_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM pending_confirmations WHERE id = ?", (confirmation_id,))
        await db.commit()
