from __future__ import annotations

from typing import Any, Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Integration Service", version="0.1.0")

# ---------------------------------------------------------------------------
# SAFETY BOUNDARY
# ---------------------------------------------------------------------------
# This service is a DISABLED, DRY-RUN-ONLY skeleton. It never connects to any
# CA / KMS / HSM / CI-signing / VPN / ticketing system and never executes a
# production change. It only validates a proposed integration action against
# the deterministic approval boundary and returns a preview. `executed` is
# always False. Real connectors are intentionally out of scope (Trust Zone 4).

INTEGRATION_MODE = "dry_run_disabled"

TargetType = Literal["ca", "kms", "hsm", "ci_signing", "vpn", "ticketing"]

# Known actions -> (allowed target types, required approvals).
ACTION_CATALOG: dict[str, dict[str, Any]] = {
    "issue_certificate": {"targets": ["ca"], "approvals": ["security_review"]},
    "rotate_certificate": {"targets": ["ca", "kms"], "approvals": ["security_review", "change_approval"]},
    "revoke_certificate": {"targets": ["ca"], "approvals": ["security_review"]},
    "rotate_key": {"targets": ["kms", "hsm"], "approvals": ["security_review", "change_approval"]},
    "sign_artifact": {"targets": ["ci_signing", "hsm"], "approvals": ["release_approval"]},
    "update_trust_anchor": {"targets": ["ca"], "approvals": ["security_review", "change_approval"]},
    "open_ticket": {"targets": ["ticketing"], "approvals": []},
}

TARGETS: list[str] = ["ca", "kms", "hsm", "ci_signing", "vpn", "ticketing"]

# Parameter keys that must never be accepted by this service.
_FORBIDDEN_KEY_TOKENS = (
    "private_key",
    "privatekey",
    "secret",
    "token",
    "password",
    "passwd",
    "api_key",
    "apikey",
    "credential",
)


class DryRunRequest(BaseModel):
    action: str = Field(..., min_length=1)
    target_type: TargetType
    asset_name: str = Field(..., min_length=1)
    approved: bool = False
    approvals_provided: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)


class DryRunResponse(BaseModel):
    mode: str
    executed: bool
    action: str
    target_type: str
    asset_name: str
    recognized_action: bool
    approval_required: bool
    required_approvals: list[str]
    approvals_satisfied: bool
    would_execute_if_enabled: bool
    blocked_reasons: list[str]
    parameter_keys: list[str]
    warnings: list[str]


def _sensitive_keys(parameters: dict[str, Any]) -> list[str]:
    """Return any parameter keys (recursively) that look like secret material."""
    found: list[str] = []

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            for key, value in obj.items():
                lowered = str(key).lower().replace("-", "_")
                if any(token in lowered for token in _FORBIDDEN_KEY_TOKENS):
                    found.append(str(key))
                walk(value)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(parameters)
    return found


def evaluate_dry_run(request: DryRunRequest) -> DryRunResponse:
    warnings: list[str] = []
    blocked_reasons: list[str] = []

    # Execution is always disabled in this skeleton.
    blocked_reasons.append("integration_execution_disabled")

    entry = ACTION_CATALOG.get(request.action)
    recognized = entry is not None
    if not recognized:
        blocked_reasons.append("unrecognized_action")
        required_approvals: list[str] = []
    else:
        required_approvals = list(entry["approvals"])
        if request.target_type not in entry["targets"]:
            blocked_reasons.append("target_type_not_allowed_for_action")
            warnings.append(
                f"action '{request.action}' expects target in {entry['targets']}, got '{request.target_type}'"
            )

    # Sensitive material must never be submitted here.
    sensitive = _sensitive_keys(request.parameters)
    if sensitive:
        blocked_reasons.append("sensitive_material_rejected")
        warnings.append("secret-like parameter keys were rejected and not stored")
        parameter_keys: list[str] = []
    else:
        parameter_keys = sorted(str(k) for k in request.parameters.keys())

    approvals_satisfied = recognized and set(required_approvals).issubset(
        set(request.approvals_provided)
    )
    if recognized and required_approvals and not approvals_satisfied:
        missing = sorted(set(required_approvals) - set(request.approvals_provided))
        warnings.append(f"missing approvals: {missing}")

    would_execute_if_enabled = (
        recognized
        and "target_type_not_allowed_for_action" not in blocked_reasons
        and "sensitive_material_rejected" not in blocked_reasons
        and request.approved
        and approvals_satisfied
    )

    return DryRunResponse(
        mode=INTEGRATION_MODE,
        executed=False,
        action=request.action,
        target_type=request.target_type,
        asset_name=request.asset_name,
        recognized_action=recognized,
        approval_required=True,
        required_approvals=required_approvals,
        approvals_satisfied=approvals_satisfied,
        would_execute_if_enabled=would_execute_if_enabled,
        blocked_reasons=blocked_reasons,
        parameter_keys=parameter_keys,
        warnings=warnings,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "integration-service"}


@app.get("/integrations")
def integrations() -> dict[str, Any]:
    """List known integration targets and actions. Everything is disabled."""
    return {
        "mode": INTEGRATION_MODE,
        "executed_changes_supported": False,
        "targets": [{"target_type": target, "status": "disabled"} for target in TARGETS],
        "actions": [
            {"action": action, "targets": entry["targets"], "required_approvals": entry["approvals"]}
            for action, entry in ACTION_CATALOG.items()
        ],
    }


@app.post("/dry-run", response_model=DryRunResponse)
def dry_run(request: DryRunRequest) -> DryRunResponse:
    return evaluate_dry_run(request)
