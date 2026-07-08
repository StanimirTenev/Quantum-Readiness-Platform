from app.migration_planner import build_migration_plan_summary


def _plan(wave_1=None, wave_2=None, wave_3=None):
    wave_1, wave_2, wave_3 = wave_1 or [], wave_2 or [], wave_3 or []
    return {
        "summary": {
            "total_assets": len(wave_1) + len(wave_2) + len(wave_3),
            "total_risks": len(wave_1) + len(wave_2) + len(wave_3),
            "wave_1_count": len(wave_1),
            "wave_2_count": len(wave_2),
            "wave_3_count": len(wave_3),
        },
        "wave_1": wave_1,
        "wave_2": wave_2,
        "wave_3": wave_3,
    }


def _item(asset_name="asset-a", rating="critical", score=90.0, reasons=None, vendor_blocked=False, action="Escalate immediately."):
    return {
        "asset_name": asset_name,
        "rating": rating,
        "priority_score_100": score,
        "planning_reasons": reasons or [],
        "vendor_blocked": vendor_blocked,
        "recommended_action": action,
    }


def test_wave_summary_counts_and_labels():
    plan_data = _plan(wave_1=[_item()], wave_2=[_item("asset-b", "medium", 50.0)])
    result = build_migration_plan_summary(plan_data, [])
    wave_1 = result["waves"][0]
    assert wave_1["label"] == "Wave 1 (urgent)"
    assert "1 asset(s)" in wave_1["summary"]
    assert result["waves"][2]["summary"].endswith("no assets currently placed here.")


def test_item_narrative_includes_matched_planning_reasons():
    item = _item(reasons=["stage2_weak_public_key", "stage2_expiring_certificate", "priority_score_computed"])
    result = build_migration_plan_summary(_plan(wave_1=[item]), [])
    narrative = result["waves"][0]["assets"][0]["narrative"]
    assert "weak/undersized public key" in narrative
    assert "close to expiry" in narrative
    # bookkeeping-only code must not leak into the narrative text
    assert "priority_score_computed" not in narrative


def test_item_narrative_falls_back_when_no_reasons_matched():
    item = _item(reasons=["priority_score_computed"])
    result = build_migration_plan_summary(_plan(wave_1=[item]), [])
    narrative = result["waves"][0]["assets"][0]["narrative"]
    assert "no specific evidence signals were flagged" in narrative


def test_vendor_blocked_item_is_flagged_in_narrative_and_wave_summary():
    item = _item(vendor_blocked=True)
    result = build_migration_plan_summary(_plan(wave_1=[item]), [])
    assert "vendor readiness blocker is in effect" in result["waves"][0]["assets"][0]["narrative"]
    assert "1 blocked by vendor readiness" in result["waves"][0]["summary"]


def test_vendor_readiness_context_with_no_documents():
    result = build_migration_plan_summary(_plan(), [])
    assert "No vendor documents have been analyzed" in result["vendor_readiness_context"]["note"]


def test_vendor_readiness_context_flags_blocked_documents():
    readiness_matrix = [
        {"doc_id": "vendor-a.md", "product_hint": "Vendor A", "has_migration_blocker": True},
        {"doc_id": "vendor-b.md", "product_hint": "Vendor B", "has_migration_blocker": False},
    ]
    result = build_migration_plan_summary(_plan(), readiness_matrix)
    context = result["vendor_readiness_context"]
    assert context["blocked_document_count"] == 1
    assert context["documents_reviewed"] == 2
    assert "Vendor A" in context["note"]
    assert "Vendor B" not in context["note"]


def test_vendor_readiness_context_with_no_blockers():
    readiness_matrix = [{"doc_id": "vendor-c.md", "product_hint": "Vendor C", "has_migration_blocker": False}]
    result = build_migration_plan_summary(_plan(), readiness_matrix)
    assert "no migration blockers found" in result["vendor_readiness_context"]["note"]


def test_narrative_mentions_wave_counts():
    plan_data = _plan(wave_1=[_item()], wave_2=[_item("asset-b")], wave_3=[_item("asset-c")])
    result = build_migration_plan_summary(plan_data, [])
    assert "1 in Wave 1" in result["narrative"]
    assert "1 in Wave 2" in result["narrative"]
    assert "1 in Wave 3" in result["narrative"]


def test_empty_plan_produces_no_crash():
    result = build_migration_plan_summary(_plan(), [])
    assert result["summary"]["total_assets"] == 0
    assert all(wave["assets"] == [] for wave in result["waves"])
