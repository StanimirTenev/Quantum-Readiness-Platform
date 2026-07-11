from tools.report import build_operator_report as reporter


def _asset(name, readiness, risk, hndl=False, qv=0, weak=0, chain=None, app=None):
    return {
        "asset_name": name,
        "application": app,
        "assess": {
            "fingerprint": {"summary": {"quantum_vulnerable_count": qv, "hndl_exposure": hndl, "weak_count": weak, "pqc_ready_count": 0}},
            "pqc_readiness": {"readiness": readiness},
            "risk": {"rating": risk} if risk else None,
            "attribution": {"attributed_findings": (
                [{"vulnerability": {"algorithm_family": "RSA", "classification": "classical_vulnerable", "quantum_vulnerable": True}, "chain": chain or ["RSA (classical_vulnerable)", "h:443", "svc", "asset:x", "certificate:CN=x"]}]
                if qv else []
            )},
        },
    }


def test_wave_assignment_rules():
    v_urgent = reporter.asset_view(_asset("a", "classical_only", "critical", hndl=True, qv=2))
    assert reporter.assign_wave(v_urgent) == 1
    v_near = reporter.asset_view(_asset("b", "classical_only", "medium", qv=1))
    assert reporter.assign_wave(v_near) == 2
    v_hybrid = reporter.asset_view(_asset("c", "hybrid_capable", "low", qv=1))
    assert reporter.assign_wave(v_hybrid) == 2
    v_ready = reporter.asset_view(_asset("d", "pqc_ready", None, qv=0))
    assert reporter.assign_wave(v_ready) == 3
    v_clean = reporter.asset_view(_asset("e", "unknown", None, qv=0))
    assert reporter.assign_wave(v_clean) == 3


def test_report_has_expected_sections_and_metrics():
    bundle = {
        "environment": "unit-test",
        "assets": [
            _asset("payments-api", "classical_only", "critical", hndl=True, qv=2, weak=1, app="payments"),
            _asset("backup-store", "hybrid_capable", "medium", qv=1),
            _asset("modern-svc", "pqc_ready", "low", qv=0),
        ],
    }
    report = reporter.build_report(bundle)
    assert "# Quantum Readiness — Migration Assessment Report" in report
    assert "## Executive Summary" in report
    assert "Assets assessed: **3**" in report
    assert "1 classical-only" in report
    assert "Harvest-now-decrypt-later exposure: **1**" in report
    assert "## Migration Waves" in report
    assert "Wave 1 — urgent" in report
    assert "## Attribution & Evidence Chains" in report
    # the urgent asset must be in wave 1 and its chain rendered
    assert "payments-api" in report
    assert "certificate:CN=x" in report


def test_recommended_action_reflects_wave1():
    bundle = {"assets": [_asset("x", "classical_only", "critical", hndl=True, qv=1)]}
    assert "Begin Wave 1 now" in reporter.build_report(bundle)


def test_empty_bundle_is_handled():
    report = reporter.build_report({"assets": []})
    assert "Assets assessed: **0**" in report
    assert "Posture is largely post-quantum ready" in report


def _windows_host(name, rating, score_100, rationale=None, app="windows-host"):
    return {
        "asset_name": name,
        "application": app,
        "persisted_risk": {
            "rating": rating,
            "normalized_score_100": score_100,
            "rationale": rationale or {},
        },
    }


def test_windows_host_view_has_unknown_readiness_and_no_fingerprint_signals():
    view = reporter.asset_view(_windows_host("dc-01", "critical", 90, {"windows_domain_controller": True}))
    assert view["readiness"] == "unknown"
    assert view["quantum_vulnerable"] == 0
    assert view["hndl"] is False
    assert view["source"] == "windows_host"
    assert "windows_domain_controller" in view["windows_high_signals"]


def test_windows_host_high_signal_reaches_wave_1_when_score_is_high():
    view = reporter.asset_view(_windows_host("dc-01", "critical", 60, {"windows_domain_controller": True}))
    # 60 base + 15 high-signal boost = 75 >= 65 -> wave 1
    assert reporter.assign_wave(view) == 1


def test_windows_host_high_signal_is_capped_at_wave_2_not_3():
    # Low base score (30) + 15 boost = 45 would normally be wave 2 anyway;
    # use a score low enough that only the wave-3 cap saves it (e.g. base 10).
    view = reporter.asset_view(_windows_host("dc-02", "low", 10, {"windows_expired_certificates": True}))
    # 10 + 15 = 25 -> would be wave 3, but a high-priority signal caps it at 2.
    assert reporter.assign_wave(view) == 2


def test_windows_host_with_no_signals_and_low_score_lands_in_wave_3():
    view = reporter.asset_view(_windows_host("clean-host", "minimal", 5, {}))
    assert reporter.assign_wave(view) == 3


def test_windows_host_medium_signal_only_reaches_wave_2():
    view = reporter.asset_view(_windows_host("big-estate", "low", 40, {"windows_large_certificate_estate": True}))
    # 40 + 5 = 45 -> wave 2
    assert reporter.assign_wave(view) == 2


