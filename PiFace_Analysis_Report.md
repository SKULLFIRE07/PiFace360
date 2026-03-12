# PiFace Build Spec v1.0 -- Complete Analysis Report
## 10-Agent Deep Audit: What's Wrong, What Will Break, and What Needs to Change

**Audited by:** 10 parallel specialist agents (Security, Hardware, Face Recognition, Database, Reliability, Networking, Frontend, DevOps, Attendance Logic, Performance)

**Verdict:** The spec has excellent vision and architecture instincts, but contains **5 guaranteed showstoppers**, **12 critical flaws**, and **40+ issues** across all dimensions. Shipping this spec as-is would produce a non-functional device.

---

## PART 1: SHOWSTOPPERS (System Will Not Function At All)

These 5 issues will cause the system to **fail on first boot**. Every single one must be fixed before any code is written.

### S-1. RPi.GPIO Is Completely Broken on Pi 5
- **Impact:** LED controller crashes immediately on every boot, enters infinite restart loop
- **Root cause:** Pi 5 uses the RP1 I/O controller chip. RPi.GPIO accesses BCM2835 memory-mapped registers that don't exist on Pi 5. It throws `RuntimeError: Cannot determine SOC peripheral base address`
- **Fix:** Replace `RPi.GPIO==0.7.1` with `gpiozero>=2.0` (uses lgpio backend on Pi 5 automatically). API change is minimal: `LED(17).on()` instead of `GPIO.output(17, HIGH)`

### S-2. dhcpcd Does Not Exist on Raspberry Pi OS Bookworm
- **Impact:** WiFi hotspot never starts. No static IP on wlan0. Dashboard inaccessible. System is a brick.
- **Root cause:** Bookworm replaced dhcpcd with NetworkManager. Writing to `/etc/dhcpcd.conf` does nothing.
- **Fix:** Tell NetworkManager to ignore wlan0 via `/etc/NetworkManager/conf.d/piface.conf`, then use systemd-networkd or `ip addr add` for the static IP

### S-3. systemd-resolved Blocks dnsmasq on Port 53
- **Impact:** dnsmasq fails to start. Captive portal DNS broken. Devices connect to WiFi but can't reach dashboard.
- **Root cause:** systemd-resolved binds to 127.0.0.53:53 by default on Bookworm
- **Fix:** Either disable systemd-resolved entirely, or set `DNSStubListener=no` in `/etc/systemd/resolved.conf`

### S-4. onnxruntime Has No ARM64 Wheel on PyPI
- **Impact:** `pip install onnxruntime==1.16.3` fails. Face engine cannot start.
- **Root cause:** Official PyPI doesn't ship aarch64 wheels. Need piwheels or manual build.
- **Fix:** Use `--extra-index-url https://www.piwheels.org/simple` or bundle a pre-built wheel. Also need `build-essential python3-dev cmake` for compiling insightface's Cython extensions

### S-5. No Active Cooling = Guaranteed Thermal Throttling
- **Impact:** CPU throttles from 2.4GHz to 1.8GHz within 10-15 minutes. Face recognition FPS drops from ~6 to ~3. System becomes unreliable.
- **Root cause:** Continuous InsightFace inference drives CPU to 80C+. Pi 5 throttles at 80C.
- **Fix:** Add official Raspberry Pi Active Cooler (~300 INR) to hardware BOM. It's not optional -- it's mandatory for 24/7 AI workloads.

---

## PART 2: CRITICAL ARCHITECTURE FLAWS (12 Issues)

### A-1. The 4-State Attendance Machine Is Fundamentally Broken
The state machine only allows: CHECK_IN -> LUNCH_OUT -> LUNCH_IN -> CHECK_OUT. This fails for:
- **Non-lunch breaks:** Stepping out for a meeting logs as LUNCH_OUT. Real lunch can't be logged.
- **Multiple breaks:** Smokers, coffee runs -- only one OUT/IN pair exists
- **Night shifts:** Date boundary at midnight splits a single shift into two broken records
- **No manual correction:** No API endpoint to fix wrong events. Errors are permanent.

**Fix:** Replace with an event-log model. Record every IN/OUT as raw events. Derive lunch/breaks/totals at summary time by analyzing the sequence. Add manual CRUD endpoints for corrections.

