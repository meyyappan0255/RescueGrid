# ambulance_unit/main.py
# ─────────────────────────────────────────────────────────────
# RescueGrid — Ambulance Unit Firmware (MicroPython / ESP32)
#
# Workflow:
#  1. Connect to Wi-Fi (GSM as fallback)
#  2. Poll GPS every GPS_INTERVAL seconds
#  3. POST location + metadata to central server
#  4. Blink LED to indicate TX status
#  5. Push-button to raise/lower patient criticality
# ─────────────────────────────────────────────────────────────

import time
from machine import Pin, Timer
import config
from gps_module import GPSModule
from comm_module import CommModule

# ── Hardware init ────────────────────────────────────────────
led    = Pin(config.LED_PIN, Pin.OUT)
button = Pin(config.BUTTON_PIN, Pin.IN, Pin.PULL_UP)

gps  = GPSModule(config.GPS_UART_ID, config.GPS_TX_PIN,
                 config.GPS_RX_PIN, config.GPS_BAUDRATE)
comm = CommModule()

# ── State ────────────────────────────────────────────────────
criticality      = config.DEFAULT_CRITICALITY
priority_active  = False
last_button_time = 0

def _blink(n=2, period=0.1):
    for _ in range(n):
        led.on();  time.sleep(period)
        led.off(); time.sleep(period)

def _check_button():
    """Toggle priority activation on button press (debounced)."""
    global priority_active, last_button_time
    now = time.ticks_ms()
    if not button.value() and time.ticks_diff(now, last_button_time) > 500:
        priority_active = not priority_active
        last_button_time = now
        state = "ACTIVE" if priority_active else "INACTIVE"
        print(f"[MAIN] Priority: {state}")
        _blink(4 if priority_active else 1)

# ── Boot sequence ────────────────────────────────────────────
print("=" * 40)
print("  RescueGrid Ambulance Unit Booting")
print(f"  ID: {config.AMBULANCE_ID}")
print("=" * 40)

_blink(3, 0.2)
comm.connect_wifi()
comm.init_gsm()

print("[MAIN] Waiting for GPS fix...")
fix_timeout = time.time() + 60   # wait up to 60 s for first fix
while not gps.has_fix() and time.time() < fix_timeout:
    gps.update()
    time.sleep(0.5)

if gps.has_fix():
    print("[MAIN] GPS fix acquired ✓")
    _blink(5, 0.05)
else:
    print("[MAIN] No GPS fix — continuing without (server will flag)")

# ── Main loop ────────────────────────────────────────────────
last_tx = 0

while True:
    gps.update()
    _check_button()

    now = time.time()
    if now - last_tx >= config.GPS_INTERVAL:
        last_tx = now
        loc = gps.get_location()

        payload = {
            "ambulance_id":    config.AMBULANCE_ID,
            "priority_active": priority_active,
            "criticality":     criticality,
            "gps": loc if loc else {
                "latitude":   None,
                "longitude":  None,
                "speed_kmh":  0,
                "heading":    0,
                "altitude":   0,
                "satellites": 0,
                "fix_quality": 0,
            },
            "timestamp": now,
        }

        led.on()
        success = comm.send_location(payload)
        led.off()

        if success:
            print(f"[MAIN] TX OK | lat={loc['latitude'] if loc else 'N/A'} "
                  f"lon={loc['longitude'] if loc else 'N/A'} "
                  f"spd={loc['speed_kmh'] if loc else 0:.1f} km/h "
                  f"priority={'YES' if priority_active else 'no'}")
        else:
            print("[MAIN] TX FAILED — will retry next cycle")
            _blink(6, 0.05)   # Rapid blink = error

    time.sleep(0.05)   # Yield CPU briefly
