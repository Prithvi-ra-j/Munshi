from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum


class IntentType(str, Enum):
    TASK = "TASK"
    FOLLOW_UP = "FOLLOW_UP"
    REPLY_DRAFT = "REPLY_DRAFT"
    STATUS_QUERY = "STATUS_QUERY"
    STORE_INFO = "STORE_INFO"
    TASK_COMPLETE = "TASK_COMPLETE"        # "Ravi ne pay kar diya"
    REMINDER_CONTROL = "REMINDER_CONTROL"  # "snooze" / "cancel reminder"
    CONFIRMATION = "CONFIRMATION"          # "haan" / "nahi" responses
    UNKNOWN = "UNKNOWN"


class WAHAWebhookPayload(BaseModel):
    event: str
    session: str
    payload: dict


class TaskCreate(BaseModel):
    user_phone: str
    description: str
    contact_name: Optional[str] = None
    amount: Optional[float] = None
    due_date: Optional[str] = None
    intent_type: str


class TaskResponse(BaseModel):
    id: int
    description: str
    contact_name: Optional[str]
    due_date: Optional[str]
    status: str
    created_at: datetime


class EvalResult(BaseModel):
    intent_accuracy: float
    entity_precision: float
    p50_latency_ms: float
    p95_latency_ms: float
    total_messages: int
