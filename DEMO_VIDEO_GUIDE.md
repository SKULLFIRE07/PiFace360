# PiFace Attendance System - Demo Video Recording Guide

## Prerequisites

Before recording, ensure:
1. Backend is running on port 8001
2. Frontend (Vite) is running on port 5173
3. Laptop webcam is available (for live feed demo)

### Start the servers

```bash
cd /home/aryan-budukh/Desktop/ATTENDANCE-MONITOR-RASPBERRY-PI

# Terminal 1: Start backend
source venv/bin/activate
python -m uvicorn piface.backend.main:app --host 0.0.0.0 --port 8001

# Terminal 2: Start frontend
cd piface/frontend
npx vite --port 5173
```

Open browser at: **http://localhost:5173**

---

## Screen Recording Setup

### Option 1: OBS Studio (Recommended)
```bash
sudo apt install obs-studio
```
- Open OBS Studio
- Add "Window Capture" or "Screen Capture" source
- Set output to 1920x1080, 30fps
- Start recording

### Option 2: SimpleScreenRecorder
```bash
sudo apt install simplescreenrecorder
```
- Quick and lightweight
- Select the browser window

### Option 3: Built-in GNOME Screen Recorder
- Press `Ctrl+Shift+Alt+R` to start/stop recording
- Videos saved to ~/Videos

---

## Demo Script (5-7 minutes)

### Scene 1: Login (30 seconds)
1. Open http://localhost:5173 in Chrome
2. Show the login page
3. Login with: **Username:** `admin` / **Password:** `admin`
4. Show successful login redirecting to dashboard

### Scene 2: Today's Attendance Dashboard (60 seconds)
1. Show the "Today's Attendance" page with:
   - Summary stats cards (Present, Absent, On Leave, Avg Hours)
   - Employee status table (will be empty initially)
   - Live Events sidebar (SSE-powered)
2. Click **"View Live Feed"** button to show webcam stream
3. Click **"Snapshot"** to capture a frame
4. Explain: "Real-time attendance monitoring with face recognition"

### Scene 3: Employees Management (90 seconds)
1. Navigate to **Employees** page
2. Click **"Add Employee"**
3. Fill in: Name, Employee ID, Department, Job Title
4. Upload a photo (or take one with webcam)
5. Save - show the new employee card
6. Click on the employee card to show detail modal
7. Show edit and delete options
8. Explain: "Face enrollment for recognition"

### Scene 4: Attendance Log (60 seconds)
1. Navigate to **Attendance Log** page
2. Show filters: date range, employee, event type
3. Show the event table with columns
4. Click **"Add Event"** to manually create an IN/OUT event
5. Show **"Export CSV"** button
6. Explain: "Complete audit trail with manual override"

### Scene 5: Leave Management (60 seconds)
1. Navigate to **Leave** page
2. Show the calendar view with color-coded days
3. Click **"Add Leave"**
4. Select employee, dates, leave type
5. Submit the leave request
6. Show leave record in the table
7. Scroll to **Holiday Management** section
8. Add a holiday (e.g., "Company Holiday" on a future date)
9. Explain: "Leave and holiday tracking integrated with attendance"

### Scene 6: Reports (60 seconds)
1. Navigate to **Reports** page
2. Select a date range
3. Show the report dashboard with:
   - Summary table (per-employee stats)
   - Bar chart (daily attendance)
   - Pie chart (present/absent/leave breakdown)
4. Click **"Download Excel"** and **"Download PDF"**
5. Show report history section
6. Explain: "Automated daily reports with export"

### Scene 7: Settings (60 seconds)
1. Navigate to **Settings** page
2. Show System Status section (uptime, DB size, disk, camera)
3. Show Company Info editing
4. Show Working Hours configuration (shift times, late threshold, weekend days)
5. Show WiFi settings (no-op in dev)
6. Show Backup/Restore section
7. Show Service Management (restart face engine, LED controller)
8. Explain: "Full system configuration and management"

### Scene 8: Unknown Persons (30 seconds)
1. Navigate to **Unknowns** page
2. Show unknown persons detected by the system
3. Demonstrate **"Rename"** to convert an unknown to a known employee
4. Explain: "Auto-detect and identify new faces"

### Closing (15 seconds)
- Return to the Today page
- Summarize: "PiFace: Complete facial recognition attendance monitoring system"

---

## Tips for a Good Demo

1. **Use Chrome** - best compatibility with MJPEG streams
2. **Full screen the browser** - cleaner look
3. **Slow down** - pause on each page for 2-3 seconds before clicking
4. **Add some test data first** - add 2-3 employees before recording
5. **Pre-create a few attendance events** so tables aren't empty
6. **Good lighting** - for the webcam feed demo
7. **Close notifications** - disable OS notifications during recording

## Adding Sample Data Before Recording

You can add sample data via the API:

```bash
# Add employees (use the UI or API)
# Login first to get cookies
curl -c /tmp/demo-cookies.txt http://localhost:8001/api/auth/login \
  -X POST -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin"}'

# Add a holiday
curl -b /tmp/demo-cookies.txt http://localhost:8001/api/holidays/ \
  -X POST -H "Content-Type: application/json" \
  -d '{"name":"Company Foundation Day","date":"2026-03-20"}'
```

For employees, use the UI to upload photos (which also enrolls their face).

---

## Output

After recording:
- Trim the video (remove pauses at start/end)
- Export as MP4 (H.264, 1080p)
- File size target: under 100MB for a 5-7 min video