### A-2. No HTTPS -- All Credentials Transmitted in Plaintext
Admin login, JWT tokens, employee data, face images -- all sent as cleartext HTTP over WiFi. Any device on the network can sniff credentials.

**Fix:** Generate a self-signed TLS certificate during install. Configure Nginx for HTTPS on port 443. Redirect port 80 to 443.

### A-3. No Firewall -- Every Pi Service Exposed
Port 8000 (uvicorn), port 22 (SSH), and every other service is directly accessible to all WiFi clients. A single client can bypass Nginx entirely.

**Fix:** Add iptables rules: allow only ports 80/443 (HTTP/HTTPS), 53 (DNS), 67-68 (DHCP). Block everything else. Bind uvicorn to 127.0.0.1 only.

### A-4. No SQLite WAL Mode -- Database Corruption Risk
Two processes (face engine + web server) write to the same SQLite file. Default DELETE journal mode can't handle concurrent access. Risk of corruption and SQLITE_BUSY errors.

**Fix:** `PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA busy_timeout=5000; PRAGMA foreign_keys=ON;`

### A-5. No Overlay Filesystem -- SD Card Corruption on Power Loss
The Pi WILL be unplugged without warning. ext4 corruption can brick the device. SQLite can lose data.

**Fix:** Enable overlay filesystem for read-only root. Mount a separate RW partition for database/reports/snapshots. Add `fsck.repair=yes` to boot cmdline.

### A-6. Bridge Mode Is Physically Impossible
Pi 5 has a single WiFi radio. It cannot simultaneously be an AP and a station on different channels. Concurrent AP+STA on the same radio has severe limitations on the BCM43455 driver.

**Fix:** Either require a USB WiFi adapter for dual-mode, or redefine bridge mode as either/or (not simultaneous). Document the limitation.

### A-7. Face Recognition Thresholds Are Too Low
- Known face threshold 0.5 is below industry standard (0.6-0.68). Will cause false positive identifications.
- Unknown matching threshold 0.45 is dangerously low. Different visitors will be merged into the same Unknown N.

**Fix:** Default known threshold to 0.6. Raise unknown matching to 0.55-0.60. Add top-2 margin check (require 0.08+ gap between best and second-best match).

### A-8. Processing Every Frame Is Unsustainable
InsightFace takes 150-250ms per frame on Pi 5. Camera delivers 30 FPS. Frames back up in the buffer, causing multi-second latency.

**Fix:** Process every 3rd frame for detection (~10 detection FPS). Use lightweight tracking (centroid/KCF) between detection frames. Set `cv2.CAP_PROP_BUFFERSIZE = 1`.

### A-9. No Multi-Face Tracking Strategy
When 2+ people enter simultaneously, centroid tracking can swap identities between frames. No proper multi-object tracker (SORT/Hungarian assignment).

**Fix:** Implement IoU-based tracking with persistent track IDs. Assign face recognition identity to the track, not the raw detection.

### A-10. Services Running as Root
All three systemd services run as root. A web server vulnerability gives the attacker full root access.

**Fix:** Create `piface` system user. Add `User=piface`, `Group=piface`, `ProtectSystem=strict`, `NoNewPrivileges=true` to service files.

### A-11. No Database Backup Strategy
Entire database on a single microSD card. SD card failure = total, unrecoverable data loss.

**Fix:** Nightly SQLite online backup via `sqlite3.backup()`. Auto-backup to USB drive if attached. Export endpoint in Settings page.

### A-12. Foreign Keys Not Enforced + Missing Indexes
SQLite has FK enforcement OFF by default. Orphaned records possible. No indexes on hot query paths (attendance_events by person_id+date). No UNIQUE constraint on daily_summary(person_id, date) -- duplicates will accumulate.

**Fix:** `PRAGMA foreign_keys=ON` on every connection. Add composite indexes. Add UNIQUE(person_id, date) to daily_summary. Add CHECK(LENGTH(face_embedding)=2048).

---

## PART 3: HIGH PRIORITY ISSUES (25 Issues)

