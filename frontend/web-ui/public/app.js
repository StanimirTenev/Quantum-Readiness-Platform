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
  payload.vendor_blocked = $("fp-vendor").checked;
  payload.hybrid_supported = $("fp-hybrid").checked;
  setMsg("Assessing...");
  try {
    const data = await api("POST", "/api/assess", payload);
    renderReadiness(data.pqc_readiness);
    renderFingerprint(data.fingerprint);
    setMsg("Done. Pipeline: " + (data.pipeline || []).join(" → "));
  } catch (err) { setMsg(err.message, true); }
});

function readinessKind(state) {
  return {
    classical_only: "high",
    hybrid_capable: "medium",
    pqc_ready: "pqc",
    vendor_blocked: "critical",
    unknown: "minimal",
  }[state] || "minimal";
}

function renderReadiness(r) {
  if (!r) { $("fp-readiness").innerHTML = ""; return; }
  const reasons = (r.reasons || []).map((x) => `<li>${esc(x)}</li>`).join("");
  $("fp-readiness").innerHTML =
    `<div class="readiness">
      <div class="readiness-head">
        <span class="k">PQC readiness</span>
        ${pill(String(r.readiness || "unknown").replace(/_/g, " "), readinessKind(r.readiness))}
        <span class="conf">confidence: ${esc(r.confidence || "-")}</span>
      </div>
      ${reasons ? `<ul class="readiness-reasons">${reasons}</ul>` : ""}
    </div>`;
}

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

// --- Graph diagram (inline SVG, no library) ---
const GTYPE_ORDER = ["Asset", "Service", "Certificate", "Package", "ConfigFile", "CryptoFinding", "MigrationTask", "Owner"];
const GTYPE_COLOR = {
  Asset: "#5b8cff", Service: "#4fd1c5", Certificate: "#ff9f45", Package: "#7bd88f",
  ConfigFile: "#9aa3b2", CryptoFinding: "#ff5c72", MigrationTask: "#ffd452", Owner: "#c58cff",
};
let graphData = { nodes: [], edges: [] };

async function loadGraphData() {
  try {
    const [nodesRes, edgesRes] = await Promise.all([
      api("GET", "/graph/nodes"),
      api("GET", "/graph/edges"),
    ]);
    graphData = { nodes: nodesRes.nodes || [], edges: edgesRes.edges || [] };
    renderGraphSvg([]);
  } catch (err) {
    setMsg("Could not load graph diagram: " + err.message, true);
  }
}

function truncate(text, n) {
  const s = String(text || "");
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}

function renderGraphSvg(highlightIds) {
  const highlight = new Set(highlightIds || []);
  const nodes = graphData.nodes;
  if (!nodes.length) { $("gr-graph").innerHTML = ""; return; }

  const colW = 210, rowH = 66, nodeW = 172, nodeH = 40, mX = 22, mY = 26;
  const byType = {};
  nodes.forEach((n) => { (byType[n.type] = byType[n.type] || []).push(n); });
  const types = [
    ...GTYPE_ORDER.filter((t) => byType[t]),
    ...Object.keys(byType).filter((t) => !GTYPE_ORDER.includes(t)),
  ];

  const pos = {};
  types.forEach((t, ci) => {
    byType[t].forEach((n, ri) => { pos[n.id] = { x: mX + ci * colW, y: mY + ri * rowH }; });
  });
  const width = mX * 2 + types.length * colW;
  const maxRows = Math.max(1, ...types.map((t) => byType[t].length));
  const height = mY * 2 + maxRows * rowH;
  const active = highlight.size > 0;
  const center = (id) => ({ x: pos[id].x + nodeW / 2, y: pos[id].y + nodeH / 2 });

  const edgeSvg = graphData.edges.map((e) => {
    if (!pos[e.from] || !pos[e.to]) return "";
    const a = center(e.from), b = center(e.to);
    const on = highlight.has(e.from) && highlight.has(e.to);
    const cls = "gedge" + (on ? " hl" : (active ? " dim" : ""));
    const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
    return `<line class="${cls}" x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" marker-end="url(#garrow)"><title>${esc(e.type)}</title></line>`
      + `<text class="gedge-label${on ? "" : (active ? " dim" : "")}" x="${mx}" y="${my - 3}" text-anchor="middle">${esc(e.type)}</text>`;
  }).join("");

  const nodeSvg = nodes.map((n) => {
    const p = pos[n.id];
    const color = GTYPE_COLOR[n.type] || "#9aa3b2";
    const on = highlight.has(n.id);
    const cls = "gnode" + (on ? " hl" : (active ? " dim" : ""));
    return `<g class="${cls}" data-node-id="${esc(n.id)}"><title>${esc(n.id)}</title>`
      + `<rect x="${p.x}" y="${p.y}" width="${nodeW}" height="${nodeH}" rx="8" fill="${color}22" stroke="${color}"></rect>`
      + `<text class="gtype" x="${p.x + 10}" y="${p.y + 15}">${esc(n.type)}</text>`
      + `<text x="${p.x + 10}" y="${p.y + 30}">${esc(truncate(n.label || n.id, 24))}</text>`
      + `</g>`;
  }).join("");

  $("gr-graph").innerHTML =
    `<svg viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" xmlns="http://www.w3.org/2000/svg">`
    + `<defs><marker id="garrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">`
    + `<path d="M0,0 L10,5 L0,10 z" fill="var(--muted)"></path></marker></defs>`
    + edgeSvg + nodeSvg + `</svg>`;
}

