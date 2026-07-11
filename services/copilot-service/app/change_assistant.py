"""Change Assistant: the fifth and last deterministic Copilot subagent.
Drafts a human-reviewable pre-change checklist for a specific asset --
what to verify before migrating it, whether a workflow task already tracks
it, and its recommended wave -- without executing or scheduling anything
itself. No LLM call, read-only synthesis over risk-engine's rationale,
planner-service's wave plan, and workflow-service's tasks.

QRP's stated boundary (see tools/report/build_operator_report.py's report
header and docs/architecture) is that the platform discovers, assesses and
plans but does not execute changes -- Trust Zone 4 integrations
(CA/KMS/HSM/signing) stay dry-run only until an operator approves. Change
Assistant inherits that boundary directly: it never calls workflow-service's
POST /tasks or any dry-run/execute endpoint, only GETs existing state and
narrates a draft."""

from __future__ import annotations

from typing import Any

SAFETY_NOTICE = (
    "This is a draft plan for human review only -- QRP discovers, assesses, and plans; it does "
    "not execute changes. Trust Zone 4 integrations (CA/KMS/HSM/signing) remain dry-run only "
    "until an operator approves."
)

# (rationale key, actionable pre-change checklist item). Keys mirror the same
# flags risk_narrator.py already narrates -- the checklist turns "why this
# is risky" into "what to verify before changing it".
PRE_CHANGE_CHECKLIST_ITEMS: list[tuple[str, str]] = [
    ("weak_public_key_detected", "Confirm a PQC-capable (or at minimum RSA >=3072-bit) replacement certificate is provisioned and tested before rotating."),
    ("private_key_files_detected", "Confirm private key files are rotated and old key material is securely destroyed as part of the change."),
    ("embedded_private_key_in_repo_detected", "Rotate the exposed key immediately, purge it from version-control history, and audit for unauthorized use."),
    ("legacy_ssh_host_key_detected", "Plan migration to a PQC-ready SSH host key algorithm and disable ssh-rsa/ssh-dss once clients are updated."),
    ("weak_ssh_kex_detected", "Disable SHA-1-based key exchange algorithms and confirm clients support a modern replacement (e.g. curve25519-sha256)."),
    ("expiring_certificate_detected", "Confirm the renewal/replacement certificate is provisioned before the current one expires."),
    ("windows_expired_certificates", "Confirm expired certificates in the store are identified and scheduled for removal/reissue."),
    ("windows_weak_signature_certificates", "Confirm weak-signature certificates have a reissue plan before this change proceeds."),
    ("windows_domain_controller", "This host is a domain trust anchor -- coordinate with AD/PKI owners before any certificate change."),
    ("windows_large_certificate_estate", "Plan for a staged rollout given the large certificate estate on this host."),
    ("crypto_packages_detected", "Confirm PQC-capable library versions are available for the crypto packages installed on this asset."),
    ("tls_config_detected", "Review TLS configuration for cipher/algorithm changes needed alongside the certificate change."),
    ("ssh_config_detected", "Review SSH host key algorithms for a PQC-ready update path."),
    ("weak_ssh_cipher_detected", "Disable legacy SSH ciphers (3DES/RC4/Blowfish/CAST128/DES) in the server configuration."),
    ("weak_ssh_mac_detected", "Disable legacy SSH MAC algorithms (hmac-md5*/hmac-sha1*) in the server configuration."),
]

WAVE_LABELS = {"wave_1": "Wave 1 (urgent)", "wave_2": "Wave 2 (near-term)", "wave_3": "Wave 3 (planned)"}


def _find_wave(asset_name: str, plan_data: dict[str, Any]) -> str | None:
    for wave_key in ("wave_1", "wave_2", "wave_3"):
        for item in plan_data.get(wave_key, []):
            if item.get("asset_name") == asset_name:
                return wave_key
    return None


def _build_checklist(risk: dict[str, Any]) -> list[str]:
    rationale = risk.get("rationale") or {}
    checklist = [phrase for key, phrase in PRE_CHANGE_CHECKLIST_ITEMS if rationale.get(key)]

    if risk.get("vendor_blocked"):
        checklist.append("Vendor readiness blocker is in effect -- confirm a vendor escalation ticket is open before committing to a timeline.")

    dependency_count = risk.get("dependency_count")
    if dependency_count:
        checklist.append(f"This asset has {dependency_count} dependent system(s) -- coordinate downstream validation before and after the change.")

    checklist.append("Document a rollback plan and post-change validation/retest steps before execution.")
    return checklist


def build_change_plan(
    asset_name: str,
    asset_bundle: dict[str, Any],
    plan_data: dict[str, Any],
    tasks: list[dict[str, Any]],
) -> dict[str, Any]:
    risks = asset_bundle.get("risks") or []
    existing_task = next((t for t in tasks if t.get("asset_name") == asset_name), None)

    if not risks:
        narrative = (
            f"No risk data has been computed yet for asset '{asset_name}'; a change plan cannot be "
            f"drafted until it is assessed. {SAFETY_NOTICE}"
        )
        return {
            "asset_name": asset_name,
            "narrative": narrative,
            "rating": None,
            "wave": None,
            "pre_change_checklist": [],
            "existing_task": existing_task,
            "safety_notice": SAFETY_NOTICE,
        }

    risk = max(risks, key=lambda r: r.get("normalized_score_100", 0))
    rating = risk.get("rating", "unknown")
    wave_key = _find_wave(asset_name, plan_data)
    wave_label = WAVE_LABELS.get(wave_key) if wave_key else None
    checklist = _build_checklist(risk)

    narrative_parts = [f"Draft change plan for '{asset_name}' (rated {rating})."]
    if wave_label:
        narrative_parts.append(f"Recommended wave: {wave_label}.")
    if existing_task:
        narrative_parts.append(
            f"An existing workflow task already tracks this asset (id={existing_task.get('id')}, "
            f"status={existing_task.get('status')}) -- update that task rather than creating a duplicate."
        )
    else:
        narrative_parts.append(
            "No existing workflow task found for this asset -- consider creating one via "
            "planner-service's export-tasks or workflow-service's POST /tasks."
        )
    narrative_parts.append(SAFETY_NOTICE)

    return {
        "asset_name": asset_name,
        "narrative": " ".join(narrative_parts),
        "rating": rating,
        "wave": wave_key,
        "pre_change_checklist": checklist,
        "existing_task": existing_task,
        "safety_notice": SAFETY_NOTICE,
    }
