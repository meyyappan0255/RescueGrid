# junction_unit/comm_handler.py
# ─────────────────────────────────────────────────────────────
# RescueGrid — Junction Communication Handler
# Receives SignalCommand from the central server and sends
# JunctionAck back after executing the command.
# ─────────────────────────────────────────────────────────────

import httpx
import logging
from datetime import datetime, timezone

logger = logging.getLogger("comm_handler")

class CommHandler:
    def __init__(self, server_url: str, junction_id: str):
        self._server    = server_url.rstrip("/")
        self._jid       = junction_id
        self._client    = httpx.Client(timeout=5.0)

    def send_ack(self, ambulance_id: str, state: str,
                 success: bool, message: str = ""):
        payload = {
            "junction_id":  self._jid,
            "ambulance_id": ambulance_id,
            "state":        state,
            "ack_at":       datetime.now(timezone.utc).isoformat(),
            "success":      success,
            "message":      message,
        }
        try:
            resp = self._client.post(f"{self._server}/junction/ack", json=payload)
            if resp.status_code == 200:
                logger.info(f"ACK sent to server ✓ (amb={ambulance_id})")
            else:
                logger.warning(f"Server returned {resp.status_code} for ACK")
        except Exception as e:
            logger.error(f"Failed to send ACK: {e}")
