# PiFace Attendance System -- Raspberry Pi 5 Setup Guide

This guide walks you through setting up a brand-new Raspberry Pi 5 to run the
PiFace Attendance System from scratch. No prior Raspberry Pi experience is
required. Follow each step in order.

---

## Table of Contents

1. [What You Need (Shopping List)](#1-what-you-need-shopping-list)
2. [Flash the SD Card](#2-flash-the-sd-card)
3. [Hardware Assembly](#3-hardware-assembly)
4. [First Boot and SSH Connection](#4-first-boot-and-ssh-connection)
5. [Transfer PiFace Software](#5-transfer-piface-software)
6. [Run the Install Script](#6-run-the-install-script)
7. [Copy the InsightFace Model](#7-copy-the-insightface-model)
8. [Build the Frontend (if not pre-built)](#8-build-the-frontend-if-not-pre-built)
9. [Reboot and Verify](#9-reboot-and-verify)
10. [First-Time Configuration](#10-first-time-configuration)
11. [Camera Mounting](#11-camera-mounting)
12. [Troubleshooting](#12-troubleshooting)
13. [Maintenance](#13-maintenance)
14. [Technical Specs Summary](#14-technical-specs-summary)

---

## 1. What You Need (Shopping List)

Gather everything below before you begin. All items are available in India.

| # | Item | Why You Need It | Where to Buy (India) |
|---|------|----------------|----------------------|
| 1 | **Raspberry Pi 5 (8 GB RAM)** | The brain of the system. 8 GB is required -- 4 GB will run out of memory during face recognition. | [Robu.in](https://robu.in/) / [ThinkRobotics.com](https://thinkrobotics.com/) / [Amazon.in](https://www.amazon.in/) -- search "Raspberry Pi 5 8GB" |
| 2 | **Official Raspberry Pi Active Cooler** | **MANDATORY.** The Pi 5 generates significant heat when running AI workloads. Without the active cooler, the CPU will thermal-throttle (automatically slow down to prevent overheating), which drops face recognition from ~6 FPS to ~2 FPS or worse. The system becomes unreliable. Do not skip this. | Same stores as above -- search "Raspberry Pi 5 Active Cooler" |
| 3 | **Samsung PRO Endurance 64 GB microSD card** (or similar surveillance-grade card) | The system writes attendance logs and snapshots continuously. Consumer-grade SD cards (like the Samsung EVO) fail within months under this write load. Surveillance/endurance-rated cards are designed for 24/7 recording and last 2-5 years. | [Amazon.in](https://www.amazon.in/) -- search "Samsung PRO Endurance 64GB" |
| 4 | **Official Raspberry Pi 27 W USB-C power supply** | The Pi 5 needs a proper 5V/5A supply. Phone chargers and cheap adapters cause under-voltage warnings, random crashes, and USB device disconnections. Use only the official 27 W supply. | Same stores as the Pi |
| 5 | **USB Webcam (Logitech C270 or C310 recommended)** | Captures video for face recognition. The C270 and C310 are well-tested with Linux and provide reliable 640x480 at 30 FPS. Avoid no-name cameras -- they often have driver issues. | [Amazon.in](https://www.amazon.in/) / [Flipkart](https://www.flipkart.com/) |
| 6 | **DS3231 RTC module** | Keeps accurate time even when the Pi has no internet. Without this, the clock drifts and attendance timestamps become wrong. The DS3231 is accurate to about 2 seconds per month. | [Robu.in](https://robu.in/) / [Amazon.in](https://www.amazon.in/) -- search "DS3231 RTC module" (usually costs 100-200 INR) |
| 7 | **2x LEDs (5 mm): 1 Green + 1 Red** | Visual indicators: green = entry confirmed, red = exit confirmed, both = system starting up. | Any local electronics shop or [Robu.in](https://robu.in/) |
| 8 | **2x 220-ohm resistors (1/4 W)** | Current-limiting resistors to protect the LEDs from burning out. Without them the LEDs will draw too much current and may damage the Pi's GPIO pins. | Any local electronics shop |
| 9 | **Jumper wires (female-to-female)** | Connect the LEDs and RTC module to the Pi's GPIO header. Get at least 10 wires. | Any local electronics shop or [Robu.in](https://robu.in/) |
| 10 | **Project enclosure** | Protects the Pi from dust and accidental contact. **Must have ventilation holes or an opening for the active cooler fan** -- a sealed box will trap heat and defeat the purpose of the cooler. | 3D print one, or buy a Pi 5 case with fan cutout from Amazon.in |
| 11 | **A laptop or PC** | For flashing the SD card, SSH access, and initial configuration. Windows, macOS, or Linux all work. | (You probably already have one) |

**Optional but helpful:**
- A USB keyboard and micro-HDMI-to-HDMI cable (for direct debugging if SSH fails)
- An Ethernet cable (for initial setup if you prefer wired connection)

---

## 2. Flash the SD Card

You will install Raspberry Pi OS onto the microSD card using the Raspberry Pi
Imager tool on your laptop.

### Step 2.1 -- Download the Imager

Go to [https://www.raspberrypi.com/software/](https://www.raspberrypi.com/software/)
and download **Raspberry Pi Imager** for your operating system (Windows, macOS,
or Ubuntu). Install it.

### Step 2.2 -- Insert the SD card

Insert your Samsung PRO Endurance microSD card into your laptop (use an adapter
if your laptop has a full-size SD slot).

### Step 2.3 -- Open Pi Imager and configure

1. Open **Raspberry Pi Imager**.
2. Click **Choose Device** and select **Raspberry Pi 5**.
3. Click **Choose OS** and select:
   - **Raspberry Pi OS (other)**
   - Then select **Raspberry Pi OS Lite (64-bit)** -- this is the "Bookworm"
     release with no desktop environment. We do not need a desktop; the system
     runs headless (no monitor).
4. Click **Choose Storage** and select your microSD card.

   **WARNING:** Double-check you selected the right drive. The imager will erase
   everything on the selected device.

5. Click **Next**. A dialog will ask "Would you like to apply OS customisation
   settings?" Click **Edit Settings**.

6. In the **General** tab, configure:
   - **Set hostname:** `piface`
   - **Set username and password:**
     - Username: `pi`
     - Password: choose a strong password and write it down somewhere safe
   - **Set locale settings:**
     - Time zone: `Asia/Kolkata`
     - Keyboard layout: `us` (or your preference)
   - **Configure wireless LAN:** **Leave this unchecked / skip it.**
     The install script will configure its own WiFi hotspot later. If you need
     internet during setup, use an Ethernet cable instead.

7. In the **Services** tab:
   - **Enable SSH:** Yes
   - **Use password authentication:** Yes

8. Click **Save**, then click **Yes** to start writing.

9. Wait for the write and verification to complete (takes 5-10 minutes).

10. When done, **eject the SD card** safely from your laptop.

---

## 3. Hardware Assembly

### Step 3.1 -- Attach the Active Cooler

The active cooler must be installed before powering on the Pi.

1. Place the Raspberry Pi 5 board on a flat, clean surface with the GPIO pins
   at the top-right.
2. Peel the protective film off the thermal pad on the bottom of the active
   cooler.
3. The cooler has a small 4-pin connector cable. Locate the **FAN** header on
   the Pi 5 board -- it is between the USB-C power port and the first
   micro-HDMI port.
4. Align the cooler over the CPU (the large silver chip in the center of the
   board). The spring-loaded push pins on the cooler line up with the two
   mounting holes on either side of the CPU.
5. Press down firmly on both push pins until they click into place.
6. Plug the fan cable into the FAN header (it only fits one way).

### Step 3.2 -- Insert the microSD card

1. Locate the microSD card slot on the bottom of the Pi 5 (opposite side from
   the USB ports).
2. Insert the flashed microSD card with the label side facing up (contacts
   facing the board). Push gently until it clicks in.

### Step 3.3 -- Connect the DS3231 RTC module

The RTC module uses the I2C bus. Connect it with jumper wires:

```
DS3231 Module          Raspberry Pi 5 GPIO Header
+-----------+          +---------------------------+
| VCC  ------>------>  Pin 1  (3.3V Power)         |
| GND  ------>------>  Pin 6  (Ground)             |
| SDA  ------>------>  Pin 3  (GPIO 2 / SDA1)      |
| SCL  ------>------>  Pin 5  (GPIO 3 / SCL1)      |
+-----------+          +---------------------------+
```

**Important:** Connect VCC to the **3.3V** pin (pin 1), NOT 5V. The DS3231
board has an onboard regulator, but using 3.3V is safer for the Pi's I2C lines.

### Step 3.4 -- Connect the LEDs

Each LED needs a 220-ohm resistor in series. Here is the wiring:

```
GREEN LED CIRCUIT
=================

GPIO 17 (Pin 11) ---[ 220 ohm ]---+---|>|---  GND (Pin 9)
                     resistor      anode  cathode
                                   (long  (short
                                    leg)   leg)


RED LED CIRCUIT
===============

GPIO 27 (Pin 13) ---[ 220 ohm ]---+---|>|---  GND (Pin 14)
                     resistor      anode  cathode
                                   (long  (short
                                    leg)   leg)
```

**How to identify LED polarity:**
- The **longer leg** is the anode (+), connects toward the GPIO pin (through
  the resistor).
- The **shorter leg** is the cathode (-), connects to Ground.
- If the legs have been trimmed, look for the **flat edge** on the LED housing
  -- that side is the cathode.

**GPIO header reference (relevant pins):**

```
                    Raspberry Pi 5 GPIO Header
                    (looking at the board with USB ports facing you)

                     3V3  (1) (2)  5V
               SDA / GPIO2  (3) (4)  5V
               SCL / GPIO3  (5) (6)  GND
                     GPIO4  (7) (8)  GPIO14
                      GND  (9) (10) GPIO15
  GREEN LED -> GPIO17 (11) (12) GPIO18
    RED LED -> GPIO27 (13) (14) GND  <- RED LED ground
                     GPIO22 (15) (16) GPIO23
                      3V3 (17) (18) GPIO24
                     GPIO10 (19) (20) GND
                      GPIO9 (21) (22) GPIO25
                     GPIO11 (23) (24) GPIO8
                      GND (25) (26) GPIO7
```

### Step 3.5 -- Connect the USB webcam

Plug the webcam into any of the four USB ports on the Pi. The blue USB 3.0
ports are preferred if your webcam supports USB 3.0, but either type works.

### Step 3.6 -- Connect the power supply

Plug the official 27W USB-C power supply into the Pi's USB-C port.

**DO NOT plug the power cable into the wall yet.** We will do that in the next
section.

---

## 4. First Boot and SSH Connection

### Step 4.1 -- Power on

1. Plug the power supply into the wall outlet.
2. The Pi will begin booting. You will see:
   - The red power LED on the board turns on (steady).
   - The active cooler fan spins up briefly.
   - The green activity LED on the board flickers as it reads the SD card.
3. **Wait 60-90 seconds** for the first boot to complete. The first boot takes
   longer because Pi OS resizes the filesystem and generates SSH keys.

### Step 4.2 -- Connect your laptop to the same network

You need your laptop and the Pi on the same network to SSH in. Two options:

**Option A: Ethernet (recommended for first setup)**
- Connect the Pi and your laptop to the same router/switch with Ethernet
  cables.

**Option B: Direct USB-Ethernet**
- If you have a USB-to-Ethernet adapter, connect the Pi directly to your
  laptop.

### Step 4.3 -- SSH into the Pi

Open a terminal (Command Prompt / PowerShell on Windows, Terminal on
macOS/Linux) and run:

```bash
ssh pi@piface.local
```

If `piface.local` does not resolve (common on some Windows setups), you need
the Pi's IP address. Check your router's admin page for connected devices, or
use a tool like `nmap`:

```bash
# From Linux/macOS:
nmap -sn 192.168.1.0/24 | grep -i "pi"

# Or try:
ping piface.local
```

Then connect with the IP:

```bash
ssh pi@192.168.1.XXX
```

When prompted "Are you sure you want to continue connecting?", type `yes`.
Enter the password you set in the Pi Imager.

### Step 4.4 -- Update the system

Once logged in, update all packages to the latest versions:

```bash
sudo apt update && sudo apt upgrade -y
```

This may take 5-15 minutes depending on your internet speed. Let it finish.

### Step 4.5 -- Verify hardware

Check that the RTC module is detected:

```bash
sudo i2cdetect -y 1
```

You should see `68` in the grid (the DS3231's I2C address). If you see `UU`
instead, that means the kernel driver has already claimed it (also fine).

Check that the webcam is detected:

```bash
ls /dev/video*
```

You should see `/dev/video0` (and possibly `/dev/video1`). If nothing appears,
unplug and re-plug the webcam, then check again.

---

## 5. Transfer PiFace Software

You need to copy the `piface/` directory from this repository to the Pi.

### Option A: SCP from your laptop

From your laptop's terminal (not the Pi's SSH session), navigate to the
directory containing the `piface/` folder and run:

```bash
scp -r piface/ pi@piface.local:/home/pi/
```

This copies the entire project to `/home/pi/piface/` on the Pi.

### Option B: Clone from Git (if available)

If the project is hosted on a Git repository:

```bash
# On the Pi (via SSH):
sudo apt install -y git
git clone <repository-url> /home/pi/piface
```

### Option C: USB drive

If the Pi has no internet:

1. Copy the `piface/` folder to a USB drive on your laptop.
2. Plug the USB drive into the Pi.
3. On the Pi:

```bash
sudo mkdir -p /mnt/usb
sudo mount /dev/sda1 /mnt/usb
cp -r /mnt/usb/piface /home/pi/piface
sudo umount /mnt/usb
```

---

## 6. Run the Install Script

The install script automates the entire system configuration. It will take
15-30 minutes depending on your internet speed.

### Step 6.1 -- Make the script executable and run it

```bash
cd /home/pi/piface/setup
chmod +x install.sh
sudo ./install.sh
```

### Step 6.2 -- What the script does

The script performs 20 steps automatically. Here is what each one does:

| Step | What It Does |
|------|-------------|
| 1-2 | Updates all system packages, installs hostapd, dnsmasq, nginx, Python build tools, I2C tools, and iptables |
| 3-5 | Configures NetworkManager to ignore wlan0, sets up static IP `192.168.4.1` on wlan0, disables systemd-resolved |
| 6 | Installs hostapd (WiFi access point) and dnsmasq (DHCP/DNS) configuration |
| 7 | Creates the `piface` system user with GPIO, video, and I2C group access |
| 8 | Creates the directory structure under `/opt/piface/` |
| 9-10 | Creates a Python virtual environment, installs all Python packages (OpenCV, face-recognition, FastAPI, gpiozero, etc.) |
| 11 | Generates a self-signed TLS certificate (valid for 10 years) |
| 12 | Generates a random JWT secret for authentication tokens |
| 13 | Configures Nginx as a reverse proxy with HTTPS |
| 14 | Installs the three systemd services: `piface-engine`, `piface-web`, `piface-leds` |
| 15 | Configures the iptables firewall (allows only DHCP, DNS, HTTP, HTTPS on wlan0) |
| 16 | Installs logrotate configuration for log management |
| 17 | Configures hardware settings: DS3231 RTC overlay, USB max current, CPU performance governor, Asia/Kolkata timezone, disables Bluetooth |
| 18 | Enables the three PiFace services to start at boot |
| 19 | Adds `noatime` to the root filesystem to reduce SD card writes |
| 20 | Installs a restricted service-restart helper and sudoers entry |

### Step 6.3 -- If something goes wrong

If the script fails at any point, check the install log:

```bash
cat /var/log/piface-install.log
```

Common issues:
- **"Could not resolve host"** -- The Pi has no internet. Connect an Ethernet
  cable to your router.
- **"dpkg was interrupted"** -- Run `sudo dpkg --configure -a` and then re-run
  the install script.
- **"No space left on device"** -- Your SD card is too small or corrupted.
  Re-flash with a larger card.

### Step 6.4 -- Copy application code to /opt/piface

After the install script finishes, copy the application code into the
installation directory:

```bash
sudo cp -r /home/pi/piface/core/* /opt/piface/core/
sudo cp -r /home/pi/piface/backend/* /opt/piface/backend/
sudo cp -r /home/pi/piface/frontend/* /opt/piface/frontend/
sudo chown -R piface:piface /opt/piface
```

---

## 7. Copy the InsightFace Model

The face recognition engine uses the InsightFace Buffalo_S model. The model
files must be placed at `/opt/piface/models/buffalo_s/`.

### If the model files are included in the repository

```bash
sudo cp -r /home/pi/piface/models/* /opt/piface/models/
sudo chown -R piface:piface /opt/piface/models
```

### If the model files are NOT included (download them)

The model files are large and may not be in the Git repository. To download
them, run this on a machine with internet (your laptop or the Pi if it has
internet):

```python
# Run in Python 3:
from insightface.app import FaceAnalysis
app = FaceAnalysis(name='buffalo_s', root='./models')
app.prepare(ctx_id=0)
```

This will download the model to `./models/models/buffalo_s/`. Then copy the
files to the Pi:

```bash
# From your laptop:
scp -r models/ pi@piface.local:/home/pi/insightface_models/

# Then on the Pi:
sudo cp -r /home/pi/insightface_models/* /opt/piface/models/
sudo chown -R piface:piface /opt/piface/models
```

### Verify the model files

After copying, verify the files are in place:

```bash
ls -la /opt/piface/models/buffalo_s/
```

You should see several `.onnx` files (the neural network weights). If this
directory is empty or missing, face recognition will not work.

---

## 8. Build the Frontend (if not pre-built)

The web dashboard is a React application that needs to be compiled into static
files. If the `frontend/dist/` directory already contains built files (an
`index.html` and `.js`/`.css` files), you can skip this step.

### Check if the frontend is already built

```bash
ls /opt/piface/frontend/dist/
```

If you see `index.html` along with `assets/` directory, the frontend is already
built. Skip to Step 9.

### If you need to build it

#### Step 8.1 -- Install Node.js 20

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo bash -
sudo apt install -y nodejs
```

Verify the installation:

```bash
node --version   # Should show v20.x.x
npm --version    # Should show 10.x.x
```

#### Step 8.2 -- Install dependencies and build

```bash
cd /opt/piface/frontend
sudo -u piface npm ci
sudo -u piface npm run build
```

The `npm ci` command installs exact dependency versions from `package-lock.json`
(takes 2-5 minutes). The `npm run build` command compiles the React app into
optimized static files in `dist/`.

#### Step 8.3 -- Verify the build

```bash
ls /opt/piface/frontend/dist/
```

You should see `index.html` and an `assets/` directory containing `.js` and
`.css` files.

---

## 9. Reboot and Verify

### Step 9.1 -- Reboot

```bash
sudo reboot
```

Your SSH session will disconnect. This is normal.

### Step 9.2 -- Watch the LEDs

After plugging in (or after reboot), watch the LEDs you wired up:

| Time After Boot | What You Should See | What It Means |
|----------------|---------------------|---------------|
| ~5-10 seconds | **5 rapid green blinks** (0.2 s on, 0.2 s off) | The LED controller service has started and is running the boot sequence |
| ~15-30 seconds | **Both green and red LEDs on steady** | The face recognition engine is loading the AI model into memory |
| ~40-50 seconds | **Both LEDs turn off** | System is ready and operational |

If the LEDs do not behave this way, see the [Troubleshooting](#12-troubleshooting)
section.

### Step 9.3 -- Connect to the WiFi hotspot

1. On your phone or laptop, open WiFi settings.
2. Look for a network called **AttendanceSystem**.
3. Connect using the password: **ChangeMe123**

   (You should change this password before deploying. See Troubleshooting.)

4. Your device should connect within a few seconds. You will see a "no
   internet" warning -- this is expected. The Pi is a local-only access point;
   it does not provide internet access.

### Step 9.4 -- Open the dashboard

1. Open a web browser.
2. Navigate to: **https://192.168.4.1**
3. You will see a **certificate warning** (e.g., "Your connection is not
   private" in Chrome, or "Warning: Potential Security Risk" in Firefox).

   **This is normal and expected.** The system uses a self-signed TLS
   certificate because it runs on a local network without a domain name. Click
   "Advanced" and then "Proceed" (Chrome) or "Accept the Risk and Continue"
   (Firefox).

4. You should see either:
   - The **Setup Wizard** (if this is the first time), or
   - The **Login page** (if already configured).

---

## 10. First-Time Configuration

### Step 10.1 -- Complete the Setup Wizard

The Setup Wizard appears only on first use. It walks you through three screens:

**Screen 1: Organization Details**
- Enter your company or organization name.
- Set an admin username (this is your login to the dashboard).
- Set a strong admin password.

**Screen 2: Working Hours**
- Set the standard work start time and end time.
- Select which days are weekends (e.g., Saturday and Sunday).
- These are used for attendance reports and late-arrival detection.

**Screen 3: Camera Calibration**
- You will see a live camera feed.
- Draw an **IN arrow** -- an arrow pointing in the direction that employees
  walk when entering the building.
- Draw an **OUT arrow** -- an arrow pointing in the direction that employees
  walk when leaving the building.
- These arrows tell the system which direction of movement means "check in"
  versus "check out."

Click **Complete** when done.

### Step 10.2 -- Enroll your first employee

1. Log in to the dashboard with the admin credentials you just created.
2. Go to the **Employees** page.
3. Click **Add Employee**.
4. You will be asked to capture the employee's face:
   - **Option A: Record a 5-second video** -- The employee should look directly
     at the camera and slowly turn their head left and right. This gives the
     system multiple angles for better recognition.
   - **Option B: Take a photo** -- A single front-facing photo. Less reliable
     than video but faster.
5. Fill in the employee details (name, employee ID, department, etc.).
6. Click **Save** and wait for processing to complete. The system extracts face
   embeddings from the captured images -- this takes 10-30 seconds.

### Step 10.3 -- Test recognition

After enrolling, have the employee walk past the camera. Within 1-3 seconds,
you should see:
- The **green LED** lights up for 3 seconds (entry confirmed), or
- The **red LED** lights up for 3 seconds (exit confirmed).
- The attendance event appears on the dashboard in real time.

---

## 11. Camera Mounting

Proper camera placement is critical for reliable face recognition.

### Position

- Mount the webcam at the **entrance doorway** that employees use.
- **Height:** 1.2 to 1.5 meters from the floor (roughly chest to eye level).
  This ensures faces are captured at a natural angle.
- **Angle:** Point the camera toward incoming foot traffic. Tilt it 15-20
  degrees downward so it captures faces rather than the tops of heads.

### Lighting

- Ensure there is **good, even lighting on people's faces**.
- **Avoid backlighting:** Do NOT point the camera toward a window or bright
  light source. If the window is behind the people walking in, the camera will
  see silhouettes instead of faces.
- If the entrance is dim, add an LED panel or desk lamp aimed at the doorway.

### Field of view

- The camera should capture people from about **1 to 3 meters away**.
- Too close: people's faces overflow the frame.
- Too far: faces are too small for reliable recognition.

### After mounting

After you mount the camera in its final position, you **must recalibrate** the
IN/OUT arrows:

1. Log in to the dashboard.
2. Go to **Settings**.
3. Find the camera calibration section.
4. Redraw the IN and OUT arrows to match the new camera angle and position.

```
  GOOD MOUNTING                       BAD MOUNTING

  +----------+                        +----------+
  | Camera   |  Faces lit             | Camera   |  Window behind
  | v        |  from front            | v        |  people = backlit
  |          |                        |    |||   |  (silhouettes)
  |  [ :) ]  |  <-- person            |  [shadow]|  <-- person
  +----------+                        +----------+
  Light source                        Light source
  behind camera                       behind subject
  (CORRECT)                           (WRONG)
```

---

## 12. Troubleshooting

### LEDs not working

1. **Check wiring:** Verify the LED polarity (long leg = anode toward GPIO,
   short leg = cathode toward GND). Verify the resistors are 220 ohm.
2. **Check GPIO pins:** Confirm green is on pin 11 (GPIO 17) and red is on
   pin 13 (GPIO 27).
3. **Check the LED service:**
   ```bash
   sudo systemctl status piface-leds
   ```
4. **Verify gpiozero is installed:**
   ```bash
   /opt/piface/venv/bin/python -c "import gpiozero; print('OK')"
   ```

### Camera not detected

1. Try a different USB port.
2. Check if the device is recognized:
   ```bash
   ls /dev/video*
   lsusb
   ```
3. If `ls /dev/video*` shows nothing, the webcam may be incompatible.
   Try a different webcam (Logitech C270/C310 are most reliable).

### WiFi hotspot not appearing

1. Check hostapd status:
   ```bash
   sudo systemctl status hostapd
   ```
2. Check if wlan0 has the correct IP:
   ```bash
   ip addr show wlan0
   ```
   It should show `192.168.4.1/24`.
3. Check dnsmasq:
   ```bash
   sudo systemctl status dnsmasq
   ```
4. Restart both services:
   ```bash
   sudo systemctl restart hostapd dnsmasq
   ```

### Dashboard not loading

1. Check if the web service is running:
   ```bash
   sudo systemctl status piface-web
   ```
2. Check if Nginx is running:
   ```bash
   sudo systemctl status nginx
   ```
3. Check if the Nginx config is valid:
   ```bash
   sudo nginx -t
   ```
4. Check Nginx error logs:
   ```bash
   sudo tail -20 /var/log/nginx/error.log
   ```
5. If you see "502 Bad Gateway," the piface-web backend is not running.
   Check its logs:
   ```bash
   sudo journalctl -u piface-web -n 50
   ```

### Face recognition not working

1. Verify model files exist:
   ```bash
   ls -la /opt/piface/models/buffalo_s/
   ```
   If empty, go back to [Step 7](#7-copy-the-insightface-model).
2. Check the face engine logs:
   ```bash
   sudo journalctl -u piface-engine -f
   ```
   Press `Ctrl+C` to stop following the log.
3. Check memory usage (face engine needs significant RAM):
   ```bash
   free -h
   ```

### System logs (general)

```bash
# Follow face engine logs in real time:
sudo journalctl -u piface-engine -f

# Follow web server logs in real time:
sudo journalctl -u piface-web -f

# Follow LED controller logs in real time:
sudo journalctl -u piface-leds -f

# View the install log:
cat /var/log/piface-install.log

# View all PiFace logs:
sudo journalctl -u "piface-*" --since "1 hour ago"
```

### Changing the WiFi password

**Do this before deploying the system.** The default password `ChangeMe123` is
not secure.

```bash
sudo nano /etc/hostapd/hostapd.conf
```

Find the line `wpa_passphrase=ChangeMe123` and change it to your desired
password (minimum 8 characters). Save and exit (`Ctrl+X`, then `Y`, then
`Enter`). Then restart hostapd:

```bash
sudo systemctl restart hostapd
```

### RTC time is wrong

```bash
# Check if the DS3231 is detected:
sudo i2cdetect -y 1

# Read the time from the RTC:
sudo hwclock -r

# Set the RTC from the system clock (if the system clock is correct):
sudo hwclock -w

# Set the system clock from the RTC (if the RTC is correct):
sudo hwclock -s
```

---

## 13. Maintenance

### Regular backups

- Use **Settings > Backup** in the dashboard to create a database backup.
- Do this at least once a week, or before any hardware changes.
- Store backups on a USB drive or download them to your laptop.

### Monitor disk space

- Check in **Settings > System Status** on the dashboard.
- Or from SSH:
  ```bash
  df -h /
  ```
- If disk usage exceeds 80%, delete old snapshots or increase the SD card size.

### Keep the cooler clean

- **Once a month**, check the active cooler fan for dust buildup.
- Use a can of compressed air to blow dust out of the fan and heatsink fins.
- A clogged fan leads to thermal throttling and reduced recognition performance.

### SD card replacement

SD cards wear out eventually (2-5 years with the wear protection measures the
install script applies). If the system starts crashing randomly or you see
filesystem errors, replace the SD card.

**Replacement procedure:**

1. Create a full backup from **Settings > Backup** in the dashboard.
2. Download the backup to your laptop.
3. Flash a new SD card following [Step 2](#2-flash-the-sd-card).
4. Follow Steps 4 through 8 again on the new card.
5. After the system is running, go to **Settings > Restore** and upload your
   backup file.
6. All employee data, attendance records, and settings will be restored.

### Checking system health from SSH

```bash
# CPU temperature (should be under 70C with active cooler):
vcgencmd measure_temp

# CPU frequency (should be 2400 MHz with performance governor):
vcgencmd measure_clock arm

# Throttling status (0x0 = no throttling, good):
vcgencmd get_throttled

# Memory usage:
free -h

# Disk usage:
df -h /

# Service status overview:
sudo systemctl status piface-engine piface-web piface-leds --no-pager
```

---

## 14. Technical Specs Summary

| Specification | Value |
|--------------|-------|
| **CPU** | Broadcom BCM2712, 4-core Cortex-A76 @ 2.4 GHz |
| **Core assignment** | Cores 0-1: face recognition engine, Core 2: web API server, Core 3: LED controller + system |
| **RAM** | 8 GB LPDDR4X (steady-state usage ~1.5 GB) |
| **Face detection speed** | ~5-7 FPS at 640x480 resolution |
| **Max enrolled employees** | ~500 (comfortable), ~2000 (maximum) |
| **Max WiFi clients** | 20 simultaneous devices |
| **Max MJPEG live viewers** | 5 concurrent browser sessions |
| **Boot to operational** | ~50 seconds |
| **WiFi network** | SSID: AttendanceSystem, IP: 192.168.4.1, DHCP range: 192.168.4.2-50 |
| **Web interface** | HTTPS on port 443, HTTP on port 80 (redirects to HTTPS) |
| **TLS certificate** | Self-signed, valid 10 years |
| **Firewall** | iptables: DROP all INPUT by default, allow only DHCP/DNS/HTTP/HTTPS on wlan0 |
| **SD card lifespan** | 2-5 years (with noatime mount, logrotate, surveillance-grade card) |
| **Python environment** | Virtual environment at `/opt/piface/venv/` |
| **Log management** | Logrotate: daily rotation, 7-day retention, 10 MB max per file |
| **Services** | `piface-engine` (face AI), `piface-web` (FastAPI + Uvicorn), `piface-leds` (GPIO LED controller) |
| **Power supply** | 27W USB-C (5V / 5A) -- official Raspberry Pi supply required |
| **Operating temperature** | 0-50 C ambient (active cooler keeps CPU under 70 C) |

---

## Quick Reference Card

After setup is complete, keep this handy:

```
WiFi SSID:        AttendanceSystem
WiFi Password:    ChangeMe123  (CHANGE THIS!)
Dashboard URL:    https://192.168.4.1
SSH Access:       ssh pi@piface.local  (or ssh pi@192.168.4.1)

Restart services:
  sudo systemctl restart piface-engine
  sudo systemctl restart piface-web
  sudo systemctl restart piface-leds

View logs:
  sudo journalctl -u piface-engine -f
  sudo journalctl -u piface-web -f

Check temperature:
  vcgencmd measure_temp

Full system restart:
  sudo reboot
```

---

*PiFace Attendance System -- Setup Guide v2.0*
