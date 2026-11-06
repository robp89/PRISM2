/* PRISM2 viewer: plain JavaScript, no build step. Reads the API served by `prism serve`. */
"use strict";

const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (x, d = 3) => (x === null || x === undefined || Number.isNaN(x)) ? "–" : (Math.abs(x) >= 1000 ? x.toFixed(0) : Number(x.toPrecision(d)).toString());
const api = async (path, opts) => {
  const r = await fetch(`/api${path}`, opts);
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw Object.assign(new Error(r.statusText), { body, status: r.status });
  return body;
};

const GLOSSARY = {
  tier: "Quality tier A to D: how far the inventory can be trusted, from measured, reviewed and signed off (A) to screening only (D).",
  coverage: "How much of the operating window and which feedstock grades the runs actually cover.",
  balance: "Whether what goes in (element by element) equals what comes out, within a tolerance.",
  "fitted model": "A fast stand-in for the simulation or plant (a surrogate), trained on runs and tested on runs it never saw.",
  "held-out": "Runs set aside before fitting and used only to test the model.",
  gate: "The accuracy test a fitted model must pass before its inventory can be certified.",
  envelope: "The spread of an exchange across low, mid and high feedstock grades.",
  driver: "The input whose variation moves this exchange most (rank correlation in the Monte Carlo).",
  "R²": "Share of the variation in held-out results the model explains (1 is perfect).",
  "p5 to p95": "The range holding 90% of Monte Carlo results.",
};
const g = (term, label) => `<abbr data-g="${esc(term)}">${esc(label || term)}</abbr>`;

const LEVEL_BADGE = { "Ready": "b-teal", "Use with care": "b-tealt", "Screening only": "b-grey", "Demo": "b-lime", "Needs fixing": "b-warn", "Failed": "b-warn", "Ready to build": "b-tealt", "Not started": "b-grey", "Building": "b-grey" };
const SEV_BADGE = { error: "b-warn", warning: "b-limet", info: "b-tealt", skipped: "b-grey", pass: "b-tealt" };
const STEPS = [["process", "Process"], ["data", "Your data"], ["check", "Check"], ["build", "Build"], ["use", "Use"]];
const state = { snap: null, grade: null, sev: "error", busy: false };

/* ---- shell ---- */
function setAdvanced(on) {
  document.body.classList.toggle("advanced", on);
  $("#advanced").checked = on;
  try { localStorage.setItem("prism.advanced", on ? "1" : "0"); } catch (e) { /* storage blocked */ }
}
function crumbs(parts) {
  $("#crumbs").innerHTML = parts.map((p) => p.href ? `<a href="${p.href}">${esc(p.t)}</a>` : `<span>${esc(p.t)}</span>`).join('<span class="sep">/</span>');
}
function navActive(key) { document.querySelectorAll("#mainnav a").forEach((a) => a.classList.toggle("active", a.dataset.nav === key)); }

/* ---- small components ---- */
const badge = (t, cls) => `<span class="badge ${cls}">${esc(t)}</span>`;
const kt = (k, t, extra = "") => `<div class="kt"><span class="kicker">${esc(k)}</span><h2>${t}</h2>${extra}</div>`;
const tierBox = (t) => `<span class="tier tier-${t}">${esc(t)}</span>`;
function rangeBar(v, lo, hi, min, max) {
  const span = max - min || 1, pos = (x) => Math.max(0, Math.min(100, ((x - min) / span) * 100));
  return `<div class="range" title="${fmt(lo)} to ${fmt(hi)}"><div class="track"></div><div class="band" style="left:${pos(lo)}%;width:${Math.max(1, pos(hi) - pos(lo))}%"></div><div class="dot" style="left:${pos(v)}%"></div></div>`;
}

