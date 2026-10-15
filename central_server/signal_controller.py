# central_server/signal_controller.py
# ─────────────────────────────────────────────────────────────
# RescueGrid — Signal Controller
# Sends green-corridor and normal-restore commands to
# junction units via HTTP.  Tracks pending commands and
# handles timeouts if no ACK is received.
# ─────────────────────────────────────────────────────────────

import asyncio
import logging
import httpx
from datetime import datetime, timezone
from models import SignalCommand, SignalState

logger = logging.getLogger("signal_controller")

# Seconds before ambulance arrival to issue the command
PREEMPTION_LEAD = 20

# Seconds to wait for junction ACK before re-sending
ACK_TIMEOUT = 8

class SignalController:
    def __init__(self, junction_urls: dict[str, str]):
        """
        junction_urls: {junction_id: "http://192.168.x.x:5000"}
        """
        self._urls    = junction_urls
        self._pending: dict[str, SignalCommand] = {}   # junction_id → command
        self._acked:   set[str] = set()
        self._client  = httpx.AsyncClient(timeout=5.0)

    # ── Public API ───────────────────────────────────────────

    async def issue_emergency(self, junction_id: str, ambulance_id: str,
                               green_direction: int, duration: int = 30):
        """Tell a junction to switch to EMERGENCY mode."""
        cmd = SignalCommand(
            junction_id      = junction_id,
            ambulance_id     = ambulance_id,
            state            = SignalState.EMERGENCY,
            green_direction  = green_direction,
            duration_seconds = duration,
            issued_at        = datetime.now(timezone.utc),
        )
        await self._send(cmd)

    async def restore_normal(self, junction_id: str, ambulance_id: str):
        """Restore junction to normal timed operation."""
        cmd = SignalCommand(
            junction_id      = junction_id,
            ambulance_id     = ambulance_id,
            state            = SignalState.NORMAL,
            green_direction  = 0,
            duration_seconds = 0,
            issued_at        = datetime.now(timezone.utc),
        )
        await self._send(cmd)

    def handle_ack(self, junction_id: str, success: bool):
        """Called by the feedback handler when a junction responds."""
        if success:
            self._acked.add(junction_id)
            self._pending.pop(junction_id, None)
            logger.info(f"[SIGNAL] ACK received from {junction_id} ✓")
        else:
            logger.warning(f"[SIGNAL] NACK from {junction_id} — re-sending")
            pending = self._pending.get(junction_id)
            if pending:
                asyncio.create_task(self._retry(pending))

    async def process_route_etas(self, route: list[str],
                                  etas: dict[str, float],
                                  ambulance_id: str,
                                  green_direction: int = 0):
        """
        Schedule green-corridor commands for each junction on the route.
        Commands are sent PREEMPTION_LEAD seconds before predicted arrival.
        """
        tasks = []
        for jid, eta in etas.items():
            if jid not in self._urls:
                logger.warning(f"No URL registered for junction {jid}")
                continue
            delay = max(0, eta - PREEMPTION_LEAD)
            tasks.append(
                self._scheduled_emergency(jid, ambulance_id,
                                          green_direction, delay)
            )
        await asyncio.gather(*tasks)

    # ── Internal helpers ─────────────────────────────────────

    async def _send(self, cmd: SignalCommand):
        url = self._urls.get(cmd.junction_id)
        if not url:
            logger.error(f"No URL for junction {cmd.junction_id}")
            return
        self._pending[cmd.junction_id] = cmd
        try:
            resp = await self._client.post(
                f"{url}/command",
                json=cmd.model_dump(mode="json"),
            )
            if resp.status_code == 200:
                logger.info(f"[SIGNAL] CMD sent to {cmd.junction_id} "
                            f"state={cmd.state}")
            else:
                logger.warning(f"[SIGNAL] {cmd.junction_id} returned "
                               f"{resp.status_code}")
                await asyncio.sleep(ACK_TIMEOUT)
                await self._retry(cmd)
        except Exception as e:
            logger.error(f"[SIGNAL] Failed to reach {cmd.junction_id}: {e}")
            await asyncio.sleep(ACK_TIMEOUT)
            await self._retry(cmd)

    async def _retry(self, cmd: SignalCommand, max_attempts: int = 3):
        for attempt in range(1, max_attempts + 1):
            logger.info(f"[SIGNAL] Retry {attempt}/{max_attempts} "
                        f"→ {cmd.junction_id}")
            try:
                url = self._urls[cmd.junction_id]
                resp = await self._client.post(
                    f"{url}/command",
                    json=cmd.model_dump(mode="json"),
                )
                if resp.status_code == 200:
                    logger.info(f"[SIGNAL] Retry success {cmd.junction_id}")
                    return
            except Exception as e:
                logger.error(f"[SIGNAL] Retry {attempt} failed: {e}")
            await asyncio.sleep(2 ** attempt)
        logger.critical(f"[SIGNAL] All retries failed for {cmd.junction_id} "
                        f"— junction may be offline")

    async def _scheduled_emergency(self, junction_id, ambulance_id,
                                    direction, delay_seconds):
        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)
        await self.issue_emergency(junction_id, ambulance_id,
                                   direction, duration=45)
