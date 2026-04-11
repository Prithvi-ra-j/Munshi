import asyncio
import aiosqlite
from contextlib import asynccontextmanager
from typing import AsyncIterator
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from app.models import WAHAWebhookPayload, TaskResponse, EvalResult
from app.db.sqlite_client import init_db, get_pending_tasks
from app.waha_client import get_session_status
from app.scheduler import get_scheduler, load_pending_reminders
from app.agents.orchestrator import init_graph


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # --- Startup ---
    await init_db()
    await load_pending_reminders()

    # Initialize AsyncSqliteSaver for conversation checkpointing.
    # We open a dedicated aiosqlite connection that lives for the full app lifetime.
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
    import os
    checkpoint_db = os.getenv("CHECKPOINT_DB", "./checkpoints.sqlite")
    _conn = await aiosqlite.connect(checkpoint_db)
    checkpointer = AsyncSqliteSaver(_conn)
    await checkpointer.setup()        # Creates LangGraph checkpoint tables if missing

    # Compile the LangGraph orchestrator with the checkpointer baked in
    init_graph(checkpointer=checkpointer)

    scheduler = get_scheduler()
    scheduler.start()

    yield

    # --- Shutdown ---
    scheduler.shutdown(wait=False)
    await _conn.close()              # Clean up the checkpoint DB connection


app = FastAPI(title="Munshi API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    waha_status = await get_session_status()
    try:
        await init_db()
        db_status = "connected"
    except Exception:
        db_status = "error"

    scheduler = get_scheduler()
    scheduler_status = "running" if scheduler.running else "stopped"

    return {
        "status": "ok",
        "waha": waha_status or "disconnected",
        "db": db_status,
        "scheduler": scheduler_status,
        "version": "1.0.0",
    }


@app.post("/webhook", status_code=200)
async def webhook(payload: WAHAWebhookPayload, background_tasks: BackgroundTasks) -> dict:
    from app.webhook import handle_webhook
    background_tasks.add_task(handle_webhook, payload)
    return {"status": "queued"}


@app.get("/tasks/{phone}")
async def get_tasks(phone: str) -> dict:
    tasks = await get_pending_tasks(phone, limit=20)
    return {
        "phone": phone,
        "pending_count": len(tasks),
        "tasks": tasks,
    }


@app.post("/eval/run")
async def run_eval() -> dict:
    from eval.run_eval import run_evaluation
    results = await run_evaluation()
    return {"results": results}

