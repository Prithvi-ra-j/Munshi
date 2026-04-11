#!/bin/bash
set -e

# Initialize DB and start server
python -c "import asyncio; from app.db.sqlite_client import init_db; asyncio.run(init_db())"

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
