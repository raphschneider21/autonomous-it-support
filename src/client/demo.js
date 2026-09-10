let autoRefreshHandle = null;

const PREVIEW_LAB = {
    endpoint: "ubuntu-demo-01",
    mode: "simulated",
    available_faults: [
        { id: "cups_stopped", label: "CUPS printing service stopped", category: "printing" },
        { id: "dns_broken", label: "DNS resolution failing", category: "network" },
        { id: "disk_full", label: "Root disk nearly full", category: "storage" },
        { id: "pulse_audio_down", label: "Audio service stopped", category: "audio" },
    ],
    active_faults: [],
    services: {
        cups: "active",
        dns: "healthy",
        disk: "healthy",
        audio: "active",
    },
};

const SERVICE_LABELS = {
    cups: "Printing",
    dns: "DNS",
    disk: "Storage",
    audio: "Audio",
    network: "Network",
};

function $(id) { return document.getElementById(id); }

function showError(msg) {
    if (document._labErrorTimer) clearTimeout(document._labErrorTimer);
    const el = $("fault-action-feedback");
    el.textContent = msg;
    el.className = "fault-feedback feedback-error";
    document._labErrorTimer = setTimeout(() => { el.textContent = ""; el.className = "fault-feedback"; }, 6000);
}

function showFeedback(msg, kind) {
    const el = $("fault-action-feedback");
    el.textContent = msg;
    el.className = "fault-feedback feedback-" + kind;
    clearTimeout(document._faultOkTimer);
    document._faultOkTimer = setTimeout(() => { el.textContent = ""; el.className = "fault-feedback"; }, 6000);
}

function renderState(state) {
    if (!state) return;
    $("endpoint-name").textContent = state.endpoint || "ubuntu-demo-01";

    const badge = $("mode-badge");
    if (state.mode === "simulated") {
        badge.textContent = "Simulated Endpoint";
        badge.className = "chip chip-demo";
    } else {
        badge.textContent = "Live Endpoint";
        badge.className = "chip chip-demo chip-live";
    }

    // Endpoint-level health badge
    const stateEl = $("endpoint-state");
    const activeFaults = state.active_faults || [];
    const activeCount = activeFaults.length;
    stateEl.innerHTML = activeCount === 0
        ? '<span class="state-pill pill-ok">Healthy</span>'
        : `<span class="state-pill pill-bad">${activeCount} fault${activeCount > 1 ? "s" : ""} active</span>`;

    // Services grid
    const grid = $("services-grid");
    grid.innerHTML = "";
    const services = state.services || {};
    const serviceKeys = Object.keys(services).length ? Object.keys(services) : ["cups", "dns", "disk", "audio"];

    for (const key of serviceKeys) {
        const raw = services[key];
        const normalised = (raw || "").toString().toLowerCase();
        const label = SERVICE_LABELS[key] || key;

        const row = document.createElement("div");
        row.className = "service-row";

        const name = document.createElement("span");
        name.className = "service-name";
        name.textContent = label;

        if (raw) {
            const detail = document.createElement("span");
            detail.className = "service-detail";
            detail.textContent = raw;
            row.appendChild(name);
            row.appendChild(detail);
        } else {
            row.appendChild(name);
        }

        const pill = document.createElement("span");
        const faulted = /inactive|stopped|fail|down|full|error/.test(normalised);
        if (faulted) {
            pill.className = "state-pill pill-bad";
            pill.textContent = "Fault injected";
        } else {
            pill.className = "state-pill pill-ok";
            pill.textContent = "Healthy";
        }

        row.appendChild(pill);
        grid.appendChild(row);
    }

    // Fault buttons - always render from available_faults when present.
    // A fault that is already active is disabled so the presenter cannot
    // double-inject and is always certain whether a fault is live.
    const container = $("fault-buttons");
    const faults = state.available_faults || [];
    if (faults.length === 0) {
        container.innerHTML = '<p class="empty-state">No faults are available from the backend.</p>';
        return;
    }

    container.innerHTML = "";
    for (const fault of faults) {
        const isActive = activeFaults.includes(fault.id);
        const btn = document.createElement("button");
        btn.className = "btn-fault" + (isActive ? " btn-fault-active" : "");
        btn.textContent = isActive ? `Active: ${fault.label}` : `Inject: ${fault.label}`;
        if (isActive) btn.disabled = true;
        btn.addEventListener("click", () => injectFault(fault.id));
        container.appendChild(btn);
    }
}

/* ===== Live polling ===== */
function startPolling() {
    stopPolling();
    autoRefreshHandle = setInterval(refresh, 5000);
}

function stopPolling() {
    if (autoRefreshHandle) {
        clearInterval(autoRefreshHandle);
        autoRefreshHandle = null;
    }
}

async function refresh({ silent } = {}) {
    try {
        const res = await fetch("/api/demo/state");
        if (!res.ok) throw new Error("Demo backend returned " + res.status);
        const state = await res.json();
        renderState(state);
        delete $("fault-buttons").dataset.fallback;
        if (!silent) showFeedback("Lab state refreshed.", "ok");
    } catch (err) {
        if (!silent) showError("Could not reach the Demo Lab backend. (" + err.message + ")");
        renderFallbackState(err.message);
    }
}

/* ===== Fault / reset actions ===== */
async function injectFault(faultId) {
    showFeedback("Injecting demo fault\u2026", "working");
    try {
        const res = await fetch(`/api/demo/faults/${encodeURIComponent(faultId)}`, {
            method: "POST",
        });
        if (!res.ok) throw new Error("Demo backend returned " + res.status);
        await refresh({ silent: true });
        showFeedback("Demo fault injected.", "ok");
    } catch (err) {
        showError("Could not inject the fault. (" + err.message + ")");
        renderFallbackState(err.message);
    }
}

async function resetLab() {
    showFeedback("Resetting endpoint\u2026", "working");
    try {
        const res = await fetch("/api/demo/reset", { method: "POST" });
        if (!res.ok) throw new Error("Demo backend returned " + res.status);
        await refresh({ silent: true });
        showFeedback("Endpoint reset. All services healthy.", "ok");
    } catch (err) {
        showError("Could not reset the endpoint. (" + err.message + ")");
        renderFallbackState(err.message);
    }
}

/* ===== UI wiring ===== */
$("btn-reset").addEventListener("click", resetLab);

/* ===== Preview fallback =====
   Development-only rehearsal aid so the Demo Lab UI can be exercised while
   Dev1's backend endpoints are being implemented. Production code always
   calls the real /api/demo/* endpoints; the fallback only replaces the
   rendered state when the backend is unreachable. */
function renderFallbackState(reason) {
    const container = $("fault-buttons");
    if (!container.dataset.fallback) {
        container.dataset.fallback = "1";
        renderState(PREVIEW_LAB);
        const note = document.createElement("p");
        note.className = "empty-state";
        note.textContent = "Backend not reachable. Showing local preview only (" + reason + ").";
        container.prepend(note);
    }
}

/* ===== Init ===== */
(async function init() {
    const hasPreview = new URLSearchParams(window.location.search).get("preview") === "1";
    if (hasPreview) {
        renderState(PREVIEW_LAB);
        startPolling();
        return;
    }
    try {
        await refresh({ silent: true });
        startPolling();
    } catch {
        renderFallbackState("initial load");
        startPolling();
    }
})();
