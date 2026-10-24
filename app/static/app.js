// ReviewPulse dashboard (vanilla JS + Chart.js). Talks only to the FastAPI JSON endpoints.
const $ = (id) => document.getElementById(id);
const state = { city: "", platform: "", page: 1, size: 15, topic: "", sentiment: "", q: "", mismatch: false, totalPages: 1 };
const charts = {};
const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const pct = (x) => (x == null ? "–" : `${Math.round(x * 100)}%`);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function api(path, params = {}) {
  const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== "" && v !== false && v != null));
  const res = await fetch(`${path}${qs.toString() ? "?" + qs : ""}`);
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || res.statusText);
  return res.json();
}

async function loadFilters() {
  const f = await api("/api/filters");
  const fill = (sel, items) => { sel.length = 1; items.forEach((v) => sel.add(new Option(v, v))); };
  fill($("fCity"), f.cities);
  fill($("fPlatform"), f.platforms);
  fill($("rTopic"), f.topics);
  $("dateRange").textContent = f.date_from ? `${f.date_from} → ${f.date_to}` : "no data yet";
}

function renderKpis(k) {
  const tiles = [
    ["Total reviews", k.total_reviews.toLocaleString("en-IN"), "in current filter"],
    ["Average rating", k.avg_rating ?? "–", "out of 5 stars"],
    ["CSAT", pct(k.csat), "share of 4–5★ reviews"],
    ["Negative sentiment", pct(k.pct_negative), "from review text"],
    ["Stars ≠ text", k.mismatches.toLocaleString("en-IN"), "hidden dissatisfaction"],
  ];
  $("kpis").innerHTML = tiles.map(([l, v, n]) =>
    `<div class="kpi"><div class="label">${l}</div><div class="value">${v}</div><div class="note">${n}</div></div>`).join("");
}

function baseChartOpts() {
  Chart.defaults.font.family = "Inter, system-ui, sans-serif";
  Chart.defaults.color = css("--muted");
  Chart.defaults.borderColor = css("--border");
}

function renderTrend(trend) {
  const data = {
    labels: trend.map((t) => t.week.slice(5)),
    datasets: [
      { type: "line", label: "Avg rating", data: trend.map((t) => t.avg_rating), yAxisID: "y",
        borderColor: css("--accent"), backgroundColor: css("--accent"), tension: .3, pointRadius: 2, borderWidth: 2 },
      { type: "bar", label: "% negative", data: trend.map((t) => +(t.pct_negative * 100).toFixed(1)), yAxisID: "y1",
        backgroundColor: css("--neg") + "55", borderRadius: 3 },
    ],
  };
  const options = {
    responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
    plugins: { legend: { position: "bottom", labels: { boxWidth: 12 } },
      tooltip: { callbacks: { title: (i) => `Week of ${trend[i[0].dataIndex].week} · ${trend[i[0].dataIndex].reviews} reviews` } } },
    scales: { y: { min: 1, max: 5, title: { display: true, text: "Stars" }, grid: { display: false } },
      y1: { position: "right", min: 0, max: 100, ticks: { callback: (v) => v + "%" } } },
  };
  charts.trend?.destroy();
  charts.trend = new Chart($("trendChart"), { data, options });
}

function renderTopics(topics) {
  const t = topics.filter((x) => x.topic !== "Other");
  const data = {
    labels: t.map((x) => x.topic),
    datasets: [
      { label: "Negative", data: t.map((x) => x.negative), backgroundColor: css("--neg") },
      { label: "Neutral", data: t.map((x) => x.mentions - x.negative - x.positive), backgroundColor: css("--neu") + "88" },
      { label: "Positive", data: t.map((x) => x.positive), backgroundColor: css("--pos") + "bb" },
    ],
  };
  const options = {
    indexAxis: "y", responsive: true, maintainAspectRatio: false,
    plugins: { legend: { position: "bottom", labels: { boxWidth: 12 } },
      tooltip: { callbacks: { afterTitle: (i) => `${pct(t[i[0].dataIndex].pct_negative)} negative · ${t[i[0].dataIndex].avg_rating}★ avg` } } },
    scales: { x: { stacked: true, title: { display: true, text: "Mentions" } }, y: { stacked: true, grid: { display: false } } },
    onClick: (_e, els) => {
      if (!els.length) return;
      $("rTopic").value = t[els[0].index].topic; $("rSentiment").value = "negative";
      Object.assign(state, { topic: $("rTopic").value, sentiment: "negative", page: 1 });
      loadReviews(); $("explorer").scrollIntoView({ behavior: "smooth" });
    },
  };
  charts.topic?.destroy();
  charts.topic = new Chart($("topicChart"), { type: "bar", data, options });
}

function renderSegments(tableId, rows, key) {
  const maxNeg = Math.max(...rows.map((r) => r.pct_negative), 0.01);
  $(tableId).querySelector("tbody").innerHTML = rows.map((r) => `
    <tr data-value="${esc(r.segment)}" class="${state[key] === r.segment ? "active" : ""}">
      <td>${esc(r.segment)}</td><td class="num">${r.reviews.toLocaleString("en-IN")}</td>
      <td class="num">${r.avg_rating.toFixed(2)}</td><td class="num">${pct(r.csat)}</td>
      <td class="num">${pct(r.pct_negative)}<span class="bar" style="width:${Math.round(40 * r.pct_negative / maxNeg)}px"></span></td>
    </tr>`).join("");
  $(tableId).querySelectorAll("tbody tr").forEach((tr) => tr.addEventListener("click", () => {
    const v = tr.dataset.value;
    state[key] = state[key] === v ? "" : v;
    $(key === "city" ? "fCity" : "fPlatform").value = state[key];
    refresh();
  }));
}

