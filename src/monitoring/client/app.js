/* IT Service Desk.
 *
 * Polls rather than streams. Tickets arrive from endpoint agents over HTTP, so
 * there is no single incident to subscribe to, and a short poll against a
 * SQLite table is far less to go wrong mid-presentation than a fan-out
 * subscription. One second keeps the queue feeling live without the trace
 * flickering while someone reads it.
 *
 * Rendering rule: everything on screen comes from the ticket payload. Ownership
 * labels, operational status and the trace vocabulary are all derived
 * server-side, so this file presents state and never decides it. */

const POLL_MS = 1000;

let mode = "tickets";
let filter = "all";
let selectedId = null;
let activeTab = "overview";
let tickets = [];
let lastTraceKey = "";

document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".mode").forEach((b) =>
        b.addEventListener("click", () => setMode(b.dataset.mode)));

    document.querySelectorAll(".filter").forEach((b) =>
        b.addEventListener("click", () => {
            document.querySelectorAll(".filter").forEach((x) => x.classList.remove("active"));
            b.classList.add("active");
            filter = b.dataset.status;
            refresh();
        }));

    refresh();
    setInterval(refresh, POLL_MS);
});

function setMode(next) {
    mode = next;
    document.querySelectorAll(".mode").forEach((b) => {
        const on = b.dataset.mode === next;
        b.classList.toggle("active", on);
        b.setAttribute("aria-selected", String(on));
    });
    document.getElementById("view-tickets").hidden = next !== "tickets";
    document.getElementById("view-live").hidden = next !== "live";
    if (next === "live") renderLive();
}

async function refresh() {
    try {
        const [list, stats] = await Promise.all([
            fetch(`/api/tickets?status=${filter}`).then((r) => r.json()),
            fetch("/api/stats").then((r) => r.json()),
        ]);
        tickets = list;
        renderMetrics(stats);
        renderQueue();
        if (selectedId) renderDetail(find(selectedId));
        if (mode === "live") renderLive();
        setConnected(true);
    } catch {
        setConnected(false);
    }
}

const find = (id) => tickets.find((t) => t.incident_id === id);

function setConnected(ok) {
    document.getElementById("conn-dot").classList.toggle("stale", !ok);
    document.getElementById("conn-label").textContent =
        ok ? `${window.location.host} · live` : "service desk unreachable";
}

/* ------------------------------- metrics ------------------------------- */

function renderMetrics(s) {
    set("m-open", s.open);
    set("m-closed", s.closed);
    set("m-escalated", s.escalated);
    set("m-auto", pct(s.auto_resolution_rate));
    set("m-false", s.confirmations ? pct(s.false_resolution_rate) : "–");
    // Engine latency, not human resolution time. The label says so; keep the
    // unit visible so the number cannot be mistaken for a service-desk SLA.
    set("m-latency", s.avg_latency_ms ? `${s.avg_latency_ms} ms` : "–");
}

const set = (id, v) => { document.getElementById(id).textContent = v; };
const pct = (v) => `${Math.round((v || 0) * 100)}%`;

/* -------------------------------- queue -------------------------------- */

function renderQueue() {
    const el = document.getElementById("queue");
    if (!tickets.length) {
        el.innerHTML = `<li class="empty">No ${filter === "all" ? "" : filter + " "}tickets yet.</li>`;
        return;
    }

    el.innerHTML = tickets.map((t) => `
        <li class="ticket ${t.incident_id === selectedId ? "selected" : ""}
                   ${t.escalated_from_automation ? "is-escalated" : ""}
                   ${t.refused ? "is-refused" : ""}"
            data-id="${esc(t.incident_id)}" tabindex="0" role="button">
          <div class="t-top">
            <span class="t-id">${esc(t.incident_id)}</span>
            ${statusBadge(t)}
          </div>
          <div class="t-title">${esc(t.title || "(no description)")}</div>
          <div class="t-meta">
            ${ownerBadge(t)}
            <span>${esc(t.hostname || "unknown endpoint")}</span>
            ${t.category ? `<span class="sep">·</span><span>${esc(t.category)}</span>` : ""}
            ${t.refused ? `<span class="badge danger">Refused</span>` : ""}
            ${t.false_resolution ? `<span class="badge danger">User: still broken</span>` : ""}
          </div>
        </li>`).join("");

    el.querySelectorAll(".ticket").forEach((node) => {
        const open = () => select(node.dataset.id);
        node.addEventListener("click", open);
        node.addEventListener("keydown", (e) => {
            if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); }
        });
    });
}

