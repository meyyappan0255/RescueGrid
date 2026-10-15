# 🚑 RescueGrid — AI & GPS-Based Smart Ambulance Priority System

**Purpose:** prototype for GPS-based ambulance tracking, junction coordination, and a live dashboard.  
**Status:** hackathon / research prototype — **not approved for real-world traffic control**.

## Overview

RescueGrid is a modular prototype with:
- ESP32/MicroPython ambulance unit for GPS updates, Wi-Fi, and a SIM800L/GSM fallback path.
- FastAPI central server for status updates, route/ETA logic, priority management, junction commands, and dashboard updates.
- Raspberry Pi junction unit with camera-detection hooks, a signal-driver abstraction, and a watchdog.
- Browser dashboard displaying ambulance and junction state on a Leaflet map.

Capabilities depend on configured hardware, junction registration, network reachability, model availability, and integration work. This repository does not demonstrate certified traffic-signal control or production-grade AI detection. Simulated runs are not safety evidence.

## Repository layout

```text
ambulance_unit/       ESP32 MicroPython code and device configuration
central_server/       FastAPI service, models, persistence, routing and priority logic
junction_unit/        Raspberry Pi service, detector, signal driver and watchdog
dashboard/            HTML/CSS/JavaScript map dashboard
docs/                 Architecture, deployment, wiring and security guidance
tests/                Hardware-independent unit tests
requirements-dev.txt  Development/test dependencies
```

See [docs/architecture.md](docs/architecture.md) for component responsibilities and data flow.

## Quick start — central server

Use Python 3.11 or newer. From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r central_server/requirements.txt
cd central_server
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

The default database is a local SQLite file. CORS defaults to common localhost dashboard origins. Set `RESCUEGRID_CORS_ORIGINS` to a comma-separated list of exact trusted browser origins when hosting the dashboard elsewhere. Do not use wildcard CORS for deployment.

## Run the dashboard

In another terminal, from the repository root:

```bash
cd dashboard
python -m http.server 8080
```

Open http://localhost:8080. The dashboard currently connects to `ws://localhost:8000/ws/dashboard`; update `dashboard/app.js` for another server host and use secure WebSockets (WSS) when served over HTTPS.

## Run the junction service

On a supported Raspberry Pi or compatible development environment:

```bash
pip install -r junction_unit/requirements.txt
cd junction_unit
python main.py --junction-id JN001 --server http://127.0.0.1:8000 --no-camera
```

The signal driver may use a hardware-free fallback when GPIO is unavailable. Verify the actual driver and GPIO behavior before connecting any physical signal equipment. This is not a certified traffic controller.

## Ambulance unit configuration

1. Edit `ambulance_unit/config.py` for your device ID, server URL, Wi-Fi, carrier APN, UARTs, and pins.
2. Upload all four Python files to the ESP32 using Thonny or mpremote.
3. Test GPS parsing and network delivery on a bench before any field trial.

Checked-in values are examples/placeholders. Never commit real passwords, tokens, private keys, personal data, or production endpoints.

## API endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/ambulance/update` | Receive ambulance GPS/status update |
| GET | `/ambulance/{id}/status` | Read ambulance status |
| GET | `/junctions` | List junction state |
| POST | `/junction/ack` | Receive junction acknowledgment |
| WebSocket | `/ws/dashboard` | Stream dashboard state |

The API may change during development. Open `/docs` while the local server is running for interactive API documentation.

## Tests

From the repository root:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Tests cover data validation, priority-queue behavior, and route-planning basics. They do not test ESP32 hardware, GPS reception, camera model accuracy, relay timing, network fault recovery, or safe operation at a real junction. Record test output from your own environment before claiming tests passed.

## Safety, security and limitations

- Never connect this prototype to live public-road signals.
- API endpoints and junction commands do not yet have complete authentication/authorization. Run only on a trusted isolated lab network until this is implemented.
- Use HTTPS/WSS, restricted network access, managed secrets, command freshness/replay protection, and audit logs before any controlled trial.
- A software watchdog is not a certified traffic controller. Use independently engineered and locally approved signal hardware and fail-safe behavior.
- The route graph and junction configuration are demonstration data and must be replaced with verified data.
- AI detection quality depends on the actual model and representative validation data. A generic model or colour heuristic is not proof of reliable ambulance recognition.
- GPS, Wi-Fi, cellular service, cameras, and hardware may fail. Test failures safely on a bench.

See [docs/security.md](docs/security.md) and [docs/deployment.md](docs/deployment.md).

## AI assistance disclosure

AI assistance was used to help review and improve project documentation, security notes, and test scaffolding. The project team remains responsible for reviewing changes, verifying test results, validating hardware behavior, and accurately describing what is implemented. Update this statement if the actual tools or scope of assistance differ.

## License

MIT — see [LICENSE](LICENSE).
