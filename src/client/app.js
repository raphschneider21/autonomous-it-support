let currentIncidentId = null;
let eventSource = null;

/* ===== Intake ===== */
async function startDiagnosis() {
    const prompt = document.getElementById("user-prompt").value.trim();
    if (!prompt) return alert("Please describe your issue.");

    showScreen("screen-progress");
    document.getElementById("event-feed").innerHTML = "";

    try {
        const res = await fetch("/api/incidents", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({user_prompt: prompt}),
        });
        const data = await res.json();
        currentIncidentId = data.incident_id;
        openEventStream();
    } catch (err) {
        addEvent({agent: "System", message: "Error: " + err.message, tier: "red"});
    }
}

/* ===== SSE live stream ===== */
function openEventStream() {
    closeEventStream();
    eventSource = new EventSource(`/api/incidents/${currentIncidentId}/events`);

    eventSource.addEventListener("event", (e) => {
        const event = JSON.parse(e.data);
        addEvent(event);
    });

    eventSource.addEventListener("done", (e) => {
        const result = JSON.parse(e.data);
        handleDone(result);
    });

    eventSource.onerror = () => {
        // Connection dropped. If we already have the current incident and no
        // pending approval, do not loop forever.
    };
}

function closeEventStream() {
    if (eventSource) {
        eventSource.close();
        eventSource = null;
    }
}

function handleDone(result) {
    // A run reaches a terminal state in one pass. The user consented once on
    // the intake screen, so Green and Yellow actions have already executed
    // inside that window; anything the allowlist refused was escalated rather
    // than offered for approval.
    closeEventStream();
    showResolution(result);
}

function showResolution(data) {
    const status = data.status || "unknown";
    const title = document.getElementById("resolution-title");
    const details = document.getElementById("resolution-details");
    const question = document.getElementById("resolution-question");

    if (status === "resolved") {
        title.textContent = "Issue Resolved";
        details.innerHTML = "<p>The agent has resolved the incident.</p>";
        question.classList.remove("hidden");
    } else if (status === "escalated") {
        title.textContent = "Escalated to Tier 2";
        details.innerHTML = "<p>This issue requires human IT support. A ticket has been created.</p>";
        question.classList.add("hidden");
    } else {
        title.textContent = "Status: " + status;
        details.innerHTML = "";
        question.classList.add("hidden");
    }

    showScreen("screen-resolution");
}

function addEvent(event) {
    const feed = document.getElementById("event-feed");
    const div = document.createElement("div");
    div.className = "event-item";
    div.innerHTML = `<span class="event-agent tier-${event.tier}">[${event.agent}]</span> ${event.message}`;
    feed.appendChild(div);
    feed.scrollTop = feed.scrollHeight;
}

function showScreen(id) {
    document.querySelectorAll(".screen").forEach(s => s.classList.remove("active"));
    document.getElementById(id).classList.add("active");
}

function resetUI() {
    closeEventStream();
    currentIncidentId = null;
    document.getElementById("user-prompt").value = "";
    document.getElementById("event-feed").innerHTML = "";
    showScreen("screen-intake");
}

/* The second closure gate. The agent's verification proves the command ran;
 * only the user can say whether their problem is actually gone. Both answers
 * are recorded — "still broken" after a passing verification is the most
 * valuable signal this system produces, because nothing else can see it. */
async function confirmResolved() {
    await sendConfirmation(true, "Thank you! Have a great day.");
}

async function reportStillBroken() {
    await sendConfirmation(false, null);
}

async function sendConfirmation(solved, successMessage) {
    if (!currentIncidentId) { resetUI(); return; }
    try {
        const response = await fetch(`/api/incidents/${currentIncidentId}/confirm`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ solved }),
        });
        const body = await response.json();
        if (solved) {
            alert(successMessage);
        } else {
            const ticket = body.escalation_ticket;
            alert(
                `Ticket ${currentIncidentId} has been escalated to Tier 2.\n\n` +
                (ticket && ticket.ticket_title ? `${ticket.ticket_title}\n\n` : "") +
                "Everything the agent already tried has been attached, so IT will " +
                "not have to ask you to repeat it."
            );
        }
    } catch (err) {
        alert("Could not reach the support service. Please contact IT directly.");
    }
    resetUI();
}

function cancelAll() {
    if (confirm("Cancel the diagnostic session?")) resetUI();
}
