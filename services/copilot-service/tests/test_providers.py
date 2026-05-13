from app.providers import CopilotProviderRuntime, DisabledCopilotProvider


def test_disabled_provider_shell_returns_disabled_safe_result(monkeypatch) -> None:
    monkeypatch.setenv("COPILOT_PROVIDER", "disabled")
    result = DisabledCopilotProvider().query("req-1")

    assert result["provider_mode"] == "disabled"
    assert result["used_external_provider"] is False
    assert result["citations"] == []
    assert result["redaction_applied"] is False
    assert "copilot_provider_disabled" in result["warnings"]


def test_runtime_preserves_request_id_and_never_uses_external(monkeypatch) -> None:
    monkeypatch.setenv("COPILOT_PROVIDER", "external")
    result = CopilotProviderRuntime().query("req-123")

    assert result["metadata"]["request_id"] == "req-123"
    assert result["provider_mode"] == "disabled"
    assert result["used_external_provider"] is False
    assert "copilot_external_provider_not_implemented" in result["warnings"]


def test_unknown_local_external_paths_stay_disabled_safe(monkeypatch) -> None:
    runtime = CopilotProviderRuntime()

    monkeypatch.setenv("COPILOT_PROVIDER", "unexpected")
    unknown = runtime.query("r-unknown")
    assert unknown["provider_mode"] == "disabled"
    assert unknown["used_external_provider"] is False

    monkeypatch.setenv("COPILOT_PROVIDER", "local")
    monkeypatch.setenv("COPILOT_LOCAL_URL", "http://localhost:11434/api")
    local = runtime.query("r-local")
    assert local["provider_mode"] == "disabled"
    assert local["used_external_provider"] is False
    assert "copilot_local_provider_not_implemented" in local["warnings"]

    monkeypatch.setenv("COPILOT_PROVIDER", "external")
    external = runtime.query("r-external")
    assert external["provider_mode"] == "disabled"
    assert external["used_external_provider"] is False


def test_raw_copilot_local_url_is_not_exposed(monkeypatch) -> None:
    monkeypatch.setenv("COPILOT_PROVIDER", "local")
    monkeypatch.setenv("COPILOT_LOCAL_URL", "http://localhost:11434/secret-endpoint")

    result = CopilotProviderRuntime().query("req-local")

    metadata_values = [str(value) for value in result["metadata"].values()]
    assert all("secret-endpoint" not in value for value in metadata_values)
    assert all("localhost:11434" not in value for value in metadata_values)
