# central_server/main.py
# ─────────────────────────────────────────────────────────────
# RescueGrid — Central Server (FastAPI)
#
# Key endpoints:
#   POST /ambulance/update     ← GPS pings from ambulances
#   GET  /ambulance/{id}/status
#   GET  /junctions            ← All junctions & their states
#   POST /junction/ack         ← ACK from junction units
#   WS   /ws/dashboard         ← Live feed to dashboard
# ─────────────────────────────────────────────────────────────

import asyncio
import json
import logging
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from models import AmbulanceUpdate, AmbulanceStatus, JunctionAck, DashboardUpdate
from database import (init_db, get_session, AmbulanceRecord,
                       JunctionRecord, GPSLog)
from route_predictor import RoadGraph, RoutePlanner, build_demo_graph
from priority_manager import PriorityManager, AmbulanceRequest
from signal_controller import SignalController
from feedback_handler import FeedbackHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("central_server")

# ── Startup / Shutdown ───────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    asyncio.create_task(_purge_loop())
    logger.info("RescueGrid Central Server started ✓")
    yield
    logger.info("Server shutting down.")

app = FastAPI(title="RescueGrid Central Server", version="1.0.0",
              lifespan=lifespan)

app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

# ── Singletons ───────────────────────────────────────────────
# In production, load junction URLs from DB / config file
JUNCTION_URLS = {
    "JN001": "http://192.168.1.10:5000",
    "JN002": "http://192.168.1.11:5000",
    "JN003": "http://192.168.1.12:5000",
    "JN004": "http://192.168.1.13:5000",
    "JN005": "http://192.168.1.14:5000",
}

HOSPITAL_JUNCTION = "HOSP"   # End node in road graph

graph:   RoadGraph       = build_demo_graph()
planner: RoutePlanner    = RoutePlanner(graph)
prio_mgr = PriorityManager()
sig_ctrl = SignalController(JUNCTION_URLS)
fb_handler = FeedbackHandler(sig_ctrl)

# Active WebSocket connections for dashboard
_ws_clients: set[WebSocket] = set()

# ── Background tasks ─────────────────────────────────────────
async def _purge_loop():
    while True:
        await asyncio.sleep(30)
        prio_mgr.purge_expired()