function select(id) {
    if (selectedId !== id) activeTab = "overview";
    selectedId = id;
    renderQueue();
    renderDetail(find(id));
}

const ownerBadge = (t) =>
    `<span class="badge ${t.support_level === "HUMAN L2" ? "l2" : "l1"}">${esc(t.support_level || "AUTOMATED L1")}</span>`;

function statusBadge(t) {
    const s = t.display_status || "INVESTIGATING";
    const cls = { INVESTIGATING: "st-investigating", "AWAITING USER": "st-awaiting",
                  CLOSED: "st-closed", ESCALATED: "st-escalated" }[s] || "st-investigating";
    return `<span class="badge ${cls}">${esc(s)}</span>`;
}

/* ------------------------------- detail -------------------------------- */

const TABS = [
    ["overview", "Overview", () => ""],
    ["timeline", "Timeline", (t) => (t.actions || []).length],
    ["diagnostics", "Diagnostics", (t) => commandRows(t).length],
    ["documentation", "Documentation", () => ""],
    ["escalation", "Escalation", () => ""],
];

function renderDetail(t) {
    const pane = document.getElementById("detail");
    if (!t) {
        pane.innerHTML = `<div class="placeholder"><h2>Ticket not in this filter</h2>
            <p>Switch to <strong>All</strong> to see it.</p></div>`;
        return;
    }

    const tabs = TABS.filter(([id]) => id !== "escalation" || t.escalated_from_automation);

    pane.innerHTML = `
      <div class="d-head">
        <div class="d-eyebrow">
          <span class="t-id">${esc(t.incident_id)}</span>
          ${statusBadge(t)} ${ownerBadge(t)}
          ${t.refused ? `<span class="badge danger">Policy refusal</span>` : ""}
        </div>
        <h2>${esc(t.title || t.incident_id)}</h2>
        ${t.user_prompt ? `<p class="d-quote">${esc(t.user_prompt)}</p>` : ""}
      </div>

      <div class="tabs" role="tablist">
        ${tabs.map(([id, label, count]) => {
            const n = count(t);
            return `<button class="tab ${id === activeTab ? "active" : ""}" data-tab="${id}" role="tab">
                      ${label}${n ? `<span class="count">${n}</span>` : ""}</button>`;
        }).join("")}
      </div>

      <div class="panel ${activeTab === "overview" ? "active" : ""}" data-panel="overview">${overviewPanel(t)}</div>
      <div class="panel ${activeTab === "timeline" ? "active" : ""}" data-panel="timeline">${timelinePanel(t)}</div>
      <div class="panel ${activeTab === "diagnostics" ? "active" : ""}" data-panel="diagnostics">${diagnosticsPanel(t)}</div>
      <div class="panel ${activeTab === "documentation" ? "active" : ""}" data-panel="documentation">${documentationPanel(t)}</div>
      ${t.escalated_from_automation
        ? `<div class="panel ${activeTab === "escalation" ? "active" : ""}" data-panel="escalation">${escalationPanel(t)}</div>`
        : ""}
    `;

    pane.querySelectorAll(".tab").forEach((b) =>
        b.addEventListener("click", () => {
            activeTab = b.dataset.tab;
            pane.querySelectorAll(".tab").forEach((x) => x.classList.toggle("active", x === b));
            pane.querySelectorAll(".panel").forEach((p) =>
                p.classList.toggle("active", p.dataset.panel === activeTab));
        }));

    pane.querySelectorAll(".disclosure").forEach((b) =>
        b.addEventListener("click", () => {
            const target = document.getElementById(b.dataset.target);
            const open = target.hasAttribute("hidden");
            target.toggleAttribute("hidden", !open);
            b.textContent = open ? b.dataset.hide : b.dataset.show;
        }));
}

/* -- Overview ----------------------------------------------------------- */

