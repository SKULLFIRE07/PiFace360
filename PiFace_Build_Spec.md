# 📷 PiFace Attendance System
## Complete Technical Build Specification for Claude Code
**Version 1.0 | Raspberry Pi 5 | Single Camera | Self-Contained | Zero Internet**

---

## Table of Contents
1. [System Overview](#1-system-overview)
2. [Hardware Specification](#2-hardware-specification)
3. [System Architecture](#3-system-architecture)
4. [Database Schema](#4-database-schema)
5. [Face Recognition Engine](#5-face-recognition-engine)
6. [Attendance Logic](#6-attendance-logic)
7. [LED Controller](#7-led-controller)
8. [WiFi Hotspot Configuration](#8-wifi-hotspot-configuration)
9. [Web Dashboard — All Pages](#9-web-dashboard--all-pages)
10. [Backend API Endpoints](#10-backend-api-endpoints)
11. [Auto-Generated Daily Reports](#11-auto-generated-daily-reports)
12. [Pi Setup — install.sh](#12-pi-setup--installsh)
13. [Build Phases for Claude Code](#13-build-phases-for-claude-code)
14. [Critical Rules for Claude Code](#14-critical-rules-for-claude-code)
15. [Complete Dependency Lists](#15-complete-dependency-lists)
16. [Final Build Checklist](#16-final-build-checklist)

---

# 1. System Overview

PiFace is a fully self-contained, AI-powered office attendance monitoring system running entirely on a Raspberry Pi 5. It requires no internet connection, no cloud, no external IT infrastructure, and no technical expertise from the client. The client plugs it in and it works — forever.

## 1.1 What The System Does

- Monitors a single office entrance camera continuously
- Recognises enrolled employees in real-time using InsightFace AI
- Logs every check-in, check-out, lunch-out, and lunch-return with timestamps
- Automatically detects and tracks unknown visitors as `Unknown 1`, `Unknown 2` ... `Unknown N`
- Allows admin to rename any Unknown to a real person — retroactively updating all records
- Broadcasts its own WiFi hotspot so any phone or laptop can access the web dashboard
- Controls two GPIO LEDs — green for entry, red for exit — completely independent of the UI
- Auto-generates daily attendance reports and stores them, available for download anytime
- All three core processes (face engine, web server, LED controller) run independently forever

## 1.2 What The System Does NOT Do

- Does NOT require internet connection at any point
- Does NOT use any cloud service or external API
- Does NOT require client to have any technical knowledge
- Does NOT need a monitor, keyboard, or mouse attached to the Pi
- Does NOT stop working if the web dashboard is closed or nobody is connected

---

# 2. Hardware Specification

## 2.1 Required Components

| Component | Specification | Purpose | Approx Cost (INR) |
|---|---|---|---|
| Raspberry Pi 5 | 8GB RAM model | Main processing unit | ₹8,000 |
| MicroSD Card | 32GB minimum, Class A2 | OS and database storage | ₹800 |
| Pi Power Supply | Official 27W USB-C | Stable power delivery | ₹800 |
| USB Webcam or Pi Camera Module 3 | 1080p minimum, wide angle preferred | Face detection at entrance | ₹1,500 – ₹3,000 |
| Green LED | 5mm standard, 3.3V compatible | Entry confirmed indicator | ₹10 |
| Red LED | 5mm standard, 3.3V compatible | Exit confirmed indicator | ₹10 |
| 2x 220Ω Resistors | Through-hole | LED current limiting | ₹5 |
| Jumper wires | Female-to-male | GPIO connections | ₹50 |
| Small project enclosure | Plastic box, 15x10x5cm | Housing the Pi | ₹300 |

## 2.2 GPIO Wiring

```
Pi 5 GPIO Header:

  PIN 11  (GPIO 17) ──[ 220Ω ]──[ GREEN LED + ]──[ GND (PIN 9)  ]
  PIN 13  (GPIO 27) ──[ 220Ω ]──[ RED LED   + ]──[ GND (PIN 14) ]

Note: Always use resistors. Never connect LED directly to GPIO.
```

## 2.3 Camera Placement

- Mounted at approximately 1.2–1.5 metres height
- Facing the direction of incoming movement for clearest face capture
- Angled slightly downward — approximately 15–20 degrees
- Ensure good lighting on the face side — not backlit from a window

---

# 3. System Architecture

## 3.1 Three Independent Processes

**Process 1 — Face Engine (`core/face_engine.py`)**
- Reads camera feed continuously via OpenCV
- Runs InsightFace detection on every frame
- Compares detected faces against enrolled embeddings in database
- Tracks person movement using frame-by-frame position vectors
- Compares movement to calibrated IN/OUT vectors using cosine similarity
- Writes attendance events to SQLite database
- Fires LED events via a shared event queue
- Runs 24/7 regardless of whether web dashboard is open

**Process 2 — Web Server (`backend/main.py`)**
- FastAPI application serving REST API
- Nginx serves React frontend at `http://192.168.4.1`
- Provides all dashboard endpoints: employees, attendance, reports, settings
- Reads from and writes to the same SQLite database
- Can crash and auto-restart without affecting face engine or LEDs

**Process 3 — LED Controller (`core/led_controller.py`)**
- Listens on a Unix socket / event queue for signals from face engine
- Controls GPIO 17 (green) and GPIO 27 (red) directly via RPi.GPIO
- Executes LED patterns independently — no web dependency
- Handles system boot blink sequence on startup

## 3.2 Data Flow

```
Camera Frame
    │
    ▼
OpenCV (frame grab + resize for performance)
    │
    ▼
InsightFace Detection (is there a face in this frame?)
    │
    ├─ NO FACE → skip frame
    │
    └─ FACE FOUND
           │
           ▼
       Face Matching (compare 512D embedding vs all enrolled)
           │
           ├─ MATCH (similarity > threshold)
           │      │
           │      ▼
           │  Direction Check (cosine similarity vs calibrated vector)
           │      │
           │      ├─ IN  → log CHECK_IN event + fire GREEN LED
           │      └─ OUT → log CHECK_OUT event + fire RED LED
           │
           └─ NO MATCH
                  │
                  ▼
              Assign Unknown N (if new face embedding)
              Save snapshot photo
              Log IN/OUT event under Unknown N
              Fire ALTERNATE LED (green-red blink)
```

## 3.3 Project Directory Structure

```
piface/
├── core/
│   ├── face_engine.py          # InsightFace recognition engine
│   ├── tracker.py              # Movement vector + IN/OUT cosine logic
│   ├── camera.py               # Camera capture + frame management
│   ├── led_controller.py       # GPIO LED control (independent process)
│   └── event_bus.py            # Shared event queue between processes
│
├── backend/
│   ├── main.py                 # FastAPI entry point
│   ├── database.py             # SQLAlchemy setup + SQLite connection
│   ├── models.py               # DB table models
│   ├── schemas.py              # Pydantic request/response schemas
│   └── routes/
│       ├── employees.py        # Add/edit/delete employees
│       ├── attendance.py       # Attendance log endpoints
│       ├── unknowns.py         # Unknown persons + rename
│       ├── reports.py          # Daily/weekly/monthly reports
│       ├── calibration.py      # IN/OUT direction vector endpoints
│       └── settings.py         # System settings
│
├── frontend/                   # React app (built to frontend/dist/)
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Today.jsx       # Live attendance dashboard
│   │   │   ├── Employees.jsx   # Employee management
│   │   │   ├── Unknowns.jsx    # Unknown persons page
│   │   │   ├── Reports.jsx     # Reports + download
│   │   │   ├── Settings.jsx    # Settings page
│   │   │   └── Setup.jsx       # First-time setup wizard
│   │   └── components/
│   │       ├── Calibration.jsx # Arrow drawing on live feed
│   │       └── LiveFeed.jsx    # Camera stream component
│
├── setup/
│   ├── install.sh              # Full Pi setup script (run once)
│   ├── hostapd.conf            # WiFi hotspot configuration
│   ├── dnsmasq.conf            # DHCP + DNS configuration
│   ├── nginx.conf              # Web server configuration
│   ├── piface-engine.service   # systemd: face engine
│   ├── piface-web.service      # systemd: web server
│   └── piface-leds.service     # systemd: LED controller
│
├── database/
│   └── attendance.db           # SQLite database (auto-created)
│
├── reports/                    # Auto-generated daily reports (PDF + Excel)
│   └── YYYY-MM-DD/
│       ├── attendance_YYYY-MM-DD.pdf
│       └── attendance_YYYY-MM-DD.xlsx
│
├── snapshots/                  # Unknown person face snapshots
│
└── models/                     # InsightFace model files (Buffalo_S)
```

---

# 4. Database Schema

## 4.1 `persons` Table

| Column | Type | Description |
|---|---|---|
| id | INTEGER PRIMARY KEY | Auto-increment ID |
| name | TEXT NOT NULL | Full name (or 'Unknown N' if unidentified) |
| employee_id | TEXT UNIQUE | Employee ID (NULL for unknowns) |
| department | TEXT | Department name |
| job_title | TEXT | Job title / designation |
| phone | TEXT | Phone number (optional) |
| face_embedding | BLOB NOT NULL | 512D float array — InsightFace embedding |
| face_image | TEXT | Path to enrollment face snapshot |
| is_unknown | BOOLEAN DEFAULT FALSE | True if auto-assigned Unknown N |
| unknown_index | INTEGER | N value for Unknown N (NULL if named) |
| enrolled_at | DATETIME | Enrollment timestamp |
| is_active | BOOLEAN DEFAULT TRUE | Soft delete flag |

## 4.2 `attendance_events` Table

| Column | Type | Description |
|---|---|---|
| id | INTEGER PRIMARY KEY | Auto-increment |
| person_id | INTEGER FK → persons.id | Who was detected |
| event_type | TEXT | CHECK_IN / CHECK_OUT / LUNCH_OUT / LUNCH_IN |
| timestamp | DATETIME NOT NULL | Exact time of event |
| confidence | REAL | Face match confidence score (0.0 – 1.0) |
| snapshot_path | TEXT | Path to face snapshot at time of detection |
| direction_vector | TEXT | JSON [dx,dy] — movement vector at detection |
| date | DATE | Date of event (for fast daily queries) |

## 4.3 `daily_summary` Table

| Column | Type | Description |
|---|---|---|
| id | INTEGER PRIMARY KEY | Auto-increment |
| person_id | INTEGER FK → persons.id | Employee reference |
| date | DATE NOT NULL | Date of summary |
| check_in_time | DATETIME | First entry of day |
| check_out_time | DATETIME | Last exit of day |
| lunch_out_time | DATETIME | Lunch departure |
| lunch_in_time | DATETIME | Lunch return |
| total_hours_worked | REAL | Total hours (check-out minus check-in minus lunch) |
| lunch_duration_minutes | INTEGER | Lunch duration in minutes |
| is_late | BOOLEAN | Arrived after configured shift start |
| is_early_leave | BOOLEAN | Left before configured shift end |
| overtime_minutes | INTEGER | Minutes worked beyond shift end |
| status | TEXT | PRESENT / ABSENT / HALF_DAY |

## 4.4 `system_settings` Table

| Column | Type | Description |
|---|---|---|
| key | TEXT PRIMARY KEY | Setting key |
| value | TEXT | Setting value (JSON serialised) |
| updated_at | DATETIME | Last modified time |

**Settings keys stored:**
`company_name`, `shift_start`, `shift_end`, `late_threshold_minutes`, `lunch_duration_limit_minutes`, `wifi_ssid`, `wifi_password`, `admin_username`, `admin_password_hash`, `in_vector`, `out_vector`, `setup_complete`, `unknown_counter`

---

# 5. Face Recognition Engine

## 5.1 Model

- **Library:** InsightFace (`pip install insightface`)
- **Model:** Buffalo_S — optimised for ARM64, best speed/accuracy on Pi 5
- **Embedding size:** 512 dimensions per face
- **Detection backend:** RetinaFace
- **Recognition backend:** ArcFace
- **Matching:** Cosine similarity — threshold 0.5 (configurable in settings)

## 5.2 Enrollment Process

```
If VIDEO uploaded:
  1. Extract all frames with OpenCV
  2. For each frame, run blur detection (Laplacian variance)
  3. Keep top 15 sharpest frames that contain a face
  4. Run InsightFace on each kept frame
  5. Generate 512D embedding for each
  6. Average all embeddings → single enrollment embedding
  7. This averaged embedding is much more robust than a single photo

If PHOTO uploaded:
  1. Run InsightFace directly on photo
  2. Generate single 512D embedding
  3. Store as enrollment embedding

Store embedding as BLOB in persons.face_embedding
Store best frame as face_image path
```

## 5.3 Real-Time Recognition

```
Every frame from camera:
  1. Resize to 640x480 for performance
  2. InsightFace.get() → returns list of detected faces
  3. For each detected face:
     a. Extract 512D embedding
     b. Load all enrolled embeddings from DB (cached in memory, refreshed every 30s)
     c. Compute cosine similarity against all
     d. Best match above 0.5 threshold → KNOWN person
     e. No match above threshold → UNKNOWN
  4. For known person: run direction check (Section 5.4)
  5. For unknown: run unknown handling (Section 5.5)
```

## 5.4 IN/OUT Direction Detection — Cosine Vector Method

This is the core directional logic. Admin draws arrows once during setup. System stores the vectors permanently.

```
Admin draws IN arrow:  point A(x1,y1) → point B(x2,y2)
Stored as IN vector:   [x2-x1, y2-y1]  e.g. [300, 20]

Admin draws OUT arrow: point C(x3,y3) → point D(x4,y4)
Stored as OUT vector:  [x4-x3, y4-y3]  e.g. [-300, -20]

Person tracking per detection:
  - Track person centroid across 5-10 consecutive frames
  - Compute movement vector: [last_x - first_x, last_y - first_y]
  - Cosine similarity with IN vector  → in_score
  - Cosine similarity with OUT vector → out_score
  - in_score  > 0.7 → log as IN event
  - out_score > 0.7 → log as OUT event
  - Neither above 0.7 → person is stationary, no event logged
  - Cooldown: same person cannot trigger another event for 60 seconds
```

**Cosine similarity formula:**
```
similarity = dot(person_vector, calibrated_vector)
           / (magnitude(person_vector) * magnitude(calibrated_vector))

Result range: -1.0 to +1.0
  1.0  = exactly same direction as arrow
  0.0  = perpendicular
 -1.0  = exactly opposite direction

Threshold 0.7 means person must be moving within ±45° of arrow direction
```

## 5.5 Unknown Person Handling

```
Face detected, no match above threshold:

1. Check if this embedding matches any existing unknown
   (in case same unknown was seen before)
   → If matches unknown with similarity > 0.45 → same unknown, continue tracking

2. If truly new face:
   → Increment unknown_counter in settings
   → Create persons record: name='Unknown N', is_unknown=TRUE, unknown_index=N
   → Save face snapshot to snapshots/unknown_N_timestamp.jpg
   → Begin tracking this person

3. Log their IN/OUT events same as known employees

Admin renames Unknown N:
   → UPDATE persons SET name='Real Name', is_unknown=FALSE,
      employee_id=..., department=..., job_title=...
   → All past attendance_events for that person_id now show real name
   → All future detections recognise them as real name
   → No data is lost or duplicated
```

---

# 6. Attendance Logic

## 6.1 Event Type Decision

```
On every IN detection for a person on a given day:

  No events today yet           → event_type = CHECK_IN
  CHECK_IN exists, no LUNCH_OUT → person was in, skip (already IN)
  LUNCH_OUT exists, no LUNCH_IN → event_type = LUNCH_IN
  LUNCH_IN exists               → no new event (already back)

On every OUT detection for a person on a given day:

  No CHECK_IN today             → ignore (tail-end from yesterday)
  CHECK_IN exists, no LUNCH_OUT → event_type = LUNCH_OUT
  LUNCH_IN exists               → event_type = CHECK_OUT
  CHECK_OUT already exists      → ignore (already logged out)
```

## 6.2 Daily Summary Computation

Runs automatically at midnight every day via a scheduled background task:

```
For each person with events today:

  check_in_time    = earliest CHECK_IN event timestamp
  check_out_time   = latest CHECK_OUT event timestamp
  lunch_out_time   = LUNCH_OUT event timestamp
  lunch_in_time    = LUNCH_IN event timestamp

  lunch_duration   = lunch_in_time - lunch_out_time (if both exist)

  total_hours      = (check_out_time - check_in_time) - lunch_duration
                     (if no check_out yet, total_hours = NULL = still 'IN')

  is_late          = check_in_time > (shift_start + late_threshold_minutes)
  is_early_leave   = check_out_time < shift_end
  overtime_minutes = max(0, check_out_time - shift_end) in minutes

  status = PRESENT  (if check_in exists)
           ABSENT   (if no events at all)
           HALF_DAY (if total_hours < shift_hours / 2)

  INSERT or REPLACE INTO daily_summary
```

## 6.3 Anti-Duplicate Logic

- **60-second cooldown** per person — same person cannot log another event within 60 seconds
- **State machine** per person per day — prevents illogical event sequences (e.g. LUNCH_IN without LUNCH_OUT)
- **Minimum movement distance** — face must have moved at least 50px across tracked frames to trigger direction check
- **Confidence minimum** — only face matches above 0.5 cosine similarity trigger events

---

# 7. LED Controller

## 7.1 LED Patterns — Full Reference

| Event | Pattern | Duration | GPIO |
|---|---|---|---|
| System boot complete | 5 rapid green blinks | 2 seconds total | GPIO 17 (green) |
| Known person — CHECK IN | Green solid ON | 3 seconds | GPIO 17 (green) |
| Known person — LUNCH IN | Green solid ON | 3 seconds | GPIO 17 (green) |
| Known person — CHECK OUT | Red solid ON | 3 seconds | GPIO 27 (red) |
| Known person — LUNCH OUT | Red solid ON | 3 seconds | GPIO 27 (red) |
| Unknown person detected | Green-Red alternate blink | 2 seconds | Both |
| Camera disconnected | Red slow blink (every 2s) | Continuous until fixed | GPIO 27 (red) |
| System error / crash | Red double blink (every 3s) | Continuous until fixed | GPIO 27 (red) |
| Face engine starting up | Both LEDs on steady | During startup only | Both |

## 7.2 Independence Guarantee

The LED controller process must be designed such that:
- It starts **before** the web server and face engine
- It runs its boot sequence (5 green blinks) independently from any other process
- It receives events from the face engine via a **Unix domain socket — not HTTP**
- It continues blinking camera-error pattern if it receives no heartbeat from face engine for 30 seconds
- It survives web server crashes entirely — zero dependency on FastAPI

---

# 8. WiFi Hotspot Configuration

## 8.1 Stack

- **hostapd** — creates and manages the WiFi access point
- **dnsmasq** — DHCP server (assigns IPs to connecting devices) + DNS resolver
- **Nginx** — serves React frontend at `192.168.4.1:80`
- **Avahi** — optional mDNS so `attendance.local` also works on some devices

## 8.2 Network Details

| Setting | Value | Notes |
|---|---|---|
| WiFi SSID | AttendanceSystem (default) | Admin can change in Settings |
| WiFi Password | Set during first-time wizard | Pre-printed sticker on Pi box |
| Pi static IP | 192.168.4.1 | Never changes — hardcoded |
| DHCP range | 192.168.4.2 – 192.168.4.20 | Supports up to 19 connected devices |
| Web UI URL | http://192.168.4.1 | Works on any browser |
| DNS redirect | Any domain → 192.168.4.1 | Captive portal — any URL opens dashboard |
| WiFi band | 2.4 GHz | Maximum device compatibility |
| Max connections | 20 simultaneous devices | Pi 5 WiFi chip capability |

## 8.3 `hostapd.conf`

```ini
interface=wlan0
driver=nl80211
ssid=AttendanceSystem
hw_mode=g
channel=6
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=CHANGE_ON_SETUP
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
```

## 8.4 `dnsmasq.conf`

```ini
interface=wlan0
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
domain=local
address=/#/192.168.4.1
# The address=/#/ line redirects ALL DNS to 192.168.4.1
# This acts as a captive portal — any URL typed opens the dashboard
```

## 8.5 Dual Mode (Hotspot + Office WiFi)

Admin can switch between two modes in Settings:
- **Hotspot Mode (default)** — Pi broadcasts its own WiFi, no internet, fully isolated
- **Bridge Mode** — Pi joins existing office WiFi AND still serves dashboard at its IP

Mode switching is handled by the Settings page calling a backend endpoint that rewrites config files and restarts networking services. No terminal access needed.

---

# 9. Web Dashboard — All Pages

## 9.1 First-Time Setup Wizard *(shown only once)*

Triggered when `setup_complete = false` in settings. Wizard steps:

- **Step 1 — Company Info:** company name, admin username, admin password
- **Step 2 — Working Hours:** shift start time, shift end time, late arrival threshold, max lunch duration
- **Step 3 — Direction Calibration:** live camera feed shown, admin draws IN arrow and OUT arrow by click-dragging directly on the live feed
- **Step 4 — Completion:** `system_settings.setup_complete = true`, redirect to Today page

## 9.2 Today Page

- Live list of all enrolled employees with current status:
  - 🟢 Green dot `IN` — currently in office
  - 🟡 Yellow dot `At Lunch` — LUNCH_OUT logged, LUNCH_IN not yet
  - ⚫ Grey dot `OUT` — checked out for the day
  - 🔴 Red dot `Not Arrived` — no events today, expected in
- Shows today's check-in time, lunch duration, hours worked so far
- Live camera feed widget (MJPEG stream with face boxes + name labels overlaid)
- Last event ticker — scrolling feed of recent IN/OUT events

## 9.3 Attendance Log Page

- Full event history across all employees
- Filters: by person name, date range, department, event type
- Table columns: Person, Department, Event Type, Timestamp, Confidence, Duration
- Expandable row — shows face snapshot thumbnail at time of detection

## 9.4 Employees Page

- Card grid of all enrolled employees with face photo, name, department, job title
- **Add Employee** button → opens modal:
  - Upload photo or 5-second video
  - Fields: Full Name, Employee ID, Department, Job Title, Phone
  - System processes enrollment in background, shows progress bar
- **Edit Employee** — update any field, re-enroll face if needed
- **Delete Employee** — soft delete, records preserved for history
- Click any employee → individual attendance history page with calendar view

## 9.5 Unknowns Page

- Grid of all Unknown N persons with their auto-captured face snapshot
- Shows: number of visits, first seen, last seen, total time in office
- **Rename button** → modal to enter real name, employee ID, department, job title
- On save: persons record updated, all past events retroactively renamed
- Unknown who is never renamed stays as Unknown N forever, still fully tracked

## 9.6 Reports Page

- Date range picker — select any day, week, or month
- Summary table: employee, days present, total hours, avg arrival time, late days, absences
- Per-employee drill-down: full daily breakdown for selected period
- Daily reports: auto-generated every midnight, stored in `reports/YYYY-MM-DD/`
- **Download buttons:**
  - Download as Excel (`.xlsx`) — full formatted spreadsheet
  - Download as PDF — printable formatted report
  - Download Today's Report — partial same-day report on demand
- Report history: list of all past auto-generated reports with download links

## 9.7 Settings Page

- **Company Info** — edit company name
- **Working Hours** — shift start, shift end, late threshold, lunch limit
- **Direction Calibration** — recalibrate IN/OUT arrows on live feed anytime
- **WiFi Settings** — change SSID and password, switch hotspot/bridge mode
- **Admin Password** — change admin credentials
- **Face Recognition** — adjust similarity threshold (0.3–0.8 slider)
- **System Status** — shows uptime, DB size, camera status, last detection time
- **Restart Services** — restart face engine or web server from UI
- **Factory Reset** — clears all data and returns to setup wizard

---

# 10. Backend API Endpoints

## 10.1 Employee Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/employees` | List all active employees |
| POST | `/api/employees` | Enroll new employee (multipart: photo/video + metadata) |
| GET | `/api/employees/{id}` | Get single employee + their attendance stats |
| PUT | `/api/employees/{id}` | Update employee details |
| DELETE | `/api/employees/{id}` | Soft-delete employee |
| GET | `/api/employees/{id}/history` | Full attendance history for employee |
| POST | `/api/employees/{id}/reenroll` | Re-enroll face for existing employee |

## 10.2 Attendance Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/attendance/today` | All events today with current status per person |
| GET | `/api/attendance/events` | Paginated event log (filters: person_id, date, type) |
| GET | `/api/attendance/summary` | Daily summaries (filters: date_from, date_to, person_id) |
| GET | `/api/attendance/live` | SSE stream of real-time detection events for live feed |

## 10.3 Unknown Persons Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/unknowns` | List all unknown persons with stats |
| PUT | `/api/unknowns/{id}/rename` | Rename unknown — provide full person details |
| DELETE | `/api/unknowns/{id}` | Remove unknown person record |

## 10.4 Reports Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/reports/daily/{date}` | Get or generate report for specific date |
| GET | `/api/reports/history` | List all stored auto-generated report files |
| GET | `/api/reports/download/{date}/excel` | Download Excel report for date |
| GET | `/api/reports/download/{date}/pdf` | Download PDF report for date |
| POST | `/api/reports/generate` | Manually trigger report generation for any date |

## 10.5 System Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/settings` | Get all system settings |
| PUT | `/api/settings` | Update settings |
| POST | `/api/calibration/set` | Save IN/OUT direction vectors from arrow drawing |
| GET | `/api/calibration/get` | Get current calibration vectors |
| GET | `/api/stream/video` | MJPEG camera stream with face overlay for live feed |
| GET | `/api/system/status` | Camera status, DB size, uptime, last detection |
| POST | `/api/system/restart/{service}` | Restart face engine or LED controller |
| POST | `/api/auth/login` | Admin login — returns JWT token |
| POST | `/api/auth/logout` | Invalidate session |

---

# 11. Auto-Generated Daily Reports

## 11.1 Auto-Generation Schedule

- Every day at `23:59:00` a background task triggers report generation for that day
- Report saved to `reports/YYYY-MM-DD/attendance_YYYY-MM-DD.xlsx` and `.pdf`
- If device was off at midnight, report generates on next boot for any missing days
- Reports are cumulative and never deleted — full archive always available

## 11.2 Excel Report Contents

Generated using `openpyxl`. Contains these sheets:
- **Sheet 1 — Summary:** one row per employee with totals for the day
- **Sheet 2 — Full Log:** every IN/OUT event with timestamps
- **Sheet 3 — Unknowns:** any unknown visitors that day
- Formatting: company name header, date, colour-coded late/absent rows

## 11.3 PDF Report Contents

Generated using `reportlab`. Contains:
- Header: company name, date, generated-at timestamp
- Summary table: employee name, check-in, check-out, lunch duration, total hours, status
- Colour coding: red = absent/late, green = on time, yellow = half day
- Footer: total present, total absent, average hours worked
- Page numbers and auto-pagination for large teams

## 11.4 On-Demand Download

- Any past report can be downloaded any time from Reports page
- Current day report can be generated on demand (partial data for the day so far)
- Both Excel and PDF always available for every stored report

---

# 12. Pi Setup — `install.sh`

This script is run **once** on a fresh Raspberry Pi OS (64-bit, Bookworm) install. It sets up everything automatically. The client never runs this — it is run before shipping the device.

## 12.1 Script Steps in Order

```bash
1.  System update: apt update && apt upgrade -y

2.  Install system packages:
      hostapd dnsmasq nginx python3-pip python3-venv
      libcamera-apps ffmpeg libopenblas-dev nodejs npm git

3.  Configure static IP for wlan0 in /etc/dhcpcd.conf

4.  Write hostapd.conf with default SSID

5.  Write dnsmasq.conf with DHCP range and DNS redirect

6.  Enable hostapd and dnsmasq services

7.  Create Python virtual environment at /opt/piface/venv

8.  Install Python dependencies:
      insightface onnxruntime opencv-python-headless
      fastapi uvicorn sqlalchemy pydantic
      RPi.GPIO pandas openpyxl reportlab pillow

9.  Download InsightFace Buffalo_S model files to models/

10. Build React frontend: npm install && npm run build

11. Configure Nginx to serve frontend at 192.168.4.1

12. Install systemd service files for all 3 processes

13. Enable all services:
      systemctl enable piface-engine piface-web piface-leds

14. Set system timezone to Asia/Kolkata (or configurable)

15. Configure Pi to boot to CLI (no desktop needed)

16. Reboot
```

## 12.2 systemd Service Files

```ini
# piface-leds.service
[Unit]
Description=PiFace LED Controller
After=multi-user.target

[Service]
ExecStart=/opt/piface/venv/bin/python /opt/piface/core/led_controller.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target

# ---

# piface-engine.service
[Unit]
Description=PiFace Face Engine
After=piface-leds.service

[Service]
ExecStart=/opt/piface/venv/bin/python /opt/piface/core/face_engine.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target

# ---

# piface-web.service
[Unit]
Description=PiFace Web Server
After=piface-engine.service

[Service]
ExecStart=/opt/piface/venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

---

# 13. Build Phases for Claude Code

Build in this exact order. Each phase is independently testable before moving to the next.

## Phase 1 — Core Infrastructure
- `setup/install.sh` — full Pi setup script
- `setup/hostapd.conf` and `dnsmasq.conf`
- `setup/nginx.conf`
- `setup/*.service` files for all three processes
- `database.py` — SQLAlchemy setup, all table models
- `backend/main.py` — FastAPI skeleton with CORS and auth middleware
- `core/led_controller.py` — GPIO control, boot sequence, event listener

## Phase 2 — Face Engine
- `core/camera.py` — OpenCV camera capture, frame resize, MJPEG encode
- `core/face_engine.py` — InsightFace init, enrollment processing, real-time recognition
- `core/tracker.py` — centroid tracking, cosine similarity direction detection, cooldown logic
- `core/event_bus.py` — Unix socket event queue between processes
- `backend/routes/employees.py` — enrollment endpoints (photo + video upload)
- `backend/routes/attendance.py` — event logging, today summary, SSE live stream

## Phase 3 — Unknown Person System
- Unknown detection and auto-naming logic in `face_engine.py`
- Snapshot saving to `snapshots/` directory
- `backend/routes/unknowns.py` — list, rename, delete endpoints
- Rename logic — retroactive update of all `attendance_events`

## Phase 4 — Web Dashboard
- React app scaffold with routing and auth context
- `Setup.jsx` — first-time wizard with calibration step
- `Calibration.jsx` — live feed with arrow drawing (SVG overlay on MJPEG)
- `Today.jsx` — live status dashboard
- `Employees.jsx` — enrollment, edit, delete
- `Unknowns.jsx` — unknown grid, rename modal
- `AttendanceLog.jsx` — filtered event log
- `Settings.jsx` — all system settings

## Phase 5 — Reports
- `core/report_generator.py` — Excel and PDF generation with openpyxl and reportlab
- Daily midnight scheduler using APScheduler
- `backend/routes/reports.py` — history, download, on-demand generation
- `Reports.jsx` — date picker, summary, download buttons, report history list

## Phase 6 — Polish & Hardening
- Missing-day report backfill on boot
- Face engine embedding cache refresh every 30 seconds
- Camera watchdog — detect disconnection and trigger LED error pattern
- JWT authentication on all API endpoints
- WiFi mode switching (hotspot ↔ bridge) from Settings page
- Factory reset endpoint
- System status endpoint with uptime, camera health, DB size

---

# 14. Critical Rules for Claude Code

## 🔴 Must Follow — No Exceptions

1. Never use cloud APIs, external services, or internet calls anywhere in the codebase
2. All three processes (face engine, web server, LED controller) must be completely independent
3. LED controller must work even if web server and face engine are both down
4. Face engine must work even if web server is down (logs to DB directly)
5. SQLite is the only database — never introduce Postgres, Redis, or any other DB
6. All Python must run in `/opt/piface/venv` virtual environment
7. All paths must be absolute — never relative paths in production code
8. Face embeddings must be cached in memory in face engine — never query DB per frame
9. Camera stream for web UI must be MJPEG over HTTP — no WebRTC, no WebSockets for video
10. Admin password must be stored as bcrypt hash — never plaintext

## 🟡 Architecture Decisions — Do Not Change

1. InsightFace Buffalo_S model — do not substitute with another model
2. Cosine similarity for direction detection — no angle/degree calculations
3. Unix socket for LED event bus — not HTTP, not Redis pub/sub
4. APScheduler for midnight report generation — not cron, not celery
5. MJPEG stream endpoint for live video — keep it simple
6. openpyxl for Excel, reportlab for PDF — no other libraries
7. React frontend served by Nginx — not by FastAPI
8. hostapd + dnsmasq for hotspot — no NetworkManager approach
9. systemd for process management — not supervisord, not PM2
10. JWT stored in httpOnly cookie — not localStorage

## 🟢 Quality Standards

1. All API endpoints return consistent JSON: `{success: bool, data: any, error: string|null}`
2. All database operations wrapped in try/except with proper rollback
3. Face engine logs to `/var/log/piface/engine.log` with rotation
4. LED patterns must be non-blocking — use `threading.Timer`, never `time.sleep` on main thread
5. Enrollment video processing must show progress to frontend via SSE or polling endpoint
6. Unknown counter must be atomic — use DB-level increment, not application-level
7. Calibration vectors stored as JSON in system_settings — both IN and OUT required before engine starts tracking
8. React components must handle loading, error, and empty states for every data fetch
9. All file uploads (photos/videos) must validate MIME type and file size before processing
10. Setup wizard must be impossible to skip — middleware checks `setup_complete` on every request

---

# 15. Complete Dependency Lists

## 15.1 Python `requirements.txt`

```txt
# Face Recognition
insightface==0.7.3
onnxruntime==1.16.3
opencv-python-headless==4.8.1.78

# Web Framework
fastapi==0.104.1
uvicorn[standard]==0.24.0
python-multipart==0.0.6
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4

# Database
sqlalchemy==2.0.23

# GPIO
RPi.GPIO==0.7.1

# Reports
pandas==2.1.3
openpyxl==3.1.2
reportlab==4.0.7
Pillow==10.1.0

# Scheduling
APScheduler==3.10.4

# Utilities
numpy==1.26.2
pydantic==2.5.2
python-dotenv==1.0.0
```

## 15.2 Frontend `package.json`

```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.20.0",
    "axios": "^1.6.2",
    "date-fns": "^2.30.0",
    "@tanstack/react-query": "^5.8.4",
    "lucide-react": "^0.294.0",
    "recharts": "^2.10.1"
  },
  "devDependencies": {
    "vite": "^5.0.0",
    "tailwindcss": "^3.3.5",
    "@vitejs/plugin-react": "^4.2.0"
  }
}
```

---

# 16. Final Build Checklist

Use this to verify the complete system before delivery to client:

| # | Check | How to Verify |
|---|---|---|
| 1 | Pi boots and hotspot appears within 30 seconds | Connect to AttendanceSystem WiFi |
| 2 | 5 green LED blinks on boot | Watch LEDs on power-on |
| 3 | Browser to 192.168.4.1 loads Setup Wizard on first boot | Test with fresh SD card |
| 4 | Setup wizard completes and redirects to Today page | Complete all 4 wizard steps |
| 5 | Calibration arrow drawing works on live feed | Draw IN and OUT arrows, save, confirm vectors stored |
| 6 | Employee enrollment with video works | Upload 5s video, fill details, confirm face recognized |
| 7 | Employee enrollment with photo works | Upload single photo, confirm face recognized |
| 8 | Known employee triggers green LED on CHECK IN | Walk toward camera after calibration |
| 9 | Known employee triggers red LED on CHECK OUT | Walk away from camera |
| 10 | Unknown person auto-named Unknown 1 | Walk unknown person past camera |
| 11 | Unknown renamed → all past records updated | Rename from Unknowns page, check log |
| 12 | Today page shows live status correctly | Verify IN/OUT status matches events |
| 13 | Reports page downloads Excel file | Click Download Excel for today |
| 14 | Reports page downloads PDF file | Click Download PDF for today |
| 15 | Daily report auto-generates at midnight | Wait for midnight or manually trigger |
| 16 | Past reports available in report history | Check Reports > History |
| 17 | Settings page saves and applies changes | Change shift time, verify late detection updates |
| 18 | WiFi SSID/password change works | Change SSID, reconnect with new name |
| 19 | Camera disconnection triggers red slow blink | Unplug camera, watch LED |
| 20 | All 3 processes restart automatically after kill | Kill each process, verify systemd restarts it |

---

*PiFace Attendance System — Build Specification v1.0*
*One Pi. One Camera. Two LEDs. Zero Internet. Runs Forever.*
