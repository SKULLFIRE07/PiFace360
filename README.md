<p align="center">
  <img src="https://img.shields.io/badge/PiFace360-AI%20Attendance-0066FF?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCI+PHBhdGggZD0iTTkgMTBoLjAxTTE1IDEwaC4wMU0xMiAxNWguMDFNNCA4VjZhMiAyIDAgMCAxIDItMmgxMmEyIDIgMCAwIDEgMiAydjJNNCA4djhhMiAyIDAgMCAwIDIgMmgxMmEyIDIgMCAwIDAgMi0yVjhNNCA4aDE2Ii8+PC9zdmc+" alt="PiFace360">
</p>

<h1 align="center">PiFace360</h1>

<p align="center">
  <strong>AI-Powered Facial Recognition Attendance System for Raspberry Pi 5</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/react-18.2-61dafb?style=flat-square&logo=react&logoColor=white" alt="React">
  <img src="https://img.shields.io/badge/fastapi-0.104-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/platform-RPi5-c51a4a?style=flat-square&logo=raspberrypi&logoColor=white" alt="RPi5">
  <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/status-production--ready-brightgreen?style=flat-square" alt="Status">
</p>

<p align="center">
  <em>Zero-cloud, zero-internet, fully offline attendance monitoring -- powered by edge AI on a Raspberry Pi 5.</em>
</p>

---

## What is PiFace360?

**PiFace360** is a self-contained, enterprise-grade attendance monitoring system that runs entirely on a Raspberry Pi 5. It uses real-time facial recognition to automatically log employee entry and exit -- no badges, no fingerprints, no cloud dependency.

Connect to the Pi's WiFi hotspot, open the dashboard, and you're running a complete HR attendance system.

```
Employee walks in --> Camera detects face --> AI identifies person --> Attendance logged --> LED confirms
```

### Why PiFace360?

| Problem | PiFace360 Solution |
|---------|-------------------|
| Cloud-based systems need internet | Runs 100% offline on local hardware |
| Badge/fingerprint systems are slow | Face recognition is instant and contactless |
| Enterprise systems cost thousands | Runs on a $80 Raspberry Pi 5 |
| Complex setup & IT dependencies | One-script installation, WiFi hotspot built-in |
| Privacy concerns with cloud storage | All data stays on-device, never leaves your network |

---

## Features

### Core

- **Real-Time Face Recognition** -- InsightFace AI engine processes live camera feeds at ~15 FPS
- **Dual Camera System** -- Separate IN (entrance) and OUT (exit) cameras for accurate direction tracking
- **Automatic IN/OUT Logging** -- Timestamps every entry and exit with confidence scores
- **Unknown Visitor Detection** -- Flags unrecognized faces for admin review and enrollment

### Dashboard & UI

- **Live Dashboard** -- Real-time attendance stats, present/absent counts, live camera feeds
- **Employee Management** -- Add, edit, enroll faces, manage departments
- **Attendance Log** -- Searchable, sortable historical records with filters
- **Leave Management** -- Submit and track sick, casual, annual, and personal leave with calendar view
- **Reports** -- Generate and download Excel/PDF daily and monthly attendance reports
- **Camera Management** -- Detect, assign, and monitor multiple USB cameras
- **Settings** -- Company info, working hours, face recognition thresholds, system status, backup/restore

### Hardware & Deployment

- **WiFi Hotspot** -- Pi creates its own network (no router needed)
- **LED Indicators** -- Green flash for entry, red flash for exit (GPIO-driven)
- **HTTPS** -- Self-signed TLS certificate for secure access
- **Captive Portal** -- Auto-redirects connected devices to the dashboard
- **Systemd Services** -- Auto-starts on boot, auto-restarts on failure
- **One-Script Install** -- Complete deployment in a single command

### Security

- **JWT Authentication** -- Token-based admin login
- **CSRF Protection** -- Double-submit cookie pattern
- **Rate Limiting** -- Brute-force protection on auth endpoints
- **Firewall** -- iptables rules restrict access to essential ports only

---

## Architecture

```
                         ┌──────────────────────────────────┐
                         │        Raspberry Pi 5            │
                         │                                  │
  ┌──────────┐          │  ┌───────────┐  ┌────────────┐  │
  │ Camera IN├──────────┼──│           │  │  FastAPI    │  │
  └──────────┘          │  │  Face     │  │  Backend    │──┼──── HTTPS ──── Browser
  ┌──────────┐          │  │  Engine   │──│  (Uvicorn)  │  │     :443
  │Camera OUT├──────────┼──│           │  │             │  │
  └──────────┘          │  │ InsightFace│  └─────┬──────┘  │
                         │  └─────┬─────┘        │         │
                         │        │         ┌────┴─────┐   │
  ┌──────────┐          │  ┌─────┴─────┐   │  SQLite  │   │
  │  LEDs    ├──────────┼──│    LED    │   │    DB    │   │
  │ (GPIO)   │          │  │ Controller│   └──────────┘   │
  └──────────┘          │  └───────────┘                   │
                         │                                  │
                         │  ┌───────────┐  ┌────────────┐  │
                         │  │  hostapd  │  │  Nginx     │  │
                         │  │  (WiFi AP)│  │  (Reverse  │  │
                         │  └───────────┘  │   Proxy)   │  │
                         │                  └────────────┘  │
                         └──────────────────────────────────┘
```

