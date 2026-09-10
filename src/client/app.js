let currentIncidentId = null;
let eventSource = null;
const PREVIEW = new URLSearchParams(window.location.search).get("preview") === "1";

const stepsList = document.getElementById("progress-steps");
const intakeError = document.getElementById("intake-error");

const $ = (id) => document.getElementById(id);

function showScreen(id) {
    document.querySelectorAll(".screen").forEach(s => s.classList.remove("active"));
    $(id).classList.add("active");
}

function setLive(on) {
    const el = $("live-indicator");
    if (!el) return;
    el.classList.toggle("hidden", !on);
}

/* ===== Screen transitions ===== */
$("btn-to-consent").addEventListener("click", () => {
    const prompt = $("user-prompt").value.trim();
    if (!prompt) {
        intakeError.textContent = "Please describe the problem first.";
        intakeError.classList.remove("hidden");
        return;
    }
    intakeError.classList.add("hidden");
    $("consent-summary").textContent = `Problem: "${prompt}"`;
    showScreen("screen-consent");
});

$("btn-back-intake").addEventListener("click", () => showScreen("screen-intake"));

$("btn-start-troubleshooting").addEventListener("click", () => startDiagnosis());

$("btn-new-incident").addEventListener("click", resetUI);
$("btn-new-incident-2").addEventListener("click", resetUI);
$("btn-new-incident-3").addEventListener("click", resetUI);
$("btn-error-retry").addEventListener("click", resetUI);
$("btn-stop").addEventListener("click", () => {
    if (confirm("Stop troubleshooting and return to the start screen?")) resetUI();
});

$("btn-solved").addEventListener("click", () => sendVerdict(true));
$("btn-still-broken").addEventListener("click", () => sendVerdict(false));

/* ===== Employee-friendly event translation =====
   The engine's messages are internal evidence. Employees see a truthful but
   non-technical phrasing of the same step. Unknown messages degrade to a
   neutral "Continuing…" instead of leaking agent/tier jargon. */
function translateEvent(event) {
    const msg = event.message || "";
    const agent = event.agent || "";

    if (event.tier === "red") {
        return { text: "A restricted action was stopped before it ran. The case is being reviewed.", tone: "error" };
    }
    if (/Input security check passed/.test(msg)) {
        return { text: "Support request received", tone: "done" };
    }
    if (/Classified as/.test(msg)) {
        return { text: "Understanding your problem\u2026", tone: "working" };
    }
    if (/Ran:/.test(msg) || agent === "DiagnosticAgent") {
        return { text: "Checking the relevant services\u2026", tone: "working" };
    }
    if (/Agents agree on root cause/.test(msg)) {
        return { text: "Problem identified", tone: "info" };
    }
    if (/Disagreement detected/.test(msg)) {
        return { text: "Comparing findings\u2026", tone: "working" };
    }
    if (/Reconciled/.test(msg)) {
        return { text: "Problem identified", tone: "info" };
    }
    if (/Runbook found/.test(msg)) {
        return { text: "Found a known fix for this issue", tone: "info" };
    }
    if (/No runbook matched/.test(msg)) {
        return { text: "No standard fix found, reasoning about the cause\u2026", tone: "working" };
    }
    if (/Proposed fix/.test(msg) || /Executed:/.test(msg)) {
        return { text: "Applying an approved fix\u2026", tone: "working" };
    }
    if (/only .*% confident/.test(msg)) {
        return { text: "Checking whether a fix is safe to apply\u2026", tone: "working" };
    }
    if (/Verification (PASSED|passed)/.test(msg)) {
        return { text: "Verifying the result\u2026", tone: "working" };
    }
    if (/Verification FAILED/.test(msg) || /Re-checked: the fault is still present/.test(msg)) {
        return { text: "The fix could not be verified\u2026", tone: "error" };
    }
    if (/Incident resolved successfully/.test(msg)) {
        return { text: "The fix has been applied and verified", tone: "done" };
    }
    if (/Incident report generated/.test(msg)) {
        return { text: "Recording the result in the ticket\u2026", tone: "working" };
    }
    if (/Escalating to Tier 2/.test(msg)) {
        return { text: "Preparing a hand-off to IT support\u2026", tone: "info" };
    }
    if (/blocked|REFUSED|BLOCKED/i.test(msg)) {
        return { text: "A restricted action was stopped before it ran.", tone: "error" };
    }

    return { text: "Continuing\u2026", tone: "working" };
}

