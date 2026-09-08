let currentIncidentId = null;

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

        for (const event of data.events || []) {
            addEvent(event);
        }

        if (data.status === "awaiting_approval") {
            showApprovalModal(data.pending_command, "This action requires your approval.");
        } else {
            showResolution(data);
        }
    } catch (err) {
        addEvent({agent: "System", message: "Error: " + err.message, tier: "red"});
    }
}

async function approveAction() {
    hideApprovalModal();
    if (!currentIncidentId) return;

    const command = document.getElementById("approval-command").textContent;
    try {
        const res = await fetch(`/api/incidents/${currentIncidentId}/approve`, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({command}),
        });
        const data = await res.json();
        for (const event of data.events || []) {
            addEvent(event);
        }
        showResolution(data);
    } catch (err) {
        addEvent({agent: "System", message: "Error: " + err.message, tier: "red"});
    }
}

function denyAction() {
    hideApprovalModal();
    addEvent({agent: "System", message: "User denied the action.", tier: "yellow"});
    showResolution({status: "escalated"});
}

function emergencyStop() {
    hideApprovalModal();
    addEvent({agent: "System", message: "EMERGENCY STOP triggered by user.", tier: "red"});
    showResolution({status: "escalated"});
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

function showApprovalModal(command, description) {
    document.getElementById("approval-command").textContent = command;
    document.getElementById("approval-description").textContent = description;
    document.getElementById("approval-modal").classList.remove("hidden");
}

function hideApprovalModal() {
    document.getElementById("approval-modal").classList.add("hidden");
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
    currentIncidentId = null;
    document.getElementById("user-prompt").value = "";
    document.getElementById("event-feed").innerHTML = "";
    showScreen("screen-intake");
}

function confirmResolved() {
    alert("Thank you! Have a great day.");
    resetUI();
}

function reportStillBroken() {
    alert("A Tier 2 ticket has been created. IT support will contact you.");
    resetUI();
}

function cancelAll() {
    if (confirm("Cancel the diagnostic session?")) resetUI();
}