function renderInsights(list) {
  $("insights").innerHTML = list.length ? list.map((i) => `
    <li class="insight">
      <div class="row"><span class="sev ${i.severity}">${i.severity}</span><strong>${esc(i.title)}</strong></div>
      <div class="detail">${esc(i.detail)}</div>
      <div class="action">${esc(i.action)}</div>
    </li>`).join("") : `<li class="muted">Not enough data for insights yet.</li>`;
}

async function loadReviews() {
  const params = { city: state.city, platform: state.platform, topic: state.topic, sentiment: state.sentiment,
    q: state.q, mismatch: state.mismatch, page: state.page, size: state.size };
  const r = await api("/api/reviews", params);
  state.totalPages = Math.max(1, Math.ceil(r.total / r.size));
  $("reviewCount").textContent = `${r.total.toLocaleString("en-IN")} matching reviews`;
  $("pageInfo").textContent = `Page ${r.page} of ${state.totalPages}`;
  $("prevPage").disabled = r.page <= 1; $("nextPage").disabled = r.page >= state.totalPages;
  $("reviewRows").innerHTML = r.items.length ? r.items.map((x) => `
    <tr>
      <td class="muted" style="white-space:nowrap">${x.date}</td>
      <td>${esc(x.city)}<br><span class="muted">${esc(x.platform)}</span></td>
      <td class="num"><span class="stars">${"★".repeat(x.rating)}</span></td>
      <td><span class="pill ${x.sentiment}">${x.sentiment}</span>${x.mismatch ? '<span class="flag">stars ≠ text</span>' : ""}</td>
      <td>${x.topics.map((t) => `<span class="pill">${esc(t)}</span>`).join("")}</td>
      <td>${esc(x.text)}</td>
    </tr>`).join("") : `<tr><td colspan="6" class="muted">No reviews match these filters.</td></tr>`;
  const exportParams = new URLSearchParams(Object.entries(params).filter(([k, v]) => v && !["page", "size"].includes(k)));
  $("btnExport").href = "/api/export.csv" + (exportParams.toString() ? "?" + exportParams : "");
}

async function refresh() {
  state.page = 1;
  const d = await api("/api/dashboard", { city: state.city, platform: state.platform });
  renderKpis(d.kpis); renderTrend(d.trend); renderTopics(d.topics);
  renderSegments("cityTable", d.cities, "city"); renderSegments("platformTable", d.platforms, "platform");
  await loadReviews();
}

async function loadInsights() {
  const [ins, sum] = await Promise.all([api("/api/insights"), api("/api/summary")]);
  renderInsights(ins.insights);
  $("summaryText").textContent = sum.summary || "Upload reviews to generate a summary.";
  $("summarySource").textContent = sum.source.startsWith("llm") ? "AI-generated" : "rule-based";
}

async function reloadAll() { await loadFilters(); await Promise.all([refresh(), loadInsights()]); }

function wire() {
  $("fCity").onchange = (e) => { state.city = e.target.value; refresh(); };
  $("fPlatform").onchange = (e) => { state.platform = e.target.value; refresh(); };
  $("rTopic").onchange = (e) => { state.topic = e.target.value; state.page = 1; loadReviews(); };
  $("rSentiment").onchange = (e) => { state.sentiment = e.target.value; state.page = 1; loadReviews(); };
  $("rMismatch").onchange = (e) => { state.mismatch = e.target.checked; state.page = 1; loadReviews(); };
  let t; $("rSearch").oninput = (e) => { clearTimeout(t); t = setTimeout(() => { state.q = e.target.value.trim(); state.page = 1; loadReviews(); }, 300); };
  $("prevPage").onclick = () => { if (state.page > 1) { state.page--; loadReviews(); } };
  $("nextPage").onclick = () => { if (state.page < state.totalPages) { state.page++; loadReviews(); } };

  const dlg = $("uploadDialog");
  $("btnUpload").onclick = () => { $("uploadMsg").textContent = ""; dlg.showModal(); };
  $("btnClose").onclick = () => dlg.close();
  $("uploadForm").onsubmit = async (e) => {
    e.preventDefault();
    const file = $("uploadFile").files[0]; if (!file) return;
    const fd = new FormData(); fd.append("file", file);
    $("uploadMsg").textContent = "Analysing…"; $("btnDoUpload").disabled = true;
    try {
      const res = await fetch(`/api/upload?replace=${$("uploadReplace").checked}`, { method: "POST", body: fd });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail);
      $("uploadMsg").textContent = `Done: ${body.inserted} reviews added, ${body.skipped_invalid} invalid rows skipped.`;
      Object.assign(state, { city: "", platform: "" }); await reloadAll();
    } catch (err) { $("uploadMsg").textContent = "Error: " + err.message; }
    finally { $("btnDoUpload").disabled = false; }
  };
  $("btnReset").onclick = async () => {
    $("uploadMsg").textContent = "Reloading demo data…";
    const res = await fetch("/api/reset-demo", { method: "POST" });
    const body = await res.json();
    $("uploadMsg").textContent = `Demo data reloaded (${body.inserted} reviews).`;
    Object.assign(state, { city: "", platform: "" }); await reloadAll();
  };
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { baseChartOpts(); refresh(); });
}

baseChartOpts(); wire();
reloadAll().catch((e) => { $("summaryText").textContent = "Could not load data: " + e.message; });