### Tech Stack

| Layer | Technology |
|-------|-----------|
| **AI Engine** | InsightFace + ONNX Runtime (512-d face embeddings) |
| **Backend** | Python 3.11, FastAPI, SQLAlchemy 2.0, SQLite (WAL mode) |
| **Frontend** | React 18, Vite 5, TailwindCSS, TanStack Query, Recharts |
| **Streaming** | MJPEG over HTTP, Server-Sent Events (SSE) |
| **Hardware** | gpiozero + lgpio (Pi 5 native), picamera2 / USB webcams |
| **Networking** | hostapd (WiFi AP), dnsmasq (DHCP), Nginx (reverse proxy) |
| **Security** | JWT, CSRF tokens, bcrypt, self-signed TLS, iptables |
| **Process Mgmt** | systemd (3 services: web, engine, LEDs) |

---

## Hardware Requirements

### Shopping List

| Item | Specification | Approx. Cost |
|------|--------------|-------------|
| Raspberry Pi 5 | 8GB RAM recommended | $80 |
| microSD Card | 64GB+ Class 10 / A2 | $12 |
| USB-C Power Supply | 27W (5.1V, 5A) official PSU | $12 |
| USB Camera(s) | 1080p, USB 2.0/3.0 (x2 for dual setup) | $25 each |
| LEDs + Resistors | Green LED, Red LED, 330 ohm resistors | $2 |
| Case (optional) | Official Pi 5 case or 3D printed | $10 |
| **Total** | | **~$165** |

### GPIO Wiring

```
Pi 5 GPIO Header
─────────────────
Pin 11 (GPIO 17) ──── 330Ω ──── Green LED (+) ──── GND (Pin 9)
Pin 13 (GPIO 27) ──── 330Ω ──── Red LED (+)   ──── GND (Pin 14)
```

---

## Quick Start

### 1. Flash Raspberry Pi OS

```bash
# Use Raspberry Pi Imager
# OS: Raspberry Pi OS (64-bit) Bookworm
# Enable SSH in imager settings
# Set username: pi, password: <your-password>
```

### 2. Clone & Install

```bash
ssh pi@raspberrypi.local

git clone https://github.com/SKULLFIRE07/PiFace360.git
cd PiFace360

# Run the one-script installer (takes ~15 minutes)
sudo bash piface/setup/install.sh
```

### 3. Connect & Use

```
1. Look for WiFi network: "AttendanceSystem"
2. Connect from any device (phone/laptop)
3. Open browser --> auto-redirects to dashboard
4. Login with default credentials:
   Username: admin
   Password: admin123
5. Complete the setup wizard
6. Enroll employees via the Employees tab
7. Point cameras at entry/exit doors
8. Done -- attendance is now automatic
```

---

## Development Setup

For local development on any machine (no Pi required):

### Backend

```bash
cd PiFace360

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r piface/requirements.txt

# Seed demo data (20 employees, 14 days of attendance)
python seed_data.py

# Start backend
python -m uvicorn piface.backend.main:app --host 0.0.0.0 --port 8001 --reload
```

### Frontend

```bash
cd piface/frontend

# Install dependencies
npm install

# Start dev server (proxies API to :8001)
npx vite --port 5173
```

Open `http://localhost:5173` -- login with `admin` / `admin123`.

---

## Project Structure

