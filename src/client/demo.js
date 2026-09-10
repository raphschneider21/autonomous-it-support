let autoRefreshHandle = null;
const PREVIEW = new URLSearchParams(window.location.search).get("preview") === "1";

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
let previewLabState = JSON.parse(JSON.stringify(PREVIEW_LAB));

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
    if (PREVIEW) {
        renderState(previewLabState);
        if (!silent) showFeedback("Local preview state refreshed.", "ok");
        return;
    }
    try {
        const res = await fetch("/api/demo/state");
        if (!res.ok) throw new Error("Demo backend returned " + res.status);
        const state = await res.json();
        renderState(state);
        delete $("fault-buttons").dataset.fallback;
        if (!silent) showFeedback("Lab state refreshed.", "ok");
    } catch (err) {
        if (!silent) showError("Could not reach the Demo Lab backend. (" + err.message + ")");
        renderOfflineState();
    }
}

/* ===== Fault / reset actions ===== */
async function injectFault(faultId) {
    showFeedback("Injecting demo fault\u2026", "working");
    if (PREVIEW) {
        if (!previewLabState.active_faults.includes(faultId)) {
            previewLabState.active_faults.push(faultId);
        }
        const serviceByFault = {
            cups_stopped: ["cups", "inactive"],
            dns_broken: ["dns", "failed"],
            disk_full: ["disk", "full"],
            pulse_audio_down: ["audio", "inactive"],
        };
        const service = serviceByFault[faultId];
        if (service) previewLabState.services[service[0]] = service[1];
        renderState(previewLabState);
        showFeedback("Local preview fault injected.", "ok");
        return;
    }
    try {
        const res = await fetch(`/api/demo/faults/${encodeURIComponent(faultId)}`, {
            method: "POST",
        });
        if (!res.ok) throw new Error("Demo backend returned " + res.status);
        await refresh({ silent: true });
        showFeedback("Demo fault injected.", "ok");
    } catch (err) {
        showError("Could not inject the fault. (" + err.message + ")");
        renderOfflineState();
    }
}

async function resetLab() {
    showFeedback("Resetting endpoint\u2026", "working");
    if (PREVIEW) {
        previewLabState = JSON.parse(JSON.stringify(PREVIEW_LAB));
        renderState(previewLabState);
        showFeedback("Local preview reset.", "ok");
        return;
    }
    try {
        const res = await fetch("/api/demo/reset", { method: "POST" });
        if (!res.ok) throw new Error("Demo backend returned " + res.status);
        await refresh({ silent: true });
        showFeedback("Endpoint reset. All services healthy.", "ok");
    } catch (err) {
        showError("Could not reset the endpoint. (" + err.message + ")");
        renderOfflineState();
    }
}

/* ===== UI wiring ===== */
$("btn-reset").addEventListener("click", resetLab);

/* Production failures never substitute local fault data, because that could
   mislead the presenter about endpoint state. Preview data is opt-in above. */
function renderOfflineState() {
    $("mode-badge").textContent = "Backend Offline";
    $("mode-badge").className = "chip chip-demo chip-live";
    $("endpoint-state").innerHTML = '<span class="state-pill pill-bad">Unavailable</span>';
    $("services-grid").innerHTML = '<p class="empty-state">Live endpoint state is unavailable.</p>';
    const container = $("fault-buttons");
    container.innerHTML = '<p class="empty-state">Fault controls are unavailable until the backend reconnects.</p>';
}

/* ===== Init ===== */
(async function init() {
    if (PREVIEW) {
        renderState(previewLabState);
        return;
    }
    await refresh({ silent: true });
    startPolling();
})();