function overviewPanel(t) {
    const confirmed = { solved: "Confirmed solved", still_broken: "Reported still broken" }[t.user_confirmed]
        || "Not yet confirmed";

    return `
      ${t.false_resolution ? falseResolutionCallout() : ""}
      ${t.refused ? refusalCallout() : ""}
      ${t.escalated_from_automation ? handoff(t) : ""}

      <h3 class="sec">Incident</h3>
      <dl class="kv">
        <div><dt>Incident</dt><dd class="mono">${esc(t.incident_id)}</dd></div>
        <div><dt>Endpoint</dt><dd class="mono">${esc(t.hostname || "–")}</dd></div>
        <div><dt>Category</dt><dd>${esc(t.category || "–")}</dd></div>
        <div><dt>Severity</dt><dd>${esc(t.severity || "–")}</dd></div>
        <div><dt>Status</dt><dd>${esc(t.display_status || "–")}</dd></div>
        <div><dt>Support owner</dt><dd>${esc(t.support_level || "–")}</dd></div>
        <div><dt>Runbook matched</dt><dd class="mono">${esc(t.runbook_id || "none matched")}</dd></div>
        <div><dt>Employee confirmation</dt><dd>${esc(confirmed)}</dd></div>
        <div><dt>Last update</dt><dd class="mono">${esc(clock(t.updated_at) || "–")}</dd></div>
      </dl>

      ${t.resolution ? `<h3 class="sec">Automated assessment</h3><p>${esc(t.resolution)}</p>` : ""}

      <h3 class="sec">Measured</h3>
      <dl class="kv">
        <div><dt>Engine latency</dt><dd class="mono">${t.latency_ms ?? "–"} ms</dd></div>
        <div><dt>Tool calls</dt><dd class="mono">${t.tool_calls ?? "–"}</dd></div>
        <div><dt>Model tokens</dt><dd class="mono">${(t.tokens_in || 0) + (t.tokens_out || 0) || "none — deterministic run"}</dd></div>
      </dl>`;
}

const falseResolutionCallout = () => `
  <div class="callout crit">
    <h4>Verified fixed, but the employee still cannot work</h4>
    <p>The automated checks passed &mdash; the service came back and verification
       confirmed it. The employee then reported the problem was still present, so
       the automation's own evidence was not enough to close the ticket.</p>
    <p>This is why closure needs both a technical check <em>and</em> the employee's
       word. No automated test can see this gap.</p>
  </div>`;

const refusalCallout = () => `
  <div class="callout crit">
    <h4>Request refused by safety policy</h4>
    <p>The requested action was outside what the endpoint agent is permitted to do.
       It was refused, recorded, and handed to a human. <strong>No remediation was
       executed on the endpoint.</strong></p>
  </div>`;

const handoff = (t) => `
  <div class="handoff">
    <div class="side">
      <div class="who from">AUTOMATED L1</div>
      <div class="what">Tier&nbsp;1 investigation complete</div>
    </div>
    <div class="arrow" aria-hidden="true">&rarr;</div>
    <div class="side">
      <div class="who to">HUMAN L2</div>
      <div class="what">${esc(t.escalation_reason || "Escalated for human review")}</div>
    </div>
  </div>`;

/* -- Timeline ----------------------------------------------------------- */

function timelinePanel(t) {
    const stages = buildTimeline(t);
    if (!stages.length) return `<p class="pending">No lifecycle activity reported yet.</p>`;

    return `<ol class="timeline">${stages.map((s) => `
      <li class="tl">
        <span class="tl-time">${esc(clock(s.timestamp) || "—")}</span>
        <span class="tl-dot ${s.tier || ""} ${s.source === "inferred" ? "inferred" : ""}"></span>
        <span class="tl-body">
          <span class="tl-stage">${esc(s.stage)}${
            s.source === "inferred" ? `<span class="tl-src">from ticket state</span>` : ""}</span>
          ${s.detail ? `<div class="tl-detail">${esc(s.detail)}</div>` : ""}
        </span>
      </li>`).join("")}</ol>
      <p class="doc-note">Stages marked <em>from ticket state</em> are derived from the
         ticket's current state rather than a timestamped audit entry.</p>`;
}

