import importlib
from pathlib import Path

from app.models import TaskCreate
from app.repository import WorkflowRepository


def test_default_db_path_honors_workflow_db_path_env(tmp_path: Path, monkeypatch) -> None:
    custom = tmp_path / "env-workflow.db"
    monkeypatch.setenv("WORKFLOW_DB_PATH", str(custom))

    import app.repository as repository_module

    reloaded = importlib.reload(repository_module)
    try:
        assert reloaded.DEFAULT_DB_PATH == custom
        repo = reloaded.WorkflowRepository()
        repo.create_task(TaskCreate(
            title="env db check",
            asset_name="env-db-host",
            wave="wave_1",
            priority="high",
            description="env db check description",
            recommended_action="env db check action",
            requested_by="test",
        ))
        assert custom.exists()
    finally:
        monkeypatch.delenv("WORKFLOW_DB_PATH", raising=False)
        importlib.reload(repository_module)


def test_workflow_repository(tmp_path: Path) -> None:
    repo = WorkflowRepository(tmp_path / "workflow.db")

    payload = TaskCreate(
        title="Review google endpoint",
        asset_name="google.com:443",
        wave="wave_1",
        priority="high",
        description="Review TLS configuration and migration path.",
        recommended_action="Review TLS configuration, certificate algorithms, and PQC migration path.",
        requested_by="planner-service",
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
            requested_by="planner-service",
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
            requested_by="planner-service",
        )
    )

    try:
        repo.create_approval(task.id, "security-lead", "approved", "Proceed")
        assert False, "Expected ValueError when task is not pending approval"
    except ValueError as exc:
        assert "pending_approval" in str(exc)


def test_create_approval_raises_error_when_approver_is_the_requester(tmp_path: Path) -> None:
    repo = WorkflowRepository(tmp_path / "workflow.db")
    task = repo.create_task(
        TaskCreate(
            title="Approve key exchange upgrade",
            asset_name="vpn-gateway",
            wave="wave_2",
            priority="high",
            description="Need explicit approval state first.",
            recommended_action="Submit before approval.",
            requested_by="alice",
        )
    )
    repo.update_task_status(task.id, "pending_approval")

    try:
        repo.create_approval(task.id, "alice", "approved", "Proceed")
        assert False, "Expected ValueError when approver is the requester"
    except ValueError as exc:
        assert "segregation of duties" in str(exc)


def test_ensure_task_columns_backfills_requested_by_on_legacy_db(tmp_path: Path) -> None:
    db_path = tmp_path / "workflow.db"
    repo = WorkflowRepository(db_path)

    with repo._connect() as connection:
        connection.execute(
            "CREATE TABLE tasks_legacy AS SELECT * FROM tasks WHERE 0"
        )
        connection.execute("DROP TABLE tasks")
        connection.execute(
            """
            CREATE TABLE tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                asset_name TEXT NOT NULL,
                wave TEXT NOT NULL,
                priority TEXT NOT NULL,
                description TEXT NOT NULL,
                recommended_action TEXT,
                status TEXT NOT NULL
            )
            """
        )
        connection.execute("DROP TABLE tasks_legacy")
        connection.execute(
            """
            INSERT INTO tasks (id, title, asset_name, wave, priority, description, status)
            VALUES ('legacy-1', 'Legacy task', 'legacy-asset', 'wave_1', 'high', 'pre-existing row', 'draft')
            """
        )
        connection.commit()

    repo._ensure_schema()

    task = repo.get_task("legacy-1")
    assert task is not None
    assert task.requested_by == "unknown"