$("gr-diagram").addEventListener("click", () => renderGraphSvg([]));
$("gr-reload").addEventListener("click", () => { loadGraphNodes(); loadGraphData(); });

// Click a node in the diagram to select it and explore its blast radius.
$("gr-graph").addEventListener("click", (event) => {
  const group = event.target.closest(".gnode");
  if (!group) return;
  const id = group.getAttribute("data-node-id");
  if (!id) return;
  const select = $("gr-node");
  if (![...select.options].some((o) => o.value === id)) {
    const n = graphData.nodes.find((x) => x.id === id);
    const option = document.createElement("option");
    option.value = id;
    option.textContent = n ? `${n.label || id} — ${n.type}` : id;
    select.appendChild(option);
  }
  select.value = id;
  $("gr-blast").click();
});

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
    renderGraphSvg([data.node_id, ...(data.affected_node_ids || [])]);
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
    renderGraphSvg((data.chain && data.chain.length) ? data.chain : [node_id]);
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
    renderGraphSvg([node_id, ...(data.neighbors || []).map((n) => n.node_id)]);
    setMsg("Done.");
  } catch (err) { setMsg(err.message, true); }
});

$("gr-evidence").addEventListener("click", async () => {
  const node_id = grNode();
  if (!node_id) return setMsg("Pick a node first.", true);
  setMsg("Building evidence path...");
  try {
    const data = await api("POST", "/api/graph/evidence-path", { node_id });
    $("gr-summary").innerHTML = stat("Chain length", data.length ?? 0);
    const chain = data.chain || [];
    const parts = chain.map((c) =>
      `<span class="pill pill-info" title="${esc(c.node_id)}">${esc(c.role)}: ${esc(c.label || c.node_id)}</span>`
    ).join(' <span class="arrow">→</span> ');
    $("gr-result").innerHTML = chain.length
      ? `<div class="chain">${parts}</div>`
      : '<p class="hint">No attribution chain from this node.</p>';
    renderGraphSvg(chain.map((c) => c.node_id));
    setMsg("Done.");
  } catch (err) { setMsg(err.message, true); }
});

// Load graph nodes the first time the Graph tab is opened.
let graphNodesLoaded = false;
document.querySelector('.tab[data-tab="graph"]').addEventListener("click", () => {
  if (!graphNodesLoaded) { graphNodesLoaded = true; loadGraphNodes(); loadGraphData(); }
});

// --- Copilot ---
// A single result renderer handles all five subagents plus /query: show the
// plain-language narrative prominently, a few known list/table fields
// readably, and the raw JSON underneath so nothing is hidden.
function findingLine(item) {
  if (typeof item === "string") return item;
  if (item && typeof item === "object") {
    return item.finding || item.note || item.narrative || item.detail || JSON.stringify(item);
  }
  return String(item ?? "");
}

