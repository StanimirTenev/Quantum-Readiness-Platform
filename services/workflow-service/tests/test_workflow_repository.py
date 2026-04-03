from pathlib import Path

from app.models import TaskCreate
from app.repository import WorkflowRepository


def test_workflow_repository(tmp_path: Path) -> None:
    repo = WorkflowRepository(tmp_path / "workflow.db")

    payload = TaskCreate(
        title="Review google endpoint",
        asset_name="google.com:443",
        wave="wave_1",
        priority="high",
        description="Review TLS configuration and migration path.",
        recommended_action="Review TLS configuration, certificate algorithms, and PQC migration path.",
    )

    task = repo.create_task(payload)
    assert task.id
    assert task.status == "draft"

    duplicate = repo.create_task(payload)
    assert duplicate.id == task.id

    submitted = repo.update_task_status(task.id, "pending_approval")
    assert submitted is not None
    assert submitted.status == "pending_approval"

    approval = repo.create_approval(task.id, "security-lead", "approved", "Proceed")
    assert approval is not None
    assert approval.decision == "approved"

    fetched = repo.get_task(task.id)
    assert fetched is not None
    assert fetched.status == "approved"

    approvals = repo.list_approvals(task.id)
    assert len(approvals) == 1
