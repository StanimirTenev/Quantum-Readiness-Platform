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
