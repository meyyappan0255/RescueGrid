# junction_unit/main.py
# ─────────────────────────────────────────────────────────────
# RescueGrid — Junction Unit (Raspberry Pi)
#
# Runs a lightweight FastAPI server that:
#   POST /command  ← Receives SignalCommand from central server
#   GET  /status   ← Returns current signal state
#
# Also runs:
#   - AI ambulance detection in a background thread
#   - Failsafe watchdog
#
# Usage:
#   python main.py --junction-id JN001 --server http://192.168.1.100:8000
# ─────────────────────────────────────────────────────────────

import argparse
import asyncio
import logging
import threading
from datetime import datetime, timezone

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional

from signal_driver import SignalDriver
from ai_detector  import AmbulanceDetector
from comm_handler import CommHandler
from failsafe     import FailsafeWatchdog

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("junction_main")

# ── CLI args ─────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--junction-id", default="JN001")
parser.add_argument("--server",      default="http://localhost:8000")
parser.add_argument("--camera",      type=int, default=0)
parser.add_argument("--port",        type=int, default=5000)
parser.add_argument("--no-camera",   action="store_true")
args = parser.parse_args()

JUNCTION_ID = args.junction_id
SERVER_URL  = args.server
PORT        = args.port

# ── Singletons ───────────────────────────────────────────────
signals  = SignalDriver()
comm     = CommHandler(SERVER_URL, JUNCTION_ID)
watchdog = FailsafeWatchdog(signals)

detector = None
if not args.no_camera:
    try:
        detector = AmbulanceDetector(args.camera)
        logger.info("AI Detector initialised ✓")
    except Exception as e:
        logger.warning(f"Camera init failed: {e} — running without AI detection")

# ── Current state ─────────────────────────────────────────────
_current_ambulance_id: Optional[str] = None
_current_state: str = "normal"

# ── FastAPI app ──────────────────────────────────────────────
app = FastAPI(title=f"RescueGrid Junction Unit {JUNCTION_ID}")

class CommandPayload(BaseModel):
    junction_id:      str
    ambulance_id:     str
    state:            str          # "normal" | "emergency" | "failsafe"
    green_direction:  int = 0
    duration_seconds: int = 30
    issued_at:        str

@app.post("/command")
async def receive_command(cmd: CommandPayload):
    global _current_ambulance_id, _current_state

    logger.info(f"Command received: {cmd.state} from server "
                f"(amb={cmd.ambulance_id})")

    # Ping watchdog — server is alive
    watchdog.ping()

    _current_ambulance_id = cmd.ambulance_id
    _current_state        = cmd.state

    # Execute in a thread so we don't block the HTTP response
    def _exec():
        try:
            if cmd.state == "emergency":
                signals.emergency_corridor(
                    green_direction = cmd.green_direction,
                    duration        = cmd.duration_seconds,
                )
                comm.send_ack(cmd.ambulance_id, "emergency",
                              success=True, message="Green corridor active")
                # After duration, automatically restore
                signals.restore_normal()
                comm.send_ack(cmd.ambulance_id, "normal",
                              success=True, message="Corridor released")

            elif cmd.state == "normal":
                signals.restore_normal()
                comm.send_ack(cmd.ambulance_id, "normal",
                              success=True, message="Normal operation")

            elif cmd.state == "failsafe":
                signals.failsafe_flash()
                comm.send_ack(cmd.ambulance_id, "failsafe",
                              success=True, message="Failsafe activated")

        except Exception as e:
            logger.error(f"Command execution error: {e}")
            comm.send_ack(cmd.ambulance_id, cmd.state,
                          success=False, message=str(e))

    threading.Thread(target=_exec, daemon=True).start()
    return {"status": "executing", "junction_id": JUNCTION_ID}


@app.get("/status")
async def status():
    return {
        "junction_id":       JUNCTION_ID,
        "signal_state":      _current_state,
        "ambulance_serving": _current_ambulance_id,
        "gpio_state":        signals.get_state(),
        "timestamp":         datetime.now(timezone.utc).isoformat(),
    }

@app.get("/health")
async def health():
    watchdog.ping()
    return {"status": "ok", "junction_id": JUNCTION_ID}

# ── AI detection background thread ──────────────────────────

def _detection_loop():
    if not detector:
        return
    def _on_detection(result, frame):
        if result["ambulance_detected"] and _current_state != "emergency":
            logger.info(
                f"AI VISUAL CONFIRM: ambulance detected "
                f"conf={result['confidence']:.2f} method={result['method']}"
            )
            # Visual confirmation — notify server (optional enhancement)
            # comm.notify_visual_confirm(_current_ambulance_id)
    detector.run_continuous(_on_detection, interval=0.5)

threading.Thread(target=_detection_loop, daemon=True).start()

# ── Entry point ──────────────────────────────────────────────
if __name__ == "__main__":
    logger.info(f"Junction Unit {JUNCTION_ID} starting on port {PORT}")
    logger.info(f"Central server: {SERVER_URL}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
