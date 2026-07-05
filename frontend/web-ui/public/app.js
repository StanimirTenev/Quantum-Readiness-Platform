"use strict";

// ---------------------------------------------------------------------------
// Quantum Readiness Console — buildless frontend for the QRP API Gateway.
// ---------------------------------------------------------------------------
const $ = (id) => document.getElementById(id);

function gateway() {
  return $("gateway-url").value.trim().replace(/\/+$/, "");
}

function setMsg(text, isError) {
  const el = $("msg");
  el.textContent = text || "";
  el.classList.toggle("error", !!isError);
}

async function api(method, path, body) {
  const opts = { method, headers: { Accept: "application/json" } };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(gateway() + path, opts);
  const text = await res.text();
  let data;
  try { data = text ? JSON.parse(text) : {}; } catch { data = { detail: text }; }
  if (!res.ok) {
    const detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail || data);
    throw new Error(`${res.status}: ${detail}`);
  }
  return data;
}

function pill(text, kind) {
  return `<span class="pill pill-${kind}">${text}</span>`;
}

function esc(value) {
  return String(value ?? "").replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

// --- Tabs ---
document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    tab.classList.add("active");
    $(tab.dataset.tab).classList.add("active");
  });
});

// --- Connection check ---
$("check-conn").addEventListener("click", async () => {
  const status = $("conn-status");
  status.className = "pill pill-muted";
  status.textContent = "checking";
  try {
    const data = await api("GET", "/health");
    status.className = "pill pill-ok";
    status.textContent = data.status === "ok" ? "connected" : "unknown";
    setMsg("Gateway healthy: " + (data.service || ""));
  } catch (err) {
    status.className = "pill pill-err";
    status.textContent = "offline";
    setMsg(err.message, true);
  }
});

// --- Fingerprint ---
$("fp-run").addEventListener("click", async () => {
  const algos = $("fp-algos").value.split(/[\n,]+/).map((s) => s.trim()).filter(Boolean);
  const payload = { asset_name: $("fp-asset").value || "asset", algorithms: algos };
  const sig = $("fp-sig").value.trim();
  const pub = $("fp-pub").value.trim();
  const bits = parseInt($("fp-bits").value, 10);
  if (sig || pub || Number.isFinite(bits)) {
    const cert = { algorithms: {} };
    if (sig) cert.algorithms.signature = sig;
    if (pub) cert.algorithms.public_key = pub;
    if (Number.isFinite(bits)) cert.key = { size_bits: bits };
    payload.tls_metadata = { certificate: cert };
  }
  setMsg("Fingerprinting...");
  try {
    const data = await api("POST", "/api/fingerprint", payload);
    renderFingerprint(data);
    setMsg("Done.");
  } catch (err) { setMsg(err.message, true); }
});

function renderFingerprint(data) {
  const s = data.summary || {};
  $("fp-summary").innerHTML = [
    stat("Readiness", s.pqc_readiness || "-"),
    stat("Quantum-vulnerable", s.quantum_vulnerable_count ?? 0),
    stat("PQC-ready", s.pqc_ready_count ?? 0),
    stat("Weak", s.weak_count ?? 0),
    stat("HNDL", s.hndl_exposure ? "yes" : "no"),
    stat("Highest", pill(s.highest_severity || "info", s.highest_severity || "info")),
  ].join("");

  const rows = (data.findings || []).map((f) => `
    <tr>
      <td class="mono">${esc(f.raw_value)}</td>
      <td>${esc(f.algorithm_family)}</td>
      <td>${classPill(f.classification)}</td>
      <td>${f.quantum_vulnerable ? '<span class="badge-yes">yes</span>' : '<span class="badge-no">no</span>'}</td>
      <td>${f.harvest_now_decrypt_later ? '<span class="badge-yes">yes</span>' : '<span class="badge-no">no</span>'}</td>
      <td>${pill(f.severity, f.severity)}</td>
      <td>${esc(f.reason)}</td>
    </tr>`).join("");
  $("fp-result").innerHTML = data.findings && data.findings.length
    ? `<div class="table-scroll"><table>
        <tr><th>Value</th><th>Family</th><th>Class</th><th>Q-vuln</th><th>HNDL</th><th>Severity</th><th>Reason</th></tr>
        ${rows}</table></div>`
    : '<p class="hint">No findings.</p>';
}

