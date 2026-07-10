import pytest
from fastapi.testclient import TestClient

from app import main
from app.repository import AssetRepository


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "repository", AssetRepository(tmp_path / "inventory.db"))

    def fake_score(self, payload):
        return {
            "contract_version": payload["contract_version"],
            "asset_name": payload["asset_name"],
            "scenario": payload["scenario"],
            "scenario_multiplier": 1.0,
            "base_score": 3.4,
            "final_score": 3.4,
            "normalized_score_100": 68.0,
            "rating": "high",
            "dependency_count": payload["dependency_count"],
            "vendor_blocked": payload["vendor_blocked"],
            "rationale": payload,
        }

    monkeypatch.setattr("app.clients.risk_engine.RiskEngineClient.score", fake_score)
    with TestClient(main.app) as test_client:
        yield test_client


def _ingest_payload(name="ws-test-asset"):
    return {
        "source": "manual",
        "assets": [{"asset_type": "server", "name": name}],
    }


def test_create_workspace_returns_id_source_created_at(client: TestClient) -> None:
    response = client.post("/workspaces", json={"source": "product-demo"})
    assert response.status_code == 201
    data = response.json()
    assert data["source"] == "product-demo"
    assert data["id"]
    assert data["created_at"]


def test_list_workspaces(client: TestClient) -> None:
    client.post("/workspaces", json={"source": "a"})
    client.post("/workspaces", json={"source": "b"})
    response = client.get("/workspaces")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_get_workspace_404_when_missing(client: TestClient) -> None:
    response = client.get("/workspaces/does-not-exist")
    assert response.status_code == 404


def test_ingest_without_workspace_id_auto_creates_one(client: TestClient) -> None:
    response = client.post("/scans/ingest", json=_ingest_payload())
    assert response.status_code == 201
    data = response.json()
    assert data["workspace_id"]

    workspace_response = client.get(f"/workspaces/{data['workspace_id']}")
    assert workspace_response.status_code == 200
    bundle = workspace_response.json()
    assert bundle["workspace"]["source"] == "manual"
    assert len(bundle["scans"]) == 1
    assert bundle["scans"][0]["id"] == data["scan_id"]


def test_ingest_with_explicit_workspace_id_groups_scans(client: TestClient) -> None:
    workspace = client.post("/workspaces", json={"source": "product-demo"}).json()
    ws_id = workspace["id"]

    r1 = client.post(f"/scans/ingest?workspace_id={ws_id}", json=_ingest_payload("asset-a"))
    r2 = client.post(f"/scans/ingest?workspace_id={ws_id}", json=_ingest_payload("asset-b"))
    assert r1.json()["workspace_id"] == ws_id
    assert r2.json()["workspace_id"] == ws_id

    bundle = client.get(f"/workspaces/{ws_id}").json()
    assert len(bundle["scans"]) == 2
    assert len(bundle["risks"]) == 2


def test_ingest_with_unknown_workspace_id_is_404(client: TestClient) -> None:
    response = client.post("/scans/ingest?workspace_id=bogus", json=_ingest_payload())
    assert response.status_code == 404


def test_reused_asset_keeps_its_original_workspace_id(client: TestClient) -> None:
    ws1 = client.post("/workspaces", json={"source": "first"}).json()
    r1 = client.post(f"/scans/ingest?workspace_id={ws1['id']}", json=_ingest_payload("shared-asset"))
    asset_id = r1.json()["asset_ids"][0]
    original_workspace_id = client.get(f"/assets/{asset_id}").json()["workspace_id"]
    assert original_workspace_id == ws1["id"]

    ws2 = client.post("/workspaces", json={"source": "second"}).json()
    client.post(f"/scans/ingest?workspace_id={ws2['id']}", json=_ingest_payload("shared-asset"))

    # same asset (matched by name+type), workspace_id must not have moved to ws2
    still_original = client.get(f"/assets/{asset_id}").json()["workspace_id"]
    assert still_original == ws1["id"]


def test_asset_has_created_at(client: TestClient) -> None:
    r = client.post("/scans/ingest", json=_ingest_payload())
    asset_id = r.json()["asset_ids"][0]
    asset = client.get(f"/assets/{asset_id}").json()
    assert asset["created_at"]


def test_create_and_fetch_workspace_report(client: TestClient) -> None:
    workspace = client.post("/workspaces", json={"source": "product-demo"}).json()
    ws_id = workspace["id"]
    client.post(f"/scans/ingest?workspace_id={ws_id}", json=_ingest_payload("report-asset"))

    report_response = client.post(f"/workspaces/{ws_id}/reports")
    assert report_response.status_code == 201
    report = report_response.json()
    assert report["workspace_id"] == ws_id
    assert report["report_type"] == "operator"
    assert "report-asset" in report["content"]
    assert "Migration Assessment Report" in report["content"]

    fetched = client.get(f"/reports/{report['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == report["id"]

    bundle = client.get(f"/workspaces/{ws_id}").json()
    assert len(bundle["reports"]) == 1


def test_create_report_with_custom_report_type(client: TestClient) -> None:
    workspace = client.post("/workspaces", json={"source": "manual"}).json()
    response = client.post(f"/workspaces/{workspace['id']}/reports", json={"report_type": "exec-summary"})
    assert response.status_code == 201
    assert response.json()["report_type"] == "exec-summary"


def test_create_report_404_for_unknown_workspace(client: TestClient) -> None:
    response = client.post("/workspaces/does-not-exist/reports")
    assert response.status_code == 404


def test_get_report_404_when_missing(client: TestClient) -> None:
    response = client.get("/reports/does-not-exist")
    assert response.status_code == 404


def test_list_reports_filtered_by_workspace(client: TestClient) -> None:
    ws1 = client.post("/workspaces", json={"source": "a"}).json()
    ws2 = client.post("/workspaces", json={"source": "b"}).json()
    client.post(f"/scans/ingest?workspace_id={ws1['id']}", json=_ingest_payload("x"))
    client.post(f"/scans/ingest?workspace_id={ws2['id']}", json=_ingest_payload("y"))
    client.post(f"/workspaces/{ws1['id']}/reports")
    client.post(f"/workspaces/{ws2['id']}/reports")

    all_reports = client.get("/reports").json()
    assert len(all_reports) == 2

    ws1_reports = client.get(f"/reports?workspace_id={ws1['id']}").json()
    assert len(ws1_reports) == 1
    assert ws1_reports[0]["workspace_id"] == ws1["id"]
