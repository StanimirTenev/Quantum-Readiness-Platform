import json
from pathlib import Path


SCHEMA_PATH = Path("shared/schemas/core-flow.contract.json")


def load_schema() -> dict:
    with SCHEMA_PATH.open("r", encoding="utf-8") as schema_file:
        return json.load(schema_file)


def test_core_flow_contract_requires_stage1_version_and_stage_map():
    schema = load_schema()

    assert schema["properties"]["contract_version"]["const"] == "stage1-v1"
    assert set(schema["properties"]["stages"]["required"]) == {
        "evidence",
        "inventory",
        "risk",
        "planning",
        "workflow",
        "dashboard",
    }


def test_risk_engine_request_contract_enforces_quantum_risk_fields():
    schema = load_schema()
    request_def = schema["$defs"]["riskEngineScoreRequest"]

    assert request_def["additionalProperties"] is False
    assert set(request_def["required"]) == {
        "contract_version",
        "asset_name",
        "criticality",
        "confidentiality_lifetime",
        "quantum_exposure",
        "blast_radius",
        "vendor_lock_in",
        "migration_difficulty",
        "dependency_count",
        "vendor_blocked",
        "scenario",
    }


def test_planner_item_contract_enforces_required_output_fields():
    schema = load_schema()
    planner_item_def = schema["$defs"]["plannerItem"]

    assert planner_item_def["additionalProperties"] is False
    assert set(planner_item_def["required"]) == {
        "asset_name",
        "asset_type",
        "rating",
        "normalized_score_100",
        "priority_score_100",
        "scenario",
        "dependency_count",
        "vendor_blocked",
        "recommended_action",
    }
