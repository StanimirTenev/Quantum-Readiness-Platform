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


def test_update_task_status_raises_error_when_transition_skips_required_approval(tmp_path: Path) -> None:
    repo = WorkflowRepository(tmp_path / "workflow.db")
    task = repo.create_task(
        TaskCreate(
            title="Move cert rotation to execution",
            asset_name="payments-api",
            wave="wave_1",
            priority="critical",
            description="Execute certificate migration.",
            recommended_action="Submit and approve before execution.",
        )
    )

    try:
        repo.update_task_status(task.id, "in_progress")
        assert False, "Expected ValueError for invalid transition"
    except ValueError as exc:
        assert "Invalid task status transition" in str(exc)


def test_create_approval_raises_error_when_task_not_pending_approval(tmp_path: Path) -> None:
    repo = WorkflowRepository(tmp_path / "workflow.db")
    task = repo.create_task(
        TaskCreate(
            title="Approve key exchange upgrade",
            asset_name="vpn-gateway",
            wave="wave_2",
            priority="high",
            description="Need explicit approval state first.",
            recommended_action="Submit before approval.",
        )
    )

    try:
        repo.create_approval(task.id, "security-lead", "approved", "Proceed")
        assert False, "Expected ValueError when task is not pending approval"
    except ValueError as exc:
        assert "pending_approval" in str(exc)
