from app.provider_config import parse_provider_config


def test_parse_provider_config_returns_disabled_when_provider_missing() -> None:
    config = parse_provider_config({})
    assert config.requested_provider == "missing"
    assert config.effective_provider == "disabled"
    assert config.provider_mode == "disabled"
    assert config.used_external_provider is False
    assert "copilot_provider_missing" in config.warnings


def test_parse_provider_config_returns_disabled_when_provider_empty() -> None:
    config = parse_provider_config({"COPILOT_PROVIDER": "   "})
    assert config.requested_provider == "empty"
    assert config.effective_provider == "disabled"
    assert config.provider_mode == "disabled"
    assert config.used_external_provider is False
    assert "copilot_provider_empty" in config.warnings


def test_parse_provider_config_returns_disabled_when_provider_disabled() -> None:
    config = parse_provider_config({"COPILOT_PROVIDER": "disabled"})
    assert config.requested_provider == "disabled"
    assert config.effective_provider == "disabled"
    assert config.provider_mode == "disabled"
    assert config.used_external_provider is False
    assert config.warnings == []


def test_parse_provider_config_returns_local_requested_without_enabling_runtime() -> None:
    config = parse_provider_config({"COPILOT_PROVIDER": "local", "COPILOT_LOCAL_URL": "http://ignored"})
    assert config.requested_provider == "local"
    assert config.effective_provider == "disabled"
    assert config.provider_mode == "disabled"
    assert config.used_external_provider is False


def test_parse_provider_config_returns_external_requested_without_enabling_external() -> None:
    config = parse_provider_config({"COPILOT_PROVIDER": "external"})
    assert config.requested_provider == "external"
    assert config.effective_provider == "disabled"
    assert config.provider_mode == "disabled"
    assert config.used_external_provider is False


def test_parse_provider_config_returns_disabled_when_provider_unknown() -> None:
    config = parse_provider_config({"COPILOT_PROVIDER": "mystery"})
    assert config.requested_provider == "mystery"
    assert config.effective_provider == "disabled"
    assert config.provider_mode == "disabled"
    assert config.used_external_provider is False
    assert "copilot_provider_unknown" in config.warnings