function verdictCard(s) {
  const v = s.verdict, c = s.certification;
  const qs = v.questions.map((q) => `<div class="q"><span class="badge ans a-${q.a}">${esc(q.a)}</span><div><div><b>${esc(q.q)}</b></div><div class="muted small">${esc(q.why)}</div>${q.fix ? `<div class="fix">→ ${esc(q.fix)}</div>` : ""}</div></div>`).join("");
  const blockers = c.blockers?.length ? `<div class="callout warn"><b>Export blocked:</b> ${c.blockers.map(esc).join("; ")}</div>` : `<div class="callout info"><b>Certified.</b> Exports are allowed.</div>`;
  const stale = s.stale?.length ? `<div class="callout lime"><b>Outdated:</b> ${s.stale.map(esc).join(", ")} changed since the last build.</div>` : "";
  return `<section class="card verdict">
    <div class="stack" style="gap:14px">
      <div class="row">${badge(v.level, LEVEL_BADGE[v.level] || "b-grey")}<span class="muted small">${g("tier", "Quality tier")} ${esc(c.tier)} · ${esc(c.tier_text)}</span></div>
      <div class="pill">${esc(v.headline)}</div>
      <div class="row"><span class="muted small">Next:</span><b>${esc(v.next_action)}</b></div>
      ${blockers}${stale}
      ${c.raise_by?.length ? `<div class="small muted"><b>To raise the tier:</b> ${c.raise_by.map(esc).join("; ")}</div>` : ""}
    </div>
    <div>${qs}</div>
  </section>`;
}

function stepStatus(s, key) {
  const c = s.certification;
  switch (key) {
    case "process": return s.process.status === "reviewed" ? "done" : "warn";
    case "data": return s.n_runs ? "done" : "";
    case "check": return s.findings.some((f) => f.severity === "error") ? "warn" : s.n_runs ? "done" : "";
    case "build": return s.model ? (c.gate.passed ? "done" : "warn") : "";
    case "use": return s.inventory ? (c.certified ? "done" : "warn") : "";
  }
  return "";
}

/* ---- pages ---- */
async function pageProjects() {
  navActive("projects"); crumbs([{ t: "Projects" }]);
  const list = await api("/projects");
  $("#app").innerHTML = `
    <div class="stack">
      <div class="kt"><span class="kicker">PRISM · simulation to inventory</span><h1>Projects</h1>
      <p class="lede">Each project is one inventory being produced, kept as plain files in git. Bring a simulation or plant data; PRISM checks it, fits and tests a model, certifies it and hands XYCLE a ready inventory with its evidence and ranges.</p></div>
      <div class="grid g3">${list.map(projectCard).join("") || `<div class="empty">No model repositories found. Run <code>prism init my-model</code>.</div>`}</div>
    </div>`;
}
function projectCard(p) {
  if (p.error) return `<div class="card"><h3>${esc(p.id)}</h3><div class="callout warn">${esc(p.error)}</div></div>`;
  return `<a class="card project-card" href="#/p/${encodeURIComponent(p.id)}">
    <div class="row between">${badge(p.verdict.level, LEVEL_BADGE[p.verdict.level] || "b-grey")}${tierBox(p.tier)}</div>
    <div class="kt"><span class="kicker">${esc(p.process.title)}</span><h3 style="font-size:17px">${esc(p.title)}</h3></div>
    <div class="muted small">${esc(p.verdict.headline)}</div>
    <div class="row small"><span class="muted">${p.n_runs} runs · ${esc(p.origin)}</span>${p.process.status === "draft" ? badge("draft process", "b-warn") : ""}${p.stale ? badge("outdated", "b-limet") : ""}</div>
    <div class="small"><span class="muted">Next:</span> <b>${esc(p.verdict.next_action)}</b></div>
  </a>`;
}

async function pageProject(pid, step) {
  navActive("projects");
  if (!state.snap || state.snap.id !== pid) { state.snap = await api(`/projects/${encodeURIComponent(pid)}`); state.grade = null; }
  const s = state.snap;
  step = step || "use";
  crumbs([{ t: "Projects", href: "#/" }, { t: s.title, href: `#/p/${encodeURIComponent(pid)}` }, { t: STEPS.find((x) => x[0] === step)?.[1] || step }]);
  const steps = STEPS.map(([k, t], i) => `<a class="step ${stepStatus(s, k)} ${k === step ? "active" : ""}" href="#/p/${encodeURIComponent(pid)}/${k}"><span class="n">${i + 1}</span>${t}</a>`).join("");
  const body = { process: stepProcess, data: stepData, check: stepCheck, build: stepBuild, use: stepUse }[step](s);
  $("#app").innerHTML = `<div class="stack">
    <div class="row between"><div class="kt"><span class="kicker">${esc(s.process.title)} · ${esc(s.origin)} data</span><h1>${esc(s.title)}</h1></div>
      <div class="row small muted">${s.built_at ? `Built ${esc(s.built_at.replace("T", " ").slice(0, 16))}` : "Never built"}</div></div>
    ${verdictCard(s)}
    <nav class="steps">${steps}</nav>
    ${body}
  </div>`;
  bindProject(s);
}

