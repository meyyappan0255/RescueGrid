# central_server/priority_manager.py
# ─────────────────────────────────────────────────────────────
# RescueGrid — Priority Conflict Manager
#
# Resolves which ambulance gets the green corridor when
# multiple units approach the same junction within overlapping
# time windows.  Uses a weighted priority score.
# ─────────────────────────────────────────────────────────────

import time
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("priority_manager")

# ── Scoring weights ──────────────────────────────────────────
W_CRITICALITY = 40   # 1-5 scale → up to 200 pts
W_WAIT_TIME   = 30   # seconds waiting → capped at 300 pts
W_DISTANCE    = 20   # closer ambulance gets higher score
W_TRIP_DIST   = 10   # shorter remaining trip gets priority

MAX_WAIT_CAP  = 300  # seconds — score boost saturates here
ETA_WINDOW    = 30   # seconds — two ETAs within this are "conflicting"

@dataclass
class AmbulanceRequest:
    ambulance_id:    str
    junction_id:     str
    eta_seconds:     float     # seconds until arrival at junction
    criticality:     int       # 1–5
    dist_to_junction: float    # metres
    trip_remaining_m: float    # metres to hospital
    requested_at:    float = field(default_factory=time.time)

    @property
    def wait_seconds(self):
        return time.time() - self.requested_at

    def score(self) -> float:
        crit_score  = self.criticality * W_CRITICALITY
        wait_score  = min(self.wait_seconds, MAX_WAIT_CAP) / MAX_WAIT_CAP * W_WAIT_TIME * 10
        dist_score  = max(0, (500 - self.dist_to_junction) / 500) * W_DISTANCE * 10
        trip_score  = max(0, (5000 - self.trip_remaining_m) / 5000) * W_TRIP_DIST * 10
        return crit_score + wait_score + dist_score + trip_score

class PriorityManager:
    """
    Maintains a queue of active ambulance requests per junction
    and resolves conflicts by score.
    """

    def __init__(self):
        # {junction_id: [AmbulanceRequest]}
        self._queues: dict[str, list[AmbulanceRequest]] = {}

    # ── Public API ───────────────────────────────────────────

    def register(self, req: AmbulanceRequest):
        """Add or update an ambulance request for a junction."""
        jq = self._queues.setdefault(req.junction_id, [])
        # Remove existing entry for this ambulance at this junction
        self._queues[req.junction_id] = [
            r for r in jq if r.ambulance_id != req.ambulance_id
        ]
        self._queues[req.junction_id].append(req)
        logger.info(f"Registered {req.ambulance_id} @ {req.junction_id} "
                    f"ETA={req.eta_seconds:.0f}s score={req.score():.1f}")

    def deregister(self, ambulance_id: str, junction_id: str):
        """Remove a request once the ambulance has passed."""
        if junction_id in self._queues:
            self._queues[junction_id] = [
                r for r in self._queues[junction_id]
                if r.ambulance_id != ambulance_id
            ]

    def get_winner(self, junction_id: str) -> Optional[AmbulanceRequest]:
        """
        Return the highest-priority request for a junction among those
        whose ETAs overlap within ETA_WINDOW seconds.
        Returns None if no active requests.
        """
        candidates = self._queues.get(junction_id, [])
        if not candidates:
            return None

        # Filter to requests that are actually imminent
        imminent = [r for r in candidates if r.eta_seconds <= ETA_WINDOW * 2]
        if not imminent:
            # Return the one arriving soonest
            return min(candidates, key=lambda r: r.eta_seconds)

        # Among imminent, pick highest score
        winner = max(imminent, key=lambda r: r.score())
        logger.info(f"Winner @ {junction_id}: {winner.ambulance_id} "
                    f"score={winner.score():.1f} crit={winner.criticality}")
        return winner

    def get_deferred(self, junction_id: str,
                     winner_id: str) -> list[AmbulanceRequest]:
        """Return all requests at junction that are not the winner."""
        return [
            r for r in self._queues.get(junction_id, [])
            if r.ambulance_id != winner_id
        ]

    def junction_status(self, junction_id: str) -> dict:
        """Summary of all requests at a junction (for logging/dashboard)."""
        reqs = self._queues.get(junction_id, [])
        return {
            "junction_id": junction_id,
            "request_count": len(reqs),
            "requests": [
                {
                    "ambulance_id": r.ambulance_id,
                    "eta_seconds":  round(r.eta_seconds, 1),
                    "criticality":  r.criticality,
                    "score":        round(r.score(), 1),
                    "wait_s":       round(r.wait_seconds, 1),
                }
                for r in sorted(reqs, key=lambda x: -x.score())
            ],
        }

    def purge_expired(self, max_eta: float = 120):
        """Remove stale requests (ETA > max_eta seconds — ambulance diverted)."""
        for jid in list(self._queues.keys()):
            before = len(self._queues[jid])
            self._queues[jid] = [
                r for r in self._queues[jid]
                if r.eta_seconds <= max_eta
            ]
            removed = before - len(self._queues[jid])
            if removed:
                logger.debug(f"Purged {removed} stale request(s) from {jid}")