function addProgressStep(event) {
    const item = translateEvent(event);
    const li = document.createElement("li");
    li.className = "progress-item progress-item-" + item.tone;
    li.innerHTML = `<span class="progress-dot" aria-hidden="true"></span><span class="progress-text">${item.text}</span>`;
    stepsList.appendChild(li);
    li.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

/* ===== Start incident ===== */
async function startDiagnosis() {
    setLive(false);
    stepsList.innerHTML = "";
    showScreen("screen-progress");
    const prompt = $("user-prompt").value.trim();
    const userPrompt = prompt || "System issue reported by user";

    if (PREVIEW) {
        runPreview();
        return;
    }

    try {
        const res = await fetch("/api/incidents", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ user_prompt: userPrompt }),
        });
        if (!res.ok) {
            const detail = await safeJson(res);
            throw new Error(detail?.detail || `Server returned ${res.status}`);
        }
        const data = await res.json();
        currentIncidentId = data.incident_id;
        setLive(true);
        openEventStream();
    } catch (err) {
        showError("Could not reach the support service. Please check that the server is running and try again. (" + err.message + ")");
    }
}

async function safeJson(res) {
    try { return await res.json(); } catch { return null; }
}

/* ===== SSE live stream ===== */
let incidentFinished = false;

function openEventStream() {
    closeEventStream();
    eventSource = new EventSource(`/api/incidents/${currentIncidentId}/events`);

    eventSource.addEventListener("event", (e) => {
        try {
            const event = JSON.parse(e.data);
            addProgressStep(event);
        } catch { /* ignore malformed frames */ }
    });

    eventSource.addEventListener("done", (e) => {
        try {
            const result = JSON.parse(e.data);
            handleDone(result);
        } catch (err) {
            showError("The support service returned an unexpected response.");
        }
    });

    eventSource.onerror = () => {
        // The stream can close without a 'done' frame (e.g. a dropped
        // connection). If the incident never reached a terminal state, fall
        // back to the detail endpoint for the final status.
        if (currentIncidentId && !incidentFinished) {
            fetchIncidentFallback();
        }
    };
}

function closeEventStream() {
    if (eventSource) {
        eventSource.close();
        eventSource = null;
    }
}

async function handleDone(result) {
    incidentFinished = true;
    closeEventStream();
    const status = result.status || "unknown";

    const redFlagged = (result.events || []).some(ev => ev.tier === "red");

    if (status === "resolved") {
        // A resolved run can still contain a red event (e.g. a runbook step
        // the allowlist refused, with other steps succeeding). The fix was
        // verified, so the employee confirms the outcome rather than the sand.
        setLive(false);
        $("result-success-summary").textContent = result.report_path
            ? "The assistant fixed the problem and recorded the result."
            : "The assistant applied a fix and verified it worked.";
        $("result-success-banner").classList.remove("hidden");
        $("result-neutral-banner").classList.add("hidden");
        $("verdict-block").classList.remove("hidden");
        showScreen("screen-result");
        return;
    }

    if (status === "escalated" && !redFlagged) {
        setLive(false);
        $("escalated-ticket").textContent = currentIncidentId;
        showScreen("screen-escalated");
        return;
    }

    if (status === "escalated" && redFlagged) {
        // Security/refusal outcome (scenario C). Never described as success.
        setLive(false);
        $("refused-ticket").textContent = currentIncidentId;
        showScreen("screen-refused");
        return;
    }

    // Unknown/abnormal status - readable final state, no blank screen.
    setLive(false);
    $("result-neutral-title").textContent = "Troubleshooting complete";
    $("result-neutral-summary").textContent = "The assistant finished reviewing your issue.";
    $("result-success-banner").classList.add("hidden");
    $("result-neutral-banner").classList.remove("hidden");
    $("verdict-block").classList.remove("hidden");
    showScreen("screen-result");
}

async function fetchIncidentFallback() {
    try {
        const res = await fetch(`/api/incidents/${currentIncidentId}`);
        if (!res.ok) return;
        const data = await res.json();
        const status = data.incident?.status;
        if (status === "resolved") {
            handleDone({ status: "resolved", report_path: null });
        } else if (status === "escalated") {
            handleDone({ status: "escalated" });
        }
    } catch { /* stream will simply stop; nothing sensible to render */ }
}