function stepProcess(s) {
  const p = s.process;
  const draft = p.status !== "reviewed" ? `<div class="callout warn"><b>Draft process type.</b> Results cannot be rated above tier D until the named owners review it and record the review in the process-type file.</div>` : "";
  const fields = Object.entries(p.fields).map(([k, f]) => `<tr><td><b>${esc(f.label || k)}</b><div class="mono muted">${esc(k)}</div></td><td>${esc(f.group || "")}</td><td>${esc(f.unit || "")}</td><td class="num">${fmt(f.min)} to ${fmt(f.max)}</td><td class="num">${f.default ?? (f.required ? "required" : "–")}</td></tr>`).join("");
  const ex = p.exchanges.map((e) => `<tr><td>${esc(e.name)}</td><td>${esc(e.category)}</td><td>${esc(e.unit)}</td><td><span class="formula">${esc(e.formula)}</span></td><td>${esc(e.assumption || "")}</td></tr>`).join("");
  const sc = s.scope || {};
  return `<div class="grid g-side">
    <div class="stack">
      <section class="card">${kt("Process type", esc(p.title), `<div class="row small">${badge(p.status, p.status === "reviewed" ? "b-teal" : "b-warn")}<span class="mono muted">${esc(p.id)} v${esc(p.version)}</span>${p.placeholder ? badge("placeholder", "b-grey") : ""}${p.wp ? badge(p.wp, "b-grey") : ""}</div>`)}
        ${draft}
        <div class="muted">${esc(p.boundary || "")}</div>
        <div class="tbl-wrap"><table class="tbl"><tr><th>Field</th><th>Group</th><th>Unit</th><th class="num">Window</th><th class="num">Default</th></tr>${fields}</table></div>
      </section>
      <section class="card adv-only">${kt("Recipe", "Exchanges as formulas")}<p class="muted small" style="margin:0">Every exchange is a formula of the inputs, written in the subset XYCLE's Parameter Import accepts. Assumption ids point to docs/ASSUMPTIONS.md.</p>
        <div class="tbl-wrap"><table class="tbl"><tr><th>Exchange</th><th>Category</th><th>Unit</th><th>Formula</th><th>Assumption</th></tr>${ex}</table></div></section>
    </div>
    <div class="stack">
      <section class="card">${kt("Scope card", "What this inventory is for")}
        <div class="small"><div class="muted">Goal</div><div>${esc(sc.goal || "not set")}</div></div>
        <div class="small"><div class="muted">Functional unit</div><div>${esc(sc.functional_unit || "not set")}</div></div>
        <div class="small"><div class="muted">Boundary</div><div>${esc(sc.boundary || "not set")}</div></div>
        <div class="row small">${badge(sc.intended_use || "use not set", "b-grey")}${badge("target tier " + (sc.target_tier || "–"), "b-tealt")}</div>
        <div class="small muted">${sc.agreed_by ? `Agreed by ${esc(sc.agreed_by.name)}` : "Not yet agreed by the LCA practitioner"}</div>
      </section>
      <section class="card">${kt("Owners", "Who reviews")}
        ${Object.entries(p.owners || {}).map(([k, v]) => `<div class="row between small"><span class="muted">${esc(k.replace("_", " "))}</span><b>${esc(v)}</b></div>`).join("")}
        <div class="small muted">${p.reviews?.length ? p.reviews.map((r) => `${esc(r.by)}, ${esc(r.date)}`).join("<br>") : "No review recorded"}</div>
      </section>
      <section class="card">${kt("Rules", `${p.rules.length} checks`)}${p.rules.map((r) => `<div class="row small"><span class="badge b-grey">${esc(r.id)}</span>${esc(r.title || r.check)}</div>`).join("")}</section>
    </div></div>`;
}