function classPill(cls) {
  if (cls === "classical_vulnerable") return pill("classical", "high");
  if (cls === "pqc_ready") return pill("pqc-ready", "pqc");
  if (cls === "deprecated_weak") return pill("weak", "critical");
  if (cls === "symmetric_reduced") return pill("symmetric", "low");
  if (cls === "hash") return pill("hash", "info");
  return pill(cls || "unknown", "minimal");
}

function stat(k, v) {
  return `<div class="stat"><div class="k">${esc(k)}</div><div class="v">${v}</div></div>`;
}

// --- Scenarios ---
async function loadScenarios() {
  try {
    const data = await api("GET", "/api/algorithms"); // warm connection; ignore result
  } catch { /* ignore */ }
  const known = ["public_timeline", "early_break", "hidden_capability", "hndl_active_now",
    "partial_break", "vendor_lag", "compliance_pressure"];
  $("sc-scenario").innerHTML = known.map((s) => `<option value="${s}">${s}</option>`).join("");
  $("sc-scenario").value = "hidden_capability";
}

$("sc-run").addEventListener("click", async () => {
  const assets = $("sc-assets").value.split(/\n+/).map((line) => {
    const [name, score] = line.split("=");
    if (!name || score === undefined) return null;
    const base = parseFloat(score);
    if (!name.trim() || !Number.isFinite(base)) return null;
    return { asset_name: name.trim(), base_score: base };
  }).filter(Boolean);
  setMsg("Running scenario...");
  try {
    const data = await api("POST", "/api/scenarios/run", { scenario: $("sc-scenario").value, assets });
    $("sc-summary").innerHTML = [
      stat("Scenario", esc(data.scenario)),
      stat("Multiplier", "×" + data.scenario_multiplier),
      stat("Assets", data.asset_count),
      stat("Highest", pill(data.highest_rating, data.highest_rating)),
    ].join("");
    const rows = (data.results || []).map((r) => `
      <tr><td>${esc(r.asset_name)}</td><td>${r.base_score}</td>
      <td>${r.final_score}</td><td>${r.normalized_score_100}</td>
      <td>${pill(r.rating, r.rating)}</td></tr>`).join("");
    $("sc-result").innerHTML = `<div class="table-scroll"><table>
      <tr><th>Asset</th><th>Base</th><th>Final</th><th>Normalized</th><th>Rating</th></tr>
      ${rows}</table></div>`;
    setMsg("Done.");
  } catch (err) { setMsg(err.message, true); }
});

// --- Integrations ---
async function loadIntegrationActions() {
  const actions = ["issue_certificate", "rotate_certificate", "revoke_certificate",
    "rotate_key", "sign_artifact", "update_trust_anchor", "open_ticket"];
  $("in-action").innerHTML = actions.map((a) => `<option>${a}</option>`).join("");
  $("in-action").value = "rotate_certificate";
}

$("in-run").addEventListener("click", async () => {
  const payload = {
    action: $("in-action").value,
    target_type: $("in-target").value,
    asset_name: $("in-asset").value || "asset",
    approved: $("in-approved").checked,
    approvals_provided: $("in-approvals").value.split(",").map((s) => s.trim()).filter(Boolean),
  };
  setMsg("Dry-run...");
  try {
    const data = await api("POST", "/api/integrations/dry-run", payload);
    const blocked = (data.blocked_reasons || []).map((b) => pill(b.replace(/_/g, " "), "err")).join(" ");
    $("in-result").innerHTML = `
      <div class="summary">
        ${stat("Executed", data.executed ? pill("yes", "critical") : pill("no", "ok"))}
        ${stat("Would execute*", data.would_execute_if_enabled ? "yes" : "no")}
        ${stat("Approvals ok", data.approvals_satisfied ? "yes" : "no")}
      </div>
      <p class="hint">Required approvals: <span class="mono">${esc((data.required_approvals || []).join(", ") || "none")}</span></p>
      <p class="hint">Blocked: ${blocked || "none"}</p>
      <p class="hint">*would_execute_if_enabled is a preview only; this service never executes.</p>`;
    setMsg("Done. Integrations are disabled by design.");
  } catch (err) { setMsg(err.message, true); }
});

// --- Algorithms ---
$("al-load").addEventListener("click", async () => {
  setMsg("Loading...");
  try {
    const data = await api("GET", "/api/algorithms");
    const rows = (data.algorithms || []).map((a) => `
      <tr><td>${esc(a.family)}</td><td>${classPill(a.classification)}</td>
      <td>${esc(a.kind)}</td><td>${a.hndl_capable ? '<span class="badge-yes">yes</span>' : '<span class="badge-no">no</span>'}</td></tr>`).join("");
    $("al-result").innerHTML = `<div class="table-scroll"><table>
      <tr><th>Family</th><th>Class</th><th>Kind</th><th>HNDL capable</th></tr>${rows}</table></div>`;
    setMsg("Done.");
  } catch (err) { setMsg(err.message, true); }
});