def test_windows_host_does_not_pollute_pqc_readiness_counts():
    bundle = {
        "environment": "unit-test",
        "assets": [
            _asset("payments-api", "classical_only", "critical", hndl=True, qv=2),
            _windows_host("dc-01", "critical", 90, {"windows_domain_controller": True, "windows_expired_certificates": True}),
        ],
    }
    report = reporter.build_report(bundle)
    assert "Assets assessed: **2**" in report
    # only the assess-pipeline asset counts toward classical-only, not the windows host.
    assert "1 classical-only" in report
    assert "dc-01" in report
    assert "Windows: windows_domain_controller, windows_expired_certificates" in report


def test_report_has_new_sections():
    bundle = {"assets": [_asset("payments-api", "classical_only", "critical", hndl=True, qv=2)]}
    report = reporter.build_report(bundle)
    assert "## Vendor Blocker Table" in report
    assert "## Evidence Table" in report
    assert "## Change Checklist" in report
    assert "## Technical Appendix" in report


def test_evidence_table_lists_matched_signals_for_persisted_risk_asset():
    bundle = {
        "assets": [
            _windows_host("ssh-gw", "critical", 80, {
                "weak_ssh_kex_detected": True,
                "legacy_ssh_host_key_detected": True,
            }),
        ],
    }
    report = reporter.build_report(bundle)
    assert "SHA-1-based Diffie-Hellman" in report
    assert "legacy host key algorithm" in report
    assert "| ssh-gw |" in report


def test_evidence_table_lists_matched_ipsec_signals():
    bundle = {
        "assets": [
            _windows_host("vpn-gw", "critical", 80, {
                "legacy_ipsec_dh_group_detected": True,
                "weak_ipsec_encryption_detected": True,
            }),
        ],
    }
    report = reporter.build_report(bundle)
    assert "legacy Diffie-Hellman group" in report
    assert "weak or legacy encryption algorithm" in report
    assert "| vpn-gw |" in report


def test_evidence_table_lists_matched_ad_certificate_estate_signals():
    bundle = {
        "assets": [
            _windows_host("corp.example.local", "critical", 80, {
                "ad_weak_certificate_template_detected": True,
                "ad_ca_certificate_expiring_detected": True,
            }),
        ],
    }
    report = reporter.build_report(bundle)
    assert "a weak certificate template was found in Active Directory" in report
    assert "root Certificate Authority certificate close to expiry" in report
    assert "| corp.example.local |" in report


def test_evidence_table_lists_matched_ci_signing_signal():
    bundle = {
        "assets": [
            _windows_host("release-pipeline", "medium", 40, {"ci_signing_command_detected": True}),
        ],
    }
    report = reporter.build_report(bundle)
    assert "CI/CD pipeline signing command was detected" in report
    assert "| release-pipeline |" in report


def test_evidence_table_empty_state():
    bundle = {"assets": [_windows_host("clean-host", "minimal", 5, {})]}
    report = reporter.build_report(bundle)
    assert "_No evidence signals flagged across this workspace._" in report


def test_vendor_blocker_table_lists_blocked_asset():
    bundle = {"assets": [_windows_host("vendor-locked", "high", 70, {"vendor_blocked": True})]}
    report = reporter.build_report(bundle)
    assert "## Vendor Blocker Table" in report
    assert "vendor-locked" in report
    assert "escalate for a PQC-capable replacement timeline" in report


def test_vendor_blocker_table_empty_state():
    bundle = {"assets": [_windows_host("clean-host", "minimal", 5, {})]}
    report = reporter.build_report(bundle)
    assert "_No vendor blockers identified in this workspace._" in report


def test_change_checklist_includes_matched_items_and_rollback_note():
    bundle = {
        "assets": [
            _windows_host("repo-with-key", "critical", 95, {"embedded_private_key_in_repo_detected": True}),
        ],
    }
    report = reporter.build_report(bundle)
    assert "### repo-with-key (risk: critical)" in report
    assert "- [ ] Rotate the exposed key immediately" in report
    assert "- [ ] Document a rollback plan" in report


def test_change_checklist_empty_state():
    bundle = {"assets": [_windows_host("clean-host", "minimal", 5, {})]}
    report = reporter.build_report(bundle)
    assert "_No assets currently require a pre-change checklist._" in report


def test_technical_appendix_lists_raw_rationale_flags():
    bundle = {
        "assets": [
            _windows_host("dc-01", "critical", 90, {
                "windows_domain_controller": True,
                "windows_expired_certificates": True,
            }),
        ],
    }
    report = reporter.build_report(bundle)
    assert "### dc-01" in report
    assert "Rationale flags: windows_domain_controller, windows_expired_certificates" in report


def test_technical_appendix_no_flags_set():
    bundle = {"assets": [_windows_host("clean-host", "minimal", 5, {})]}
    report = reporter.build_report(bundle)
    assert "_none set_" in report