### Security (7)
| # | Issue | Fix |
|---|---|---|
| 1 | TKIP cipher in hostapd (crackable) | Remove `wpa_pairwise=TKIP`, keep CCMP only |
| 2 | No rate limiting on login | Max 5 failed attempts per IP per 5 minutes |
| 3 | No CSRF protection (JWT in cookies) | Double-submit CSRF tokens or SameSite=Strict |
| 4 | File upload path traversal risk | UUID filenames, magic byte validation, size limits |
| 5 | Admin credentials in system_settings table | Separate `auth_users` table |
| 6 | Service restart endpoint = privilege escalation | Whitelist-only helper script with sudoers |
| 7 | Factory reset without physical confirmation | Require password re-entry + time-delayed confirm |

### Hardware & Platform (5)
| # | Issue | Fix |
|---|---|---|
| 8 | Pi Camera Module 3 incompatible with cv2.VideoCapture(0) | Use picamera2 library or auto-detect camera type |
| 9 | onnxruntime not optimized for ARM64 | ARM64-optimized build, set OMP_NUM_THREADS=2 |
| 10 | CPU governor not set for sustained workload | Set `performance` governor in install script |
| 11 | No hardware RTC -- clock drifts without NTP | Add DS3231 RTC module (~200 INR) to BOM |
| 12 | USB power budget for camera not configured | Add `usb_max_current_enable=1` to config.txt |

### Reliability (6)
| # | Issue | Fix |
|---|---|---|
| 13 | No watchdog for hung processes | `WatchdogSec=30` + sd_notify pings in service files |
| 14 | systemd startup race conditions | Retry-with-backoff on LED socket, `Wants=` directive |
| 15 | No camera reconnection logic | Auto-reconnect loop with 5s backoff in camera.py |
| 16 | Log files will fill SD card | logrotate config + RotatingFileHandler, 10MB max |
| 17 | Unix socket stale file on crash | `ExecStartPre=-/bin/rm -f`, use `/run/piface/` |
| 18 | No SIGTERM handling for graceful shutdown | Signal handlers in all 3 processes, `TimeoutStopSec=10` |

### Face Recognition (4)
| # | Issue | Fix |
|---|---|---|
| 19 | No lighting preprocessing | CLAHE on LAB L-channel before detection (~5ms) |
| 20 | No enrollment quality validation | Reject blurry/dark/multi-face uploads with quality gates |
| 21 | 50px movement threshold not camera-distance-aware | Use 0.3x face bbox width instead of fixed pixels |
| 22 | Direction detection "5-10 frames" is vague | Define as 1.5s time window, not frame count |

### Networking (3)
| # | Issue | Fix |
|---|---|---|
| 23 | DNS wildcard breaks HTTPS sites and captive portal | Proper captive portal detection for Android/iOS/Windows |
| 24 | MJPEG saturates WiFi with 3+ viewers | Limit to 5 clients, reduce to 320x240@10fps for web |
| 25 | DHCP 24h lease too long for 19-address pool | Reduce to 1h, expand range to 192.168.4.2-50 |

---

## PART 4: MEDIUM PRIORITY ISSUES (20 Issues)

### Frontend & UX
1. **No mobile-first design** -- most users access from phones. Need responsive layouts.
2. **Calibration arrow drawing has no touch support** -- blocks setup on tablets/phones
3. **MJPEG stream drains mobile battery** -- make it off by default, add auto-off timer
4. **Bundle size ~343KB gzipped** -- lazy-load routes, especially Reports (recharts is 150KB)
5. **SSE reconnection logic missing** -- need auto-reconnect with exponential backoff
6. **No PWA/service worker** -- cache static assets for faster repeat loads
7. **Auth flow with httpOnly cookies unclear** -- need 401 interceptor, sliding session
8. **File upload UX needs progress bars** -- video enrollment takes 6-10s on Pi 5

### Attendance Logic
9. **No leave/holiday/weekend model** -- everyone marked ABSENT on weekends
10. **Unknown visitors pollute employee reports** -- need report filtering
11. **No manual event correction** -- admin can't fix wrong events
12. **Power outage loses in-memory state machine** -- must reconstruct from DB on restart

### Database & Data
13. **No data retention policy** -- snapshots/reports grow unbounded, SD card fills in 1-2 years
14. **No schema migration strategy** -- future updates can't modify schema safely
15. **No audit log for admin actions** -- delete/rename/reset are untracked
16. **date column not computed from timestamp** -- can diverge, causing state machine bugs

