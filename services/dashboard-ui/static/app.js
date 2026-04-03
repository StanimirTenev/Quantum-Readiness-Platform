async function getJSON(url, options = {}) {
  const res = await fetch(url, options);
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(txt || `${res.status}`);
  }
  return res.json();
}

function pretty(obj) {
  return JSON.stringify(obj, null, 2);
}

function renderTopRisks(items) {
  const body = document.getElementById("topRisksBody");
  body.innerHTML = "";
  for (const item of items) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${item.asset_name || "-"}</td>
      <td>${item.normalized_score_100 ?? "-"}</td>
      <td><span class="badge ${item.rating === "high" ? "high" : item.rating === "medium" ? "medium" : "low"}">${item.rating || "-"}</span></td>
    `;
    body.appendChild(tr);
  }
}

function renderWave(targetId, items) {
  const node = document.getElementById(targetId);
  node.innerHTML = "";
  if (!items || items.length === 0) {
    node.innerHTML = `<div class="muted">No items.</div>`;
    return;
  }
  for (const item of items) {
    const div = document.createElement("div");
    div.className = "item";
    div.innerHTML = `
      <div><strong>${item.asset_name}</strong></div>
      <small>${item.asset_type} · ${item.rating} · score ${item.normalized_score_100}</small><br>
      <small>${item.recommended_action || ""}</small>
    `;
    node.appendChild(div);
  }
}

function renderTasks(items) {
  const body = document.getElementById("tasksBody");
  body.innerHTML = "";
  for (const item of items) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${item.title}</td>
      <td>${item.wave}</td>
      <td>${item.status}</td>
    `;
    body.appendChild(tr);
  }
}

async function loadOverview() {
  const [summary, op, plan, tasks] = await Promise.all([
    getJSON("/api/summary"),
    getJSON("/api/operational-summary"),
    getJSON("/api/plan"),
    getJSON("/api/tasks")
  ]);

  document.getElementById("statAssets").textContent = op.platform.asset_count;
  document.getElementById("statScans").textContent = op.platform.scan_count;
  document.getElementById("statRisks").textContent = op.platform.risk_count;
  document.getElementById("statTasks").textContent = op.workflow.task_count;

  document.getElementById("operationalSummary").textContent = pretty(op);
  renderTopRisks(summary.top_risks || []);
  renderWave("wave1", plan.wave_1 || []);
  renderWave("wave2", plan.wave_2 || []);
  renderWave("wave3", plan.wave_3 || []);
  renderTasks(tasks || []);
}

async function loadAsset() {
  const assetName = document.getElementById("assetInput").value.trim();
  if (!assetName) return;
  const data = await getJSON(`/api/asset?asset_name=${encodeURIComponent(assetName)}`);
  document.getElementById("assetOutput").textContent = pretty(data);
}

async function runSearch() {
  const query = document.getElementById("searchInput").value.trim();
  if (!query) return;
  const data = await getJSON("/api/search", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({query})
  });
  document.getElementById("searchOutput").textContent = pretty(data);
}

async function askCopilot() {
  const question = document.getElementById("copilotQuestion").value.trim();
  if (!question) return;
  const data = await getJSON("/api/copilot-query", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({question})
  });
  document.getElementById("copilotOutput").textContent = pretty(data);
}

async function exportTasks(waves) {
  const data = await getJSON("/api/export-tasks", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({waves})
  });
  alert(`Created/returned tasks: ${data.created_count}`);
  await loadOverview();
}

async function health() {
  try {
    await getJSON("/api/health");
    document.getElementById("healthStatus").textContent = "Dashboard UI OK";
  } catch (e) {
    document.getElementById("healthStatus").textContent = "Dashboard UI error";
  }
}

document.getElementById("assetBtn").addEventListener("click", loadAsset);
document.getElementById("searchBtn").addEventListener("click", runSearch);
document.getElementById("copilotBtn").addEventListener("click", askCopilot);
document.getElementById("btnRefreshPlan").addEventListener("click", loadOverview);
document.getElementById("btnExportW1").addEventListener("click", () => exportTasks(["wave_1"]));
document.getElementById("btnExportW12").addEventListener("click", () => exportTasks(["wave_1", "wave_2"]));

(async function init() {
  await health();
  await loadOverview();
  await loadAsset();
  await runSearch();
})();
