from __future__ import annotations

from fastapi.testclient import TestClient

from app.context_packaging import package_copilot_context
from app.main import app
from app.providers import CopilotProvider, CopilotProviderRuntime, DisabledCopilotProvider


class FakeLocalContractProvider(CopilotProvider):
    """Test-only provider that models a future local provider contract."""

    def __init__(self, packaged_context: dict[str, object], warnings: list[str], redaction_applied: bool) -> None:
        self._packaged_context = packaged_context
        self._warnings = warnings
        self._redaction_applied = redaction_applied

    def query(self, request_id: str | None) -> dict[str, object]:
        resolved_request_id = request_id or "fake-local-contract"
        return {
            "answer": "mocked local response",
            "provider_mode": "local",
            "citations": [],
            "warnings": ["mock_provider_contract", *self._warnings],
            "used_external_provider": False,
            "redaction_applied": self._redaction_applied,
            "metadata": {
                "provider_name": "fake-local-contract",
                "request_id": resolved_request_id,
                "context": self._packaged_context,
            },
        }


client = TestClient(app)


def test_fake_provider_implements_copilot_provider_interface_without_network_calls() -> None:
    packaged = package_copilot_context({"risk_summary": {"total_assets": 2, "risk_level": "low"}})
    fake_provider = FakeLocalContractProvider(packaged.summary, packaged.warnings, packaged.redaction_applied)

    assert isinstance(fake_provider, CopilotProvider)
    result = fake_provider.query("req-contract-1")
    assert result["provider_mode"] == "local"
    assert result["used_external_provider"] is False


def test_fake_provider_response_shape_matches_copilot_contract() -> None:
    packaged = package_copilot_context({"risk_summary": {"total_assets": 1, "risk_level": "medium"}})
    result = FakeLocalContractProvider(packaged.summary, packaged.warnings, packaged.redaction_applied).query("req-shape")

    assert set(result.keys()) == {
        "answer",
        "provider_mode",
        "citations",
        "warnings",
        "used_external_provider",
        "redaction_applied",
        "metadata",
    }
    assert result["used_external_provider"] is False


def test_fake_provider_uses_packaged_context_and_never_leaks_raw_identifiers() -> None:
    raw_context = {
        "risk_summary": {"total_assets": 4, "risk_level": "high", "top_risk_categories": ["tls"]},
        "hostnames": ["db.internal"],
        "ips": ["10.0.0.8"],
        "packages": ["openssl", "nginx"],
    }
    packaged = package_copilot_context(raw_context)

    result = FakeLocalContractProvider(packaged.summary, packaged.warnings, packaged.redaction_applied).query("req-safe")

    assert result["redaction_applied"] is True
    context_payload = result["metadata"]["context"]
    assert "hostnames" not in str(context_payload)
    assert "10.0.0.8" not in str(context_payload)
    assert "openssl" not in str(context_payload)
    assert "nginx" not in str(context_payload)


def test_runtime_production_path_still_uses_disabled_provider_only() -> None:
    runtime = CopilotProviderRuntime()

    assert isinstance(runtime._disabled_provider, DisabledCopilotProvider)


def test_copilot_query_local_and_external_remain_disabled_and_hide_local_url(monkeypatch) -> None:
    monkeypatch.setenv("COPILOT_LOCAL_URL", "http://localhost:11434/private-path")

    monkeypatch.setenv("COPILOT_PROVIDER", "local")
    local_response = client.post("/copilot/query", json={"query": "hello"})
    local_data = local_response.json()
    assert local_response.status_code == 200
    assert local_data["provider_mode"] == "disabled"
    assert local_data["used_external_provider"] is False

    local_metadata_values = [str(value) for value in local_data["metadata"].values()]
    assert all("localhost:11434" not in value for value in local_metadata_values)
    assert all("private-path" not in value for value in local_metadata_values)

    monkeypatch.setenv("COPILOT_PROVIDER", "external")
    external_response = client.post("/copilot/query", json={"query": "hello"})
    external_data = external_response.json()
    assert external_response.status_code == 200
    assert external_data["provider_mode"] == "disabled"
    assert external_data["used_external_provider"] is False