/* ===== Final verdict (frozen contract) ===== */
async function sendVerdict(solved) {
    $("verdict-block").classList.add("hidden");
    if (solved) {
        $("closed-ticket").textContent = currentIncidentId;
        showScreen("screen-closed");
    } else {
        $("escalated-ticket").textContent = currentIncidentId;
        showScreen("screen-escalated");
    }

    if (PREVIEW) return;

    try {
        const res = await fetch(`/api/incidents/${currentIncidentId}/confirm`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ solved }),
        });
        if (!res.ok) throw new Error("Server returned " + res.status);
        const body = await res.json();
        // "Still broken" escalates server-side and returns the typed ticket.
        // Surface the ticket title if the backend gave us one.
        if (!solved && body?.escalation_ticket?.ticket_title) {
            $("escalated-ticket").textContent = currentIncidentId;
        }
    } catch { /* the UI already reflects the outcome; the backend persists it */ }
}

/* ===== Error state ===== */
function showError(message) {
    setLive(false);
    $("error-message").textContent = message;
    showScreen("screen-error");
}

function resetUI() {
    closeEventStream();
    incidentFinished = false;
    currentIncidentId = null;
    $("user-prompt").value = "";
    $("intake-error").classList.add("hidden");
    document.querySelectorAll("#result-success-banner, #result-neutral-banner, #verdict-block").forEach(b => b.classList.add("hidden"));
    stepsList.innerHTML = "";
    setLive(false);
    showScreen("screen-intake");
}

/* ===== Preview mode (UI rehearsal only; production uses the real API) =====
   Mirrors the current one-pass engine: resolved (printer), escalated
   (no runbook / novel fix), refused (security red). */
function runPreview() {
    const prompt = ($("user-prompt").value || "").toLowerCase();
    const delayed = (fn, ms) => setTimeout(fn, ms);

    currentIncidentId = "INC-PREVIEW0001";
    setLive(true);
    addProgressStep({ agent: "SecurityAgent", message: "Input security check passed", tier: "green" });

    if (/printer|print/.test(prompt)) {
        delayed(() => addProgressStep({ agent: "TriageAgent", message: "Classified as printing", tier: "green" }), 500);
        delayed(() => addProgressStep({ agent: "DiagnosticAgent", message: "Ran: systemctl is-active cups", tier: "green" }), 1000);
        delayed(() => addProgressStep({ agent: "IncidentCommander", message: "Runbook found: print queue", tier: "green" }), 1500);
        delayed(() => addProgressStep({ agent: "DiagnosticAgent", message: "Executed: cancel -a", tier: "yellow" }), 2100);
        delayed(() => addProgressStep({ agent: "DiagnosticAgent", message: "Verification PASSED", tier: "green" }), 2600);
        delayed(() => {
            addProgressStep({ agent: "IncidentCommander", message: "Incident resolved successfully", tier: "green" });
            handleDone({ status: "resolved", report_path: "preview" });
        }, 3200);
    } else if (/ignore security|grant administrator|bypass security|disable firewall|disable antivirus|add user|delete system|wipe|ransom/i.test(prompt)) {
        delayed(() => addProgressStep({ agent: "SecurityAgent", message: "ALERT: Prompt injection attempt detected and blocked.", tier: "red" }), 700);
        delayed(() => handleDone({ status: "escalated", events: [{ tier: "red" }, { tier: "red" }] }), 1200);
    } else if (/vpn|network|internet|wifi|connect|install|incompatible|error/i.test(prompt)) {
        delayed(() => addProgressStep({ agent: "DiagnosticAgent", message: "Ran: systemctl status", tier: "green" }), 900);
        delayed(() => addProgressStep({ agent: "IncidentCommander", message: "No runbook matched", tier: "green" }), 1600);
        delayed(() => addProgressStep({ agent: "IncidentCommander", message: "Escalating to Tier 2", tier: "yellow" }), 2200);
        delayed(() => handleDone({ status: "escalated" }), 2600);
    } else {
        delayed(() => addProgressStep({ agent: "TriageAgent", message: "Classified as unknown", tier: "green" }), 500);
        delayed(() => addProgressStep({ agent: "IncidentCommander", message: "No runbook matched", tier: "green" }), 1100);
        delayed(() => handleDone({ status: "escalated" }), 1500);
    }
}