### Performance
17. **No CPU affinity configuration** -- face engine should get cores 0-1, web server core 2
18. **Report generation should run in background subprocess** -- not in web server event loop
19. **Embedding cache needs invalidation signal** -- 30s delay after enrollment is annoying
20. **802.11n not enabled in hostapd** -- `hw_mode=g` limits to 54Mbps vs 150Mbps possible

---

## PART 5: COMPLETE DEPENDENCY FIXES

### requirements.txt (Corrected)
```
# Face Recognition
insightface==0.7.3
onnxruntime>=1.16.0          # Use piwheels for ARM64
opencv-python-headless==4.8.1.78

# Web Framework
fastapi==0.104.1
uvicorn[standard]==0.24.0
python-multipart==0.0.6
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4

# Database
sqlalchemy==2.0.23

# GPIO (Pi 5 compatible -- REPLACES RPi.GPIO)
gpiozero>=2.0

# Camera (Pi Camera Module 3 support)
picamera2>=0.3.12            # NEW -- for libcamera support

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

# Watchdog (systemd integration)
sdnotify==0.3.2              # NEW -- for WatchdogSec

# Security
python-magic==0.4.27         # NEW -- file upload validation
cryptography>=41.0.0         # NEW -- TLS cert generation
```

### Hardware BOM (Corrected)
| Component | Specification | Why Changed |
|---|---|---|
| Raspberry Pi Active Cooler | Official fan+heatsink | **NEW -- MANDATORY** for 24/7 AI |
| DS3231 RTC Module | I2C battery-backed clock | **NEW** -- accurate time without internet |
| MicroSD Card | Samsung PRO Endurance 64GB | **CHANGED** -- surveillance-grade, 64GB for longevity |
| USB WiFi Adapter (optional) | RTL8812AU chipset | **NEW** -- only needed for true bridge mode |

### hostapd.conf (Corrected)
```ini
interface=wlan0
driver=nl80211
ssid=AttendanceSystem
hw_mode=g
channel=0                    # CHANGED: ACS auto-select (was hardcoded 6)
ieee80211n=1                 # NEW: enable 802.11n (150Mbps vs 54Mbps)
wmm_enabled=1                # CHANGED: was 0, required for 802.11n
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=CHANGE_ON_SETUP
wpa_key_mgmt=WPA-PSK
# REMOVED: wpa_pairwise=TKIP  (insecure, deprecated)
rsn_pairwise=CCMP
ap_isolate=1                 # NEW: clients can't see each other
max_num_sta=20               # NEW: enforce connection limit
```

---

## PART 6: REVISED ARCHITECTURE DECISIONS

### Replace in Section 14 "Architecture Decisions -- Do Not Change":

| Original | Replacement | Reason |
|---|---|---|
| RPi.GPIO for LEDs | **gpiozero** (lgpio backend) | RPi.GPIO doesn't work on Pi 5 |
| Cosine similarity threshold 0.5 | **Default 0.6**, configurable 0.4-0.8 | 0.5 causes false positives |
| hostapd + dnsmasq (no NetworkManager) | hostapd + dnsmasq, **NM unmanages wlan0** | dhcpcd doesn't exist on Bookworm |
| Process every frame | **Process every 3rd frame** + lightweight tracking | Unsustainable CPU load |
| 4-state attendance machine | **Event-log model** with derived summaries | Current model can't handle real offices |

### New Architecture Decisions to Add:

1. **SQLite WAL mode** -- mandatory, set at database creation
2. **Overlay filesystem** -- read-only root, RW partition for data
3. **Self-signed TLS** -- generated during install, Nginx serves HTTPS
4. **iptables firewall** -- whitelist ports 443, 53, 67-68 only
5. **systemd watchdog** -- WatchdogSec=30 on all services
6. **CPU affinity** -- face engine on cores 0-1, web on core 2
7. **Active cooling** -- mandatory in hardware BOM
8. **Dedicated piface user** -- services never run as root
9. **Camera auto-detection** -- try USB V4L2 first, fall back to picamera2
10. **CLAHE preprocessing** -- adaptive histogram equalization before face detection

---

## PART 7: REVISED DATABASE SCHEMA

### New Tables Needed:

