"use strict";
const $ = (id) => document.getElementById(id);
let current = null;
let dirty = false;
let busy = false;
function status(message, error = false) { $("status").textContent = message; $("status").classList.toggle("error", error); }
async function api(path, method = "GET", body) {
  const response = await fetch(path, {method, headers: {"Content-Type": "application/json"}, body: body === undefined ? undefined : JSON.stringify(body)});
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Check the required fields and try again.");
  return data;
}
async function action(work) {
  if (busy) return;
  busy = true;
  document.querySelectorAll("button, input, textarea, select").forEach((el) => { el.disabled = true; });
  try { await work(); } catch (error) { status(error.message, true); }
  finally { busy = false; document.querySelectorAll("button, input, textarea, select").forEach((el) => { el.disabled = false; }); }
}
function canLeave() { return !dirty || window.confirm("Discard unsaved SQL edits?"); }
function renderResult(result, target = $("results")) {
  target.replaceChildren();
  const meta = document.createElement("p"); meta.textContent = `${result.rows.length} rows · ${result.duration_ms.toFixed(1)} ms`; target.append(meta);
  const table = document.createElement("table"); const head = document.createElement("thead"); const tr = document.createElement("tr");
  result.columns.forEach((name) => { const th = document.createElement("th"); th.textContent = name; tr.append(th); }); head.append(tr); table.append(head);
  const body = document.createElement("tbody");
  result.rows.forEach((row) => { const tr = document.createElement("tr"); row.forEach((value) => { const td = document.createElement("td"); td.textContent = value === null ? "NULL" : typeof value === "object" ? JSON.stringify(value) : String(value); tr.append(td); }); body.append(tr); });
  table.append(body); target.append(table);
}
async function refreshDatasets() {
  const datasets = await api("/api/experiments"); $("datasets").replaceChildren();
  datasets.forEach((dataset) => { const button = document.createElement("button"); button.className = "secondary dataset"; button.textContent = dataset.name; button.setAttribute("aria-current", String(current?.id === dataset.id)); button.onclick = () => { if (canLeave()) action(() => openDataset(dataset.id)); }; $("datasets").append(button); });
}
function renderQueries() {
  $("savedQueries").replaceChildren(new Option("Choose a saved query", ""));
  current.queries.forEach((query, index) => $("savedQueries").append(new Option(query.name, index)));
}
function setEditor(query) { $("queryName").value = query.name; $("sql").value = query.sql; dirty = false; }
async function openDataset(id) {
  current = await api(`/api/experiments/${id}`); dirty = false;
  $("experiment").hidden = false; $("name").textContent = current.name; $("context").textContent = current.description;
  $("snapshot").textContent = `Fixed snapshot ${current.snapshot_sha256.slice(0, 12)} · Saved ${new Date(current.created_at).toLocaleString()}`;
  $("tables").replaceChildren();
  current.tables.forEach((table) => {
    const heading = document.createElement("h2"); heading.textContent = table.name;
    const description = document.createElement("p"); description.textContent = table.description;
    const ddl = document.createElement("pre"); ddl.textContent = table.ddl;
    const preview = document.createElement("button"); preview.className = "secondary"; preview.textContent = `Preview ${table.name}`;
    preview.onclick = () => action(async () => { renderResult(await api(`/api/experiments/${current.id}/run`, "POST", {sql: `SELECT * FROM "${table.name}" LIMIT 50`})); status(`Preview of ${table.name}.`); });
    $("tables").append(heading, description, ddl, preview);
  });
  renderQueries(); setEditor(current.queries[0] || {name: "Query 1", sql: `SELECT * FROM "${current.tables[0].name}" LIMIT 100;`});
  $("results").replaceChildren(); history.replaceState(null, "", `/explore?id=${id}`); await refreshDatasets(); status("Dataset opened. SQL runs against this fixed snapshot.");
}
$("demo").onclick = () => { if (canLeave()) action(async () => { status("Creating offline dataset…"); const dataset = await api("/api/experiments/demo", "POST"); await openDataset(dataset.id); }); };
$("generate").onclick = () => {
  if (!$("description").value.trim()) return status("Describe the dataset to generate.", true);
  if (canLeave()) action(async () => { status("Generating and validating a dataset. This may take several minutes…"); const dataset = await api("/api/experiments/generate", "POST", {description: $("description").value, provider: $("provider").value}); await openDataset(dataset.id); });
};
$("run").onclick = () => action(async () => { $("results").replaceChildren(); status("Running SQL…"); renderResult(await api(`/api/experiments/${current.id}/run`, "POST", {sql: $("sql").value})); status("Query completed. No correctness expectation was applied."); });
$("save").onclick = () => action(async () => {
  const query = {name: $("queryName").value.trim(), sql: $("sql").value.trim()};
  const queries = [...current.queries]; const index = queries.findIndex((item) => item.name === query.name);
  if (index < 0) queries.push(query); else queries[index] = query;
  current = await api(`/api/experiments/${current.id}/queries`, "PUT", {revision: current.revision, queries}); dirty = false; renderQueries(); status("Query saved locally.");
});
$("newQuery").onclick = () => { if (canLeave()) setEditor({name: `Query ${current.queries.length + 1}`, sql: ""}); };
$("savedQueries").onchange = () => { const query = current.queries[Number($("savedQueries").value)]; if (query && canLeave()) setEditor(query); };
[$("sql"), $("queryName")].forEach((el) => el.addEventListener("input", () => { dirty = true; }));
window.addEventListener("beforeunload", (event) => { if (dirty || busy) { event.preventDefault(); event.returnValue = ""; } });
action(async () => { const id = new URLSearchParams(location.search).get("id"); if (id) await openDataset(id); else await refreshDatasets(); });
