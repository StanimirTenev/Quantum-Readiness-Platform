from __future__ import annotations

from fastapi import FastAPI, HTTPException, status

from .models import ApprovalDecision, ApprovalRecord, Task, TaskCreate, TaskStatusUpdate
from .repository import WorkflowRepository

app = FastAPI(title="Workflow Service", version="0.1.0")
repository = WorkflowRepository()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "workflow-service"}


@app.post("/tasks", response_model=Task, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate) -> Task:
    return repository.create_task(payload)


@app.get("/tasks", response_model=list[Task])
def list_tasks() -> list[Task]:
    return repository.list_tasks()


@app.get("/tasks/{task_id}", response_model=Task)
def get_task(task_id: str) -> Task:
    task = repository.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.post("/tasks/{task_id}/submit", response_model=Task)
def submit_task(task_id: str) -> Task:
    task = repository.update_task_status(task_id, "pending_approval")
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.post("/tasks/{task_id}/status", response_model=Task)
def update_status(task_id: str, payload: TaskStatusUpdate) -> Task:
    task = repository.update_task_status(task_id, payload.status)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.post("/tasks/{task_id}/approve", response_model=ApprovalRecord)
def approve_task(task_id: str, payload: ApprovalDecision) -> ApprovalRecord:
    approval = repository.create_approval(task_id, payload.approver, payload.decision, payload.note)
    if approval is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return approval


@app.get("/approvals", response_model=list[ApprovalRecord])
def list_approvals(task_id: str | None = None) -> list[ApprovalRecord]:
    return repository.list_approvals(task_id=task_id)
