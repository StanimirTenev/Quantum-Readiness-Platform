from app.change_assistant import build_change_plan


def _risk(rating="critical", score=90.0, rationale=None, vendor_blocked=False, dependency_count=0):
    return {
        "rating": rating,
        "normalized_score_100": score,
        "rationale": rationale or {},
        "vendor_blocked": vendor_blocked,
        "dependency_count": dependency_count,
    }


def _plan(wave_1=None, wave_2=None, wave_3=None):
    return {"wave_1": wave_1 or [], "wave_2": wave_2 or [], "wave_3": wave_3 or []}


def test_no_risk_data_returns_early_with_safety_notice():
    result = build_change_plan("asset-a", {"risks": []}, _plan(), [])
    assert "cannot be drafted" in result["narrative"]
    assert "does not execute changes" in result["narrative"]
    assert result["pre_change_checklist"] == []


def test_checklist_includes_matched_rationale_items():
    risk = _risk(rationale={"weak_public_key_detected": True, "expiring_certificate_detected": True})
    result = build_change_plan("asset-a", {"risks": [risk]}, _plan(), [])
    checklist_text = " ".join(result["pre_change_checklist"])
    assert "PQC-capable" in checklist_text
    assert "renewal/replacement certificate" in checklist_text


def test_checklist_includes_vendor_blocked_note():
    risk = _risk(vendor_blocked=True)
    result = build_change_plan("asset-a", {"risks": [risk]}, _plan(), [])
    assert any("vendor escalation ticket" in item for item in result["pre_change_checklist"])


def test_checklist_includes_dependency_count_note():
    risk = _risk(dependency_count=4)
    result = build_change_plan("asset-a", {"risks": [risk]}, _plan(), [])
    assert any("4 dependent system(s)" in item for item in result["pre_change_checklist"])


def test_checklist_always_includes_rollback_note():
    result = build_change_plan("asset-a", {"risks": [_risk()]}, _plan(), [])
    assert any("rollback plan" in item for item in result["pre_change_checklist"])


def test_wave_is_looked_up_from_plan_data():
    item = {"asset_name": "asset-a"}
    result = build_change_plan("asset-a", {"risks": [_risk()]}, _plan(wave_1=[item]), [])
    assert result["wave"] == "wave_1"
    assert "Wave 1 (urgent)" in result["narrative"]


def test_no_wave_match_leaves_wave_none():
    result = build_change_plan("asset-a", {"risks": [_risk()]}, _plan(), [])
    assert result["wave"] is None


def test_existing_task_is_referenced_not_duplicated():
    tasks = [{"id": "task-1", "asset_name": "asset-a", "status": "draft"}]
    result = build_change_plan("asset-a", {"risks": [_risk()]}, _plan(), tasks)
    assert result["existing_task"]["id"] == "task-1"
    assert "already tracks this asset" in result["narrative"]
    assert "task-1" in result["narrative"]


def test_no_existing_task_suggests_creating_one():
    result = build_change_plan("asset-a", {"risks": [_risk()]}, _plan(), [])
    assert result["existing_task"] is None
    assert "No existing workflow task found" in result["narrative"]


def test_picks_highest_scoring_risk_when_multiple_present():
    risks = [_risk(rating="low", score=20.0), _risk(rating="critical", score=95.0)]
    result = build_change_plan("asset-a", {"risks": risks}, _plan(), [])
    assert result["rating"] == "critical"


def test_safety_notice_always_present():
    result = build_change_plan("asset-a", {"risks": [_risk()]}, _plan(), [])
    assert "does not execute changes" in result["safety_notice"]
    assert "Trust Zone 4" in result["safety_notice"]