function renderList(title, items) {
  if (!items || !items.length) return "";
  const lis = items.map((item) => `<li>${esc(findingLine(item))}</li>`).join("");
  return `<div class="stat" style="min-width:100%;"><div class="k">${esc(title)}</div>
    <ul class="readiness-reasons">${lis}</ul></div>`;
}

function renderReadinessMatrix(matrix) {
  if (!matrix || !matrix.length) return "";
  const rows = matrix.map((m) => `
    <tr><td>${esc(m.product_hint || m.doc_id)}</td>
    <td>${pill(String(m.claimed_readiness || "unknown").replace(/_/g, " "), readinessKind(m.claimed_readiness))}</td>
    <td>${esc(m.confidence)}</td>
    <td>${m.has_migration_blocker ? '<span class="badge-yes">yes</span>' : '<span class="badge-no">no</span>'}</td>
    <td>${m.claim_count ?? 0}</td></tr>`).join("");
  return `<div class="table-scroll"><table>
    <tr><th>Product / doc</th><th>Claimed readiness</th><th>Confidence</th><th>Blocker</th><th>Claims</th></tr>
    ${rows}</table></div>`;
}

function renderWaves(waves) {
  if (!waves || !waves.length) return "";
  return waves.map((w) => {
    if (!w.assets || !w.assets.length) return `<p class="hint">${esc(w.summary)}</p>`;
    const rows = w.assets.map((a) => `
      <tr><td>${esc(a.asset_name)}</td><td>${pill(a.rating, a.rating)}</td>
      <td>${a.priority_score_100 ?? "-"}</td>
      <td>${a.vendor_blocked ? '<span class="badge-yes">yes</span>' : '<span class="badge-no">no</span>'}</td></tr>`).join("");
    return `<p class="hint">${esc(w.summary)}</p><div class="table-scroll"><table>
      <tr><th>Asset</th><th>Rating</th><th>Priority</th><th>Vendor blocked</th></tr>${rows}</table></div>`;
  }).join("");
}

function renderCopilotResult(intentLabel, data) {
  const parts = [];
  if (intentLabel) parts.push(`<p class="hint">Intent: <span class="mono">${esc(intentLabel)}</span></p>`);
  $("cp-narrative").innerHTML = esc(data.narrative || "");

  parts.push(renderList("Explicit findings", data.explicit_findings));
  parts.push(renderList("Inferred context", data.inferred_context));
  parts.push(renderList("Evidence gaps", data.evidence_gaps));
  parts.push(renderList("Claims", data.claims));
  parts.push(renderReadinessMatrix(data.readiness_matrix));
  parts.push(renderList("Pre-change checklist", data.pre_change_checklist));
  parts.push(renderWaves(data.waves));
  if (data.risk) parts.push(renderList("Risk rationale", [JSON.stringify(data.risk)]));

  parts.push(`<details><summary class="hint">Raw JSON</summary><pre class="mono">${esc(JSON.stringify(data, null, 2))}</pre></details>`);
  $("cp-result").innerHTML = parts.filter(Boolean).join("");
}

function cpAsset() {
  const name = $("cp-asset").value.trim();
  if (!name) setMsg("Enter an asset name first.", true);
  return name;
}

$("cp-ask").addEventListener("click", async () => {
  const question = $("cp-question").value.trim();
  if (!question) return setMsg("Enter a question first.", true);
  setMsg("Asking Copilot...");
  try {
    const data = await api("POST", "/api/copilot/query", { question });
    renderCopilotResult(data.intent, data.result || {});
    setMsg("Done.");
  } catch (err) { setMsg(err.message, true); }
});

$("cp-narrate").addEventListener("click", async () => {
  const asset = cpAsset();
  if (!asset) return;
  setMsg("Asking Risk Narrator...");
  try {
    const data = await api("GET", "/api/copilot/narrate/" + encodeURIComponent(asset));
    renderCopilotResult("narrate_asset", data);
    setMsg("Done.");
  } catch (err) { setMsg(err.message, true); }
});

