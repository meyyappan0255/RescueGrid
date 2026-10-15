# ambulance_unit/config.py
# RescueGrid ESP32 configuration.
# Replace the example values for your own device before flashing.
# Do not commit real credentials or private production endpoints.

AMBULANCE_ID = "AMB-001"
DEFAULT_CRITICALITY = 3  # 1 (low) to 5 (highest)

# Example private LAN address only; update for your test network.
SERVER_URL = "http://192.168.1.100:8000"
WIFI_SSID = "CHANGE_ME_WIFI_SSID"
WIFI_PASS = "CHANGE_ME_WIFI_PASSWORD"

GPS_INTERVAL = 1
GPS_UART_ID = 1
GPS_TX_PIN = 17
GPS_RX_PIN = 16
GPS_BAUDRATE = 9600

GSM_UART_ID = 2
GSM_TX_PIN = 26
GSM_RX_PIN = 27
GSM_BAUDRATE = 9600
GSM_APN = "CHANGE_ME_APN"
# Optional destination; leave blank unless SMS fallback is configured.
SERVER_SMS_NUMBER = ""

# Check pin assignments against the exact ESP32 board.
BUTTON_PIN = 0
LED_PIN = 2
