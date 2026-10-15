# RescueGrid — Hardware Wiring Guide

## Ambulance Unit (ESP32)

```
NEO-6M GPS Module
  VCC  → 3.3V
  GND  → GND
  TX   → ESP32 GPIO16 (RX)
  RX   → ESP32 GPIO17 (TX)

SIM800L GSM Module
  VCC  → 5V (needs 2A peak — use dedicated supply!)
  GND  → GND (share with ESP32 GND)
  TX   → ESP32 GPIO27 (RX2)
  RX   → ESP32 GPIO26 (TX2)

Push Button (Criticality / Manual Priority)
  One side → GPIO0 (BOOT pin)
  Other    → GND
  (Internal pull-up enabled in firmware)

LED Indicator (Built-in)
  GPIO2 (built-in LED on most ESP32 boards)
```

### Power
- Power ESP32 via USB or 5V regulator
- SIM800L must have its OWN 5V supply capable of 2A surge
- Share GND between ESP32 and SIM800L

---

## Junction Unit (Raspberry Pi 4)

### Traffic Signal Relay Module (5-channel)
Connect relay module IN pins to Pi GPIO (BCM):

```
Direction 0 (North):
  RED    → GPIO2   (Pin 3)
  YELLOW → GPIO3   (Pin 5)
  GREEN  → GPIO4   (Pin 7)
  EMRG   → GPIO5   (Pin 29)   ← 4th Emergency Signal

Direction 1 (East):
  RED    → GPIO6   (Pin 31)
  YELLOW → GPIO13  (Pin 33)
  GREEN  → GPIO19  (Pin 35)
  EMRG   → GPIO26  (Pin 37)

Direction 2 (South):
  RED    → GPIO14  (Pin 8)
  YELLOW → GPIO15  (Pin 10)
  GREEN  → GPIO18  (Pin 12)
  EMRG   → GPIO23  (Pin 16)

Direction 3 (West):
  RED    → GPIO24  (Pin 18)
  YELLOW → GPIO25  (Pin 22)
  GREEN  → GPIO8   (Pin 24)
  EMRG   → GPIO7   (Pin 26)

Relay VCC → Pi 5V (Pin 2 or 4)
Relay GND → Pi GND (Pin 6)
```

### Traffic Light Lamps
- Each relay COM connected to 12V DC supply
- NO (Normally Open) connected to lamp
- LED signal lamps recommended (12V, 10W each)
- Emergency signal: use flashing amber/white LED strobe

### Pi Camera Module v2
- Connect to Pi CSI-2 ribbon cable port
- Enable with: `sudo raspi-config` → Interface Options → Camera

### Manual Override Switch
- Key switch wired to GPIO12 (Pin 32) with pull-up
- When switch is ON: junction falls back to manual control

---

## Network Topology

```
[ Central Server ]  ←→  Internet / LAN
       ↑↓
  [ Wi-Fi Router ]
   ↑           ↑
[ Pi Junction ] [ Pi Junction ] ...  (wired LAN or Wi-Fi)
                          ↑
                  [ ESP32 Ambulance ] (Wi-Fi)
```

### Recommended: Static IPs
- Server:       192.168.1.100
- Junction JN001: 192.168.1.10
- Junction JN002: 192.168.1.11
- Junction JN003: 192.168.1.12
- (etc.)

Set static IPs in your router's DHCP reservation table by MAC address.

---

## Bill of Materials (per unit)

### Ambulance Unit
| Component | Qty | Approx Cost (INR) |
|-----------|-----|-------------------|
| ESP32 DevKit v1 | 1 | ₹450 |
| NEO-6M GPS module | 1 | ₹350 |
| SIM800L GSM module | 1 | ₹550 |
| Push button | 1 | ₹10 |
| 5V 2A power bank / supply | 1 | ₹300 |
| Jumper wires + enclosure | — | ₹150 |
| **Total** | | **≈ ₹1,810** |

### Junction Unit
| Component | Qty | Approx Cost (INR) |
|-----------|-----|-------------------|
| Raspberry Pi 4 (2GB) | 1 | ₹4,500 |
| Pi Camera Module v2 | 1 | ₹1,200 |
| 5-channel relay module | 1 | ₹200 |
| LED signal lamps (12V) | 16 | ₹800 |
| Emergency strobe LED | 4 | ₹400 |
| 12V 5A power supply | 1 | ₹600 |
| Key switch | 1 | ₹150 |
| Enclosure + wiring | — | ₹500 |
| **Total** | | **≈ ₹8,350** |
