# ambulance_unit/config.py
# ─────────────────────────────────────────────────────────────
# RescueGrid — Ambulance Unit Configuration
# Flash this file to the ESP32 after editing with your values.
# ─────────────────────────────────────────────────────────────

# Unique ID for this ambulance (must match server registration)
AMBULANCE_ID = "AMB-001"

# Patient criticality: 1 (low) to 5 (cardiac arrest / trauma)
# Paramedic sets this via push-button before departure
DEFAULT_CRITICALITY = 3

# ── Primary Communication (Wi-Fi / 4G) ──────────────────────
SERVER_URL   = "http://192.168.1.100:8000"   # Change to your server IP
WIFI_SSID    = "RescueGrid_Network"
WIFI_PASS    = "your_wifi_password"

# GPS update interval (seconds)
GPS_INTERVAL = 1

# ── GPS Module (NEO-6M) ──────────────────────────────────────
GPS_UART_ID  = 1      # UART bus ID on ESP32
GPS_TX_PIN   = 17     # ESP32 TX → GPS RX
GPS_RX_PIN   = 16     # ESP32 RX ← GPS TX
GPS_BAUDRATE = 9600

# ── GSM Backup (SIM800L) ────────────────────────────────────
GSM_UART_ID  = 2
GSM_TX_PIN   = 26
GSM_RX_PIN   = 27
GSM_BAUDRATE = 9600
GSM_APN      = "airtelgprs.com"    # Change to your carrier APN
SERVER_SMS_NUMBER = "+919876543210" # Server's fallback SMS number

# ── Push-button (manual priority activation) ─────────────────
BUTTON_PIN   = 0      # BOOT button on most ESP32 boards

# ── LED indicators ───────────────────────────────────────────
LED_PIN      = 2      # Built-in LED — blinks while transmitting
