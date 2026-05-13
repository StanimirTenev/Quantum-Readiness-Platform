from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_SAFE_RISK_FIELDS = {
    "total_assets",
    "risk_level",
    "top_risk_categories",
    "wave_counts",
    "confidence_summary",
}

_REDACTED_FIELD_WARNINGS = {
    "assets": "raw_identifiers_redacted",
    "hostnames": "raw_identifiers_redacted",
    "ips": "raw_identifiers_redacted",
    "ip_addresses": "raw_identifiers_redacted",
    "packages": "package_list_redacted",
    "graph_snapshot": "graph_snapshot_redacted",
    "certificates": "certificates_redacted",
    "certificate_fingerprints": "certificates_redacted",
    "secrets": "sensitive_fields_redacted",
    "tokens": "sensitive_fields_redacted",
    "private_keys": "sensitive_fields_redacted",
}


@dataclass(frozen=True)
class CopilotContextPackage:
    summary: dict[str, Any] = field(default_factory=dict)
    redaction_applied: bool = False
    warnings: list[str] = field(default_factory=list)
    omitted_fields: list[str] = field(default_factory=list)


def package_copilot_context(context: dict[str, Any]) -> CopilotContextPackage:
    if not isinstance(context, dict):
        return CopilotContextPackage(summary={}, warnings=["context_not_dict"])

    summary: dict[str, Any] = {}
    warnings: list[str] = []
    omitted_fields: list[str] = []

    risk_summary = context.get("risk_summary")
    if isinstance(risk_summary, dict):
        safe_risk_summary = {
            key: risk_summary[key]
            for key in _SAFE_RISK_FIELDS
            if key in risk_summary
        }
        if safe_risk_summary:
            summary["risk_summary"] = safe_risk_summary

    for field_name, warning in _REDACTED_FIELD_WARNINGS.items():
        if field_name in context:
            omitted_fields.append(field_name)
            if warning not in warnings:
                warnings.append(warning)

    redaction_applied = bool(omitted_fields)

    return CopilotContextPackage(
        summary=summary,
        redaction_applied=redaction_applied,
        warnings=warnings,
        omitted_fields=omitted_fields,
    )