function stepData(s) {
  const cov = s.coverage, m = s.manifest.data || {};
  const covRows = Object.entries(cov.fields).map(([k, v]) => `<tr><td class="mono">${esc(k)}</td><td style="width:40%"><div class="bar"><span style="width:${v.share * 100}%"></span></div></td><td class="num">${v.filled}/${v.bins}</td><td class="num muted">${v.observed ? fmt(v.observed[0]) + " to " + fmt(v.observed[1]) : "–"}</td></tr>`).join("");
  const grades = Object.entries(cov.grades).map(([k, n]) => `<div class="row between small"><span>${esc(k)}</span>${badge(n + " runs", n ? "b-tealt" : "b-warn")}</div>`).join("") || `<div class="muted small">No feedstock grades defined.</div>`;
  const cols = s.runs_preview.length ? Object.keys(s.runs_preview[0]).slice(0, 14) : [];
  const exc = m.exclude || [];
  return `<div class="grid g-side">
    <div class="stack">
      <section class="card">${kt("Your data", `${s.n_runs} runs from <span class="mono">${esc(m.runs || "–")}</span>`)}
        <div class="row">${badge(s.origin, s.origin === "synthetic" ? "b-lime" : "b-tealt")}${m.tool ? `<span class="muted small">${esc(m.tool.name)} ${esc(m.tool.version || "")}</span>` : ""}</div>
        ${s.origin === "synthetic" ? `<div class="callout lime"><b>Invented data.</b> It shows the workflow and proves nothing. Exports are refused outside demo mode.</div>` : ""}
        <div class="tbl-wrap"><table class="tbl"><tr>${cols.map((c) => `<th>${esc(c)}</th>`).join("")}</tr>${s.runs_preview.map((r) => `<tr>${cols.map((c) => `<td class="${typeof r[c] === "number" ? "num" : ""}">${esc(typeof r[c] === "number" ? fmt(r[c], 4) : r[c])}</td>`).join("")}</tr>`).join("")}</table></div>
        <div class="muted small">First ${s.runs_preview.length} of ${s.n_runs} runs.</div>
      </section>
      <section class="card">${kt("Coverage", `${Math.round(cov.share * 100)}% of the operating window`)}<p class="muted small" style="margin:0">Each field's window is split in four; a bin counts when a run falls in it. ${g("coverage", "Why coverage matters")}.</p>
        <table class="tbl"><tr><th>Field</th><th>Bins filled</th><th class="num"></th><th class="num">Observed</th></tr>${covRows}</table>
        ${cov.gaps.length ? `<div class="callout lime">Gaps in ${cov.gaps.map(esc).join(", ")}. Generate a run sheet with <code>prism design</code>.</div>` : ""}
      </section>
    </div>
    <div class="stack">
      <section class="card">${kt("Feedstock grades", "Runs per grade")}${grades}</section>
      <section class="card">${kt("Left out on purpose", `${exc.length} run(s)`)}${exc.map((e) => `<div class="small"><b class="mono">${esc(e.run)}</b><div class="muted">${esc(e.reason)}</div></div>`).join("") || `<div class="muted small">None. Exclusions are recorded in prism.yaml with a reason.</div>`}</section>
    </div></div>`;
}

function stepCheck(s) {
  const rows = s.rules.map((r) => `<tr><td><span class="badge b-grey">${esc(r.id)}</span></td><td><b>${esc(r.title)}</b><div class="mono muted small">${esc(r.check)}</div></td><td class="num">${r.counts.pass}</td><td class="num">${r.counts.warning}</td><td class="num">${r.counts.error}</td><td class="num">${r.counts.skipped}</td><td>${badge(r.status, SEV_BADGE[r.status])}</td></tr>`).join("");
  const counts = s.findings.reduce((a, f) => ((a[f.severity] = (a[f.severity] || 0) + 1), a), {});
  const sevs = ["error", "warning", "info", "skipped"];
  const list = s.findings.filter((f) => state.sev === "all" || f.severity === state.sev);
  return `<div class="stack">
    <section class="card">${kt("Check", "Every rule, run by run")}<p class="muted small" style="margin:0">A rule that cannot run reports <b>skipped</b>, never pass. Runs left out in prism.yaml show as info.</p>
      <div class="tbl-wrap"><table class="tbl"><tr><th>Rule</th><th>Check</th><th class="num">Pass</th><th class="num">Warn</th><th class="num">Fail</th><th class="num">Skipped</th><th>Status</th></tr>${rows}</table></div></section>
    <section class="card">${kt("Findings", "By file and line")}
      <div class="chips">${sevs.map((v) => `<button class="chip ${state.sev === v ? "on" : ""}" data-sev="${v}">${v} · ${counts[v] || 0}</button>`).join("")}<button class="chip ${state.sev === "all" ? "on" : ""}" data-sev="all">all</button></div>
      <div class="tbl-wrap"><table class="tbl"><tr><th>Where</th><th>Severity</th><th>Id</th><th>Message</th></tr>
      ${list.slice(0, 300).map((f) => `<tr><td class="where">${esc(f.where)}</td><td>${badge(f.severity, SEV_BADGE[f.severity])}</td><td class="mono small">${esc(f.id)}${f.subject ? `<div class="muted">${esc(f.subject)}</div>` : ""}</td><td>${esc(f.message)}${f.fix ? `<div class="fix">→ ${esc(f.fix)}</div>` : ""}</td></tr>`).join("") || `<tr><td colspan="4" class="muted">Nothing here.</td></tr>`}</table></div>
      ${list.length > 300 ? `<div class="muted small">Showing 300 of ${list.length}. Run <code>prism validate</code> for all.</div>` : ""}
    </section></div>`;
}

