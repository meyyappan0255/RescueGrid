# ambulance_unit/gps_module.py
# ─────────────────────────────────────────────────────────────
# RescueGrid — NEO-6M GPS NMEA Parser (MicroPython / ESP32)
# Parses GPRMC and GPGGA sentences to extract lat, lon,
# speed, heading, and fix quality.
# ─────────────────────────────────────────────────────────────

from machine import UART, Pin
import time

class GPSModule:
    def __init__(self, uart_id, tx_pin, rx_pin, baudrate=9600):
        self.uart = UART(uart_id, baudrate=baudrate,
                         tx=Pin(tx_pin), rx=Pin(rx_pin))
        self.uart.init(baudrate, bits=8, parity=None, stop=1)

        self.latitude   = None
        self.longitude  = None
        self.speed_kmh  = 0.0
        self.heading    = 0.0
        self.altitude   = 0.0
        self.fix_qual   = 0       # 0 = no fix, 1 = GPS, 2 = DGPS
        self.satellites = 0
        self._buffer    = b""

    # ── Public API ───────────────────────────────────────────

    def update(self):
        """Read available bytes and parse any complete NMEA sentences.
        Call this in a tight loop or on a timer."""
        if self.uart.any():
            chunk = self.uart.read(256)
            if chunk:
                self._buffer += chunk
        # Process all complete lines in buffer
        while b"\r\n" in self._buffer:
            line, self._buffer = self._buffer.split(b"\r\n", 1)
            self._parse(line.decode("ascii", errors="ignore").strip())

    def has_fix(self):
        return self.latitude is not None and self.longitude is not None

    def get_location(self):
        """Return dict with current GPS data, or None if no fix."""
        if not self.has_fix():
            return None
        return {
            "latitude":   self.latitude,
            "longitude":  self.longitude,
            "speed_kmh":  self.speed_kmh,
            "heading":    self.heading,
            "altitude":   self.altitude,
            "satellites": self.satellites,
            "fix_quality": self.fix_qual,
        }

    # ── Internal parsing ─────────────────────────────────────

    def _parse(self, sentence):
        if not sentence.startswith("$"):
            return
        if not self._checksum_ok(sentence):
            return
        parts = sentence.split(",")
        msg_type = parts[0][1:]   # Strip leading '$'

        if msg_type == "GPRMC" or msg_type == "GNRMC":
            self._parse_rmc(parts)
        elif msg_type == "GPGGA" or msg_type == "GNGGA":
            self._parse_gga(parts)

    def _parse_rmc(self, p):
        # $GPRMC,HHMMSS.ss,A,LLLL.LL,a,YYYYY.YY,a,x.x,x.x,DDMMYY,...
        try:
            if p[2] != "A":   # 'A' = Active (valid fix)
                return
            self.latitude  = self._nmea_to_decimal(p[3], p[4])
            self.longitude = self._nmea_to_decimal(p[5], p[6])
            self.speed_kmh = float(p[7]) * 1.852 if p[7] else 0.0
            self.heading   = float(p[8]) if p[8] else 0.0
        except (ValueError, IndexError):
            pass

    def _parse_gga(self, p):
        # $GPGGA,HHMMSS.ss,LLLL.LL,a,YYYYY.YY,a,x,xx,x.x,x.x,M,...
        try:
            self.fix_qual   = int(p[6]) if p[6] else 0
            self.satellites = int(p[7]) if p[7] else 0
            self.altitude   = float(p[9]) if p[9] else 0.0
            if self.fix_qual > 0:
                self.latitude  = self._nmea_to_decimal(p[2], p[3])
                self.longitude = self._nmea_to_decimal(p[4], p[5])
        except (ValueError, IndexError):
            pass

    @staticmethod
    def _nmea_to_decimal(value, direction):
        """Convert NMEA DDDMM.MMMM to decimal degrees."""
        if not value:
            return None
        dot = value.index(".")
        deg = float(value[:dot - 2])
        mins = float(value[dot - 2:]) / 60.0
        result = deg + mins
        if direction in ("S", "W"):
            result = -result
        return result

    @staticmethod
    def _checksum_ok(sentence):
        """Validate NMEA XOR checksum (*XX at end)."""
        try:
            if "*" not in sentence:
                return False
            data, checksum = sentence[1:].rsplit("*", 1)
            calc = 0
            for ch in data:
                calc ^= ord(ch)
            return calc == int(checksum.strip(), 16)
        except Exception:
            return False
