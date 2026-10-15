# junction_unit/signal_driver.py
# ─────────────────────────────────────────────────────────────
# RescueGrid — Traffic Signal GPIO Driver (Raspberry Pi)
#
# Controls 4 directions × 3 standard signals + 1 dedicated
# 4th Emergency Signal per direction.
#
# GPIO pin layout (BCM numbering):
#   Direction 0 (North): R=2,  Y=3,  G=4,  E=5
#   Direction 1 (East) : R=6,  Y=13, G=19, E=26
#   Direction 2 (South): R=14, Y=15, G=18, E=23
#   Direction 3 (West) : R=24, Y=25, G=8,  E=7
# ─────────────────────────────────────────────────────────────

import time
import logging
import threading

logger = logging.getLogger("signal_driver")

# Try importing RPi.GPIO; fall back to a stub for dev/testing
try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    _GPIO_AVAILABLE = True
except ImportError:
    logger.warning("RPi.GPIO not available — running in simulation mode")
    _GPIO_AVAILABLE = False

    class _GPIOStub:
        BCM = OUT = IN = 0
        def setmode(self, *a): pass
        def setwarnings(self, *a): pass
        def setup(self, *a, **kw): pass
        def output(self, pin, val):
            logger.debug(f"[GPIO SIM] pin {pin} → {'HIGH' if val else 'LOW'}")
        def cleanup(self): pass
        HIGH = 1
        LOW  = 0
    GPIO = _GPIOStub()

# ── Pin map ──────────────────────────────────────────────────
# Each direction: (RED, YELLOW, GREEN, EMERGENCY)
DIRECTION_PINS = {
    0: (2,  3,  4,  5),    # North
    1: (6,  13, 19, 26),   # East
    2: (14, 15, 18, 23),   # South
    3: (24, 25, 8,  7),    # West
}

R, Y, G, E = 0, 1, 2, 3   # Index aliases

class SignalDriver:
    def __init__(self):
        self._lock  = threading.Lock()
        self._state = {d: "red" for d in DIRECTION_PINS}  # track per-direction
        self._flash_thread = None
        self._stop_flash   = threading.Event()
        self._init_gpio()

    # ── GPIO setup ───────────────────────────────────────────

    def _init_gpio(self):
        for pins in DIRECTION_PINS.values():
            for p in pins:
                GPIO.setup(p, GPIO.OUT)
                GPIO.output(p, GPIO.LOW)
        logger.info(f"GPIO initialised for {len(DIRECTION_PINS)} directions")

    def _set_pin(self, pin, state: bool):
        GPIO.output(pin, GPIO.HIGH if state else GPIO.LOW)

    # ── High-level commands ──────────────────────────────────

    def normal_cycle(self, green_direction: int, green_duration: int = 30):
        """
        Standard timed cycle: one direction gets green, all others red.
        (In a real deployment, cycle through all directions.)
        """
        with self._lock:
            self._stop_flash.set()   # cancel any flashing
            for d, pins in DIRECTION_PINS.items():
                if d == green_direction:
                    self._set_green(d)
                else:
                    self._set_red(d)
        logger.info(f"Normal cycle: direction {green_direction} GREEN "
                    f"for {green_duration}s")
        time.sleep(green_duration)

    def emergency_corridor(self, green_direction: int, duration: int = 45):
        """
        EMERGENCY mode:
        - Green + 4th signal ON for the ambulance direction
        - All other directions: RED only
        """
        with self._lock:
            self._stop_flash.set()
            for d, pins in DIRECTION_PINS.items():
                if d == green_direction:
                    self._set_emergency_green(d)
                else:
                    self._set_red(d)
        logger.info(f"🚨 EMERGENCY corridor: direction {green_direction} "
                    f"for {duration}s")
        time.sleep(duration)
        self.restore_normal()

    def restore_normal(self):
        """Return all signals to a safe red state."""
        with self._lock:
            self._stop_flash.set()
            for d in DIRECTION_PINS:
                self._set_red(d)
        logger.info("Signals restored to normal (all-red)")

    def failsafe_flash(self):
        """
        FAILSAFE mode: flash all yellows if server is unreachable.
        Runs in a background thread until cancelled.
        """
        self._stop_flash.clear()
        def _flash():
            while not self._stop_flash.is_set():
                for d, pins in DIRECTION_PINS.items():
                    self._set_pin(pins[R], False)
                    self._set_pin(pins[Y], True)
                    self._set_pin(pins[G], False)
                    self._set_pin(pins[E], False)
                time.sleep(0.5)
                for d, pins in DIRECTION_PINS.items():
                    self._set_pin(pins[Y], False)
                time.sleep(0.5)
        self._flash_thread = threading.Thread(target=_flash, daemon=True)
        self._flash_thread.start()
        logger.warning("⚠️  FAILSAFE mode activated — flashing yellow")

    def cleanup(self):
        self._stop_flash.set()
        GPIO.cleanup()

    # ── Internal helpers ─────────────────────────────────────

    def _set_red(self, d: int):
        pins = DIRECTION_PINS[d]
        self._set_pin(pins[R], True)
        self._set_pin(pins[Y], False)
        self._set_pin(pins[G], False)
        self._set_pin(pins[E], False)
        self._state[d] = "red"

    def _set_green(self, d: int):
        pins = DIRECTION_PINS[d]
        self._set_pin(pins[R], False)
        self._set_pin(pins[Y], False)
        self._set_pin(pins[G], True)
        self._set_pin(pins[E], False)
        self._state[d] = "green"

    def _set_emergency_green(self, d: int):
        """Green + 4th Emergency signal ON."""
        pins = DIRECTION_PINS[d]
        self._set_pin(pins[R], False)
        self._set_pin(pins[Y], False)
        self._set_pin(pins[G], True)
        self._set_pin(pins[E], True)   # 4th signal!
        self._state[d] = "emergency"
        logger.info(f"4th Emergency Signal ACTIVATED direction {d}")

    def get_state(self) -> dict:
        return dict(self._state)