/* Mirrors src/monitoring/presentation.py:timeline(). Kept in the browser so a
 * poll does not need a second round trip; the vocabulary and the honesty rule
 * (recorded vs inferred) are identical. */
function buildTimeline(t) {
    const actions = t.actions || [];
    if (!actions.length) return [];

    const first = (types) => actions.find((a) => types.includes(a.action));
    const stages = [{ stage: "Incident created", timestamp: actions[0].timestamp,
                      detail: t.user_prompt || "", source: "recorded" }];

    [["Security policy check", ["input_check", "blocked"]],
     ["Triage", ["classification"]],
     ["Diagnostics", ["diagnosis"]],
     ["Remediation", ["remediation"]],
     ["Verification", ["verification"]]].forEach(([stage, types]) => {
        const entry = first(types);
        if (!entry) return;
        const all = actions.filter((a) => types.includes(a.action));
        const detail = all.length > 1 ? `${all.length} steps`
            : String(summarise(entry) || entry.command || "").slice(0, 160);
        stages.push({ stage, timestamp: entry.timestamp, detail, source: "recorded", tier: entry.tier });
     });

    if (t.runbook_id) stages.push({ stage: "Runbook applied", timestamp: null,
                                    detail: t.runbook_id, source: "inferred" });
    if (t.user_confirmed) stages.push({
        stage: "Employee confirmation", timestamp: null,
        detail: t.user_confirmed === "solved" ? "Confirmed solved" : "Reported still broken",
        source: "inferred", tier: t.user_confirmed === "solved" ? "green" : "yellow" });
    if (t.status === "closed" || t.status === "escalated") stages.push({
        stage: t.status === "escalated" ? "Escalated to Human Tier 2" : "Ticket closed",
        timestamp: t.updated_at,
        detail: t.status === "escalated" ? (t.escalation_reason || "") : (t.resolution || ""),
        source: "inferred", tier: t.status === "escalated" ? "yellow" : "green" });

    return stages;
}

/* -- Diagnostics -------------------------------------------------------- */

const commandRows = (t) => (t.actions || []).filter((a) => a.command);

function diagnosticsPanel(t) {
    const refused = (t.actions || []).filter((a) => a.tier === "red" || a.action === "blocked");
    const rows = commandRows(t);

    return `
      ${refused.length ? `<h3 class="sec">Refused (${refused.length})</h3>
        <div class="rows">${refused.map(actionRow).join("")}</div>` : ""}

      <h3 class="sec">Commands executed (${rows.length})</h3>
      ${rows.length ? `<div class="rows">${rows.map(actionRow).join("")}</div>`
                    : `<p class="pending">No commands were executed on the endpoint.</p>`}

      <h3 class="sec">Full agent activity</h3>
      <button class="disclosure" data-target="raw-actions-${esc(t.incident_id)}"
              data-show="Show all ${(t.actions || []).length} audit entries"
              data-hide="Hide audit entries">Show all ${(t.actions || []).length} audit entries</button>
      <pre class="raw" id="raw-actions-${esc(t.incident_id)}" hidden>${esc(JSON.stringify(t.actions || [], null, 2))}</pre>`;
}

function actionRow(a) {
    const red = a.tier === "red" || a.action === "blocked";
    return `
      <div class="row ${red ? "red" : ""}">
        <span class="row-time">${esc(clock(a.timestamp) || "—")}</span>
        <span><span class="badge tier-${esc(a.tier || "green")}">${esc(a.action || "action")}</span></span>
        <span class="row-body">
          ${a.command ? `<div class="row-cmd">${esc(a.command)}</div>`
                      : `<div class="row-note">${esc(a.agent || "")}</div>`}
          ${a.output ? `<div class="row-out">${esc(clip(summarise(a), 260))}</div>` : ""}
        </span>
      </div>`;
}

/* -- Documentation ------------------------------------------------------ */