```
PiFace360/
├── piface/
│   ├── backend/                 # FastAPI application
│   │   ├── main.py             #   App factory, middleware, lifespan
│   │   ├── models.py           #   SQLAlchemy ORM models
│   │   ├── schemas.py          #   Pydantic request/response schemas
│   │   ├── database.py         #   DB engine, session management
│   │   ├── security.py         #   JWT, CSRF, rate limiting
│   │   └── routes/             #   13 endpoint modules
│   │       ├── auth.py         #     Login / logout
│   │       ├── employees.py    #     Employee CRUD + face enrollment
│   │       ├── attendance.py   #     Attendance events & summaries
│   │       ├── unknowns.py     #     Unknown face management
│   │       ├── reports.py      #     Excel/PDF report generation
│   │       ├── leave.py        #     Leave records
│   │       ├── holidays.py     #     Holiday calendar
│   │       ├── settings.py     #     System configuration
│   │       ├── stream.py       #     Camera feeds & MJPEG streaming
│   │       ├── system.py       #     System health & status
│   │       ├── backup.py       #     Database backup/restore
│   │       ├── calibration.py  #     Camera calibration
│   │       └── setup.py        #     First-time setup wizard
│   │
│   ├── frontend/                # React SPA
│   │   ├── src/
│   │   │   ├── pages/          #   Today, Employees, Attendance,
│   │   │   │                   #   Unknowns, Reports, Leave,
│   │   │   │                   #   Cameras, Settings, Login, Setup
│   │   │   ├── components/     #   Layout, LiveFeed, Dialogs, etc.
│   │   │   ├── hooks/          #   useAuth, useSSE
│   │   │   └── api/            #   Axios client with interceptors
│   │   ├── package.json
│   │   └── vite.config.js
│   │
│   ├── core/                    # AI & Hardware
│   │   ├── face_engine.py      #   Main recognition loop
│   │   ├── camera.py           #   Camera capture (picamera2/USB)
│   │   ├── tracker.py          #   Multi-object face tracking
│   │   ├── preprocessing.py    #   Image preprocessing
│   │   ├── led_controller.py   #   GPIO LED control
│   │   └── event_bus.py        #   Inter-process communication
│   │
│   ├── setup/                   # Deployment
│   │   ├── install.sh          #   One-script installer
│   │   ├── nginx.conf          #   Reverse proxy + captive portal
│   │   ├── hostapd.conf        #   WiFi hotspot config
│   │   ├── dnsmasq.conf        #   DHCP server config
│   │   └── piface-*.service    #   3 systemd service files
│   │
│   └── requirements.txt         # Python dependencies
│
├── seed_data.py                 # Demo data generator
└── README.md
```

---

## API Reference

All endpoints return a unified envelope:

```json
{
  "success": true,
  "data": { ... },
  "error": null
}
```

### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/login` | Authenticate and receive JWT |
| `GET` | `/api/employees` | List all employees |
| `POST` | `/api/employees` | Create employee + enroll face |
| `GET` | `/api/attendance/events` | Query attendance events (sortable, filterable) |
| `GET` | `/api/attendance/today` | Today's attendance summary |
| `GET` | `/api/leave` | List leave records |
| `POST` | `/api/leave` | Submit leave request |
| `GET` | `/api/reports/daily` | Generate daily report |
| `GET` | `/api/cameras` | List camera assignments |
| `POST` | `/api/cameras/assign` | Assign camera to IN/OUT role |
| `GET` | `/api/video?camera=in` | MJPEG live stream |
| `GET` | `/api/settings` | Get system settings |
| `GET` | `/api/system/status` | System health (CPU, disk, temp) |

---

## RPi5 Deployment Details

### Services

PiFace360 runs as 3 independent systemd services:

| Service | CPU Cores | Memory | Priority | Purpose |
|---------|-----------|--------|----------|---------|
| `piface-engine` | 0-1 | 3 GB | -5 | Face recognition AI loop |
| `piface-web` | 2 | 1 GB | -2 | FastAPI + Nginx |
| `piface-leds` | 3 | 512 MB | -2 | GPIO LED controller |

### Network Topology

```
┌─────────────┐     WiFi (192.168.4.0/24)     ┌──────────────┐
│   Phone /   │ ◄──────────────────────────► │  RPi5        │
│   Laptop    │    SSID: AttendanceSystem     │  192.168.4.1 │
└─────────────┘    Password: (configurable)   └──────────────┘
                                                     │
                    HTTPS :443 ◄─── Nginx ◄─── Uvicorn (unix socket)
                    Captive Portal auto-redirect
```

### Performance (RPi5 8GB)

| Metric | Value |
|--------|-------|
| Face detection latency | ~50ms per frame |
| Recognition accuracy | >97% (InsightFace buffalo_l) |
| Concurrent dashboard users | 10+ |
| Database capacity | 100K+ events |
| Startup time | ~15 seconds |
| Idle power consumption | ~5W |

---

## Troubleshooting

| Issue | Solution |
|-------|---------|
| Camera not detected | Run `ls /dev/video*` -- ensure USB camera is connected |
| Face not recognized | Lower similarity threshold in Settings (default 0.6) |
| WiFi hotspot not visible | Check `sudo systemctl status hostapd` |
| Dashboard not loading | Check `sudo systemctl status piface-web` |
| High CPU temperature | Ensure case has ventilation, check `vcgencmd measure_temp` |
| Database locked | Restart web service: `sudo systemctl restart piface-web` |

---

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## License

This project is licensed under the MIT License.

---

<p align="center">
  Built with edge AI for the real world.<br>
  <strong>PiFace360</strong> -- by <a href="https://github.com/SKULLFIRE07">360</a>
</p>