$("cp-change-plan").addEventListener("click", async () => {
  const asset = cpAsset();
  if (!asset) return;
  setMsg("Asking Change Assistant...");
  try {
    const data = await api("GET", "/api/copilot/change-plan/" + encodeURIComponent(asset));
    renderCopilotResult("change_plan", data);
    setMsg("Done.");
  } catch (err) { setMsg(err.message, true); }
});

$("cp-discover").addEventListener("click", async () => {
  setMsg("Asking Discovery Analyst...");
  try {
    const data = await api("GET", "/api/copilot/discover");
    renderCopilotResult("discover", data);
    setMsg("Done.");
  } catch (err) { setMsg(err.message, true); }
});

$("cp-vendor").addEventListener("click", async () => {
  setMsg("Asking Vendor Intelligence Analyst...");
  try {
    const data = await api("GET", "/api/copilot/vendor-intelligence");
    renderCopilotResult("vendor_intelligence", data);
    setMsg("Done.");
  } catch (err) { setMsg(err.message, true); }
});

$("cp-migration").addEventListener("click", async () => {
  setMsg("Asking Migration Planner...");
  try {
    const data = await api("GET", "/api/copilot/migration-plan");
    renderCopilotResult("migration_plan", data);
    setMsg("Done.");
  } catch (err) { setMsg(err.message, true); }
});

// --- Operator workflow: Dashboard / Assets / Findings / Risk / Migration Plan / Reports ---
// Each tab lazy-loads on first visit (see the registry near the bottom); "Load Demo"
// invalidates every tab so the next visit re-fetches, and re-loads whichever tab is
// currently on screen immediately.
function renderDemoStatus(status) {
  $("demo-status").innerHTML = [
    stat("Loaded", status.loaded ? pill("yes", "ok") : pill("no", "err")),
    stat("Assets found", `${status.assets_present.length} / ${status.assets_present.length + status.assets_missing.length}`),
    stat("Total assets", status.asset_count_total ?? 0),
    stat("Graph snapshot", status.graph_snapshot_present ? pill("present", "ok") : pill("missing", "muted")),
    stat("Doc index", status.doc_index_present ? pill("present", "ok") : pill("missing", "muted")),
  ].join("");
  return status;
}

async function refreshDemoStatus() {
  const status = await api("GET", "/api/demo/status");
  renderDemoStatus(status);
  return status;
}

// --- Asset detail (the click-through flow: asset row -> narrative -> checklist -> wave) ---
const WAVE_LABELS = { wave_1: "Wave 1 (urgent)", wave_2: "Wave 2 (near-term)", wave_3: "Wave 3 (planned)" };

async function showAssetDetail(assetName) {
  const panel = $("asset-detail");
  panel.hidden = false;
  $("ad-title").textContent = "Asset detail: " + assetName;
  $("ad-meta").innerHTML = stat("Asset", esc(assetName));
  $("ad-narrative").textContent = "Loading...";
  $("ad-change-narrative").textContent = "";
  $("ad-checklist").innerHTML = "";
  $("ad-wave").innerHTML = "";
  panel.scrollIntoView({ behavior: "smooth", block: "start" });

  setMsg("Loading asset detail for " + assetName + "...");
  try {
    const [narrate, changePlan] = await Promise.all([
      api("GET", "/api/copilot/narrate/" + encodeURIComponent(assetName)),
      api("GET", "/api/copilot/change-plan/" + encodeURIComponent(assetName)),
    ]);
    $("ad-meta").innerHTML = [
      stat("Asset", esc(assetName)),
      stat("Rating", changePlan.rating ? pill(changePlan.rating, changePlan.rating) : "-"),
      stat("Wave", changePlan.wave ? pill(WAVE_LABELS[changePlan.wave] || changePlan.wave, "info") : "-"),
    ].join("");
    $("ad-narrative").innerHTML = esc(narrate.narrative || "");
    $("ad-change-narrative").innerHTML = esc(changePlan.narrative || "");
    $("ad-checklist").innerHTML = renderList("Pre-change checklist", changePlan.pre_change_checklist)
      || '<p class="hint">No checklist items.</p>';
    $("ad-wave").innerHTML = changePlan.wave
      ? stat("Migration wave", WAVE_LABELS[changePlan.wave] || changePlan.wave)
      : '<p class="hint">Not yet placed in a migration wave.</p>';
    setMsg("Done.");
  } catch (err) {
    $("ad-narrative").textContent = "";
    setMsg(err.message, true);
  }
}