function documentationPanel(t) {
    return `
      <h3 class="sec">Incident report</h3>
      ${t.incident_report ? `
        <div class="doc">
          <div class="doc-head"><h4>Incident ${esc(t.incident_id)}</h4>
            <span class="doc-kind">generated for this incident</span></div>
          <p class="doc-note">Human-readable documentation produced from this specific
             execution &mdash; what was reported, what was found, what was attempted.</p>
          <div class="doc-body">${esc(t.incident_report)}</div>
        </div>`
      : `<p class="pending">No incident report has been reported for this ticket yet.
           It is produced when the incident reaches a terminal state.</p>`}

      <h3 class="sec">Operational runbook</h3>
      ${runbookBlock(t)}`;
}

function runbookBlock(t) {
    const rb = t.runbook;
    if (!rb && !t.runbook_id) {
        return `<p class="pending">No runbook matched this incident. The automated
                system had no pre-existing operational knowledge for this problem.</p>`;
    }
    if (!rb) {
        return `<div class="doc">
            <div class="doc-head"><h4>${esc(t.runbook_id)}</h4>
              <span class="doc-kind">pre-existing knowledge</span></div>
            <p class="doc-note">Matched by the automated system. The full runbook content
               has not been reported to the Service Desk for this ticket.</p>
          </div>`;
    }
    const steps = rb.steps || [];
    return `
      <div class="doc">
        <div class="doc-head">
          <h4>${esc(rb.title || rb.runbook_id || t.runbook_id)}</h4>
          <span class="doc-kind">pre-existing knowledge</span>
        </div>
        <p class="doc-note">Machine-readable operational knowledge that already existed and
           was <em>used</em> to resolve this class of incident. It was not generated during
           this incident. <span class="mono">${esc(rb.runbook_id || t.runbook_id || "")}</span></p>
        ${steps.length ? `<ol class="steps">${steps.map((s) => `
            <li><span>
              ${s.description ? `<div class="s-desc">${esc(s.description)}</div>` : ""}
              ${s.command ? `<div class="s-cmd">${esc(s.command)}</div>` : ""}
            </span></li>`).join("")}</ol>`
          : `<p class="doc-note">No steps were included in the reported runbook.</p>`}
      </div>`;
}

/* -- Escalation --------------------------------------------------------- */

function escalationPanel(t) {
    const attempted = commandRows(t);
    const verification = (t.actions || []).filter((a) => a.action === "verification");

    return `
      ${handoff(t)}

      <h3 class="sec">Why this reached a human</h3>
      <div class="callout warn"><p>${esc(t.escalation_reason || "Escalated for human review.")}</p></div>

      <h3 class="sec">What the employee reported</h3>
      <p class="d-quote">${esc(t.user_prompt || "–")}</p>

      <h3 class="sec">Already attempted by automation (${attempted.length})</h3>
      ${attempted.length ? `<div class="rows">${attempted.map(actionRow).join("")}</div>`
        : `<p class="pending">Nothing was executed on the endpoint.</p>`}

      <h3 class="sec">Technical verification</h3>
      ${verification.length
        ? `<div class="rows">${verification.map(actionRow).join("")}</div>
           ${t.false_resolution ? falseResolutionCallout() : ""}`
        : `<p class="pending">No verification step ran.</p>`}

      <h3 class="sec">Structured handoff payload</h3>
      ${t.escalation ? `
        <button class="disclosure" data-target="raw-esc-${esc(t.incident_id)}"
                data-show="Show raw payload" data-hide="Hide raw payload">Show raw payload</button>
        <pre class="raw" id="raw-esc-${esc(t.incident_id)}" hidden>${esc(JSON.stringify(t.escalation, null, 2))}</pre>`
        : `<p class="pending">No structured escalation payload was reported.</p>`}`;
}

/* --------------------------- Live Operations --------------------------- */

