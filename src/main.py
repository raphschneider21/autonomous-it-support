import json
import os
import uuid
from datetime import datetime

from . import config  # noqa: F401 - loads .env on import
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from .models import IncidentCreate
from .database import (
    init_db,
    get_incident,
    update_incident,
    get_audit_log,
    get_all_runbooks,
    insert_audit,
)
from .integrations import monitoring_client
from .executors import factory as executor_factory
from .knowledge.runbook_parser import seed_runbooks_db, active_store
from .engine.incident_commander import run_incident, complete_incident
from .integrations.escalation import generate_escalation_ticket
from .engine.event_stream import store
from .demo.state import demo_endpoint

app = FastAPI(title="Autonomous IT Support Agent")

CLIENT_DIR = os.path.join(os.path.dirname(__file__), "client")


@app.on_event("startup")
def startup():
    init_db()
    seed_runbooks_db()

    # Which executor is live is the single most consequential thing about a
    # deployment, and mock and real runs look identical in the UI. Say it out
    # loud on every start.
    mode = executor_factory.describe()
    banner = "REAL — commands will run on this machine" if mode["executes_on_this_machine"] \
        else "MOCK — simulated endpoint state and fixtures; this machine is not touched"
    print(f"[startup] executor: {banner}")
    if mode["demo_safety_override"]:
        print(f"[startup] CONFIGURATION CONFLICT: {mode['note']}")
    print(f"[startup] demo mode: {'enabled' if config.demo_mode_enabled() else 'disabled'}; "
          f"agent path: {config.agent_mode()}")
    print(f"[startup] service desk: {monitoring_client.monitoring_url()} "
          f"({'enabled' if monitoring_client.enabled() else 'disabled'})")


@app.get("/api/health")
def health():
    """Health, plus the two facts a deployment most often gets wrong."""
    return {
        "status": "ok",
        "endpoint": config.endpoint_name(),
        "demo_mode": config.demo_mode_enabled(),
        "agent_mode": config.agent_mode(),
        "requested_agent_mode": config.requested_agent_mode(),
        "external_model_enabled": config.external_model_enabled(),
        "runbook_store": active_store(),
        **executor_factory.describe(),
        "monitoring_url": monitoring_client.monitoring_url(),
        "monitoring_enabled": monitoring_client.enabled(),
        "monitoring_reachable": monitoring_client.reachable(),
    }


@app.get("/api/demo/state")
def get_demo_state():
    """Return the shared simulated endpoint state for Demo Lab."""
    return demo_endpoint.snapshot()


@app.post("/api/demo/faults/{fault_id}")
def inject_demo_fault(fault_id: str):
    """Inject one approved deterministic fault into the simulation."""
    try:
        return demo_endpoint.inject_fault(fault_id)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown demo fault: {fault_id}",
        ) from None


@app.post("/api/demo/reset")
def reset_demo_state():
    """Idempotently restore the simulated endpoint's healthy baseline."""
    return demo_endpoint.reset()


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
    if incident["status"] != "resolved" and incident.get("user_confirmed") != verdict:
        raise HTTPException(status_code=409, detail="This incident is not awaiting user confirmation")
    status = "closed" if body.solved else "escalated"
    summary = (
        incident.get("resolution_summary")
        if body.solved else
        "Agent verification passed but the user reports the problem persists. "
        "Escalated to Tier 2 with the full record of attempted remediations."
    )
    if incident.get("user_confirmed") != verdict:
        update_incident(incident_id, user_confirmed=verdict, status=status,
                        resolution_summary=summary)
        insert_audit({
            "incident_id": incident_id,
            "timestamp": datetime.utcnow().isoformat(),
            "agent_name": "User",
            "action_type": "user_confirmation",
            "safety_tier": "green",
            "command_executed": None,
            "output": verdict,
        })

    incident = get_incident(incident_id)
    audit = get_audit_log(incident_id)
    prior_result = store.get_result(incident_id) or {}
    # Keep technical metrics even after a process restart loses the SSE cache.
    metrics = prior_result.get("metrics")
    if metrics is None:
        metrics = next((json.loads(e["output"]) for e in reversed(audit)
                        if e["action_type"] == "metrics"), {})
    result = {
        **prior_result,
        "status": status,
        "runbook_id": incident.get("runbook_id"),
        "metrics": metrics,
        "lifecycle_stage": "user_confirmed_solved" if body.solved else "user_confirmed_still_broken",
    }
    if not body.solved:
        result["escalation_ticket"] = generate_escalation_ticket(incident, audit).model_dump()

    result = complete_incident(incident_id, result)

    return {
        "incident_id": incident_id,
        "status": status,
        "user_confirmed": verdict,
        "reported_to_service_desk": result["reported_to_service_desk"],
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
