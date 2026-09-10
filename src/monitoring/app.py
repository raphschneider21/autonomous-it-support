"""Monitoring service — the IT side of the system.

Runs as its own process, on its own port, against its own database. In the graded
demo it runs on the same Mac as the endpoint/runtime process, but the services
remain logically separate and communicate over HTTP:

    Employee Support / runtime   http://127.0.0.1:8000
    IT Service Desk              http://127.0.0.1:8001

The managed endpoint itself is the explicitly simulated Ubuntu 26.04 endpoint
`ubuntu-demo-01`; the Mac host is not being repaired. Keeping separate services
and databases preserves the endpoint-to-central-IT architecture without adding
a physical VM dependency to the mock-backed demo.

    python3 -m uvicorn src.monitoring.app:app --host 127.0.0.1 --port 8001
"""
import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import store

app = FastAPI(title="IT Service Desk — Monitoring")

CLIENT_DIR = os.path.join(os.path.dirname(__file__), "client")


class TicketReport(BaseModel):
    """What an endpoint agent sends. Everything except the id is optional so a
    partial early report ("incident opened") is as valid as a final one."""

    incident_id: str = Field(..., min_length=1)
    hostname: str | None = None
    title: str | None = None
    status: str = "open"
    category: str | None = None
    severity: str | None = None
    user_prompt: str | None = None
    runbook_id: str | None = None
    resolution: str | None = None
    agent_source: str | None = None
    latency_ms: float | None = None
    tool_calls: int | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    actions: list[dict] = Field(default_factory=list)
    errors: list[dict] = Field(default_factory=list)
    escalation: dict | None = None
    user_confirmed: str | None = None
    # Optional documentation, per the frozen shared contract. Both nullable so
    # an early-lifecycle snapshot ingests exactly as well as a final one.
    incident_report: str | None = None
    runbook: dict | None = None


@app.on_event("startup")
def startup():
    store.init_db()


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "monitoring"}


@app.post("/api/tickets")
def ingest(report: TicketReport):
    """Ingest a ticket report from an endpoint agent. Idempotent per incident."""
    if report.status not in store.ALL_STATES + ("resolved",):
        raise HTTPException(status_code=422, detail=f"Unknown status: {report.status}")
    # The agent's own vocabulary calls a verified fix "resolved"; the service
    # desk only calls a ticket closed once the user has confirmed it.
    payload = report.model_dump()
    if payload["status"] == "resolved":
        payload["status"] = "closed" if payload.get("user_confirmed") == "solved" else "open"
    return store.upsert_ticket(payload)


@app.get("/api/tickets")
def tickets(status: str = "all", limit: int = 200):
    return store.list_tickets(status=status, limit=limit)


@app.get("/api/tickets/{incident_id}")
def ticket(incident_id: str):
    found = store.get_ticket(incident_id)
    if not found:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return found


@app.get("/api/stats")
def stats():
    return store.stats()


@app.get("/")
def serve_ui():
    return FileResponse(os.path.join(CLIENT_DIR, "index.html"))


app.mount("/static", StaticFiles(directory=CLIENT_DIR), name="static")
