"use strict";
const $ = (id) => document.getElementById(id);
let current = null;
let dirty = false;
let busy = false;
let candidateDatasetId = null;
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
  if (target === $("results")) showOutput("outputPanel");
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
  renderCaseDatasets(datasets);
  if (!datasets.length) { const empty = document.createElement("p"); empty.className = "muted"; empty.textContent = "Your saved datasets will appear here."; $("datasets").append(empty); }
  datasets.forEach((dataset) => { const button = document.createElement("button"); button.className = "session-row"; fillSessionRow(button, dataset.name, `${dataset.tables.length} tables · ${new Date(dataset.created_at).toLocaleDateString()}`); button.setAttribute("aria-current", String(current?.id === dataset.id)); button.onclick = () => { if (canLeave()) action(() => openDataset(dataset.id)); }; $("datasets").append(button); });
}
function renderQueries() {
  renderCandidates();
  $("savedQueries").replaceChildren(new Option("Choose a saved query", ""));
  current.queries.forEach((query, index) => $("savedQueries").append(new Option(query.name, index)));
}
function setEditor(query) { const index = current.queries.findIndex((item) => item.name === query.name); $("savedQueries").value = index < 0 ? "" : String(index); $("queryName").value = query.name; $("sql").value = query.sql; updateEditorLines(); dirty = false; }
async function openDataset(id) {
  current = await api(`/api/experiments/${id}`); dirty = false;
  document.body.classList.add("is-open");
  $("toolTabs").hidden = false; $("datasetOverview").hidden = false;
  $("datasetChooser").open = false;
  selectPanel("data-tool", "datasetTools"); showOutput("outputPanel");
  $("experiment").hidden = false; $("name").textContent = current.name; $("context").textContent = current.description;
  $("snapshot").textContent = `Fixed snapshot ${current.snapshot_sha256.slice(0, 12)} · Saved ${new Date(current.created_at).toLocaleString()}`;
  $("tables").replaceChildren();
  current.tables.forEach((table) => {
    const heading = document.createElement("h2"); heading.textContent = table.name;
    const description = document.createElement("p"); description.textContent = table.description;
    const ddl = document.createElement("pre"); ddl.textContent = table.ddl;
    const preview = document.createElement("button"); preview.className = "button ghost small"; preview.textContent = `Preview ${table.name}`;
    preview.onclick = () => action(async () => { renderResult(await api(`/api/experiments/${current.id}/run`, "POST", {sql: `SELECT * FROM "${table.name}" LIMIT 50`})); status(`Preview of ${table.name}.`); });
    $("tables").append(heading, description, ddl, preview);
  });
  renderQuestions();
  renderQueries(); setEditor(current.queries[0] || {name: "Query 1", sql: `SELECT * FROM "${current.tables[0].name}" LIMIT 100;`});
  $("comparisonResults").replaceChildren();
  $("results").replaceChildren();
  const empty = document.createElement("div"); empty.className = "result-placeholder"; empty.textContent = "Run your query to see results."; $("results").append(empty);
  history.replaceState(null, "", `/?id=${encodeURIComponent(id)}`); await refreshDatasets(); await refreshCases(); status("Dataset opened. SQL runs against this fixed snapshot.");
}
$("demo").onclick = () => { if (canLeave()) action(async () => { status("Creating offline dataset…"); const dataset = await api("/api/experiments/demo", "POST"); await openDataset(dataset.id); }); };
let selectedCompany = "";
let suggestedScenario = "";
let pendingScope = null;
const companyScenarios = {
  Airbnb: "Bookings, cancellations, and repeat guests across cities.",
  Meta: "Hardware sales, returns, and customer engagement.",
  Uber: "Trips, riders, drivers, and demand across cities.",
  Amazon: "Marketplace orders, products, sellers, and fulfillment times.",
  Netflix: "Viewing activity, subscriptions, and retention."
};
const examples = {
  orders: "Create orders, customers, and refunds data. Include repeat buyers and partial refunds.",
  retention: "Which customers returned within 30 days of their first purchase?",
  practice: "Create SQL practice questions on joins and window functions, with data I can query."
};
function updateCompany() {
  document.querySelectorAll("[data-company]").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.company === selectedCompany)));
  $("selectedContext").hidden = !selectedCompany;
  $("contextLabel").textContent = selectedCompany === "Other" ? "Custom company context" : `${selectedCompany} context`;
  $("customCompanyFields").hidden = selectedCompany !== "Other";
  $("company").required = selectedCompany === "Other";
}
$("clearCompany").onclick = () => { selectedCompany = ""; updateCompany(); };
document.querySelectorAll("[data-company]").forEach((button) => {
  button.onclick = () => {
    selectedCompany = button.dataset.company; updateCompany();
    if (!$("description").value.trim() || $("description").value === suggestedScenario) {
      suggestedScenario = companyScenarios[selectedCompany] || "";
      $("description").value = suggestedScenario;
    }
    $("scopeReview").hidden = true; $("setupForm").hidden = false;
    (selectedCompany === "Other" ? $("company") : $("description")).focus();
  };
});
document.querySelectorAll("[data-example]").forEach((button) => {
  button.onclick = () => {
    selectedCompany = ""; updateCompany();
    $("description").value = examples[button.dataset.example];
    $("scopeReview").hidden = true; $("setupForm").hidden = false; $("description").focus();
  };
});
$("settingsToggle").onclick = () => {
  const open = $("generationSettings").hidden;
  $("generationSettings").hidden = !open;
  $("settingsToggle").setAttribute("aria-expanded", String(open));
};
$("setupForm").onsubmit = (event) => {
  event.preventDefault();
  const description = $("description").value.trim();
  const company = selectedCompany === "Other" ? $("company").value.trim() : selectedCompany;
  if (!description || (selectedCompany === "Other" && !company)) return status("Describe your idea and complete the company context.", true);
  pendingScope = {
    description: company ? `Fictional ${company}-inspired business scenario: ${description}` : description,
    interpret_prompt: !$("dataOnly").checked,
    guided: !$("dataOnly").checked,
    provider: $("provider").value
  };
  $("scopeText").textContent = pendingScope.description;
  $("scopeMode").textContent = `${pendingScope.guided ? "Practice questions included" : "Data only · No practice questions"} · Native DuckDB · ${pendingScope.provider === "codex" ? "Codex" : "Claude"}`;
  $("setupForm").hidden = true; $("scopeReview").hidden = false; $("reviewTitle").focus();
};
$("editScope").onclick = () => { $("scopeReview").hidden = true; $("setupForm").hidden = false; $("description").focus(); };
$("description").addEventListener("keydown", (event) => { if ((event.metaKey || event.ctrlKey) && event.key === "Enter") { event.preventDefault(); $("setupForm").requestSubmit(); } });
$("generate").onclick = () => {
  if (!pendingScope) return;
  action(async () => { status("Generating and validating your session. This may take several minutes…"); const dataset = await api("/api/experiments/generate", "POST", pendingScope); await openDataset(dataset.id); if (current.questions.length) selectPanel("data-tool", "questionsTools"); });
};
function renderQuestions() {
  $("sessionQuestions").replaceChildren();
  if (!current.questions.length) { const note = document.createElement("p"); note.textContent = "No questions yet. Add one below, or explore the tables freely."; $("sessionQuestions").append(note); }
  current.questions.forEach((question, index) => {
    const card = document.createElement("article"), heading = document.createElement("h3"), text = document.createElement("p"), button = document.createElement("button");
    heading.textContent = `Question ${index + 1}`; text.textContent = question; button.textContent = "Work on this question"; button.className = "button ghost small";
    button.onclick = () => { if (canLeave()) { const name = `Question ${index + 1}`; setEditor(current.queries.find((query) => query.name === name) || {name, sql: ""}); $("sql").focus(); status(`Working on question ${index + 1}. Save your SQL to return to it later.`); } };
    card.append(heading, text, button); $("sessionQuestions").append(card);
  });
}
$("addQuestion").onclick = () => action(async () => {
  const question = $("newQuestion").value.trim(); if (!question) throw new Error("Enter a question to save.");
  current = await api(`/api/experiments/${current.id}/questions`, "PUT", {revision: current.revision, questions: [...current.questions, question]});
  $("newQuestion").value = ""; renderQuestions(); status("Question saved with this dataset. Your SQL edits are unchanged.");
});
$("run").onclick = () => action(async () => { $("results").replaceChildren(); status("Running SQL…"); renderResult(await api(`/api/experiments/${current.id}/run`, "POST", {sql: $("sql").value})); status("Query completed. No correctness expectation was applied."); });
$("save").onclick = () => action(async () => {
  const query = {name: $("queryName").value.trim(), sql: $("sql").value.trim()};
  const queries = [...current.queries]; const index = queries.findIndex((item) => item.name === query.name);
  if (index < 0) queries.push(query); else queries[index] = query;
  current = await api(`/api/experiments/${current.id}/queries`, "PUT", {revision: current.revision, queries}); dirty = false; renderQueries(); status("Query saved locally.");
});
$("newQuery").onclick = () => {
  if (!canLeave()) return;
  let number = 1;
  while (current.queries.some((query) => query.name === `Query ${number}`)) number++;
  setEditor({name: `Query ${number}`, sql: ""});
};
$("savedQueries").onchange = () => { const query = current.queries[Number($("savedQueries").value)]; if (query && canLeave()) setEditor(query); };
[$("sql"), $("queryName")].forEach((el) => el.addEventListener("input", () => { dirty = true; }));
window.addEventListener("beforeunload", (event) => { if (dirty || busy) { event.preventDefault(); event.returnValue = ""; } });
action(async () => { const id = new URLSearchParams(location.search).get("id"); if (id) await openDataset(id); else { await refreshDatasets(); await refreshLegacySessions(); } });

