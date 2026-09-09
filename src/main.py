import json
import os
import uuid
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from .models import IncidentCreate
from .database import init_db, get_incident, get_audit_log, get_all_runbooks
from .knowledge.runbook_parser import seed_runbooks_db
from .engine.incident_commander import run_incident
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


@app.get("/api/runbooks")
def list_runbooks():
    return get_all_runbooks()


@app.get("/")
def serve_ui():
    return FileResponse(os.path.join(CLIENT_DIR, "index.html"))


app.mount("/static", StaticFiles(directory=CLIENT_DIR), name="static")
