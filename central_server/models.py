# central_server/models.py
# ─────────────────────────────────────────────────────────────
# RescueGrid — Pydantic Data Models
# ─────────────────────────────────────────────────────────────

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum

class SignalState(str, Enum):
    NORMAL    = "normal"
    EMERGENCY = "emergency"   # Green corridor active
    FAILSAFE  = "failsafe"    # Flashing yellow

class GPSData(BaseModel):
    latitude:    Optional[float]
    longitude:   Optional[float]
    speed_kmh:   float = 0.0
    heading:     float = 0.0
    altitude:    float = 0.0
    satellites:  int   = 0
    fix_quality: int   = 0

class AmbulanceUpdate(BaseModel):
    ambulance_id:    str
    priority_active: bool  = False
    criticality:     int   = Field(3, ge=1, le=5)
    gps:             GPSData
    timestamp:       float

class AmbulanceStatus(BaseModel):
    ambulance_id:    str
    priority_active: bool
    criticality:     int
    latitude:        Optional[float]
    longitude:       Optional[float]
    speed_kmh:       float
    heading:         float
    destination_eta: Optional[dict]   # {junction_id: eta_seconds}
    last_seen:       datetime
    active:          bool

class JunctionInfo(BaseModel):
    junction_id: str
    latitude:    float
    longitude:   float
    name:        str

class SignalCommand(BaseModel):
    junction_id:      str
    ambulance_id:     str
    state:            SignalState
    green_direction:  int          # 0-3 (N/E/S/W)
    duration_seconds: int
    issued_at:        datetime

class JunctionAck(BaseModel):
    junction_id:  str
    ambulance_id: str
    state:        SignalState
    ack_at:       datetime
    success:      bool
    message:      Optional[str] = None

class DashboardUpdate(BaseModel):
    """Payload broadcast over WebSocket to the dashboard."""
    ambulances: list[AmbulanceStatus]
    junctions:  list[dict]
    timestamp:  datetime