// --- Graph ---
function shortId(id) {
  const s = String(id || "");
  return s.length > 48 ? s.slice(0, 45) + "..." : s;
}

async function loadGraphNodes() {
  const select = $("gr-node");
  try {
    const data = await api("GET", "/graph/nodes");
    const nodes = data.nodes || [];
    select.innerHTML = nodes
      .map((n) => `<option value="${esc(n.id)}">${esc(n.label || n.id)} — ${esc(n.type || "")}</option>`)
      .join("");
    setMsg(`Loaded ${nodes.length} graph node(s).`);
  } catch (err) {
    select.innerHTML = "";
    setMsg("Could not load graph nodes: " + err.message, true);
  }
}

function grNode() {
  return $("gr-node").value;
}

$("gr-reload").addEventListener("click", loadGraphNodes);

$("gr-blast").addEventListener("click", async () => {
  const node_id = grNode();
  if (!node_id) return setMsg("Pick a node first.", true);
  setMsg("Computing blast radius...");
  try {
    const data = await api("POST", "/api/graph/blast-radius", { node_id });
    $("gr-summary").innerHTML = [
      stat("Node", esc(shortId(data.node_id))),
      stat("Affected", data.affected_count ?? 0),
    ].join("");
    const rows = (data.affected || []).map((a) => `
      <tr><td>${a.depth}</td><td class="mono">${esc(a.node_id)}</td>
      <td>${esc(a.node ? a.node.type : "")}</td><td>${esc(a.node ? a.node.label : "")}</td></tr>`).join("");
    $("gr-result").innerHTML = (data.affected && data.affected.length)
      ? `<div class="table-scroll"><table>
          <tr><th>Depth</th><th>Node</th><th>Type</th><th>Label</th></tr>${rows}</table></div>`
      : '<p class="hint">Nothing depends on this node (blast radius is empty).</p>';
    setMsg("Done.");
  } catch (err) { setMsg(err.message, true); }
});

$("gr-chain").addEventListener("click", async () => {
  const node_id = grNode();
  if (!node_id) return setMsg("Pick a node first.", true);
  setMsg("Following trust chain...");
  try {
    const data = await api("POST", "/api/graph/trust-chain", { node_id });
    $("gr-summary").innerHTML = [
      stat("Length", data.length ?? 0),
      stat("Root", esc(shortId(data.root || "-"))),
    ].join("");
    const parts = (data.chain || []).map((id, i) => {
      const n = (data.chain_nodes || [])[i];
      return `<span class="pill pill-info">${esc(n ? n.label : id)}</span>`;
    }).join(' <span class="arrow">→</span> ');
    $("gr-result").innerHTML = data.length > 1
      ? `<div class="chain">${parts}</div>`
      : '<p class="hint">No SIGNED_BY chain from this node.</p>';
    setMsg("Done.");
  } catch (err) { setMsg(err.message, true); }
});

$("gr-neighbors").addEventListener("click", async () => {
  const node_id = grNode();
  if (!node_id) return setMsg("Pick a node first.", true);
  setMsg("Loading neighbours...");
  try {
    const data = await api("POST", "/api/graph/neighbors", { node_id, direction: "both" });
    $("gr-summary").innerHTML = stat("Neighbours", data.neighbor_count ?? 0);
    const rows = (data.neighbors || []).map((n) => `
      <tr><td>${esc(n.direction)}</td><td>${esc(n.edge_type)}</td>
      <td class="mono">${esc(n.node_id)}</td><td>${esc(n.node ? n.node.type : "")}</td></tr>`).join("");
    $("gr-result").innerHTML = (data.neighbors && data.neighbors.length)
      ? `<div class="table-scroll"><table>
          <tr><th>Direction</th><th>Edge</th><th>Node</th><th>Type</th></tr>${rows}</table></div>`
      : '<p class="hint">No neighbours.</p>';
    setMsg("Done.");
  } catch (err) { setMsg(err.message, true); }
});

// Load graph nodes the first time the Graph tab is opened.
let graphNodesLoaded = false;
document.querySelector('.tab[data-tab="graph"]').addEventListener("click", () => {
  if (!graphNodesLoaded) { graphNodesLoaded = true; loadGraphNodes(); }
});

// --- Init ---
loadScenarios();
loadIntegrationActions();
