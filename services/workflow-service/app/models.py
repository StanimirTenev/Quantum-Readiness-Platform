from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field

TaskStatus = Literal["draft", "pending_approval", "approved", "rejected", "in_progress", "completed"]
TaskPriority = Literal["low", "medium", "high", "critical"]


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    asset_name: str = Field(..., min_length=1, max_length=255)
    wave: Literal["wave_1", "wave_2", "wave_3"]
    priority: TaskPriority
    description: str = Field(..., min_length=3)
    recommended_action: Optional[str] = None


class Task(TaskCreate):
    id: str
    status: TaskStatus


class TaskStatusUpdate(BaseModel):
    status: TaskStatus


class ApprovalDecision(BaseModel):
    approver: str = Field(..., min_length=1, max_length=255)
    decision: Literal["approved", "rejected"]
    note: Optional[str] = None


class ApprovalRecord(BaseModel):
    task_id: str
    approver: str
    decision: Literal["approved", "rejected"]
    note: Optional[str] = None