function renderCandidates() {
  const previous = new Map(candidateDatasetId === current.id
    ? [...$("compareCandidates").querySelectorAll("input")].map((input) => [input.dataset.queryName, input.checked])
    : []);
  candidateDatasetId = current.id;
  $("compareCandidates").replaceChildren();
  current.queries.forEach((query, index) => {
    const label = document.createElement("label"); const checkbox = document.createElement("input");
    checkbox.type = "checkbox"; checkbox.value = index; checkbox.dataset.queryName = query.name;
    checkbox.checked = previous.has(query.name) ? previous.get(query.name) : index < 2;
    label.append(checkbox, document.createTextNode(` ${query.name}`)); $("compareCandidates").append(label);
  });
}
$("compare").onclick = () => action(async () => {
  const queries = [...$("compareCandidates").querySelectorAll("input:checked")].map((el) => current.queries[Number(el.value)]);
  if (queries.length < 2 || queries.length > 6) throw new Error("Save and select between two and six queries.");
  const tolerance = Number($("tolerance").value);
  if (!Number.isFinite(tolerance) || tolerance < 0 || tolerance > 1) throw new Error("Choose a numeric tolerance between 0 and 1.");
  $("comparisonResults").replaceChildren(); status("Comparing saved queries…");
  const report = await api(`/api/experiments/${current.id}/compare`, "POST", {queries, rules: {order_matters: $("orderMatters").checked, numeric_tolerance: tolerance}});
  const summary = document.createElement("p"); summary.textContent = `${report.meaning} Snapshot ${report.snapshot_sha256.slice(0, 12)}. Order ${report.rules.order_matters ? "matters" : "ignored"}; tolerance ${report.rules.numeric_tolerance}.`;
  $("comparisonResults").append(summary);
  report.outputs.forEach((output, index) => {
    const section = document.createElement("section"); const heading = document.createElement("h2");
    heading.textContent = `${output.query.name} — ${output.error ? "Execution error" : index === 0 ? "Baseline" : output.comparison === null ? "Not compared: baseline failed" : output.comparison.passed ? "Matches baseline" : "Differs from baseline"}`;
    section.append(heading); const sql = document.createElement("pre"); sql.textContent = output.query.sql; section.append(sql);
    if (output.error) { const error = document.createElement("p"); error.textContent = output.error; section.append(error); }
    if (output.comparison && !output.comparison.passed) { const diff = document.createElement("pre"); diff.textContent = JSON.stringify(output.comparison, null, 2); section.append(diff); }
    if (output.result) { const table = document.createElement("div"); table.className = "output"; renderResult(output.result, table); section.append(table); }
    $("comparisonResults").append(section);
  });
  showOutput("comparisonPanel");
  status("Comparison complete. Results reflect the saved SQL shown in the report.");
});

