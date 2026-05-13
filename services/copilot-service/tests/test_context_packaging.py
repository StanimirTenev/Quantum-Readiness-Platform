from copy import deepcopy

from app.context_packaging import package_copilot_context


def test_package_copilot_context_returns_warning_for_non_dict_input() -> None:
    result = package_copilot_context("bad-input")
    assert result.summary == {}
    assert result.redaction_applied is False
    assert result.warnings == ["context_not_dict"]
    assert result.omitted_fields == []


def test_package_copilot_context_returns_empty_summary_for_empty_dict() -> None:
    result = package_copilot_context({})
    assert result.summary == {}
    assert result.redaction_applied is False
    assert result.warnings == []
    assert result.omitted_fields == []


def test_package_copilot_context_omits_hostnames_field() -> None:
    result = package_copilot_context({"hostnames": ["db.internal"]})
    assert "hostnames" in result.omitted_fields
    assert "raw_identifiers_redacted" in result.warnings


def test_package_copilot_context_omits_ip_addresses_field() -> None:
    result = package_copilot_context({"ip_addresses": ["10.0.0.2"]})
    assert "ip_addresses" in result.omitted_fields
    assert "raw_identifiers_redacted" in result.warnings


def test_package_copilot_context_omits_package_lists() -> None:
    result = package_copilot_context({"packages": ["openssl", "nginx"]})
    assert "packages" in result.omitted_fields
    assert "package_list_redacted" in result.warnings


def test_package_copilot_context_omits_graph_snapshot() -> None:
    result = package_copilot_context({"graph_snapshot": {"nodes": ["a"]}})
    assert "graph_snapshot" in result.omitted_fields
    assert "graph_snapshot_redacted" in result.warnings


def test_package_copilot_context_omits_sensitive_secret_fields() -> None:
    result = package_copilot_context(
        {
            "secrets": ["secret"],
            "tokens": ["token"],
            "private_keys": ["-----BEGIN KEY-----"],
        }
    )
    assert "secrets" in result.omitted_fields
    assert "tokens" in result.omitted_fields
    assert "private_keys" in result.omitted_fields
    assert "sensitive_fields_redacted" in result.warnings


def test_package_copilot_context_preserves_safe_aggregate_risk_fields() -> None:
    result = package_copilot_context(
        {
            "risk_summary": {
                "total_assets": 5,
                "risk_level": "high",
                "top_risk_categories": ["crypto", "tls"],
                "wave_counts": {"wave_1": 2},
                "confidence_summary": "moderate",
                "asset_ids": ["asset-1"],
            }
        }
    )
    assert result.summary == {
        "risk_summary": {
            "total_assets": 5,
            "risk_level": "high",
            "top_risk_categories": ["crypto", "tls"],
            "wave_counts": {"wave_1": 2},
            "confidence_summary": "moderate",
        }
    }


def test_package_copilot_context_returns_only_safe_summary_for_mixed_context() -> None:
    context = {
        "risk_summary": {
            "total_assets": 7,
            "risk_level": "medium",
            "top_risk_categories": ["signing"],
        },
        "assets": [{"hostname": "prod-1"}],
        "ips": ["192.168.1.3"],
        "certificates": [{"fingerprint": "abc"}],
        "graph_snapshot": {"nodes": [1, 2], "edges": [3]},
        "packages": ["openssl"],
        "secrets": ["x"],
    }
    result = package_copilot_context(context)

    assert result.summary == {
        "risk_summary": {
            "total_assets": 7,
            "risk_level": "medium",
            "top_risk_categories": ["signing"],
        }
    }
    assert result.redaction_applied is True
    assert set(result.omitted_fields) == {
        "assets",
        "ips",
        "certificates",
        "graph_snapshot",
        "packages",
        "secrets",
    }


def test_package_copilot_context_marks_redaction_when_sensitive_fields_omitted() -> None:
    result = package_copilot_context({"tokens": ["abc"]})
    assert result.redaction_applied is True


def test_package_copilot_context_records_all_omitted_sensitive_fields() -> None:
    result = package_copilot_context({"packages": [], "graph_snapshot": {}, "certificate_fingerprints": []})
    assert result.omitted_fields == ["packages", "graph_snapshot", "certificate_fingerprints"]


def test_package_copilot_context_does_not_mutate_input_dict() -> None:
    context = {
        "risk_summary": {
            "total_assets": 3,
            "risk_level": "low",
        },
        "tokens": ["t1"],
    }
    original = deepcopy(context)
    package_copilot_context(context)
    assert context == original