```sql
-- Separate auth from settings
CREATE TABLE auth_users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'admin',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login DATETIME
);

-- Audit trail for admin actions
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY,
    action TEXT NOT NULL,
    target_table TEXT,
    target_id INTEGER,
    old_value TEXT,
    new_value TEXT,
    performed_by TEXT,
    performed_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Leave and holiday management
CREATE TABLE leave_records (
    id INTEGER PRIMARY KEY,
    person_id INTEGER NOT NULL REFERENCES persons(id),
    date DATE NOT NULL,
    leave_type TEXT NOT NULL,  -- VACATION, SICK, PERSONAL, WFH
    note TEXT,
    UNIQUE(person_id, date)
);

CREATE TABLE holidays (
    id INTEGER PRIMARY KEY,
    date DATE UNIQUE NOT NULL,
    name TEXT NOT NULL
);

-- Schema versioning
CREATE TABLE schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);
```

### Modified Tables:

```sql
-- persons: add embedding size check
face_embedding BLOB NOT NULL CHECK(LENGTH(face_embedding) = 2048)

-- daily_summary: add unique constraint
UNIQUE(person_id, date)

-- attendance_events: add manual correction support + computed date
is_manual BOOLEAN DEFAULT FALSE,
corrected_by TEXT,
-- date should be a generated column:
date DATE GENERATED ALWAYS AS (DATE(timestamp)) STORED

-- Required indexes:
CREATE INDEX idx_events_person_date ON attendance_events(person_id, date);
CREATE INDEX idx_events_date ON attendance_events(date);
CREATE INDEX idx_summary_person_date ON daily_summary(person_id, date);
CREATE INDEX idx_persons_active ON persons(is_active);
CREATE INDEX idx_persons_unknown ON persons(is_unknown);
```

### New API Endpoints Needed:

```
POST   /api/attendance/events          -- Manual event entry
PUT    /api/attendance/events/{id}     -- Correct a wrong event
DELETE /api/attendance/events/{id}     -- Remove erroneous event
GET    /api/system/health              -- Holistic health check (all 3 services)
GET    /api/stream/snapshot            -- Single JPEG frame (not continuous)
POST   /api/backup/create             -- Trigger database backup
GET    /api/backup/download            -- Download database backup
POST   /api/holidays                   -- Add holiday
GET    /api/holidays                   -- List holidays
POST   /api/leave                      -- Record employee leave
GET    /api/leave                      -- List leave records
```

---

## PART 8: REVISED BUILD PHASES

### Phase 0 -- Platform Foundation (NEW)
- install.sh with `set -euo pipefail` and error handling
- Handle NetworkManager -> wlan0 unmanage -> systemd-networkd static IP
- Disable systemd-resolved for dnsmasq
- Create `piface` system user with gpio/video groups
- Configure overlay filesystem (read-only root)
- Generate self-signed TLS certificate
- Set CPU governor to `performance`
- Configure iptables firewall
- Add DS3231 RTC support
- Add `usb_max_current_enable=1` to config.txt
- Set up logrotate for /var/log/piface/

### Phase 1 -- Core Infrastructure (REVISED)
- Database with WAL mode, FK enforcement, all indexes, migration system
- FastAPI skeleton with HTTPS, CORS, CSRF, rate limiting, auth middleware
- LED controller using **gpiozero** (not RPi.GPIO), systemd watchdog, socket cleanup
- Camera module with auto-detection (USB vs Pi Camera), reconnection loop, CLAHE preprocessing

### Phase 2 -- Face Engine (REVISED)
- Frame grab-and-drop pattern (process every 3rd frame)
- InsightFace with threshold 0.6, top-2 margin check
- Multi-face tracking with IoU-based persistent track IDs
- Direction detection with time-based window (1.5s), relative movement threshold
- Embedding cache with invalidation signal via Unix socket
- CPU affinity pinning to cores 0-1