let evaluationCases = [];
let evaluationRuns = [];
function renderCaseDatasets(datasets) {
  $("caseDatasets").replaceChildren();
  datasets.forEach((dataset) => {
    const label = document.createElement("label"); const check = document.createElement("input");
    check.type = "checkbox"; check.value = dataset.id; check.checked = dataset.id === current?.id;
    label.append(check, document.createTextNode(` ${dataset.name} (${dataset.snapshot_sha256.slice(0, 8)})`)); $("caseDatasets").append(label);
  });
}
async function refreshCases(selectedId = $("evaluationCase").value) {
  evaluationCases = await api("/api/evaluation-cases");
  $("evaluationCase").replaceChildren(new Option("Choose an evaluation case", ""));
  evaluationCases.forEach((item) => $("evaluationCase").append(new Option(`${item.name} (${item.id.slice(0, 8)})`, item.id)));
  $("evaluationCase").value = selectedId;
  await refreshRuns();
}
async function refreshRuns() {
  const selected = evaluationCases.find((item) => item.id === $("evaluationCase").value);
  $("caseDetails").textContent = selected ? `${selected.expectation}\nReference: ${selected.reference_sql}\nDatasets: ${selected.datasets.map((item) => item.name + " " + item.sha256.slice(0, 8)).join(", ")}\nOrder matters: ${selected.rules.order_matters}; tolerance: ${selected.rules.numeric_tolerance}` : "";
  evaluationRuns = selected ? await api(`/api/evaluation-cases/${selected.id}/runs`) : [];
  [$("earlierRun"), $("laterRun")].forEach((select) => {
    select.replaceChildren(); evaluationRuns.forEach((run) => select.append(new Option(`${new Date(run.created_at).toLocaleString()} (${run.id.slice(0, 8)})`, run.id)));
  });
  if (evaluationRuns.length > 1) $("earlierRun").selectedIndex = 1;
  $("evaluationResults").replaceChildren();
}
$("evaluationCase").onchange = () => action(refreshRuns);
$("referenceSql").addEventListener("input", () => { $("referenceReviewed").checked = false; });
$("createCase").onclick = () => action(async () => {
  if (!$("referenceReviewed").checked) throw new Error("Review the reference SQL and confirm before saving.");
  const dataset_ids = [...$("caseDatasets").querySelectorAll("input:checked")].map((el) => el.value);
  if (dataset_ids.length < 1 || dataset_ids.length > 4) throw new Error("Choose one to four datasets.");
  status("Validating the reference on every selected dataset…");
  const item = await api("/api/evaluation-cases", "POST", {name: $("caseName").value, expectation: $("expectation").value, dataset_ids,
    reference_sql: $("referenceSql").value, reference_reviewed: true, rules: {order_matters: $("orderMatters").checked, numeric_tolerance: Number($("tolerance").value)}});
  await refreshCases(item.id); status("Evaluation case saved. Its data, reference and rules are fixed.");
});
function showEvaluation(report) {
  showOutput("evaluationPanel");
  const target = $("evaluationResults"); target.replaceChildren();
  const summary = document.createElement("p"); summary.textContent = `${report.summary.passed} passed · ${report.summary.failed} failed · ${report.summary.error} execution errors · ${report.summary.invalid_case} invalid cases. DuckDB ${report.engine_version}.`;
  target.append(summary);
  const sql = document.createElement("details"); const label = document.createElement("summary"); label.textContent = "SQL and frozen case used in this run";
  const content = document.createElement("pre"); content.textContent = JSON.stringify({case: report.case, queries: report.queries, created_at: report.created_at}, null, 2); sql.append(label, content); target.append(sql);
  report.outcomes.forEach((outcome) => {
    const details = document.createElement("details"); const heading = document.createElement("summary"); heading.textContent = `${outcome.candidate} · ${outcome.dataset_name} · ${outcome.status}`;
    const body = document.createElement("pre"); body.textContent = outcome.error || JSON.stringify(outcome.comparison, null, 2); details.append(heading, body); target.append(details);
  });
}
$("evaluate").onclick = () => action(async () => {
  const caseId = $("evaluationCase").value; if (!caseId) throw new Error("Choose a saved evaluation case.");
  const queries = [...$("compareCandidates").querySelectorAll("input:checked")].map((el) => current.queries[Number(el.value)]);
  if (queries.length < 1 || queries.length > 6) throw new Error("Select one to six saved queries above.");
  $("evaluationResults").replaceChildren(); status("Evaluating selected queries across the case datasets…");
  const report = await api(`/api/evaluation-cases/${caseId}/runs`, "POST", {queries});
  await refreshRuns(); showEvaluation(report); status("Evaluation saved. Expand an outcome to inspect its differences.");
});
$("showRun").onclick = () => action(async () => { const report = evaluationRuns.find((run) => run.id === $("laterRun").value); if (!report) throw new Error("Choose a saved run."); showEvaluation(report); status("Showing the original saved run."); });
$("compareRuns").onclick = () => action(async () => {
  const earlier = $("earlierRun").value, later = $("laterRun").value;
  if (!earlier || !later || earlier === later) throw new Error("Choose two different runs of this case.");
  const comparison = await api(`/api/evaluation-runs/compare?earlier=${encodeURIComponent(earlier)}&later=${encodeURIComponent(later)}`);
  $("evaluationResults").replaceChildren();
  const note = document.createElement("p"); note.textContent = `Compared by candidate name and dataset. ${comparison.same_engine_version ? "Same DuckDB version." : "DuckDB versions differ; interpret changes carefully."}`; $("evaluationResults").append(note);
  comparison.changes.forEach((change) => { const row = document.createElement("p"); row.textContent = `${change.candidate} · ${change.dataset_id.slice(0, 8)}: ${change.before} → ${change.after}${change.regression ? " — regression" : change.improvement ? " — improvement" : ""}`; $("evaluationResults").append(row); });
  const details = document.createElement("details"); const summary = document.createElement("summary"); summary.textContent = "Inspect both original runs and SQL"; const body = document.createElement("pre"); body.textContent = JSON.stringify(comparison, null, 2); details.append(summary, body); $("evaluationResults").append(details);
  showOutput("evaluationPanel");
  status("Run comparison complete. Added or removed candidates are marked absent.");
});