function renderLive() {
    const t = find(selectedId) || mostActive();
    const head = {
        id: document.getElementById("live-id"),
        endpoint: document.getElementById("live-endpoint"),
        status: document.getElementById("live-status"),
        owner: document.getElementById("live-owner"),
        sub: document.getElementById("live-sub"),
    };
    const trace = document.getElementById("trace");

    if (!t) {
        head.id.textContent = head.endpoint.textContent = "–";
        head.status.textContent = head.owner.textContent = "–";
        head.sub.textContent = "No active incident";
        trace.innerHTML = `<li class="trace-empty">Waiting for the endpoint to report an incident.</li>`;
        return;
    }

    head.id.textContent = t.incident_id;
    head.endpoint.textContent = t.hostname || "unknown";
    head.status.textContent = t.display_status || "–";
    head.status.className = t.refused ? "crit" : "";
    head.owner.textContent = t.support_level || "–";
    head.owner.className = t.support_level === "HUMAN L2" ? "l2" : "";
    head.sub.textContent = t.title || "";

    // Only re-render when the trace actually changed, so a poll cannot make the
    // screen flicker while someone is reading it.
    const rows = (t.actions || []).filter((a) => a.action !== "monitoring_unreachable");
    const key = `${t.incident_id}:${rows.length}:${t.display_status}`;
    if (key === lastTraceKey) return;
    lastTraceKey = key;

    trace.innerHTML = rows.length
        ? rows.map(traceRow).join("") + runbookContextRow(t)
        : `<li class="trace-empty">No agent activity reported yet.</li>`;
}

/** The most recently updated ticket that is still being worked. */
function mostActive() {
    return tickets.find((t) => t.display_status === "INVESTIGATING") || tickets[0];
}

const COMPONENT = {
    input_check: "SECURITY", blocked: "REFUSED", classification: "TRIAGE",
    diagnosis: "DIAGNOSTIC", remediation: "EXECUTOR", verification: "VERIFY",
    disagreement: "COMMANDER", escalation: "COMMANDER", metrics: "COMMANDER",
};

function traceRow(a) {
    const refused = a.tier === "red" || a.action === "blocked";
    const comp = refused ? "REFUSED" : (COMPONENT[a.action] || (a.agent || "SYSTEM").toUpperCase());
    const summary = summarise(a);

    return `
      <li class="tr ${refused ? "refused" : ""}">
        <span class="tr-time">${esc(clock(a.timestamp, true) || "—")}</span>
        <span class="tr-comp ${comp.toLowerCase()}">${esc(comp)}</span>
        <span class="tr-body">
          ${a.command ? `<div class="tr-cmd">${esc(a.command)}</div>` : ""}
          ${summary ? `<div class="${a.command ? "tr-out" : "tr-note"}">${esc(clip(summary, 200))}</div>` : ""}
          ${refused ? `<span class="tr-flag">REFUSED BY POLICY</span>` : ""}
          ${a.action === "verification" ? `<span class="tr-flag ok">VERIFIED</span>` : ""}
        </span>
      </li>`;
}

/* The engine records the runbook match as a streamed UI event, not an audit
 * entry, so there is no real timestamp for it. Shown as untimed context rather
 * than given a fabricated one. */
function runbookContextRow(t) {
    if (!t.runbook_id) return "";
    return `
      <li class="tr">
        <span class="tr-time">—</span>
        <span class="tr-comp commander">KNOWLEDGE</span>
        <span class="tr-body"><div class="tr-note">runbook applied: ${esc(t.runbook_id)}</div></span>
      </li>`;
}

/* -------------------------------- utils -------------------------------- */

/** Audit output is sometimes a JSON blob; show the useful part, not the blob. */
function summarise(a) {
    const raw = (a.output || "").trim();
    if (!raw) return "";
    if (!raw.startsWith("{")) return raw;
    try {
        const o = JSON.parse(raw);
        if (o.category) return `category: ${o.category}   severity: ${o.severity || "–"}`;
        if (o.status) return `${o.status}   ${o.latency_ms ?? "?"} ms   ${o.tool_calls ?? "?"} tool calls`;
        if (o.root_cause) return `root cause: ${o.root_cause}`;
        if (o.ticket_title) return o.ticket_title;
        return Object.keys(o).slice(0, 4).map((k) => `${k}: ${o[k]}`).join("   ");
    } catch { return raw; }
}

function clock(iso, withMillis = false) {
    if (!iso) return "";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return String(iso).slice(11, 19);
    const t = d.toTimeString().slice(0, 8);
    return withMillis ? `${t}.${String(d.getMilliseconds()).padStart(3, "0")}` : t;
}

const clip = (s, n) => (String(s).length > n ? String(s).slice(0, n) + "…" : String(s));

function esc(v) {
    return String(v ?? "").replace(/[&<>"']/g, (c) =>
        ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
