# RescueGrid — Deployment Guide

## Prerequisites
- Python 3.11+ on the server machine
- MicroPython firmware on ESP32
- Raspberry Pi OS (64-bit) on junction Pis

---

## 1. Central Server Setup

```bash
# Clone / copy project
cd central_server
pip install -r requirements.txt

# (Optional) Set environment variables
export DATABASE_URL="sqlite+aiosqlite:///./rescuegrid.db"
# For production PostgreSQL:
# export DATABASE_URL="postgresql+asyncpg://user:pass@localhost/rescuegrid"

# Run server
uvicorn main:app --host 0.0.0.0 --port 8000
```

The server auto-creates the database on first run.

**Add your junction units to the DB** by inserting rows into the `junctions` table, or extend `main.py` to load from a JSON config.

---

## 2. Junction Unit Setup (Raspberry Pi)

```bash
# On each Raspberry Pi
cd junction_unit
pip install -r requirements.txt

# Run (replace with actual junction ID and server IP)
python main.py \
  --junction-id JN001 \
  --server http://192.168.1.100:8000 \
  --port 5000
```

### Auto-start on boot (systemd)

Create `/etc/systemd/system/rescuegrid-junction.service`:
```ini
[Unit]
Description=RescueGrid Junction Unit
After=network.target

[Service]
ExecStart=/usr/bin/python3 /home/pi/junction_unit/main.py \
    --junction-id JN001 \
    --server http://192.168.1.100:8000
WorkingDirectory=/home/pi/junction_unit
Restart=always
RestartSec=5
User=pi

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable rescuegrid-junction
sudo systemctl start  rescuegrid-junction
```

---

## 3. Ambulance Unit Setup (ESP32 MicroPython)

### Flash MicroPython firmware
```bash
# Install esptool
pip install esptool

# Erase and flash (adjust port as needed)
esptool.py --port /dev/ttyUSB0 erase_flash
esptool.py --port /dev/ttyUSB0 --baud 460800 \
  write_flash -z 0x1000 esp32-20240602-v1.23.0.bin
```
Download firmware from: https://micropython.org/download/ESP32_GENERIC/

### Upload code with mpremote
```bash
pip install mpremote

cd ambulance_unit
# Edit config.py first!

mpremote connect /dev/ttyUSB0 cp config.py     :config.py
mpremote connect /dev/ttyUSB0 cp gps_module.py :gps_module.py
mpremote connect /dev/ttyUSB0 cp comm_module.py:comm_module.py
mpremote connect /dev/ttyUSB0 cp main.py       :main.py

# Verify and run
mpremote connect /dev/ttyUSB0 ls
mpremote connect /dev/ttyUSB0 run main.py
```

---

## 4. Dashboard

Simply open `dashboard/index.html` in a browser.

For a proper deployment:
```bash
cd dashboard
python -m http.server 8080
# Then open http://localhost:8080
```

Edit the `SERVER_WS` constant in `app.js` to point to your server.

---

## 5. YOLOv8 Model (Junction AI)

The detector falls back to colour-based siren detection if no ONNX model is present.  
To use the full AI model:

```bash
# On a PC with GPU (not on the Pi)
pip install ultralytics

# Export YOLOv8n to ONNX (base model — retrain on ambulance dataset for best results)
yolo export model=yolov8n.pt format=onnx imgsz=640

# Copy to Pi
scp yolov8n.pt.onnx pi@192.168.1.10:~/junction_unit/models/yolov8n_ambulance.onnx
```

**Recommended training dataset**: fine-tune on Indian ambulance images  
(collect via Roboflow or manually label 500+ images).

---

## 6. Testing Without Hardware

The entire system can be tested on a laptop:
- Central server: `uvicorn main:app --reload`
- Junction unit: `python junction_unit/main.py --no-camera` (GPIO stub activates automatically)
- Simulate ambulance GPS: use `curl` or Postman to POST to `/ambulance/update`

Example test payload:
```bash
curl -X POST http://localhost:8000/ambulance/update \
  -H "Content-Type: application/json" \
  -d '{
    "ambulance_id": "AMB-001",
    "priority_active": true,
    "criticality": 4,
    "gps": {
      "latitude": 13.0827,
      "longitude": 80.2707,
      "speed_kmh": 40,
      "heading": 45,
      "altitude": 10,
      "satellites": 8,
      "fix_quality": 1
    },
    "timestamp": 1717027200
  }'
```
