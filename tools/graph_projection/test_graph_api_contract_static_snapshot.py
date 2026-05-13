import json
from pathlib import Path

import pytest


SNAPSHOT_PATH = Path("reports/graph/latest/graph-snapshot.json")
FIXTURE_FALLBACK_PATH = Path("tools/graph_projection/test-fixtures/graph-snapshot-fixture.json")


def _load_snapshot_for_future_contract_tests():
    """Load an existing static snapshot for future Graph API contract tests only."""
    if SNAPSHOT_PATH.exists():
        return json.loads(SNAPSHOT_PATH.read_text()), SNAPSHOT_PATH

    if FIXTURE_FALLBACK_PATH.exists():
        return json.loads(FIXTURE_FALLBACK_PATH.read_text()), FIXTURE_FALLBACK_PATH

    pytest.skip(
        "Future Graph API contract tests require an existing static snapshot; "
        "missing reports/graph/latest/graph-snapshot.json and fixture fallback."
    )


def _build_snapshot_response(snapshot):
    return {
        "graph_schema_version": snapshot["graph_schema_version"],
        "nodes": snapshot["nodes"],
        "edges": snapshot["edges"],
        "warnings": snapshot["warnings"],
    }


def _build_summary_response(snapshot):
    return {
        "graph_schema_version": snapshot["graph_schema_version"],
        "node_count": len(snapshot["nodes"]),
        "edge_count": len(snapshot["edges"]),
        "warning_count": len(snapshot["warnings"]),
    }


def _build_nodes_response(snapshot):
    return {
        "graph_schema_version": snapshot["graph_schema_version"],
        "nodes": snapshot["nodes"],
    }


def _build_edges_response(snapshot):
    transformed_edges = [
        {
            "source": edge["from"],
            "target": edge["to"],
            "type": edge["type"],
            "id": edge.get("id"),
        }
        for edge in snapshot["edges"]
    ]
    return {
        "graph_schema_version": snapshot["graph_schema_version"],
        "edges": transformed_edges,
    }


def _build_warnings_response(snapshot):
    return {
        "graph_schema_version": snapshot["graph_schema_version"],
        "warnings": snapshot["warnings"],
    }


def test_future_graph_api_contract_static_snapshot_validates_top_level_fields_and_list_types():
    snapshot, _source_path = _load_snapshot_for_future_contract_tests()

    for field in ["graph_schema_version", "nodes", "edges", "warnings"]:
        assert field in snapshot

    assert isinstance(snapshot["nodes"], list)
    assert isinstance(snapshot["edges"], list)
    assert isinstance(snapshot["warnings"], list)


def test_future_graph_api_contract_static_snapshot_validates_required_node_and_edge_fields_and_references():
    snapshot, _source_path = _load_snapshot_for_future_contract_tests()

    node_ids = set()
    for node in snapshot["nodes"]:
        assert "id" in node
        assert "type" in node
        node_ids.add(node["id"])

    for edge in snapshot["edges"]:
        assert "from" in edge
        assert "to" in edge
        assert "type" in edge
        assert edge["from"] in node_ids
        assert edge["to"] in node_ids


def test_future_graph_api_contract_static_snapshot_can_build_read_only_response_shapes_in_test_helpers_only():
    snapshot, _source_path = _load_snapshot_for_future_contract_tests()

    snapshot_response = _build_snapshot_response(snapshot)
    summary_response = _build_summary_response(snapshot)
    nodes_response = _build_nodes_response(snapshot)
    edges_response = _build_edges_response(snapshot)
    warnings_response = _build_warnings_response(snapshot)

    assert set(snapshot_response) == {"graph_schema_version", "nodes", "edges", "warnings"}

    assert set(summary_response) == {
        "graph_schema_version",
        "node_count",
        "edge_count",
        "warning_count",
    }

    assert set(nodes_response) == {"graph_schema_version", "nodes"}

    assert set(edges_response) == {"graph_schema_version", "edges"}
    for edge in edges_response["edges"]:
        assert "source" in edge
        assert "target" in edge
        assert "type" in edge

    assert set(warnings_response) == {"graph_schema_version", "warnings"}


def test_future_graph_api_contract_static_snapshot_helpers_are_read_only_without_mutation_methods_or_graph_db_dependencies():
    helper_names = {
        _build_snapshot_response.__name__,
        _build_summary_response.__name__,
        _build_nodes_response.__name__,
        _build_edges_response.__name__,
        _build_warnings_response.__name__,
    }

    disallowed_mutation_tokens = {
        "create",
        "update",
        "delete",
        "mutate",
        "write",
        "insert",
        "patch",
        "upsert",
    }
    for name in helper_names:
        lowered = name.lower()
        assert not any(token in lowered for token in disallowed_mutation_tokens)

    imported_modules = set(globals())
    assert "neo4j" not in imported_modules
    assert "psycopg" not in imported_modules
    assert "sqlalchemy" not in imported_modules
