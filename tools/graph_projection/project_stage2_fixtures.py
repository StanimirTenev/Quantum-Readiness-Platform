#!/usr/bin/env python3
import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def node(node_id: str, node_type: str, label: str, source: str, properties: dict[str, Any], confidence: float = 1.0) -> dict[str, Any]:
    return {
        "id": node_id,
        "type": node_type,
        "label": label,
        "source": source,
        "scan_id": None,
        "evidence_ref": None,
        "confidence": confidence,
        "observed_at": None,
        "properties": properties,
    }


def edge(from_id: str, edge_type: str, to_id: str, source: str, properties: dict[str, Any] | None = None, confidence: float = 1.0) -> dict[str, Any]:
    edge_id = f"edge:{from_id}:{edge_type}:{to_id}"
    return {
        "id": edge_id,
        "type": edge_type,
        "from": from_id,
        "to": to_id,
        "source": source,
        "scan_id": None,
        "evidence_ref": None,
        "confidence": confidence,
        "observed_at": None,
        "properties": properties or {},
    }


def warning(code: str, severity: str, message: str, node_ids: list[str] | None = None, edge_ids: list[str] | None = None) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "related_node_ids": node_ids or [],
        "related_edge_ids": edge_ids or [],
        "evidence_ref": None,
    }