function selectPanel(attribute, id) {
  const buttons = [...document.querySelectorAll(`[${attribute}]`)];
  buttons.forEach((button) => {
    const selected = button.getAttribute(attribute) === id;
    button.classList.toggle("active", selected);
    button.setAttribute("aria-selected", String(selected));
    button.tabIndex = selected ? 0 : -1;
    $(button.getAttribute(attribute)).hidden = !selected;
  });
  if (attribute === "data-tool") {
    $("querySelection").hidden = !["compareTools", "evaluateTools"].includes(id);
    if (["compareTools", "evaluateTools"].includes(id)) $(id).insertBefore($("querySelection"), $(id === "compareTools" ? "compare" : "evaluate"));
  }
}
function showOutput(id) { selectPanel("data-result", id); }
["data-tool", "data-result"].forEach((attribute) => {
  const buttons = [...document.querySelectorAll(`[${attribute}]`)];
  buttons.forEach((button, index) => {
    button.onclick = () => selectPanel(attribute, button.getAttribute(attribute));
    button.onkeydown = (event) => {
      let next;
      if (event.key === "ArrowRight") next = (index + 1) % buttons.length;
      if (event.key === "ArrowLeft") next = (index + buttons.length - 1) % buttons.length;
      if (event.key === "Home") next = 0;
      if (event.key === "End") next = buttons.length - 1;
      if (next === undefined) return;
      event.preventDefault(); buttons[next].click(); buttons[next].focus();
    };
  });
});
function updateEditorLines() { $("exploreLines").textContent = Array.from({length: $("sql").value.split("\n").length}, (_, index) => index + 1).join("\n"); }
$("sql").addEventListener("input", updateEditorLines);
$("sql").addEventListener("scroll", () => { $("exploreLines").scrollTop = $("sql").scrollTop; });
$("sql").addEventListener("keydown", (event) => { if ((event.metaKey || event.ctrlKey) && event.key === "Enter") { event.preventDefault(); $("run").click(); } });

async function refreshLegacySessions() {
  try {
    const data = await api("/api/history");
    data.sessions.forEach((session) => { const link = document.createElement("a"); link.href = `/practice?resume=${encodeURIComponent(session.id)}`; link.className = "session-row"; fillSessionRow(link, session.company, `${session.question_count} questions · ${new Date(session.started_at).toLocaleDateString()} · Earlier interview`); $("legacySessions").append(link); });
  } catch { const note = document.createElement("p"); note.textContent = "Earlier interview sessions could not be loaded. Refresh to try again."; $("legacySessions").append(note); }
}

function fillSessionRow(element, title, metadata) {
  const icon = document.createElement("img"), name = document.createElement("span"), meta = document.createElement("span"), arrow = document.createElement("img");
  icon.src = "/assets/icons/file.svg"; icon.alt = ""; icon.className = "ui-icon";
  name.textContent = title; name.className = "session-title";
  meta.textContent = metadata; meta.className = "session-meta";
  arrow.src = "/assets/icons/chevron-right.svg"; arrow.alt = ""; arrow.className = "ui-icon row-arrow";
  element.setAttribute("aria-label", `${title} · ${metadata}`);
  element.append(icon, name, meta, arrow);
}