function parity(points, w = 300, h = 240) {
  const ys = points.y, yh = points.yhat;
  if (!ys?.length) return "";
  const lo = Math.min(...ys, ...yh), hi = Math.max(...ys, ...yh), pad = (hi - lo) * 0.06 || 1;
  const a = lo - pad, b = hi + pad, X = (v) => 36 + ((v - a) / (b - a)) * (w - 48), Y = (v) => h - 28 - ((v - a) / (b - a)) * (h - 40);
  return `<svg viewBox="0 0 ${w} ${h}" width="100%" style="max-width:360px;display:block;margin:0 auto" role="img" aria-label="Held-out runs: measured against predicted">
    <line x1="${X(a)}" y1="${Y(a)}" x2="${X(b)}" y2="${Y(b)}" stroke="#cfd6de" stroke-dasharray="4 4"/>
    <line x1="36" y1="${h - 28}" x2="${w - 12}" y2="${h - 28}" stroke="#e3e7ec"/><line x1="36" y1="12" x2="36" y2="${h - 28}" stroke="#e3e7ec"/>
    ${ys.map((v, i) => `<circle cx="${X(v)}" cy="${Y(yh[i])}" r="4" fill="#12876f" fill-opacity=".8"><title>run value ${fmt(v)}, model ${fmt(yh[i])}</title></circle>`).join("")}
    <text x="${w / 2}" y="${h - 6}" font-size="11" fill="#404d5e" text-anchor="middle">held-out run value</text>
    <text x="12" y="${h / 2}" font-size="11" fill="#404d5e" text-anchor="middle" transform="rotate(-90 12 ${h / 2})">model</text>
    <text x="40" y="22" font-size="11" fill="#404d5e">${fmt(a)} to ${fmt(b)}</text></svg>`;
}

function stepBuild(s) {
  const m = s.model, c = s.certification;
  const btns = `<div class="row"><button class="btn primary" data-act="build">Build model and inventory</button><button class="btn" data-act="build-demo">Build in demo mode</button><span class="muted small" id="busy"></span></div>`;
  if (!m) return `<section class="card">${kt("Build", "No fitted model yet")}<p class="muted" style="margin:0">${s.n_runs < s.gate.min_runs ? `${s.n_runs} runs: at least ${s.gate.min_runs} are needed to fit and test a model. The inventory uses the mean of the runs (a quick look).` : "Data checks done: fit and test the model."}</p>${btns}</section>`;
  const targets = Object.entries(m.targets).map(([t, r]) => {
    const fams = Object.entries(r.families).map(([f, v]) => `<tr class="${f === r.chosen ? "hl" : ""}"><td>${esc(f)}${f === r.chosen ? " " + badge("chosen", "b-teal") : ""}</td><td class="num">${fmt(v.holdout.r2, 4)}</td><td class="num">${fmt(v.holdout.p90_rel_err_pct)}</td><td class="num">${fmt(v.holdout.normality_p)}</td><td class="num adv-only">${fmt(v.holdout.rmse)}</td><td class="num adv-only">${v.cv_r2 == null ? "–" : fmt(v.cv_r2, 4)}</td></tr>`).join("");
    const gt = c.gate.targets?.[t];
    const checks = gt ? gt.checks.map((k) => `<div class="row between small"><span>${esc(k.label)}</span><span>${fmt(k.value, 3)} <span class="muted">vs ${fmt(k.limit)}</span> ${badge(k.pass ? "pass" : "fail", k.pass ? "b-tealt" : "b-warn")}</span></div>`).join("") : "";
    const sob = r.sobol ? m.inputs.map((k, i) => [k, r.sobol.total[i]]).sort((a, b) => b[1] - a[1]).slice(0, 6) : [];
    const sobHtml = sob.map(([k, v]) => `<div class="small"><div class="row between"><span class="mono">${esc(k)}</span><span>${fmt(Math.max(0, v), 2)}</span></div><div class="bar"><span style="width:${Math.max(0, Math.min(1, v)) * 100}%;background:#3c8c6c"></span></div></div>`).join("");
    return `<section class="card">
      <div class="row between">${kt(t.replaceAll("_", " "), `Held-out ${g("R²")} ${fmt(r.families[r.chosen].holdout.r2, 4)}`)}${gt ? badge(gt.passed ? "gate passed" : "gate failed", gt.passed ? "b-teal" : "b-warn") : ""}</div>
      <div class="grid g2"><div class="stack" style="gap:10px">
        <table class="tbl"><tr><th>Family</th><th class="num">R²</th><th class="num">p90 err %</th><th class="num">Normality p</th><th class="num adv-only">RMSE</th><th class="num adv-only">5-fold R²</th></tr>${fams}</table>
        ${checks}</div>
        <div>${parity(r.holdout_points)}</div></div>
      <div class="adv-only"><div class="kicker" style="margin-bottom:6px">What drives it (total Sobol index)</div><div class="grid g3">${sobHtml}</div></div>
    </section>`;
  }).join("");
  return `<div class="stack">
    <section class="card">${kt("Build", `${m.n_train} runs trained, ${m.n_holdout} ${g("held-out", "held out")}`)}
      <p class="muted small" style="margin:0">Families compared on the same split: ${m.families.map(esc).join(", ")}. Decision rule, written first: ${esc(m.decision_rule)}. Only a polynomial can be exported to XYCLE as a formula; other families export inventory values.</p>${btns}</section>
    ${targets}</div>`;
}

