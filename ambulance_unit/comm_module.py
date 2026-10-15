# ambulance_unit/comm_module.py
# ─────────────────────────────────────────────────────────────
# RescueGrid — Multi-Mode Communication (MicroPython / ESP32)
# Primary  : Wi-Fi HTTP POST to central server
# Backup   : GSM SIM800L HTTP (AT commands) if Wi-Fi fails
# ─────────────────────────────────────────────────────────────

import network
import urequests
import ujson
import time
from machine import UART, Pin
import config

class CommModule:
    def __init__(self):
        self._wlan   = network.WLAN(network.STA_IF)
        self._gsm_uart = UART(config.GSM_UART_ID,
                              baudrate=config.GSM_BAUDRATE,
                              tx=Pin(config.GSM_TX_PIN),
                              rx=Pin(config.GSM_RX_PIN))
        self._wifi_connected = False
        self._gsm_ready      = False

    # ── Initialisation ───────────────────────────────────────

    def connect_wifi(self):
        self._wlan.active(True)
        if not self._wlan.isconnected():
            print("[COMM] Connecting to Wi-Fi:", config.WIFI_SSID)
            self._wlan.connect(config.WIFI_SSID, config.WIFI_PASS)
            timeout = 15
            while not self._wlan.isconnected() and timeout > 0:
                time.sleep(1)
                timeout -= 1
        self._wifi_connected = self._wlan.isconnected()
        if self._wifi_connected:
            print("[COMM] Wi-Fi connected:", self._wlan.ifconfig())
        else:
            print("[COMM] Wi-Fi failed — will try GSM backup")
        return self._wifi_connected

    def init_gsm(self):
        """Send basic AT commands to wake up SIM800L."""
        try:
            self._gsm_at("AT")               # Check alive
            self._gsm_at("AT+CREG?")         # Check registration
            self._gsm_at(f'AT+SAPBR=3,1,"APN","{config.GSM_APN}"')
            self._gsm_at("AT+SAPBR=1,1")     # Open bearer
            self._gsm_ready = True
            print("[COMM] GSM ready")
        except Exception as e:
            print("[COMM] GSM init failed:", e)
        return self._gsm_ready

    # ── Main send method ─────────────────────────────────────

    def send_location(self, location_data: dict) -> bool:
        """Send GPS payload to central server.
        Returns True on success, False if both channels fail."""
        payload = ujson.dumps(location_data)
        endpoint = config.SERVER_URL + "/ambulance/update"

        if self._wifi_connected or self.connect_wifi():
            try:
                resp = urequests.post(
                    endpoint,
                    headers={"Content-Type": "application/json"},
                    data=payload,
                    timeout=5,
                )
                ok = resp.status_code == 200
                resp.close()
                if ok:
                    return True
                print("[COMM] Server returned:", resp.status_code)
            except Exception as e:
                print("[COMM] Wi-Fi POST failed:", e)
                self._wifi_connected = False

        # Fallback: GSM
        print("[COMM] Trying GSM backup...")
        if self._gsm_ready or self.init_gsm():
            return self._gsm_post(endpoint, payload)

        print("[COMM] All channels failed.")
        return False

    # ── GSM HTTP via AT commands ─────────────────────────────

    def _gsm_post(self, url, payload):
        try:
            self._gsm_at("AT+HTTPINIT")
            self._gsm_at('AT+HTTPPARA="CID",1')
            self._gsm_at(f'AT+HTTPPARA="URL","{url}"')
            self._gsm_at('AT+HTTPPARA="CONTENT","application/json"')
            length = len(payload)
            self._gsm_at(f"AT+HTTPDATA={length},5000")
            self._gsm_uart.write(payload.encode())
            time.sleep(0.5)
            self._gsm_at("AT+HTTPACTION=1")   # POST
            time.sleep(3)
            resp = self._gsm_at("AT+HTTPREAD")
            self._gsm_at("AT+HTTPTERM")
            return "+HTTPACTION: 1,200" in resp or "200" in resp
        except Exception as e:
            print("[COMM] GSM POST error:", e)
            return False

    def _gsm_at(self, cmd, timeout=2):
        self._gsm_uart.write((cmd + "\r\n").encode())
        time.sleep(timeout * 0.4)
        response = ""
        while self._gsm_uart.any():
            chunk = self._gsm_uart.read(128)
            if chunk:
                response += chunk.decode("ascii", errors="ignore")
        return response
