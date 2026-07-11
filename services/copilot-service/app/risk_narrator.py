"""Deterministic Risk Narrator: turns a persisted risk record's structured
rationale into a plain-language explanation. No LLM call -- template rules
over already-computed risk-engine output, consistent with the platform's
"deterministic for everything critical" boundary (see
docs/ad-certificate-estate-design.md and the architecture reference docs for
the same principle applied elsewhere)."""

from __future__ import annotations

from typing import Any

# (rationale key, human-readable phrase). Keys mirror the flags risk-engine
# writes into RiskRecord.rationale (services/risk-engine/app/main.py).
HIGH_SEVERITY_SIGNALS: list[tuple[str, str]] = [
    ("weak_public_key_detected", "a weak public key was detected (RSA key below 2048 bits)"),
    ("private_key_files_detected", "private key files were found on the host"),
    ("embedded_private_key_in_repo_detected", "a private key was found embedded directly in the repository (e.g. in a Terraform or Kubernetes manifest)"),
    ("legacy_ssh_host_key_detected", "the SSH server offers a legacy host key algorithm (RSA or DSA signatures), which is quantum-vulnerable"),
    ("weak_ssh_kex_detected", "the SSH server offers a weak, SHA-1-based Diffie-Hellman key exchange algorithm"),
    ("legacy_ipsec_dh_group_detected", "the IPsec/IKE responder selected a legacy Diffie-Hellman group (1024-bit or smaller), which is quantum-vulnerable"),
    ("expiring_certificate_detected", "a certificate close to expiry was found"),
    ("windows_expired_certificates", "expired certificates were found in the Windows certificate store"),
    ("windows_weak_signature_certificates", "certificates with a weak signature algorithm were found in the Windows certificate store"),
]

MEDIUM_SEVERITY_SIGNALS: list[tuple[str, str]] = [
    ("windows_domain_controller", "the host is a domain controller, which widens its blast radius"),
    ("windows_large_certificate_estate", "the host has a large certificate store"),
    ("certificate_files_detected", "certificate files are present on the host"),
    ("tls_config_detected", "TLS configuration was found on the host"),
    ("tls_detected", "TLS was observed on this asset"),
    ("ssh_config_detected", "SSH configuration was found on the host"),
    ("weak_ssh_cipher_detected", "the SSH server offers a weak or legacy encryption cipher"),
    ("weak_ssh_mac_detected", "the SSH server offers a weak or legacy MAC algorithm"),
    ("weak_ipsec_encryption_detected", "the IPsec/IKE responder selected a weak or legacy encryption algorithm (DES/3DES/NULL)"),
    ("weak_ipsec_integrity_detected", "the IPsec/IKE responder selected a weak or legacy integrity algorithm"),
    ("weak_ipsec_prf_detected", "the IPsec/IKE responder selected a weak or legacy pseudorandom function"),
    ("crypto_packages_detected", "crypto-related packages are installed"),
    ("ci_signing_command_detected", "a CI/CD pipeline signing command was detected (e.g. gpg --sign, cosign sign); the signing key's algorithm isn't visible from the pipeline config alone and should be reviewed"),
]

RATING_RECOMMENDATIONS: dict[str, str] = {
    "critical": "Recommend prioritizing this asset for immediate (Wave 1) migration.",
    "high": "Recommend including this asset in a near-term migration wave.",
    "medium": "Recommend planning migration for this asset in a later wave.",
    "low": "No urgent action needed; continue routine monitoring.",
    "minimal": "No action needed at this time.",
}


def _matched_phrases(rationale: dict[str, Any], signals: list[tuple[str, str]]) -> list[str]:
    return [phrase for key, phrase in signals if rationale.get(key)]


def narrate_risk(asset_name: str, risk: dict[str, Any]) -> str:
    rating = str(risk.get("rating") or "unknown").lower()
    score = risk.get("normalized_score_100")
    scenario = risk.get("scenario") or "public_timeline"
    multiplier = risk.get("scenario_multiplier")
    rationale = risk.get("rationale") or {}

    sentences: list[str] = []

    score_text = f"{score}/100" if score is not None else "an unscored"
    multiplier_clause = f" (x{multiplier} scenario multiplier applied)" if multiplier is not None else ""
    sentences.append(f"Asset '{asset_name}' is rated **{rating}** ({score_text}) under the '{scenario}' scenario{multiplier_clause}.")

    high = _matched_phrases(rationale, HIGH_SEVERITY_SIGNALS)
    medium = _matched_phrases(rationale, MEDIUM_SEVERITY_SIGNALS)

    if high:
        sentences.append("Key risk drivers: " + "; ".join(high) + ".")
    if medium:
        sentences.append("Contributing factors: " + "; ".join(medium) + ".")
    if not high and not medium:
        sentences.append("No specific evidence-based risk signals were flagged; the score reflects the base risk factors only.")

    dependency_count = risk.get("dependency_count")
    if dependency_count:
        sentences.append(f"This asset has {dependency_count} dependent system(s) in its blast radius.")
    if risk.get("vendor_blocked"):
        sentences.append("Migration is currently blocked by a vendor readiness gap.")

    sentences.append(RATING_RECOMMENDATIONS.get(rating, "Review and reassess as needed."))

    return " ".join(sentences)


def narrate_asset_bundle(asset_name: str, asset_bundle: dict[str, Any]) -> dict[str, Any]:
    """asset_bundle is the shape returned by retrieval-service's GET /asset
    (assets/scans/risks/tasks lists for one asset name)."""
    risks = asset_bundle.get("risks") or []
    if not risks:
        return {
            "asset_name": asset_name,
            "narrative": f"No risk data has been computed yet for asset '{asset_name}'.",
            "risk": None,
        }

    top_risk = max(risks, key=lambda r: r.get("normalized_score_100", 0))
    return {
        "asset_name": asset_name,
        "narrative": narrate_risk(asset_name, top_risk),
        "risk": top_risk,
    }