async def _broadcast_dashboard(db: AsyncSession):
    """Push live state to all connected dashboard clients."""
    if not _ws_clients:
        return
    ambs = (await db.execute(
        select(AmbulanceRecord).where(AmbulanceRecord.active == True)  # noqa: E712
    )).scalars().all()
    jns  = (await db.execute(select(JunctionRecord))).scalars().all()

    payload = {
        "ambulances": [
            {
                "ambulance_id":    a.id,
                "priority_active": a.priority_active,
                "criticality":     a.criticality,
                "latitude":        a.last_lat,
                "longitude":       a.last_lon,
                "speed_kmh":       a.speed_kmh,
                "heading":         a.heading,
                "last_seen":       a.last_seen.isoformat(),
                "active":          a.active,
            }
            for a in ambs
        ],
        "junctions": [
            {
                "junction_id": j.id,
                "name":        j.name,
                "lat":         j.lat,
                "lon":         j.lon,
                "state":       j.state,
                "updated_at":  j.updated_at.isoformat(),
            }
            for j in jns
        ],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    dead = set()
    for ws in _ws_clients:
        try:
            await ws.send_text(json.dumps(payload))
        except Exception:
            dead.add(ws)
    _ws_clients.difference_update(dead)

# ── REST Endpoints ───────────────────────────────────────────

@app.post("/ambulance/update")
async def ambulance_update(
    data: AmbulanceUpdate,
    db: Annotated[AsyncSession, Depends(get_session)],
):
    gps = data.gps
    if gps.latitude is None or gps.longitude is None:
        logger.warning(f"{data.ambulance_id}: no GPS fix")
        return {"status": "no_fix"}

    # 1. Upsert ambulance record
    existing = await db.get(AmbulanceRecord, data.ambulance_id)
    now = datetime.now(timezone.utc)
    if existing:
        existing.last_lat        = gps.latitude
        existing.last_lon        = gps.longitude
        existing.speed_kmh       = gps.speed_kmh
        existing.heading         = gps.heading
        existing.criticality     = data.criticality
        existing.priority_active = data.priority_active
        existing.last_seen       = now
        existing.active          = True
    else:
        db.add(AmbulanceRecord(
            id             = data.ambulance_id,
            last_lat       = gps.latitude,
            last_lon       = gps.longitude,
            speed_kmh      = gps.speed_kmh,
            heading        = gps.heading,
            criticality    = data.criticality,
            priority_active= data.priority_active,
            last_seen      = now,
            active         = True,
        ))

    # 2. Log GPS point
    db.add(GPSLog(
        ambulance_id = data.ambulance_id,
        lat          = gps.latitude,
        lon          = gps.longitude,
        speed_kmh    = gps.speed_kmh,
        heading      = gps.heading,
        recorded_at  = now,
    ))
    await db.commit()

    # 3. Route prediction & signal scheduling (only if priority active)
    eta_map = {}
    if data.priority_active:
        start = graph.nearest_node(gps.latitude, gps.longitude)
        route = planner.find_route(start, HOSPITAL_JUNCTION)
        if route:
            eta_map = planner.calculate_etas(route, gps.speed_kmh)
            # Register with priority manager for each upcoming junction
            for jid, eta in eta_map.items():
                if jid in JUNCTION_URLS:
                    req = AmbulanceRequest(
                        ambulance_id      = data.ambulance_id,
                        junction_id       = jid,
                        eta_seconds       = eta,
                        criticality       = data.criticality,
                        dist_to_junction  = eta * gps.speed_kmh / 3.6,
                        trip_remaining_m  = sum(
                            eta_map[j] * gps.speed_kmh / 3.6
                            for j in eta_map
                        ),
                    )
                    prio_mgr.register(req)
                    winner = prio_mgr.get_winner(jid)
                    if winner and winner.ambulance_id == data.ambulance_id:
                        # We win this junction — schedule green
                        asyncio.create_task(
                            sig_ctrl.issue_emergency(jid, data.ambulance_id,
                                                     green_direction=0,
                                                     duration=45)
                        )

    await _broadcast_dashboard(db)
    return {"status": "ok", "etas": eta_map}


@app.get("/ambulance/{ambulance_id}/status")
async def ambulance_status(
    ambulance_id: str,
    db: Annotated[AsyncSession, Depends(get_session)],
):
    rec = await db.get(AmbulanceRecord, ambulance_id)
    if not rec:
        raise HTTPException(404, "Ambulance not found")
    return {
        "ambulance_id":    rec.id,
        "priority_active": rec.priority_active,
        "criticality":     rec.criticality,
        "latitude":        rec.last_lat,
        "longitude":       rec.last_lon,
        "speed_kmh":       rec.speed_kmh,
        "heading":         rec.heading,
        "last_seen":       rec.last_seen.isoformat(),
        "active":          rec.active,
    }


@app.get("/junctions")
async def list_junctions(
    db: Annotated[AsyncSession, Depends(get_session)],
):
    rows = (await db.execute(select(JunctionRecord))).scalars().all()
    return [
        {"id": r.id, "name": r.name, "lat": r.lat, "lon": r.lon,
         "state": r.state, "url": r.url}
        for r in rows
    ]


@app.post("/junction/ack")
async def junction_ack(
    ack: JunctionAck,
    db: Annotated[AsyncSession, Depends(get_session)],
):
    await fb_handler.process(ack, db)
    if ack.success:
        # Deregister ambulance from this junction once passed
        prio_mgr.deregister(ack.ambulance_id, ack.junction_id)
    return {"status": "received"}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "RescueGrid Central Server"}


# ── WebSocket Dashboard ──────────────────────────────────────

@app.websocket("/ws/dashboard")
async def dashboard_ws(websocket: WebSocket):
    await websocket.accept()
    _ws_clients.add(websocket)
    logger.info(f"Dashboard client connected ({len(_ws_clients)} total)")
    try:
        while True:
            await websocket.receive_text()   # Keep-alive ping
    except WebSocketDisconnect:
        _ws_clients.discard(websocket)
        logger.info("Dashboard client disconnected")
