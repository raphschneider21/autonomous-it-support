/* IT Service Desk dashboard.
 *
 * Polls rather than streams. Tickets arrive from endpoint agents over HTTP, so
 * there is no single incident to subscribe to — and a 3-second poll against a
 * SQLite table is cheaper to reason about than a fan-out subscription for a
 * dashboard someone glances at.
 */

const POLL_MS = 3000;

let currentFilter = "all";
let selectedId = null;
let tickets = [];

document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".filter").forEach((button) => {
        button.addEventListener("click", () => {
            document.querySelectorAll(".filter").forEach((b) => b.classList.remove("active"));
            button.classList.add("active");
            currentFilter = button.dataset.status;
            refresh();
        });
    });

    document.getElementById("endpoint-label").textContent =
        `monitoring · ${window.location.host}`;

    refresh();
    setInterval(refresh, POLL_MS);
});

async function refresh() {
    try {
        const [ticketResponse, statsResponse] = await Promise.all([
            fetch(`/api/tickets?status=${currentFilter}`),
            fetch("/api/stats"),
        ]);
        tickets = await ticketResponse.json();
        renderStats(await statsResponse.json());
        renderList();
        if (selectedId) renderDetail(tickets.find((t) => t.incident_id === selectedId));
        setLive(true);
    } catch (err) {
        setLive(false);
    }
}

function setLive(ok) {
    document.getElementById("live-dot").classList.toggle("stale", !ok);
}

function renderStats(s) {
    document.getElementById("s-open").textContent = s.open;
    document.getElementById("s-closed").textContent = s.closed;
    document.getElementById("s-escalated").textContent = s.escalated;
    document.getElementById("s-auto").textContent = pct(s.auto_resolution_rate);
    document.getElementById("s-false").textContent =
        s.confirmations ? pct(s.false_resolution_rate) : "–";
    document.getElementById("s-latency").textContent =
        s.avg_latency_ms ? `${s.avg_latency_ms} ms` : "–";
    document.getElementById("s-tokens").textContent =
        s.tokens_in + s.tokens_out ? compact(s.tokens_in + s.tokens_out) : "–";
}

function renderList() {
    const list = document.getElementById("ticket-list");

    if (!tickets.length) {
        list.innerHTML = `<li class="empty">No ${
            currentFilter === "all" ? "" : currentFilter + " "
        }tickets yet.</li>`;
        return;
    }

    list.innerHTML = tickets.map((t) => `
        <li class="ticket ${t.incident_id === selectedId ? "selected" : ""}"
            data-id="${esc(t.incident_id)}" tabindex="0">
          <div class="ticket-top">
            <span class="ticket-id">${esc(t.incident_id)}</span>
            <span class="pill ${statusClass(t.status)}">${esc(t.status)}</span>
          </div>
          <div class="ticket-title">${esc(t.title || "(no description)")}</div>
          <div class="ticket-meta">
            <span>${esc(t.hostname || "unknown host")}</span>
            ${t.category ? `<span>· ${esc(t.category)}</span>` : ""}
            ${t.errors.length ? `<span class="pill red">${t.errors.length} refused</span>` : ""}
            ${t.user_confirmed === "still_broken"
                ? `<span class="pill red">user says unresolved</span>` : ""}
          </div>
        </li>`).join("");

    list.querySelectorAll(".ticket").forEach((element) => {
        const select = () => {
            selectedId = element.dataset.id;
            renderList();
            renderDetail(tickets.find((t) => t.incident_id === selectedId));
        };
        element.addEventListener("click", select);
        element.addEventListener("keydown", (e) => {
            if (e.key === "Enter" || e.key === " ") { e.preventDefault(); select(); }
        });
    });
}

function renderDetail(ticket) {
    const pane = document.getElementById("detail");
    if (!ticket) {
        pane.innerHTML = `<div class="placeholder"><h2>Ticket not in this filter</h2>
            <p>Switch to All to see it.</p></div>`;
        return;
    }

    pane.innerHTML = `
        <div class="detail-head">
          <span class="pill ${statusClass(ticket.status)}">${esc(ticket.status)}</span>
          <h2>${esc(ticket.title || ticket.incident_id)}</h2>
          <p class="quote">${esc(ticket.user_prompt || "")}</p>
        </div>

        <dl class="kv">
          <div><dt>Incident</dt><dd>${esc(ticket.incident_id)}</dd></div>
          <div><dt>Endpoint</dt><dd>${esc(ticket.hostname || "–")}</dd></div>
          <div><dt>Category</dt><dd>${esc(ticket.category || "–")}</dd></div>
          <div><dt>Severity</dt><dd>${esc(ticket.severity || "–")}</dd></div>
          <div><dt>Runbook</dt><dd>${esc(ticket.runbook_id || "none matched")}</dd></div>
          <div><dt>Latency</dt><dd>${ticket.latency_ms ?? "–"} ms</dd></div>
          <div><dt>Tool calls</dt><dd>${ticket.tool_calls ?? "–"}</dd></div>
          <div><dt>Tokens</dt><dd>${ticket.tokens_in || 0} in / ${ticket.tokens_out || 0} out</dd></div>
          <div><dt>Updated</dt><dd>${esc((ticket.updated_at || "").replace("T", " "))}</dd></div>
        </dl>

        ${ticket.user_confirmed === "still_broken" ? `
          <div class="callout">
            <h4>Verified, but not actually fixed</h4>
            <p>The agent's own verification passed and the user still reports the
               problem. This is the gap a technical check cannot see — start here.</p>
          </div>` : ""}

        ${ticket.errors.length ? `
          <h3 class="section">Refused actions (${ticket.errors.length})</h3>
          <ul class="timeline">${ticket.errors.map(stepRow).join("")}</ul>` : ""}

        <h3 class="section">Agent activity (${ticket.actions.length})</h3>
        <ul class="timeline">${
            ticket.actions.length
                ? ticket.actions.map(stepRow).join("")
                : `<li class="empty">No recorded activity.</li>`
        }</ul>

        ${ticket.escalation ? `
          <h3 class="section">Tier 2 escalation payload</h3>
          <pre class="json">${esc(JSON.stringify(ticket.escalation, null, 2))}</pre>` : ""}
    `;
}

function stepRow(step) {
    const tier = (step.tier || "green").toLowerCase();
    return `
      <li class="step ${tier === "red" ? "red" : ""}">
        <span class="agent">${esc(step.agent || "—")}</span>
        <span><span class="pill ${tier}">${esc(step.action || tier)}</span></span>
        <span class="body">
          ${step.command ? `<div class="cmd">${esc(step.command)}</div>` : ""}
          ${step.output ? `<div class="out">${esc(step.output)}</div>` : ""}
        </span>
      </li>`;
}

function statusClass(status) {
    if (status === "closed") return "closed";
    if (status === "escalated") return "escalated";
    return "open";
}

function pct(value) {
    return `${Math.round((value || 0) * 100)}%`;
}

function compact(n) {
    return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n);
}

function esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, (c) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
}