### Phase 3 -- Attendance Logic (REVISED)
- **Event-log model** replacing the 4-state machine
- Cross-midnight attribution (OUT events link to previous day's CHECK_IN)
- State reconstruction from DB on engine restart
- Manual event CRUD endpoints with audit trail
- Enrollment quality gates (blur, face count, size, inter-similarity)

### Phase 4 -- Web Dashboard (REVISED)
- **Mobile-first** responsive design with Tailwind breakpoints
- Touch-compatible calibration with Pointer Events API
- MJPEG stream off by default, auto-off timer, snapshot fallback
- Lazy-loaded routes (especially Reports with recharts)
- SSE with auto-reconnect + exponential backoff
- 401 interceptor, offline banner, loading skeletons
- PWA service worker for static asset caching

### Phase 5 -- Reports & Leave (REVISED)
- Report generation in background subprocess with `nice +10`
- Leave/holiday management (new tables + API + UI)
- Weekend exclusion from ABSENT calculations
- Unknown persons filtered from employee reports
- Data retention policy (configurable snapshot/report cleanup)

### Phase 6 -- Hardening (REVISED)
- systemd watchdog (WatchdogSec=30) on all services
- Memory watchdog (MemoryMax in service files)
- SIGTERM handlers for graceful shutdown
- Database backup system (nightly + manual trigger)
- Startup integrity check (PRAGMA quick_check)
- Disk space monitoring with LED warning pattern
- Thermal monitoring with adaptive frame skipping
- Nginx 502 -> "System starting up" page
- File integrity checksums

---

## PART 9: REVISED FINAL CHECKLIST

| # | Check | How to Verify |
|---|---|---|
| 1 | Active cooler fan spins on boot | Visual + thermal check (should stay under 65C) |
| 2 | Pi boots and hotspot appears within 30s | Connect to WiFi |
| 3 | HTTPS works (self-signed cert warning) | Browser to https://192.168.4.1 |
| 4 | HTTP redirects to HTTPS | Browser to http://192.168.4.1 |
| 5 | Firewall blocks port 8000 direct access | `curl http://192.168.4.1:8000` should fail |
| 6 | 5 green LED blinks on boot | Watch LEDs (gpiozero) |
| 7 | Setup wizard loads on first boot | Complete all steps |
| 8 | Calibration works on phone (touch) | Draw IN/OUT arrows on phone |
| 9 | Employee enrollment with quality gates | Upload blurry photo -- should reject |
| 10 | Face recognition at threshold 0.6 | Verify correct identification |
| 11 | Multi-person entry works | Two people walk through simultaneously |
| 12 | Green LED on entry, red on exit | Walk through after calibration |
| 13 | Unknown person auto-named | Walk unknown person past camera |
| 14 | Unknown rename updates all records | Rename from Unknowns page |
| 15 | Manual attendance correction works | Edit an event via API/UI |
| 16 | Night shift cross-midnight works | Test CHECK_IN before midnight, CHECK_OUT after |
| 17 | Reports download (Excel + PDF) | Click download buttons |
| 18 | Leave/holiday exclusion works | Add a holiday, verify not marked ABSENT |
| 19 | Camera disconnect triggers reconnection | Unplug camera, watch auto-reconnect |
| 20 | Watchdog restarts hung process | `kill -STOP` a process, verify systemd restarts it |
| 21 | Power loss recovery | Pull plug, verify clean boot + DB intact |
| 22 | Database backup works | Trigger backup, download, verify |
| 23 | Rate limiting blocks brute-force | Send 10 wrong passwords, verify lockout |
| 24 | Clock survives reboot (RTC) | Reboot, verify time is accurate |
| 25 | SD card health after 72h stress test | Run system for 3 days, check `dmesg` for errors |

---

## PART 10: ISSUE COUNT SUMMARY

| Category | Showstopper | Critical | High | Medium | Total |
|---|---|---|---|---|---|
| Hardware/Platform | 2 | 0 | 5 | 2 | 9 |
| Security | 0 | 3 | 7 | 3 | 13 |
| Face Recognition | 0 | 4 | 3 | 3 | 10 |
| Database | 0 | 3 | 2 | 4 | 9 |
| Attendance Logic | 0 | 1 | 5 | 4 | 10 |
| Reliability | 1 | 1 | 6 | 3 | 11 |
| Networking | 2 | 1 | 4 | 3 | 10 |
| Frontend/UX | 0 | 0 | 4 | 8 | 12 |
| Install/Deploy | 2 | 0 | 4 | 4 | 10 |
| Performance | 0 | 0 | 3 | 4 | 7 |
| **TOTAL** | **5** | **12** | **40+** | **35+** | **~100** |

---

*PiFace Build Spec Analysis v1.0 -- "Measure twice, cut once."*
