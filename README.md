# 🚑 RescueGrid — AI & GPS-Based Smart Ambulance Priority System

**Team RescueGrid** | Road Safety Hackathon  
M S Ramaneshvar · V Meyyappan · S A Navasakthi · R Roshini · Subhhashree T

---

## Overview

RescueGrid is an end-to-end smart emergency system that eliminates ambulance delays at traffic intersections using:
- **Real-time GPS tracking** on the ambulance
- **AI-powered camera detection** (YOLOv8) at junctions
- **Predictive green signal control** — lights turn green *before* the ambulance arrives
- **Dedicated 4th Emergency Signal** for exclusive emergency vehicle passage
- **Priority conflict resolution** for multiple simultaneous ambulances
- **Redundant communication** (4G primary, GSM/LoRa backup)
- **Fail-safe & manual override** at every junction

---

## Project Structure

```
RescueGrid/
├── ambulance_unit/        # ESP32 firmware (MicroPython) for the ambulance
│   ├── main.py            # Entry point — GPS polling & server uplink
│   ├── gps_module.py      # NEO-6M GPS NMEA parser
│   ├── comm_module.py     # 4G/Wi-Fi primary + GSM backup
│   └── config.py          # Device config (server URL, credentials)
│
├── central_server/        # Python FastAPI cloud backend
│   ├── main.py            # FastAPI app & REST endpoints
│   ├── route_predictor.py # A* / Dijkstra route prediction & ETA
│   ├── priority_manager.py# Conflict resolution for multiple ambulances
│   ├── signal_controller.py # Issues green-corridor commands to junctions
│   ├── feedback_handler.py # Closed-loop acknowledgment from junctions
│   ├── models.py          # Pydantic data models
│   ├── database.py        # SQLite (dev) / PostgreSQL (prod) setup
│   └── requirements.txt
│
├── junction_unit/         # Raspberry Pi edge AI at each intersection
│   ├── main.py            # Entry point — orchestrates detection & signals
│   ├── ai_detector.py     # YOLOv8 ambulance detection on camera feed
│   ├── signal_driver.py   # GPIO control for traffic light + 4th signal
│   ├── comm_handler.py    # Receives server commands, sends ACK
│   ├── failsafe.py        # Watchdog — flashing yellow if server silent
│   └── requirements.txt
│
├── dashboard/             # Web dashboard (HTML + JS)
│   ├── index.html         # Live map & ambulance tracking UI
│   ├── style.css
│   └── app.js             # WebSocket client — real-time updates
│
└── docs/
    ├── wiring_diagram.md  # Hardware wiring guide
    └── deployment.md      # Setup & deployment instructions
```

---

## Quick Start

### 1. Central Server
```bash
cd central_server
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Junction Unit (Raspberry Pi)
```bash
cd junction_unit
pip install -r requirements.txt
python main.py --junction-id JN001 --server http://<server-ip>:8000
```

### 3. Ambulance Unit (ESP32 — MicroPython)
Upload all files in `ambulance_unit/` to the ESP32 via Thonny or `mpremote`.  
Edit `config.py` with your server URL and ambulance ID.

### 4. Dashboard
Open `dashboard/index.html` in a browser (or serve with any static server).

---

## Hardware Requirements

| Component | Used In | Purpose |
|-----------|---------|---------|
| ESP32 DevKit | Ambulance Unit | Main MCU, Wi-Fi/BLE |
| NEO-6M GPS Module | Ambulance Unit | Real-time location |
| SIM800L GSM Module | Ambulance Unit | Backup communication |
| Raspberry Pi 4 | Junction Unit | Edge AI processing |
| Pi Camera Module v2 | Junction Unit | Ambulance detection |
| 5-channel Relay Module | Junction Unit | Traffic light control |
| RGB LEDs / Signal Lights | Junction Unit | R/Y/G + 4th Emergency signal |

---

## API Endpoints (Central Server)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/ambulance/update` | Receive GPS ping from ambulance |
| GET | `/ambulance/{id}/status` | Get ambulance status |
| POST | `/junction/ack` | Junction acknowledgment |
| GET | `/junctions` | List all junctions & states |
| GET | `/ws/dashboard` | WebSocket — live dashboard feed |

---

## License
MIT License — Free to use, modify, and deploy.