// --- Dashboard ---
async function loadDashboardTab() {
  const [status, operational] = await Promise.all([
    refreshDemoStatus(),
    api("GET", "/api/copilot/operational-summary"),
  ]);
  const platform = operational.platform || {};
  $("dash-overview").innerHTML = [
    stat("Assets", platform.asset_count ?? 0),
    stat("Scans", platform.scan_count ?? 0),
    stat("Risks", platform.risk_count ?? 0),
    ...Object.entries(platform.risk_counts || {}).map(([rating, count]) => stat(rating, pill(String(count), rating))),
  ].join("");
  const topRisks = platform.top_risks || [];
  $("dash-top-risks").innerHTML = topRisks.length
    ? `<div class="table-scroll"><table><tr><th>Asset</th><th>Rating</th><th>Score</th></tr>${
        topRisks.map((r) => `<tr class="asset-row" data-asset="${esc(r.asset_name)}">
          <td>${esc(r.asset_name)}</td><td>${pill(r.rating, r.rating)}</td><td>${r.normalized_score_100 ?? "-"}</td></tr>`).join("")
      }</table></div>`
    : '<p class="hint">No risk data yet -- click "Load Demo" above.</p>';
  $("dash-top-risks").querySelectorAll(".asset-row").forEach((row) => {
    row.addEventListener("click", () => { switchTab("assets"); showAssetDetail(row.dataset.asset); });
  });
  return status;
}

// --- Assets ---
async function loadAssetsTab() {
  const [assets, migration] = await Promise.all([
    api("GET", "/api/assets"),
    api("GET", "/api/copilot/migration-plan").catch(() => ({ waves: [] })),
  ]);
  const ratingByAsset = {};
  (migration.waves || []).forEach((w) => (w.assets || []).forEach((a) => { ratingByAsset[a.asset_name] = a.rating; }));

  $("assets-table").innerHTML = assets.length
    ? `<div class="table-scroll"><table>
        <tr><th>Name</th><th>Type</th><th>Environment</th><th>Rating</th></tr>${
          assets.map((a) => `<tr class="asset-row" data-asset="${esc(a.name)}">
            <td>${esc(a.name)}</td><td>${esc(a.asset_type)}</td><td>${esc(a.environment || "-")}</td>
            <td>${ratingByAsset[a.name] ? pill(ratingByAsset[a.name], ratingByAsset[a.name]) : "-"}</td></tr>`).join("")
        }</table></div>`
    : '<p class="hint">No assets yet -- go to Dashboard and click "Load Demo".</p>';
  $("assets-table").querySelectorAll(".asset-row").forEach((row) => {
    row.addEventListener("click", () => showAssetDetail(row.dataset.asset));
  });
}

// --- Findings ---
async function loadFindingsTab() {
  const discover = await api("GET", "/api/copilot/discover");
  $("find-narrative").innerHTML = esc(discover.narrative || "");
  $("find-result").innerHTML = renderList("Explicit findings", discover.explicit_findings)
    + renderList("Inferred context", discover.inferred_context)
    + renderList("Evidence gaps", discover.evidence_gaps);
}

// --- Risk ---
async function loadRiskTab() {
  const migration = await api("GET", "/api/copilot/migration-plan");
  const rows = (migration.waves || []).flatMap((w) => w.assets || []);
  $("risk-table").innerHTML = rows.length
    ? `<div class="table-scroll"><table>
        <tr><th>Asset</th><th>Rating</th><th>Priority</th><th>Vendor blocked</th></tr>${
          rows.map((a) => `<tr class="asset-row" data-asset="${esc(a.asset_name)}">
            <td>${esc(a.asset_name)}</td><td>${pill(a.rating || "unknown", a.rating || "unknown")}</td>
            <td>${a.priority_score_100 ?? "-"}</td>
            <td>${a.vendor_blocked ? '<span class="badge-yes">yes</span>' : '<span class="badge-no">no</span>'}</td></tr>`).join("")
        }</table></div>`
    : '<p class="hint">No risk-scored assets yet.</p>';
  $("risk-table").querySelectorAll(".asset-row").forEach((row) => {
    row.addEventListener("click", () => { switchTab("assets"); showAssetDetail(row.dataset.asset); });
  });
}