function stepUse(s) {
  const inv = s.inventory, c = s.certification;
  if (!inv) return `<section class="card">${kt("Use", "No inventory yet")}<p class="muted">Build the project first.</p><div class="row"><button class="btn primary" data-act="build">Build</button></div></section>`;
  const grades = Object.keys(inv.grades);
  const gsel = state.grade && grades.includes(state.grade) ? state.grade : grades.includes("mid") ? "mid" : grades[0];
  state.grade = gsel;
  const gr = inv.grades[gsel];
  const fu = inv.functional_unit || {};
  const rows = inv.exchanges.map((e) => {
    const v = gr.exchanges[e.key], env = inv.envelope[e.key];
    const lo = Math.min(env.p5, v.p5), hi = Math.max(env.p95, v.p95);
    return `<tr class="${e.flow === "reference" ? "hl" : ""}"><td><b>${esc(e.name)}</b>${e.assumption ? ` <span class="muted small">${esc(e.assumption)}</span>` : ""}</td><td>${badge(e.category, e.category.includes("Input") ? "b-tealt" : e.category === "Waste" || e.category.startsWith("Emission") ? "b-warn" : "b-grey")}</td>
      <td class="num"><b>${fmt(v.value, 4)}</b> ${esc(e.unit)}</td><td class="num muted">${fmt(v.p5)} to ${fmt(v.p95)}</td><td>${rangeBar(v.value, v.p5, v.p95, lo * 0.98, hi * 1.02)}</td>
      <td class="num muted">${fmt(env.min)} to ${fmt(env.max)}</td><td class="mono small adv-only">${esc(v.driver || "–")}${v.driver ? ` <span class="muted">ρ ${fmt(v.driver_rho, 2)}</span>` : ""}</td></tr>`;
  }).join("");
  const warns = gr.warnings?.length ? `<div class="callout lime">${gr.warnings.map(esc).join("<br>")}</div>` : "";
  const exportBtns = `<div class="row"><button class="btn primary" data-act="export" ${c.certified ? "" : "disabled"}>Export to XYCLE</button><button class="btn" data-act="export-demo">Demo export (watermarked)</button><span class="muted small" id="busy"></span></div>
    ${c.certified ? "" : `<div class="small muted">Export to XYCLE is unavailable: ${c.blockers.map(esc).join("; ")}.</div>`}<div id="exported"></div>`;
  return `<div class="stack">
    <section class="card">
      <div class="row between">${kt("Inventory", `Per ${esc(fu.amount)} ${esc(fu.unit)} ${esc(fu.of)}`)}<div class="row">${tierBox(c.tier)}<div class="small" style="max-width:260px">${g("tier", "Tier")} ${esc(c.tier)}: ${esc(c.tier_text)}</div></div></div>
      <div class="row between"><div class="chips">${grades.map((x) => `<button class="chip ${x === gsel ? "on" : ""}" data-grade="${esc(x)}">${esc(x)} grade</button>`).join("")}</div>
      <span class="muted small">${g("p5 to p95")} from ${inv.n_mc} Monte Carlo samples · ${g("envelope")} across grades</span></div>
      ${warns}
      <div class="tbl-wrap"><table class="tbl"><tr><th>Exchange</th><th>Category</th><th class="num">Value</th><th class="num">p5 to p95</th><th>Range</th><th class="num">Grade envelope</th><th class="adv-only">${g("driver", "Driver")}</th></tr>${rows}</table></div>
      <div class="muted small">Physical flows only. Background data and impacts are applied in XYCLE; PRISM holds no emission factors.</div>
    </section>
    <div class="grid g2">
      <section class="card">${kt("Hand over", "XYCLE import files")}<p class="muted small" style="margin:0">Parameter Import (.csv) and Model Import (.xlsx, one sheet per grade), plus a draft passport block. Exports fail closed: they are refused while any blocker stands.</p>${exportBtns}
        <div class="row small"><a href="/api/projects/${encodeURIComponent(s.id)}/files/inventory.csv">inventory.csv</a><a href="/api/projects/${encodeURIComponent(s.id)}/files/method-note.md">method-note.md</a><a href="/api/projects/${encodeURIComponent(s.id)}/files/model.json">model.json</a></div></section>
      <section class="card">${kt("Inputs at this point", `${esc(gsel)} grade`)}<div class="tbl-wrap"><table class="tbl">${Object.entries(gr.inputs).map(([k, v]) => `<tr><td class="mono">${esc(k)}</td><td class="num">${fmt(v, 4)}</td></tr>`).join("")}</table></div></section>
    </div>
    ${s.method_note ? `<section class="card">${kt("Method note", "Drafted from the repository")}<div class="note">${md(s.method_note)}</div></section>` : ""}
  </div>`;
}

