import json
import os
import uuid
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from .models import IncidentCreate
from .database import init_db, get_incident, update_incident, get_audit_log, get_all_runbooks
from .integrations import monitoring_client
from .knowledge.runbook_parser import seed_runbooks_db
from .engine.incident_commander import run_incident
from .integrations.escalation import generate_escalation_ticket
from .engine.event_stream import store

app = FastAPI(title="Autonomous IT Support Agent")

CLIENT_DIR = os.path.join(os.path.dirname(__file__), "client")


@app.on_event("startup")
def startup():
    init_db()
    seed_runbooks_db()


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/incidents")
def create_incident(request: IncidentCreate, background_tasks: BackgroundTasks):
    incident_id = f"INC-{uuid.uuid4().hex[:8].upper()}"
    background_tasks.add_task(run_incident, incident_id, request.user_prompt)
    return {"incident_id": incident_id, "status": "diagnosing"}


@app.get("/api/incidents/{incident_id}/events")
async def incident_events(incident_id: str):
    """Server-Sent Events: stream each diagnostic event as it happens."""

    async def event_generator():
        async for event in store.subscribe(incident_id):
            if event is None:
                result = store.get_result(incident_id) or {"status": "unknown"}
                yield sse_message("done", result)
                break
            yield sse_message("event", event)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def sse_message(event_name: str, data: dict) -> str:
    """Format a Server-Sent Event frame."""
    payload = json.dumps(data)
    return f"event: {event_name}\ndata: {payload}\n\n"


@app.get("/api/incidents/{incident_id}")
def get_incident_detail(incident_id: str):
    incident = get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    audit = get_audit_log(incident_id)
    return {"incident": incident, "audit_log": audit}


class Confirmation(BaseModel):
    solved: bool


@app.post("/api/incidents/{incident_id}/confirm")
def confirm_resolution(incident_id: str, body: Confirmation):
    """The second closure gate: did this actually fix the user's problem?

    The agent's own verification proves the command ran and the service came
    back. It does not prove the user can work again — nginx can restart cleanly
    while the real fault is upstream. Only the user closes a ticket.

    "Still broken" is never a dead end: it escalates to Tier 2 carrying the full
    record of everything already attempted, so a technician starts from evidence
    rather than from "did you try rebooting".
    """
    incident = get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    verdict = "solved" if body.solved else "still_broken"
    status = "closed" if body.solved else "escalated"
    summary = (
        incident.get("resolution_summary")
        if body.solved else
        "Agent verification passed but the user reports the problem persists. "
        "Escalated to Tier 2 with the full record of attempted remediations."
    )
    update_incident(incident_id, user_confirmed=verdict, status=status,
                    resolution_summary=summary)

    incident = get_incident(incident_id)
    audit = get_audit_log(incident_id)
    result = {"status": status, "runbook_id": incident.get("runbook_id")}
    if not body.solved:
        result["escalation_ticket"] = generate_escalation_ticket(incident, audit).model_dump()

    payload = monitoring_client.build_report(incident, audit, result)
    payload["user_confirmed"] = verdict
    payload["status"] = status
    reported = monitoring_client.report(payload)

    return {
        "incident_id": incident_id,
        "status": status,
        "user_confirmed": verdict,
        "reported_to_service_desk": reported,
        "escalation_ticket": result.get("escalation_ticket"),
    }


@app.get("/api/monitoring")
def monitoring_target():
    """Where this endpoint reports, and whether the service desk is reachable."""
    return {
        "url": monitoring_client.monitoring_url(),
        "enabled": monitoring_client.enabled(),
        "last_error": monitoring_client.last_error(),
    }


@app.get("/api/runbooks")
def list_runbooks():
    return get_all_runbooks()


@app.get("/")
def serve_ui():
    return FileResponse(os.path.join(CLIENT_DIR, "index.html"))


app.mount("/static", StaticFiles(directory=CLIENT_DIR), name="static")