// --- Migration Plan ---
async function loadMigrationPlanTab() {
  const migration = await api("GET", "/api/copilot/migration-plan");
  $("mp-narrative").innerHTML = esc(migration.narrative || "");
  $("mp-waves").innerHTML = renderWaves(migration.waves) || '<p class="hint">No waves yet.</p>';
  $("mp-vendor-note").innerHTML = esc((migration.vendor_readiness_context || {}).note || "");
}

// --- Reports ---
async function loadReportsTab() {
  const summary = await api("GET", "/api/copilot/operational-summary");
  const platform = summary.platform || {};
  const planning = summary.planning || {};
  const workflow = summary.workflow || {};
  $("rep-summary").innerHTML = [
    stat("Assets", platform.asset_count ?? 0),
    stat("Scans", platform.scan_count ?? 0),
    stat("Risks", platform.risk_count ?? 0),
    stat("Wave 1", planning.wave_1_count ?? 0),
    stat("Wave 2", planning.wave_2_count ?? 0),
    stat("Wave 3", planning.wave_3_count ?? 0),
    stat("Open tasks", workflow.task_count ?? 0),
  ].join("");
  $("rep-result").innerHTML = `<details open><summary class="hint">Full operational summary (raw JSON)</summary><pre class="mono">${esc(JSON.stringify(summary, null, 2))}</pre></details>`;
}

// --- Tab registry: lazy-load on first visit, switchTab() for programmatic navigation ---
function switchTab(tabId) {
  document.querySelector(`.tab[data-tab="${tabId}"]`).click();
}

const TAB_LOADERS = {
  dashboard: loadDashboardTab,
  assets: loadAssetsTab,
  findings: loadFindingsTab,
  risk: loadRiskTab,
  "migration-plan": loadMigrationPlanTab,
  reports: loadReportsTab,
};
const tabLoaded = {};

Object.keys(TAB_LOADERS).forEach((tabId) => {
  document.querySelector(`.tab[data-tab="${tabId}"]`).addEventListener("click", () => {
    if (tabLoaded[tabId]) return;
    tabLoaded[tabId] = true;
    TAB_LOADERS[tabId]().catch((err) => setMsg(err.message, true));
  });
});

$("demo-load").addEventListener("click", async () => {
  setMsg("Loading demo dataset...");
  try {
    const data = await api("POST", "/api/demo/load");
    const statusKind = { ok: "ok", skipped: "muted", error: "err" };
    const rows = data.steps.map((s) => `
      <tr><td>${esc(s.step)}</td><td>${pill(s.status, statusKind[s.status] || "muted")}</td>
      <td>${esc(s.asset_name || s.detail || "")}</td></tr>`).join("");
    $("demo-load-result").innerHTML = `<div class="table-scroll"><table>
      <tr><th>Step</th><th>Status</th><th>Detail</th></tr>${rows}</table></div>`;

    // Invalidate every tab so the next visit re-fetches; immediately reload the
    // active one (a plain click() wouldn't re-fire since the tab's already active).
    Object.keys(tabLoaded).forEach((tabId) => { tabLoaded[tabId] = false; });
    const activeTab = document.querySelector(".tab.active")?.dataset.tab;
    if (activeTab && TAB_LOADERS[activeTab]) {
      tabLoaded[activeTab] = true;
      await TAB_LOADERS[activeTab]();
    }
    setMsg(data.overall === "ok" ? "Demo loaded." : "Demo loaded with some errors -- see the step table.");
  } catch (err) { setMsg(err.message, true); }
});

$("demo-refresh").addEventListener("click", async () => {
  setMsg("Refreshing demo status...");
  try {
    await refreshDemoStatus();
    setMsg("Done.");
  } catch (err) { setMsg(err.message, true); }
});

// --- Init ---
loadScenarios();
loadIntegrationActions();
loadDashboardTab().catch(() => {});
tabLoaded.dashboard = true;
