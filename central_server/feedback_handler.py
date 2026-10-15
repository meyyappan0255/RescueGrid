# central_server/feedback_handler.py
# ─────────────────────────────────────────────────────────────
# RescueGrid — Closed-Loop Feedback Handler
# Processes ACK / NACK messages from junction units and
# writes audit logs to the database.
# ─────────────────────────────────────────────────────────────

import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from database import SignalLog, JunctionRecord
from models import JunctionAck

logger = logging.getLogger("feedback_handler")

class FeedbackHandler:
    def __init__(self, signal_controller):
        self._signal_ctrl = signal_controller

    async def process(self, ack: JunctionAck, db: AsyncSession):
        logger.info(
            f"[FEEDBACK] {ack.junction_id} | amb={ack.ambulance_id} "
            f"success={ack.success} | {ack.message or ''}"
        )

        # 1. Update the open signal log entry
        await db.execute(
            update(SignalLog)
            .where(
                SignalLog.junction_id  == ack.junction_id,
                SignalLog.ambulance_id == ack.ambulance_id,
                SignalLog.acked_at     == None,          # noqa: E711
            )
            .values(
                acked_at = ack.ack_at,
                success  = ack.success,
                notes    = ack.message,
            )
        )

        # 2. Update junction state in DB
        await db.execute(
            update(JunctionRecord)
            .where(JunctionRecord.id == ack.junction_id)
            .values(state=ack.state, updated_at=datetime.now(timezone.utc))
        )
        await db.commit()

        # 3. Tell signal controller
        self._signal_ctrl.handle_ack(ack.junction_id, ack.success)

    async def log_command_issued(self, junction_id: str, ambulance_id: str,
                                  state: str, issued_at: datetime,
                                  db: AsyncSession):
        entry = SignalLog(
            junction_id  = junction_id,
            ambulance_id = ambulance_id,
            state        = state,
            issued_at    = issued_at,
        )
        db.add(entry)
        await db.commit()
