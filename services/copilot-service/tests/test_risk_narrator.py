from app.risk_narrator import narrate_asset_bundle, narrate_risk


def _risk(rating="high", score=72.0, scenario="public_timeline", multiplier=1.0, rationale=None, dependency_count=0, vendor_blocked=False):
    return {
        "rating": rating,
        "normalized_score_100": score,
        "scenario": scenario,
        "scenario_multiplier": multiplier,
        "dependency_count": dependency_count,
        "vendor_blocked": vendor_blocked,
        "rationale": rationale or {},
    }


def test_narrate_risk_includes_rating_score_and_scenario():
    text = narrate_risk("payments-api", _risk(rating="critical", score=91.5, scenario="hidden_capability", multiplier=1.35))
    assert "payments-api" in text
    assert "critical" in text
    assert "91.5/100" in text
    assert "hidden_capability" in text
    assert "x1.35" in text


def test_narrate_risk_surfaces_high_severity_signals():
    text = narrate_risk("host-a", _risk(rationale={"weak_public_key_detected": True, "private_key_files_detected": True}))
    assert "weak public key" in text
    assert "private key files" in text
    assert "Key risk drivers" in text


def test_narrate_risk_surfaces_windows_signals():
    text = narrate_risk("dc-01", _risk(rating="critical", rationale={"windows_domain_controller": True, "windows_expired_certificates": True}))
    assert "domain controller" in text
    assert "expired certificates" in text
    # domain controller is medium, expired certs is high -- both severity buckets present
    assert "Key risk drivers" in text
    assert "Contributing factors" in text


def test_narrate_risk_surfaces_ssh_and_embedded_key_signals():
    text = narrate_risk("ssh-gateway", _risk(rationale={
        "legacy_ssh_host_key_detected": True,
        "weak_ssh_kex_detected": True,
        "weak_ssh_cipher_detected": True,
        "weak_ssh_mac_detected": True,
        "embedded_private_key_in_repo_detected": True,
    }))
    assert "legacy host key algorithm" in text
    assert "weak, SHA-1-based Diffie-Hellman" in text
    assert "weak or legacy encryption cipher" in text
    assert "weak or legacy MAC algorithm" in text
    assert "embedded directly in the repository" in text
    assert "Key risk drivers" in text
    assert "Contributing factors" in text


def test_narrate_risk_surfaces_ipsec_signals():
    text = narrate_risk("vpn-gateway", _risk(rationale={
        "legacy_ipsec_dh_group_detected": True,
        "weak_ipsec_encryption_detected": True,
        "weak_ipsec_integrity_detected": True,
        "weak_ipsec_prf_detected": True,
    }))
    assert "legacy Diffie-Hellman group" in text
    assert "weak or legacy encryption algorithm" in text
    assert "weak or legacy integrity algorithm" in text
    assert "weak or legacy pseudorandom function" in text
    assert "Key risk drivers" in text
    assert "Contributing factors" in text


def test_narrate_risk_surfaces_ci_signing_command_signal():
    text = narrate_risk("release-pipeline", _risk(rationale={"ci_signing_command_detected": True}))
    assert "CI/CD pipeline signing command was detected" in text
    assert "Contributing factors" in text


def test_narrate_risk_no_signals_says_so():
    text = narrate_risk("clean-host", _risk(rating="low", rationale={}))
    assert "No specific evidence-based risk signals" in text


def test_narrate_risk_mentions_dependency_count_and_vendor_block():
    text = narrate_risk("core-svc", _risk(dependency_count=7, vendor_blocked=True))
    assert "7 dependent system" in text
    assert "blocked by a vendor" in text


def test_narrate_risk_recommendation_matches_rating():
    assert "Wave 1" in narrate_risk("x", _risk(rating="critical"))
    assert "near-term" in narrate_risk("x", _risk(rating="high"))
    assert "later wave" in narrate_risk("x", _risk(rating="medium"))
    assert "No urgent action" in narrate_risk("x", _risk(rating="low"))


def test_narrate_asset_bundle_picks_highest_scoring_risk():
    bundle = {
        "risks": [
            _risk(rating="low", score=20.0),
            _risk(rating="critical", score=95.0),
        ]
    }
    result = narrate_asset_bundle("multi-scan-asset", bundle)
    assert result["risk"]["normalized_score_100"] == 95.0
    assert "critical" in result["narrative"]


def test_narrate_asset_bundle_handles_no_risk_data():
    result = narrate_asset_bundle("unknown-asset", {"risks": []})
    assert result["risk"] is None
    assert "No risk data" in result["narrative"]
