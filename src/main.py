import os
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from .models import IncidentCreate
from .database import init_db, get_incident, get_audit_log, get_all_runbooks
from .engine.incident_commander import run_incident, approve_action

app = FastAPI(title="Autonomous IT Support Agent")

CLIENT_DIR = os.path.join(os.path.dirname(__file__), "client")


@app.on_event("startup")
def startup():
    init_db()


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/incidents")
def create_incident(request: IncidentCreate):
    incident_id = f"INC-{uuid.uuid4().hex[:8].upper()}"
    result = run_incident(incident_id, request.user_prompt)
    return {"incident_id": incident_id, **result}


@app.get("/api/incidents/{incident_id}")
def get_incident_detail(incident_id: str):
    incident = get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    audit = get_audit_log(incident_id)
    return {"incident": incident, "audit_log": audit}


@app.post("/api/incidents/{incident_id}/approve")
def approve_incident_action(incident_id: str, body: dict):
    command = body.get("command")
    if not command:
        raise HTTPException(status_code=400, detail="Command required")
    result = approve_action(incident_id, command)
    return result


@app.get("/api/runbooks")
def list_runbooks():
    return get_all_runbooks()


@app.get("/")
def serve_ui():
    return FileResponse(os.path.join(CLIENT_DIR, "index.html"))


app.mount("/static", StaticFiles(directory=CLIENT_DIR), name="static")