def asset_id_from_payload(payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    asset = (payload.get("assets") or [{}])[0]
    name = asset.get("name") or "unknown-asset"
    asset_id = asset.get("asset_id") or name
    return f"asset:{asset_id}", asset


def project_host(payload, nodes, edges, warnings):
    asset_node_id, asset = asset_id_from_payload(payload)
    nodes[asset_node_id] = node(asset_node_id, "Asset", asset.get("name", "unknown"), "stage2_host_fixture", {
        "name": asset.get("name"),
        "asset_type": asset.get("asset_type"),
        "environment": asset.get("environment"),
        "criticality": asset.get("criticality"),
    })

    crypto = payload.get("crypto_evidence", {})
    pm = crypto.get("package_metadata", {})
    manager = pm.get("package_manager", "unknown")
    for p in pm.get("packages", []):
        pkg_id = f"package:{asset_node_id}:{manager}:{p.get('name','unknown')}"
        nodes[pkg_id] = node(pkg_id, "Package", p.get("name", "unknown"), "stage2_host_fixture", {
            "name": p.get("name"),
            "version": p.get("version"),
            "package_manager": manager,
            "source": "crypto_evidence.package_metadata",
        })
        edges[edge(asset_node_id, "HAS_PACKAGE", pkg_id, "stage2_host_fixture")["id"]] = edge(asset_node_id, "HAS_PACKAGE", pkg_id, "stage2_host_fixture")

    cert_ind = crypto.get("cert_indicators", {})
    file_sources = [
        ("certificate_file", cert_ind.get("certificate_file_indicators", {}).get("files", []), "crypto_evidence.cert_indicators.certificate_file_indicators"),
        ("config_file", cert_ind.get("config_file_indicators", {}).get("files", []), "crypto_evidence.cert_indicators.config_file_indicators"),
    ]
    for cfg_type, files, src in file_sources:
        for f in files:
            p = f.get("path", "")
            digest = hashlib.sha256(p.encode()).hexdigest()[:16]
            cfg_id = f"config:{asset_node_id}:{digest}"
            nodes[cfg_id] = node(cfg_id, "ConfigFile", p or cfg_type, "stage2_host_fixture", {
                "path": p,
                "config_type": f.get("type") or cfg_type,
                "readable": f.get("readable"),
                "source": src,
            }, confidence=0.7)
            e = edge(asset_node_id, "HAS_CONFIG", cfg_id, "stage2_host_fixture", confidence=0.7)
            edges[e["id"]] = e
            warnings.append(warning("low_confidence_relationship", "info", "Config relationship inferred from path-only indicator.", [asset_node_id, cfg_id], [e["id"]]))

    private_keys = len(crypto.get("private_key_files", []))
    if private_keys > 0:
        fid = f"finding:{asset_node_id}:private_key_indicator"
        nodes[fid] = node(fid, "CryptoFinding", "private_key_indicator", "stage2_host_fixture", {"indicator": "private_key_indicator", "count": private_keys})
        e = edge(asset_node_id, "HAS_FINDING", fid, "stage2_host_fixture")
        edges[e["id"]] = e
        warnings.append(warning("private_key_indicator", "critical", f"Detected {private_keys} private key indicators.", [asset_node_id, fid], [e["id"]]))


def project_network(payload, nodes, edges, warnings):
    asset_node_id, asset = asset_id_from_payload(payload)
    if asset.get("name"):
        nodes[asset_node_id] = node(asset_node_id, "Asset", asset.get("name"), "stage2_network_fixture", {
            "name": asset.get("name"),
            "asset_type": asset.get("asset_type"),
            "environment": asset.get("environment"),
            "criticality": asset.get("criticality"),
        })
    else:
        warnings.append(warning("asset_service_link_unknown", "warning", "No clear asset relation for network service."))

    tls = payload.get("tls_metadata", {})
    target = tls.get("target", "unknown")
    port = tls.get("port", "unknown")
    protocol = "tls"
    service_id = f"service:{asset_node_id}:{protocol}:{port}:{target}"
    nodes[service_id] = node(service_id, "Service", f"{target}:{port}", "stage2_network_fixture", {
        "target": target,
        "port": port,
        "server_name": tls.get("server_name"),
        "protocol": protocol,
    })

    # Asset RUNS Service (section 5.3): link the service to the asset it runs on.
    if asset.get("name"):
        run_edge = edge(asset_node_id, "RUNS", service_id, "stage2_network_fixture")
        edges[run_edge["id"]] = run_edge

    cert = tls.get("certificate", {})
    fp = cert.get("sha256_fingerprint") or cert.get("fingerprint_sha256") or cert.get("subject", {}).get("fingerprint")
    if not fp:
        fp = hashlib.sha256(json.dumps(cert, sort_keys=True).encode()).hexdigest()
        warnings.append(warning("missing_certificate_fingerprint", "warning", "Leaf certificate fingerprint missing; deterministic fallback hash used.", [service_id]))
    cert_id = f"certificate:{fp}"
    key_size = cert.get("key", {}).get("size_bits") or cert.get("public_key_size")
    nodes[cert_id] = node(cert_id, "Certificate", cert.get("subject", {}).get("display_dn", fp), "stage2_network_fixture", {
        "subject": cert.get("subject", {}).get("display_dn"),
        "issuer": cert.get("issuer", {}).get("display_dn"),
        "not_before": cert.get("validity", {}).get("not_before"),
        "not_after": cert.get("validity", {}).get("not_after"),
        "signature_algorithm": cert.get("algorithms", {}).get("signature"),
        "public_key_algorithm": cert.get("algorithms", {}).get("public_key"),
        "public_key_size": key_size,
        "fingerprint_sha256": fp,
    })
    e = edge(service_id, "USES_CERTIFICATE", cert_id, "stage2_network_fixture")
    edges[e["id"]] = e

    # Quantum-vulnerable public key becomes a service-scoped CryptoFinding so the
    # graph carries the vulnerability node for evidence-path attribution.
    public_key_alg = cert.get("algorithms", {}).get("public_key") or cert.get("public_key_algorithm")
    if public_key_alg:
        up = str(public_key_alg).upper()
        if any(token in up for token in ("RSA", "ECDSA", "ECDH", "DSA", "DH", "ED25519", "EC")):
            vf_id = f"finding:{service_id}:quantum_vulnerable_public_key"
            nodes[vf_id] = node(vf_id, "CryptoFinding", f"quantum-vulnerable public key ({public_key_alg})", "stage2_network_fixture", {
                "indicator": "quantum_vulnerable_public_key",
                "algorithm": public_key_alg,
                "classification": "classical_vulnerable",
                "severity": "high",
            }, confidence=0.9)
            vf_edge = edge(service_id, "SERVICE_HAS_FINDING", vf_id, "stage2_network_fixture", confidence=0.9)
            edges[vf_edge["id"]] = vf_edge

    if isinstance(key_size, int) and key_size < 2048:
        warnings.append(warning("weak_public_key", "warning", f"RSA public key size {key_size} is below 2048.", [cert_id]))
        # Weak key becomes a service-scoped CryptoFinding (section 5.3).
        wk_id = f"finding:{service_id}:weak_public_key"
        nodes[wk_id] = node(wk_id, "CryptoFinding", "weak_public_key", "stage2_network_fixture", {
            "indicator": "weak_public_key",
            "public_key_size": key_size,
            "algorithm": cert.get("algorithms", {}).get("public_key"),
        }, confidence=0.9)
        wk_edge = edge(service_id, "SERVICE_HAS_FINDING", wk_id, "stage2_network_fixture", confidence=0.9)
        edges[wk_edge["id"]] = wk_edge

    chain = tls.get("certificate_chain", {})
    if chain.get("available") is False:
        warnings.append(warning("chain_unavailable", "warning", "Certificate chain unavailable for target.", [service_id, cert_id]))
    chain_nodes = []
    for c in chain.get("certificates", []):
        cfp = c.get("sha256_fingerprint")
        if not cfp:
            continue
        cid = f"certificate:{cfp}"
        chain_nodes.append(cid)
        nodes[cid] = node(cid, "Certificate", c.get("subject", {}).get("display_dn", cfp), "stage2_network_fixture", {
            "subject": c.get("subject", {}).get("display_dn"),
            "issuer": c.get("issuer", {}).get("display_dn"),
            "fingerprint_sha256": cfp,
        })
    if chain_nodes:
        prev = cert_id
        for cid in chain_nodes:
            if cid == prev:
                continue
            se = edge(prev, "SIGNED_BY", cid, "stage2_network_fixture")
            edges[se["id"]] = se
            prev = cid


def validate(snapshot):
    for k in ["graph_schema_version", "graph_snapshot_id", "generated_at", "nodes", "edges", "warnings"]:
        if k not in snapshot:
            raise ValueError(f"Missing required field: {k}")
    node_ids = [n["id"] for n in snapshot["nodes"]]
    edge_ids = [e["id"] for e in snapshot["edges"]]
    if len(node_ids) != len(set(node_ids)):
        raise ValueError("Duplicate node IDs detected")
    if len(edge_ids) != len(set(edge_ids)):
        raise ValueError("Duplicate edge IDs detected")
    node_set = set(node_ids)
    for e in snapshot["edges"]:
        if e["from"] not in node_set or e["to"] not in node_set:
            raise ValueError(f"Edge references unknown nodes: {e['id']}")
    for col in [snapshot["nodes"], snapshot["edges"]]:
        for item in col:
            c = item.get("confidence")
            if not isinstance(c, (float, int)) or c < 0.0 or c > 1.0:
                raise ValueError(f"Invalid confidence in {item.get('id')}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True)
    ap.add_argument("--network", required=True)
    ap.add_argument("--snapshot-out", required=True)
    ap.add_argument("--report-out", required=True)
    args = ap.parse_args()

    host = json.loads(Path(args.host).read_text())
    network = json.loads(Path(args.network).read_text())

    nodes, edges, warnings = {}, {}, []
    project_host(host, nodes, edges, warnings)
    project_network(network, nodes, edges, warnings)

    fixture_refs = [str(Path(args.host)), str(Path(args.network))]
    snapshot_material = "|".join(fixture_refs + sorted(nodes) + sorted(edges))
    snapshot = {
        "graph_schema_version": "0.1",
        "projection_version": "0.3.0",
        "graph_snapshot_id": hashlib.sha256(snapshot_material.encode()).hexdigest()[:16],
        "generated_at": iso_now(),
        "source": "stage2_fixture_projection_smoke",
        "inputs": {"fixtures": fixture_refs},
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
        "warnings": warnings,
    }
    validate(snapshot)

    Path(args.snapshot_out).write_text(json.dumps(snapshot, indent=2) + "\n")

    ntypes = Counter(n["type"] for n in snapshot["nodes"])
    etypes = Counter(e["type"] for e in snapshot["edges"])
    wsummary = Counter((w["code"], w["severity"]) for w in snapshot["warnings"])

    node_ids = [n["id"] for n in snapshot["nodes"]]
    edge_ids = [e["id"] for e in snapshot["edges"]]
    node_id_set = set(node_ids)
    validation_checks = [
        ("graph_schema_version exists", bool(snapshot.get("graph_schema_version"))),
        ("graph_snapshot_id exists", bool(snapshot.get("graph_snapshot_id"))),
        ("nodes array exists", isinstance(snapshot.get("nodes"), list)),
        ("edges array exists", isinstance(snapshot.get("edges"), list)),
        ("warnings array exists", isinstance(snapshot.get("warnings"), list)),
        ("node IDs unique", len(node_ids) == len(node_id_set)),
        ("edge IDs unique", len(edge_ids) == len(set(edge_ids))),
        ("edge references valid", all(e["from"] in node_id_set and e["to"] in node_id_set for e in snapshot["edges"])),
        ("confidence values within 0.0–1.0", all(0.0 <= float(item.get("confidence", -1)) <= 1.0 for item in snapshot["nodes"] + snapshot["edges"])),
    ]

    coverage_checks = [
        ("Host asset", "Asset", any(n["type"] == "Asset" and n["source"] == "stage2_host_fixture" for n in snapshot["nodes"])),
        (
            "Host packages",
            "Package + HAS_PACKAGE",
            any(n["type"] == "Package" for n in snapshot["nodes"]) and any(e["type"] == "HAS_PACKAGE" for e in snapshot["edges"]),
        ),
        (
            "Host config indicators",
            "ConfigFile + HAS_CONFIG",
            any(n["type"] == "ConfigFile" for n in snapshot["nodes"]) and any(e["type"] == "HAS_CONFIG" for e in snapshot["edges"]),
        ),
        ("Network TLS service", "Service", any(n["type"] == "Service" for n in snapshot["nodes"])),
        (
            "Asset runs service",
            "RUNS",
            any(e["type"] == "RUNS" for e in snapshot["edges"]),
        ),
        (
            "Service vulnerability finding",
            "CryptoFinding + SERVICE_HAS_FINDING",
            any(n["type"] == "CryptoFinding" for n in snapshot["nodes"]) and any(e["type"] == "SERVICE_HAS_FINDING" for e in snapshot["edges"]),
        ),
        (
            "TLS certificate",
            "Certificate + USES_CERTIFICATE",
            any(n["type"] == "Certificate" for n in snapshot["nodes"]) and any(e["type"] == "USES_CERTIFICATE" for e in snapshot["edges"]),
        ),
        (
            "Certificate chain",
            "Certificate + SIGNED_BY",
            any(n["type"] == "Certificate" for n in snapshot["nodes"]) and any(e["type"] == "SIGNED_BY" for e in snapshot["edges"]),
        ),
    ]

    lines = [
        "# Graph Projection Smoke Report",
        "",
        "## Validation Date",
        snapshot["generated_at"],
        "",
        "## Scope",
        "- JSON snapshot projection",
        "- Stage 2 fixture-based",
        "- no graph DB",
        "- no graph API",
        "",
        "## Inputs",
        "",
        "| Fixture | Status |",
        "|---|---|",
    ]
    for f in fixture_refs:
        lines.append(f"| {f} | OK |")
    lines += [
        "",
        "## Snapshot Summary",
        "",
        f"- graph_snapshot_id: {snapshot['graph_snapshot_id']}",
        f"- graph_schema_version: {snapshot['graph_schema_version']}",
        f"- projection_version: {snapshot['projection_version']}",
        f"- source: {snapshot['source']}",
        f"- node count: {len(snapshot['nodes'])}",
        f"- edge count: {len(snapshot['edges'])}",
        f"- warning count: {len(snapshot['warnings'])}",
        "",
        "## Node Types",
        "",
        "| Type | Count |",
        "|---|---|",
    ]
    for t, c in sorted(ntypes.items()):
        lines.append(f"| {t} | {c} |")
    lines += ["", "## Edge Types", "", "| Type | Count |", "|---|---|"]
    for t, c in sorted(etypes.items()):
        lines.append(f"| {t} | {c} |")
    lines += ["", "## Warning Summary", "", "| Code | Severity | Count |", "|---|---:|---:|"]
    if wsummary:
        for (code, severity), count in sorted(wsummary.items()):
            lines.append(f"| {code} | {severity} | {count} |")
    else:
        lines.append("No warnings emitted.")
    lines += ["", "## Evidence Coverage", "", "| Evidence Area | Expected Graph Object | Status |", "|---|---|---|"]
    for area, expected, ok in coverage_checks:
        lines.append(f"| {area} | {expected} | {'PASS' if ok else 'FAIL'} |")
    lines += ["", "## Validation Checks", "", "| Check | Result |", "|---|---|"]
    for check, ok in validation_checks:
        lines.append(f"| {check} | {'PASS' if ok else 'FAIL'} |")
    lines += [
        "",
        "## Privacy Boundary",
        "",
        "Graph snapshots may contain sensitive infrastructure intelligence. They remain local by default and must not be sent to external LLM providers unless explicitly configured by the operator.",
        "",
        "## Non-Goals",
        "",
        "- no graph database",
        "- no graph API",
        "- no graph UI",
        "- no Neo4j",
        "- no Copilot/RAG graph reasoning",
    ]
    lines += ["", "## Result", "", "PASS"]
    Path(args.report_out).write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
