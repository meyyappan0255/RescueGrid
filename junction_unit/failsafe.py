# junction_unit/failsafe.py
# ─────────────────────────────────────────────────────────────
# RescueGrid — Failsafe Watchdog
#
# Monitors server heartbeat.  If no command or ping is
# received within TIMEOUT seconds, switches signals to
# flashing yellow (failsafe) mode automatically.
# ─────────────────────────────────────────────────────────────

import time
import threading
import logging

logger = logging.getLogger("failsafe")

TIMEOUT = 10   # seconds — switch to failsafe if no message received

class FailsafeWatchdog:
    def __init__(self, signal_driver):
        self._driver      = signal_driver
        self._last_rx     = time.time()
        self._in_failsafe = False
        self._lock        = threading.Lock()
        self._thread      = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info(f"Watchdog started (timeout={TIMEOUT}s)")

    def ping(self):
        """Call this every time a message is received from the server."""
        with self._lock:
            self._last_rx = time.time()
            if self._in_failsafe:
                logger.info("Server back online — exiting failsafe")
                self._in_failsafe = False
                self._driver.restore_normal()

    def _loop(self):
        while True:
            time.sleep(1)
            with self._lock:
                elapsed = time.time() - self._last_rx
            if elapsed > TIMEOUT and not self._in_failsafe:
                logger.critical(
                    f"No server contact for {elapsed:.0f}s — activating failsafe!"
                )
                self._in_failsafe = True
                self._driver.failsafe_flash()