/* a tiny markdown renderer for the method note (headings, lists, tables, quotes, bold, code) */
function md(src) {
  const inline = (t) => esc(t).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/(^|\s)_(.+?)_(?=\s|$)/g, "$1<i>$2</i>").replace(/`(.+?)`/g, "<code>$1</code>");
  const out = []; let list = false, table = null;
  const flush = () => { if (list) { out.push("</ul>"); list = false; } if (table) { out.push(`<div class="tbl-wrap"><table>${table.join("")}</table></div>`); table = null; } };
  for (const line of src.split("\n")) {
    if (/^\|/.test(line)) {
      if (/^\|[-| ]+\|$/.test(line)) continue;
      const cells = line.split("|").slice(1, -1).map((c) => c.trim());
      if (!table) { flush(); table = [`<tr>${cells.map((c) => `<th>${inline(c)}</th>`).join("")}</tr>`]; } else table.push(`<tr>${cells.map((c) => `<td>${inline(c)}</td>`).join("")}</tr>`);
      continue;
    }
    if (table) flush();
    let m;
    if ((m = line.match(/^(#{1,3}) (.*)/))) { flush(); out.push(`<h${m[1].length}>${inline(m[2])}</h${m[1].length}>`); }
    else if ((m = line.match(/^- (.*)/))) { if (!list) { out.push("<ul>"); list = true; } out.push(`<li>${inline(m[1])}</li>`); }
    else if ((m = line.match(/^> (.*)/))) { flush(); out.push(`<blockquote>${inline(m[1])}</blockquote>`); }
    else if (line.trim()) { flush(); out.push(`<p>${inline(line)}</p>`); }
    else flush();
  }
  flush();
  return out.join("");
}

async function pageLibrary(id) {
  navActive("library");
  const lib = await api("/library");
  if (id) {
    const p = lib.find((x) => x.id === id);
    crumbs([{ t: "Process library", href: "#/library" }, { t: p ? p.title : id }]);
    if (!p) { $("#app").innerHTML = `<div class="empty">Not found.</div>`; return; }
    $("#app").innerHTML = stepProcess({ process: p, scope: null });
    return;
  }
  crumbs([{ t: "Process library" }]);
  $("#app").innerHTML = `<div class="stack"><div class="kt"><span class="kicker">Reviewed configuration, not code</span><h1>Process library</h1>
    <p class="lede">A process type is a file: fields with operating windows, the rules that check each run, and the recipe that turns a run into exchanges. A new route, such as the rare earth module, is a new file reviewed by its owners.</p></div>
    <div class="grid g3">${lib.map((p) => `<a class="card project-card" href="#/library/${encodeURIComponent(p.id)}"><div class="row between">${badge(p.status, p.status === "reviewed" ? "b-teal" : "b-warn")}${p.placeholder ? badge("placeholder", "b-grey") : ""}</div>
      <div class="kt"><span class="kicker">${esc(p.route_family || "")} · ${esc(p.wp || "")}</span><h3 style="font-size:17px">${esc(p.title)}</h3></div>
      <div class="muted small">${esc(p.functional_unit?.amount)} ${esc(p.functional_unit?.unit)} ${esc(p.functional_unit?.of)}</div>
      <div class="small muted">${Object.keys(p.fields).length} fields · ${p.rules.length} rules · ${p.exchanges.length} exchanges</div></a>`).join("")}</div></div>`;
}

/* ---- events ---- */
function bindProject(s) {
  document.querySelectorAll("[data-grade]").forEach((b) => b.addEventListener("click", () => { state.grade = b.dataset.grade; route(); }));
  document.querySelectorAll("[data-sev]").forEach((b) => b.addEventListener("click", () => { state.sev = b.dataset.sev; route(); }));
  document.querySelectorAll("[data-act]").forEach((b) => b.addEventListener("click", async () => {
    const act = b.dataset.act, demo = act.endsWith("demo"), busy = $("#busy");
    document.querySelectorAll("[data-act]").forEach((x) => (x.disabled = true));
    try {
      if (act.startsWith("build")) {
        if (busy) busy.textContent = "Fitting and testing models… this takes a few seconds";
        state.snap = await api(`/projects/${encodeURIComponent(s.id)}/build?demo=${demo}`, { method: "POST" });
        route();
      } else {
        const r = await api(`/projects/${encodeURIComponent(s.id)}/export?demo=${demo}`, { method: "POST" });
        $("#exported").innerHTML = `<div class="callout ${r.watermark ? "lime" : "info"}">${r.watermark ? "<b>Demo export, watermarked.</b> " : ""}${r.files.map((f) => `<a href="/api/projects/${encodeURIComponent(s.id)}/files/${f.replace(/^build\//, "")}">${esc(f.split("/").pop())}</a>`).join(" · ")}${r.notes.length ? `<div class="small" style="margin-top:6px">${r.notes.map(esc).join("<br>")}</div>` : ""}</div>`;
        document.querySelectorAll("[data-act]").forEach((x) => (x.disabled = x.dataset.act === "export" && !s.certification.certified));
      }
    } catch (e) {
      const why = e.body?.detail?.refused?.join("; ") || e.body?.detail || e.message;
      if ($("#exported")) $("#exported").innerHTML = `<div class="callout warn"><b>Refused:</b> ${esc(why)}</div>`;
      else if (busy) busy.textContent = `Failed: ${why}`;
      document.querySelectorAll("[data-act]").forEach((x) => (x.disabled = false));
    }
  }));
}

function bindGlossary() {
  const tip = $("#tip");
  document.addEventListener("mouseover", (e) => {
    const a = e.target.closest("abbr[data-g]");
    if (!a) { tip.hidden = true; return; }
    tip.textContent = GLOSSARY[a.dataset.g] || "";
    const r = a.getBoundingClientRect();
    tip.style.left = Math.min(window.innerWidth - 300, r.left) + "px";
    tip.style.top = r.bottom + 8 + "px";
    tip.hidden = false;
  });
}

async function route() {
  const parts = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean).map(decodeURIComponent);
  try {
    if (parts[0] === "p") await pageProject(parts[1], parts[2]);
    else if (parts[0] === "library") await pageLibrary(parts[1]);
    else { state.snap = null; await pageProjects(); }
  } catch (e) {
    $("#app").innerHTML = `<div class="card"><div class="callout warn"><b>Could not load.</b> ${esc(e.body?.detail || e.message)}</div></div>`;
  }
}

(async function init() {
  let adv = false;
  try { adv = localStorage.getItem("prism.advanced") === "1"; } catch (e) { /* storage blocked */ }
  setAdvanced(adv);
  $("#advanced").addEventListener("change", (e) => setAdvanced(e.target.checked));
  bindGlossary();
  window.addEventListener("hashchange", route);
  try { const v = await api("/version"); $("#footer").textContent = `PRISM2 ${v.prism} · API ${v.api} · research software, not engineering advice`; } catch (e) { /* offline */ }
  route();
})();
