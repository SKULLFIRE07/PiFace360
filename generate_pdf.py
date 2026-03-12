#!/usr/bin/env python3
"""Generate a beautiful black & white PDF documentation for PiFace360."""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether,
)
from reportlab.platypus.flowables import Flowable
from reportlab.pdfgen import canvas
from reportlab.lib.fonts import addMapping
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

# Colors - B&W theme with accent grays
BLACK = HexColor("#000000")
DARK = HexColor("#1a1a1a")
MID_DARK = HexColor("#333333")
MID = HexColor("#666666")
LIGHT_GRAY = HexColor("#999999")
LIGHTER = HexColor("#cccccc")
VERY_LIGHT = HexColor("#e8e8e8")
BG_LIGHT = HexColor("#f5f5f5")
WHITE = HexColor("#ffffff")
ACCENT = HexColor("#0066FF")  # small accent for emphasis

OUTPUT = "PiFace360_Documentation.pdf"
PAGE_W, PAGE_H = A4
MARGIN = 2.2 * cm


class SectionDivider(Flowable):
    """A thin horizontal rule with optional label."""
    def __init__(self, width=None):
        super().__init__()
        self.width = width or (PAGE_W - 2 * MARGIN)
        self.height = 0.5 * mm

    def draw(self):
        self.canv.setStrokeColor(LIGHTER)
        self.canv.setLineWidth(0.5)
        self.canv.line(0, 0, self.width, 0)


class BlackBox(Flowable):
    """A black background box with white text - for code/terminal blocks."""
    def __init__(self, text, width=None):
        super().__init__()
        self.text = text
        self.box_width = width or (PAGE_W - 2 * MARGIN)
        lines = text.split('\n')
        self.box_height = max(len(lines) * 14 + 20, 40)

    def draw(self):
        # Draw black background with rounded corners
        self.canv.setFillColor(DARK)
        self.canv.roundRect(0, 0, self.box_width, self.box_height, 4, fill=1, stroke=0)

        # Draw text
        self.canv.setFillColor(HexColor("#e0e0e0"))
        self.canv.setFont("Courier", 8.5)
        lines = self.text.split('\n')
        y = self.box_height - 16
        for line in lines:
            self.canv.drawString(12, y, line)
            y -= 14


def header_footer(canvas_obj, doc):
    """Draw page header and footer."""
    canvas_obj.saveState()

    # Header line
    canvas_obj.setStrokeColor(VERY_LIGHT)
    canvas_obj.setLineWidth(0.5)
    canvas_obj.line(MARGIN, PAGE_H - MARGIN + 5 * mm, PAGE_W - MARGIN, PAGE_H - MARGIN + 5 * mm)

    # Header text
    canvas_obj.setFont("Helvetica", 7)
    canvas_obj.setFillColor(LIGHT_GRAY)
    canvas_obj.drawString(MARGIN, PAGE_H - MARGIN + 7 * mm, "PiFace360 — Technical Documentation")
    canvas_obj.drawRightString(PAGE_W - MARGIN, PAGE_H - MARGIN + 7 * mm, "Confidential")

    # Footer
    canvas_obj.setStrokeColor(VERY_LIGHT)
    canvas_obj.line(MARGIN, MARGIN - 8 * mm, PAGE_W - MARGIN, MARGIN - 8 * mm)
    canvas_obj.setFont("Helvetica", 7)
    canvas_obj.setFillColor(LIGHT_GRAY)
    canvas_obj.drawString(MARGIN, MARGIN - 12 * mm, "© 2026 360 · github.com/SKULLFIRE07/PiFace360")
    canvas_obj.drawRightString(PAGE_W - MARGIN, MARGIN - 12 * mm, f"Page {doc.page}")

    canvas_obj.restoreState()


def first_page(canvas_obj, doc):
    """Custom first page - title page."""
    canvas_obj.saveState()

    # Large black band at top
    canvas_obj.setFillColor(BLACK)
    canvas_obj.rect(0, PAGE_H - 280, PAGE_W, 280, fill=1, stroke=0)

    # Title
    canvas_obj.setFillColor(WHITE)
    canvas_obj.setFont("Helvetica-Bold", 48)
    canvas_obj.drawString(MARGIN, PAGE_H - 120, "PiFace360")

    # Subtitle
    canvas_obj.setFont("Helvetica", 16)
    canvas_obj.setFillColor(HexColor("#aaaaaa"))
    canvas_obj.drawString(MARGIN, PAGE_H - 155, "AI-Powered Facial Recognition Attendance System")

    # Thin accent line
    canvas_obj.setStrokeColor(WHITE)
    canvas_obj.setLineWidth(1)
    canvas_obj.line(MARGIN, PAGE_H - 175, MARGIN + 60, PAGE_H - 175)

    # Version info
    canvas_obj.setFont("Helvetica", 11)
    canvas_obj.setFillColor(HexColor("#888888"))
    canvas_obj.drawString(MARGIN, PAGE_H - 200, "Technical Documentation · v1.0")
    canvas_obj.drawString(MARGIN, PAGE_H - 218, "Platform: Raspberry Pi 5 · March 2026")

    # Description block below black band
    canvas_obj.setFillColor(MID_DARK)
    canvas_obj.setFont("Helvetica", 11)
    y = PAGE_H - 320
    lines = [
        "A self-contained, enterprise-grade attendance monitoring system",
        "that runs entirely on a Raspberry Pi 5. Uses real-time facial",
        "recognition to automatically log employee entry and exit —",
        "no badges, no fingerprints, no cloud dependency.",
    ]
    for line in lines:
        canvas_obj.drawString(MARGIN, y, line)
        y -= 18

    # Key stats boxes
    y = PAGE_H - 440
    stats = [
        ("~$165", "Total Hardware Cost"),
        ("< 50ms", "Detection Latency"),
        ("> 97%", "Recognition Accuracy"),
        ("100%", "Offline Operation"),
    ]

    box_w = (PAGE_W - 2 * MARGIN - 3 * 8) / 4
    for i, (value, label) in enumerate(stats):
        x = MARGIN + i * (box_w + 8)
        # Box outline
        canvas_obj.setStrokeColor(LIGHTER)
        canvas_obj.setLineWidth(0.5)
        canvas_obj.roundRect(x, y, box_w, 55, 3, fill=0, stroke=1)
        # Value
        canvas_obj.setFont("Helvetica-Bold", 18)
        canvas_obj.setFillColor(BLACK)
        canvas_obj.drawCentredString(x + box_w / 2, y + 30, value)
        # Label
        canvas_obj.setFont("Helvetica", 7.5)
        canvas_obj.setFillColor(LIGHT_GRAY)
        canvas_obj.drawCentredString(x + box_w / 2, y + 12, label)

    # Footer on title page
    canvas_obj.setFont("Helvetica", 8)
    canvas_obj.setFillColor(LIGHT_GRAY)
    canvas_obj.drawString(MARGIN, MARGIN, "© 2026 360 · Built by Aryan Budukh · github.com/SKULLFIRE07/PiFace360")

    canvas_obj.restoreState()


def build_pdf():
    doc = SimpleDocTemplate(
        OUTPUT,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN + 8 * mm,
        bottomMargin=MARGIN,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    s_h1 = ParagraphStyle('H1Custom', parent=styles['Heading1'],
                          fontSize=22, spaceAfter=6 * mm, spaceBefore=10 * mm,
                          textColor=BLACK, fontName='Helvetica-Bold')

    s_h2 = ParagraphStyle('H2Custom', parent=styles['Heading2'],
                          fontSize=14, spaceAfter=4 * mm, spaceBefore=6 * mm,
                          textColor=MID_DARK, fontName='Helvetica-Bold')

    s_h3 = ParagraphStyle('H3Custom', parent=styles['Heading3'],
                          fontSize=11, spaceAfter=3 * mm, spaceBefore=4 * mm,
                          textColor=MID_DARK, fontName='Helvetica-Bold')

    s_body = ParagraphStyle('BodyCustom', parent=styles['Normal'],
                            fontSize=9.5, leading=14, spaceAfter=3 * mm,
                            textColor=MID_DARK, fontName='Helvetica',
                            alignment=TA_JUSTIFY)

    s_body_sm = ParagraphStyle('BodySmall', parent=s_body,
                                fontSize=8.5, leading=12)

    s_bullet = ParagraphStyle('BulletCustom', parent=s_body,
                               leftIndent=15, bulletIndent=5,
                               spaceBefore=1 * mm, spaceAfter=1 * mm)

    s_caption = ParagraphStyle('Caption', parent=styles['Normal'],
                                fontSize=8, textColor=LIGHT_GRAY,
                                fontName='Helvetica-Oblique',
                                alignment=TA_CENTER, spaceAfter=4 * mm)

    # Table styles
    ts_default = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), DARK),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8.5),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8.5),
        ('TEXTCOLOR', (0, 1), (-1, -1), MID_DARK),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, VERY_LIGHT),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, BG_LIGHT]),
    ])

    content_width = PAGE_W - 2 * MARGIN
    story = []

    # ─── TITLE PAGE (handled by first_page callback) ───
    story.append(PageBreak())

    # ─── TABLE OF CONTENTS ───
    story.append(Paragraph("Table of Contents", s_h1))
    story.append(SectionDivider())
    story.append(Spacer(1, 4 * mm))

    toc_items = [
        ("01", "Overview & Problem Statement"),
        ("02", "System Architecture"),
        ("03", "Tech Stack"),
        ("04", "Hardware Requirements"),
        ("05", "Features Breakdown"),
        ("06", "Database Schema"),
        ("07", "API Reference"),
        ("08", "Frontend Pages"),
        ("09", "AI & Face Recognition Engine"),
        ("10", "RPi5 Deployment"),
        ("11", "Network & Security"),
        ("12", "Development Setup"),
        ("13", "File Structure"),
    ]

    for num, title in toc_items:
        story.append(Paragraph(
            f'<font color="#999999">{num}</font>&nbsp;&nbsp;&nbsp;'
            f'<font color="#1a1a1a">{title}</font>',
            ParagraphStyle('TOC', parent=s_body, fontSize=10.5, spaceAfter=3 * mm,
                          leading=16, fontName='Helvetica')
        ))

    story.append(PageBreak())

    # ─── 01. OVERVIEW ───
    story.append(Paragraph("01 — Overview", s_h1))
    story.append(SectionDivider())
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph(
        "<b>PiFace360</b> is a self-contained, enterprise-grade attendance monitoring system "
        "designed to run entirely on a Raspberry Pi 5. It uses state-of-the-art facial recognition "
        "powered by InsightFace to automatically log employee entry and exit — eliminating the need "
        "for badges, fingerprints, or cloud services.",
        s_body
    ))

    story.append(Paragraph("The Problem", s_h2))

    problems = [
        ("Cloud dependency", "Most attendance systems require constant internet — PiFace360 runs 100% offline"),
        ("High cost", "Enterprise solutions cost thousands — PiFace360 runs on ~$165 of hardware"),
        ("Slow & intrusive", "Badge/fingerprint systems create queues — face recognition is instant & contactless"),
        ("Privacy concerns", "Cloud storage raises GDPR/privacy issues — all data stays on-device"),
        ("Complex deployment", "IT infrastructure needed — PiFace360 installs with a single script"),
    ]

    for problem, solution in problems:
        story.append(Paragraph(
            f'<bullet>&bull;</bullet><b>{problem}:</b> {solution}',
            s_bullet
        ))

    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("How It Works", s_h2))

    story.append(BlackBox(
        "Employee walks in\n"
        "  └─> Camera captures frame\n"
        "       └─> InsightFace detects & embeds face (512-d vector)\n"
        "            └─> Cosine similarity match against enrolled employees\n"
        "                 └─> Attendance event logged (IN/OUT + timestamp + confidence)\n"
        "                      └─> LED flash confirms (green=IN, red=OUT)"
    ))
    story.append(Spacer(1, 6 * mm))

    story.append(PageBreak())

    # ─── 02. ARCHITECTURE ───
    story.append(Paragraph("02 — System Architecture", s_h1))
    story.append(SectionDivider())
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph(
        "PiFace360 runs as three independent systemd services on the Raspberry Pi 5, "
        "each pinned to specific CPU cores for optimal performance. The system creates its own "
        "WiFi hotspot, so no external network infrastructure is required.",
        s_body
    ))

    story.append(BlackBox(
        "┌──────────────────────────────────────────────┐\n"
        "│              Raspberry Pi 5 (8GB)             │\n"
        "│                                               │\n"
        "│  ┌─────────────┐    ┌──────────────────────┐ │\n"
        "│  │ Face Engine  │    │  FastAPI Backend      │ │\n"
        "│  │ (cores 0-1)  │───>│  (core 2)            │ │\n"
        "│  │ InsightFace  │    │  SQLite + Uvicorn    │ │\n"
        "│  └──────┬───────┘    └──────────┬───────────┘ │\n"
        "│         │                       │             │\n"
        "│  ┌──────┴───────┐    ┌──────────┴───────────┐ │\n"
        "│  │ LED Control   │    │  Nginx Reverse Proxy │ │\n"
        "│  │ (core 3)      │    │  HTTPS :443          │ │\n"
        "│  │ GPIO 17 & 27  │    │  + Captive Portal    │ │\n"
        "│  └───────────────┘    └──────────────────────┘ │\n"
        "│                                               │\n"
        "│  ┌─────────────┐    ┌──────────────────────┐ │\n"
        "│  │ hostapd      │    │  React SPA (built)   │ │\n"
        "│  │ WiFi Hotspot │    │  Served by Nginx     │ │\n"
        "│  └─────────────┘    └──────────────────────┘ │\n"
        "└──────────────────────────────────────────────┘"
    ))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("<i>Architecture diagram: Three-service design with CPU core pinning</i>", s_caption))

    story.append(Paragraph("Service Allocation", s_h2))

    svc_data = [
        ["Service", "CPU Cores", "Memory Limit", "Nice Priority", "Purpose"],
        ["piface-engine", "0–1", "3 GB", "-5 (highest)", "Face recognition AI loop"],
        ["piface-web", "2", "1 GB", "-2", "FastAPI + static files"],
        ["piface-leds", "3", "512 MB", "-2", "GPIO LED controller"],
    ]
    t = Table(svc_data, colWidths=[80, 60, 65, 75, content_width - 280])
    t.setStyle(ts_default)
    story.append(t)

    story.append(PageBreak())

    # ─── 03. TECH STACK ───
    story.append(Paragraph("03 — Tech Stack", s_h1))
    story.append(SectionDivider())
    story.append(Spacer(1, 3 * mm))

    stack_data = [
        ["Layer", "Technology", "Version", "Purpose"],
        ["AI Engine", "InsightFace + ONNX Runtime", "0.7.3+", "512-d face embeddings, detection & recognition"],
        ["Backend", "Python + FastAPI", "3.11 / 0.104+", "REST API, business logic, auth"],
        ["ORM", "SQLAlchemy", "2.0.23+", "Database abstraction, migrations"],
        ["Database", "SQLite (WAL mode)", "3.x", "Persistent storage, ACID transactions"],
        ["Frontend", "React + Vite", "18.2 / 5.0", "Single-page application"],
        ["Styling", "TailwindCSS", "3.3.5", "Utility-first responsive CSS"],
        ["State Mgmt", "TanStack Query", "5.8.4", "Server state, caching, refetching"],
        ["Charts", "Recharts", "2.10.1", "Attendance visualizations"],
        ["Icons", "Lucide React", "0.294", "Consistent icon library"],
        ["Streaming", "MJPEG / SSE", "—", "Live camera feeds, real-time events"],
        ["Hardware", "gpiozero + lgpio", "2.0+ / 0.2+", "Pi 5 native GPIO (LED control)"],
        ["Camera", "picamera2 / OpenCV", "—", "Camera capture (CSI or USB)"],
        ["Web Server", "Nginx", "1.24+", "Reverse proxy, TLS, captive portal"],
        ["WiFi AP", "hostapd + dnsmasq", "—", "WiFi hotspot + DHCP"],
        ["Security", "JWT + CSRF + bcrypt", "—", "Authentication, session management"],
        ["Process Mgmt", "systemd", "—", "Service lifecycle, auto-restart"],
    ]
    t = Table(stack_data, colWidths=[60, 105, 50, content_width - 215])
    t.setStyle(ts_default)
    story.append(t)

    story.append(PageBreak())

    # ─── 04. HARDWARE ───
    story.append(Paragraph("04 — Hardware Requirements", s_h1))
    story.append(SectionDivider())
    story.append(Spacer(1, 3 * mm))

    hw_data = [
        ["Component", "Specification", "Est. Cost"],
        ["Raspberry Pi 5", "8GB RAM (recommended)", "$80"],
        ["microSD Card", "64GB+ Class 10 / A2", "$12"],
        ["USB-C PSU", "27W (5.1V, 5A) official", "$12"],
        ["USB Camera (×2)", "1080p USB 2.0/3.0", "$25 each"],
        ["LEDs + Resistors", "Green LED, Red LED, 330Ω ×2", "$2"],
        ["Case (optional)", "Official Pi 5 case or 3D printed", "$10"],
        ["Total", "", "~$165"],
    ]
    t = Table(hw_data, colWidths=[100, 180, content_width - 280])
    t.setStyle(ts_default)
    story.append(t)

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("GPIO Wiring Diagram", s_h2))

    story.append(BlackBox(
        "Raspberry Pi 5 GPIO Header\n"
        "──────────────────────────\n"
        "Pin 11 (GPIO 17) ──── 330Ω ──── Green LED (+) ──── GND (Pin 9)\n"
        "Pin 13 (GPIO 27) ──── 330Ω ──── Red LED (+)   ──── GND (Pin 14)\n"
        "\n"
        "Green = Entry confirmed    Red = Exit confirmed"
    ))

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Dual Camera Setup", s_h2))
    story.append(Paragraph(
        "PiFace360 supports two USB cameras for directional tracking. One camera is assigned "
        "as the <b>IN</b> camera (entrance) and the other as the <b>OUT</b> camera (exit). "
        "Camera assignment is managed through the Cameras page in the dashboard. The system "
        "probes /dev/video0 through /dev/video9 to detect connected cameras.",
        s_body
    ))

    story.append(PageBreak())

    # ─── 05. FEATURES ───
    story.append(Paragraph("05 — Features Breakdown", s_h1))
    story.append(SectionDivider())
    story.append(Spacer(1, 3 * mm))

    features = [
        ("Real-Time Face Recognition",
         "InsightFace AI engine processes live camera feeds at ~15 FPS. Uses buffalo_l model "
         "with 512-dimensional face embeddings and cosine similarity matching."),
        ("Dual Camera IN/OUT Tracking",
         "Separate entrance and exit cameras for accurate direction detection. Each camera is "
         "independently configurable through the web dashboard."),
        ("Automatic Attendance Logging",
         "Every face detection event generates a timestamped attendance record with confidence "
         "score, snapshot, and direction (IN/OUT). Manual corrections are supported."),
        ("Unknown Visitor Detection",
         "Unrecognized faces are flagged and stored with snapshots. Admins can review unknowns "
         "and optionally enroll them as new employees."),
        ("Live Dashboard",
         "Real-time attendance statistics, present/absent counts, late arrivals, and live camera "
         "feeds with dual-panel IN/OUT view."),
        ("Employee Management",
         "Full CRUD operations for employees including face enrollment via webcam capture, "
         "department assignment, and activation/deactivation."),
        ("Leave Management",
         "Submit and track sick, casual, annual, and personal leave. Calendar view shows leave "
         "entries with employee tags and reasons. Approval workflow included."),
        ("Report Generation",
         "Generate and download daily/monthly attendance reports in Excel and PDF formats. "
         "Includes hours worked, breaks, overtime, late arrivals, and early departures."),
        ("Settings & Configuration",
         "Organized settings for company info, working hours, weekend days, face recognition "
         "threshold, data retention, WiFi, backup/restore, and factory reset."),
        ("WiFi Hotspot Mode",
         "Pi creates its own WiFi network — no router needed. Captive portal auto-redirects "
         "connected devices to the dashboard. Works completely offline."),
        ("LED Indicators",
         "GPIO-driven green (entry) and red (exit) LED flashes provide immediate visual "
         "confirmation of successful attendance logging."),
        ("Security",
         "JWT authentication, CSRF protection (double-submit cookie), bcrypt password hashing, "
         "rate limiting on auth endpoints, self-signed TLS, and iptables firewall."),
    ]

    for title, desc in features:
        story.append(KeepTogether([
            Paragraph(f"▸ {title}", s_h3),
            Paragraph(desc, s_body_sm),
        ]))

    story.append(PageBreak())

    # ─── 06. DATABASE ───
    story.append(Paragraph("06 — Database Schema", s_h1))
    story.append(SectionDivider())
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph(
        "PiFace360 uses SQLite in WAL (Write-Ahead Logging) mode for concurrent read/write "
        "access. The database schema is managed through SQLAlchemy 2.0 ORM models.",
        s_body
    ))

    tables = [
        ("Person", [
            ["Column", "Type", "Description"],
            ["id", "Integer PK", "Auto-increment primary key"],
            ["name", "String(100)", "Full name of the person"],
            ["employee_id", "String(20) UNIQUE", "Company employee ID (e.g. EMP001)"],
            ["department", "String(50)", "Department name"],
            ["job_title", "String(100)", "Job title / role"],
            ["phone", "String(20)", "Contact phone number"],
            ["face_embedding", "LargeBinary", "512-d float32 vector (2048 bytes)"],
            ["face_image", "LargeBinary", "JPEG face photo for display"],
            ["is_unknown", "Boolean", "True if unidentified visitor"],
            ["is_active", "Boolean", "Soft delete flag"],
            ["enrolled_at", "DateTime", "Face enrollment timestamp"],
        ]),
        ("AttendanceEvent", [
            ["Column", "Type", "Description"],
            ["id", "Integer PK", "Auto-increment primary key"],
            ["person_id", "Integer FK", "References Person.id"],
            ["event_type", "String(10)", "IN or OUT"],
            ["timestamp", "DateTime", "Event timestamp (UTC)"],
            ["confidence", "Float", "Face match confidence (0-1)"],
            ["snapshot_path", "String(255)", "Path to captured face image"],
            ["date", "Date", "Event date (indexed)"],
            ["is_manual", "Boolean", "True if manually logged"],
        ]),
        ("DailySummary", [
            ["Column", "Type", "Description"],
            ["id", "Integer PK", "Auto-increment primary key"],
            ["person_id", "Integer FK", "References Person.id"],
            ["date", "Date", "Summary date (unique per person)"],
            ["first_in_time", "DateTime", "First entry timestamp"],
            ["last_out_time", "DateTime", "Last exit timestamp"],
            ["total_hours_worked", "Float", "Total hours present"],
            ["is_late", "Boolean", "Late arrival flag"],
            ["status", "String(20)", "PRESENT/ABSENT/HALF_DAY/ON_LEAVE/HOLIDAY"],
        ]),
        ("LeaveRecord", [
            ["Column", "Type", "Description"],
            ["id", "Integer PK", "Auto-increment primary key"],
            ["person_id", "Integer FK", "References Person.id"],
            ["date", "Date", "Leave date"],
            ["leave_type", "String(20)", "SICK / CASUAL / ANNUAL / PERSONAL"],
            ["note", "Text", "Reason / additional notes"],
            ["approved_by", "String(100)", "Approver name"],
        ]),
    ]

    for table_name, data in tables:
        story.append(Paragraph(f"<b>{table_name}</b>", s_h3))
        t = Table(data, colWidths=[85, 95, content_width - 180])
        t.setStyle(ts_default)
        story.append(t)
        story.append(Spacer(1, 3 * mm))

    story.append(Paragraph(
        "<i>Additional tables: Holiday, AuthUser, SystemSetting, AuditLog</i>",
        s_caption
    ))

    story.append(PageBreak())

    # ─── 07. API REFERENCE ───
    story.append(Paragraph("07 — API Reference", s_h1))
    story.append(SectionDivider())
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph("Unified Response Envelope", s_h2))
    story.append(BlackBox(
        '{\n'
        '  "success": true,\n'
        '  "data": { ... },\n'
        '  "error": null\n'
        '}'
    ))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Endpoint Reference", s_h2))

    api_data = [
        ["Method", "Endpoint", "Description"],
        ["POST", "/api/auth/login", "Authenticate, receive JWT token"],
        ["POST", "/api/auth/logout", "Invalidate session"],
        ["GET", "/api/employees", "List all employees (paginated)"],
        ["POST", "/api/employees", "Create employee + enroll face"],
        ["PUT", "/api/employees/{id}", "Update employee details"],
        ["DELETE", "/api/employees/{id}", "Deactivate employee"],
        ["GET", "/api/attendance/events", "Query events (sortable, filterable)"],
        ["GET", "/api/attendance/today", "Today's attendance summary"],
        ["POST", "/api/attendance/manual", "Manual attendance entry"],
        ["GET", "/api/unknowns", "List unknown face detections"],
        ["POST", "/api/unknowns/{id}/identify", "Assign unknown to employee"],
        ["GET", "/api/leave", "List leave records"],
        ["POST", "/api/leave", "Submit leave request"],
        ["GET", "/api/holidays", "List holidays"],
        ["POST", "/api/holidays", "Create holiday entry"],
        ["GET", "/api/reports/daily", "Generate daily attendance report"],
        ["GET", "/api/reports/monthly", "Generate monthly report (Excel/PDF)"],
        ["GET", "/api/cameras", "List camera assignments"],
        ["GET", "/api/cameras/detect", "Scan for connected cameras"],
        ["POST", "/api/cameras/assign", "Assign camera to IN/OUT role"],
        ["GET", "/api/video?camera=in", "MJPEG live stream (IN camera)"],
        ["GET", "/api/video?camera=out", "MJPEG live stream (OUT camera)"],
        ["GET", "/api/settings", "Get system configuration"],
        ["PUT", "/api/settings", "Update settings"],
        ["GET", "/api/system/status", "System health (CPU, disk, temp)"],
        ["POST", "/api/system/backup", "Create database backup"],
        ["POST", "/api/system/factory-reset", "Factory reset (requires password)"],
    ]
    t = Table(api_data, colWidths=[40, 130, content_width - 170])
    t.setStyle(ts_default)
    story.append(t)

    story.append(PageBreak())

    # ─── 08. FRONTEND PAGES ───
    story.append(Paragraph("08 — Frontend Pages", s_h1))
    story.append(SectionDivider())
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph(
        "The frontend is a React 18 single-page application built with Vite 5, styled with "
        "TailwindCSS, and uses TanStack Query for server state management. All pages are "
        "lazy-loaded for optimal bundle splitting.",
        s_body
    ))

    pages_data = [
        ["Page", "Route", "Key Features"],
        ["Login", "/login", "Username/password auth, JWT token storage"],
        ["Setup Wizard", "/setup/*", "4-step onboarding: Company → Hours → Calibration → Done"],
        ["Today", "/today", "Live dashboard, real-time stats, camera feeds, attendance chart"],
        ["Employees", "/employees", "List/add/edit employees, face enrollment via webcam"],
        ["Attendance Log", "/attendance", "Historical records, date/dept filters, sortable columns"],
        ["Unknowns", "/unknowns", "Unknown face gallery, assign-to-employee workflow"],
        ["Reports", "/reports", "Generate Excel/PDF reports, download history"],
        ["Leave", "/leave", "Submit leave, calendar with employee tags & reasons"],
        ["Cameras", "/cameras", "Detect USB cameras, assign IN/OUT roles, live preview"],
        ["Settings", "/settings", "Grouped settings: General, Security, System, Danger Zone"],
    ]
    t = Table(pages_data, colWidths=[70, 70, content_width - 140])
    t.setStyle(ts_default)
    story.append(t)

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Component Library", s_h2))

    comp_data = [
        ["Component", "Purpose"],
        ["AppShell", "Main layout wrapper with sidebar (desktop) and bottom nav (mobile)"],
        ["Sidebar", "Desktop navigation with collapsible panel, 8 nav items + logout"],
        ["BottomNav", "Mobile navigation with 4 primary tabs + \"More\" overflow menu"],
        ["LiveFeed", "Dual camera MJPEG streams with Snap IN / Snap OUT buttons"],
        ["ConfirmDialog", "Reusable modal confirmation with loading state"],
        ["StatusBadge", "Color-coded attendance status indicators"],
        ["ConnectionBanner", "Online/offline network status notification"],
        ["EmptyState", "Placeholder UI for empty lists with icon + message"],
        ["Skeleton", "Loading skeleton animations (text, cards, tables)"],
    ]
    t = Table(comp_data, colWidths=[100, content_width - 100])
    t.setStyle(ts_default)
    story.append(t)

    story.append(PageBreak())

    # ─── 09. AI ENGINE ───
    story.append(Paragraph("09 — AI & Face Recognition Engine", s_h1))
    story.append(SectionDivider())
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph(
        "The face recognition engine is the core of PiFace360. It runs as an independent "
        "systemd service with dedicated CPU cores (0-1) and 3GB memory limit.",
        s_body
    ))

    story.append(Paragraph("Recognition Pipeline", s_h2))

    pipeline = [
        ("1. Frame Capture", "Camera captures 1080p frame via picamera2 (CSI) or OpenCV (USB)"),
        ("2. Face Detection", "InsightFace SCRFD detector locates faces with bounding boxes"),
        ("3. Alignment", "Detected faces are aligned using 5-point landmark estimation"),
        ("4. Embedding", "ArcFace model generates 512-dimensional float32 embedding per face"),
        ("5. Matching", "Cosine similarity comparison against all enrolled embeddings"),
        ("6. Tracking", "Hungarian algorithm tracks faces across frames to avoid duplicate events"),
        ("7. Event Logging", "Matched face → attendance event written to SQLite database"),
        ("8. Notification", "Event sent to LED controller via Unix socket (green/red flash)"),
        ("9. Streaming", "Annotated frame pushed to MJPEG endpoint for live dashboard"),
    ]

    for step, desc in pipeline:
        story.append(Paragraph(f'<bullet>&bull;</bullet><b>{step}:</b> {desc}', s_bullet))

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Performance Characteristics", s_h2))

    perf_data = [
        ["Metric", "Value", "Notes"],
        ["Detection latency", "~50ms/frame", "SCRFD on RPi5 with ONNX Runtime"],
        ["Recognition accuracy", ">97%", "buffalo_l model, 512-d embeddings"],
        ["Processing rate", "~15 FPS", "Full pipeline including tracking"],
        ["Embedding size", "2,048 bytes", "512 × float32 per face"],
        ["Min face size", "80×80 pixels", "Configurable in settings"],
        ["Similarity threshold", "0.6 (default)", "Adjustable 0.4–0.8 via dashboard"],
        ["Max tracked faces", "20 simultaneous", "Hungarian algorithm capacity"],
    ]
    t = Table(perf_data, colWidths=[95, 80, content_width - 175])
    t.setStyle(ts_default)
    story.append(t)

    story.append(PageBreak())

    # ─── 10. RPi5 DEPLOYMENT ───
    story.append(Paragraph("10 — RPi5 Deployment", s_h1))
    story.append(SectionDivider())
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph("One-Script Installation", s_h2))
    story.append(Paragraph(
        "The install.sh script performs a complete 20-step deployment on a fresh Raspberry Pi OS "
        "(64-bit Bookworm) installation. It configures everything from system packages to "
        "firewall rules.",
        s_body
    ))

    story.append(BlackBox(
        "ssh pi@raspberrypi.local\n"
        "git clone https://github.com/SKULLFIRE07/PiFace360.git\n"
        "cd PiFace360\n"
        "sudo bash piface/setup/install.sh\n"
        "\n"
        "# Installation takes ~15 minutes\n"
        "# System reboots automatically when complete"
    ))

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Installation Steps", s_h2))

    steps = [
        "System package updates (apt upgrade)",
        "NetworkManager configuration (ignore wlan0)",
        "Disable systemd-resolved (prevent DNS conflicts)",
        "Static IP assignment (192.168.4.1 on wlan0)",
        "hostapd WiFi access point setup",
        "dnsmasq DHCP server configuration",
        "Create piface system user & group",
        "Directory structure creation",
        "Copy application code to /opt/piface",
        "Python virtual environment setup",
        "Install Python packages (with piwheels)",
        "Generate self-signed TLS certificate",
        "Generate JWT secret key",
        "Nginx reverse proxy configuration",
        "Install systemd service files",
        "Configure iptables firewall rules",
        "Configure logrotate for log management",
        "Hardware boot config (RTC, USB current, CPU governor)",
        "Enable and start PiFace services",
        "Filesystem optimization (noatime)",
    ]

    for i, step in enumerate(steps, 1):
        story.append(Paragraph(
            f'<font color="#999999">{i:02d}.</font>&nbsp;&nbsp;{step}',
            ParagraphStyle('Step', parent=s_body_sm, spaceAfter=1.5 * mm)
        ))

    story.append(PageBreak())

    # ─── 11. NETWORK & SECURITY ───
    story.append(Paragraph("11 — Network & Security", s_h1))
    story.append(SectionDivider())
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph("Network Topology", s_h2))

    story.append(BlackBox(
        "┌─────────────┐    WiFi (192.168.4.0/24)    ┌──────────────┐\n"
        "│  Phone /    │ <─────────────────────────> │  RPi5        │\n"
        "│  Laptop     │   SSID: AttendanceSystem    │  192.168.4.1 │\n"
        "└─────────────┘   Password: configurable    └──────────────┘\n"
        "                                                    │\n"
        "                   HTTPS :443 <── Nginx <── Uvicorn (unix socket)\n"
        "                   Captive portal auto-redirect"
    ))

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Security Layers", s_h2))

    security_data = [
        ["Layer", "Implementation", "Details"],
        ["Authentication", "JWT (python-jose)", "Token-based login, configurable expiry"],
        ["CSRF Protection", "Double-submit cookie", "Cookie + header token validation"],
        ["Password Storage", "bcrypt (passlib)", "Salted hash, configurable rounds"],
        ["Rate Limiting", "Custom middleware", "Brute-force protection on /auth/*"],
        ["Transport", "TLS 1.2+ (self-signed)", "Nginx handles HTTPS termination"],
        ["Firewall", "iptables", "Only ports 80, 443, 22 open"],
        ["Access Control", "Role-based", "Admin role required for settings/reset"],
    ]
    t = Table(security_data, colWidths=[75, 95, content_width - 170])
    t.setStyle(ts_default)
    story.append(t)

    story.append(PageBreak())

    # ─── 12. DEVELOPMENT SETUP ───
    story.append(Paragraph("12 — Development Setup", s_h1))
    story.append(SectionDivider())
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph(
        "PiFace360 can be developed on any machine — no Raspberry Pi required. The face engine "
        "and LED controller gracefully fall back to mock mode when hardware is not detected.",
        s_body
    ))

    story.append(Paragraph("Backend", s_h2))
    story.append(BlackBox(
        "cd PiFace360\n"
        "python3.11 -m venv venv\n"
        "source venv/bin/activate\n"
        "pip install -r piface/requirements.txt\n"
        "\n"
        "# Seed demo data (20 employees, 14 days)\n"
        "python seed_data.py\n"
        "\n"
        "# Start backend on port 8001\n"
        "python -m uvicorn piface.backend.main:app --host 0.0.0.0 --port 8001 --reload"
    ))

    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("Frontend", s_h2))
    story.append(BlackBox(
        "cd piface/frontend\n"
        "npm install\n"
        "npx vite --port 5173\n"
        "\n"
        "# Vite proxies /api/* to localhost:8001\n"
        "# Open http://localhost:5173\n"
        "# Login: admin / admin123"
    ))

    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("Seed Data", s_h2))
    story.append(Paragraph(
        "The seed_data.py script generates 20 employees across 7 departments with 14 days of "
        "attendance history, leave records, holidays, and mock face embeddings. Employee #1 is "
        "Aryan Budukh and #2 is Reeva Shah. Data is deterministic (seed=42) for consistency.",
        s_body
    ))

    story.append(PageBreak())

    # ─── 13. FILE STRUCTURE ───
    story.append(Paragraph("13 — File Structure", s_h1))
    story.append(SectionDivider())
    story.append(Spacer(1, 3 * mm))

    story.append(BlackBox(
        "PiFace360/\n"
        "├── piface/\n"
        "│   ├── backend/                # FastAPI application\n"
        "│   │   ├── main.py            #   App factory, middleware\n"
        "│   │   ├── models.py          #   SQLAlchemy ORM models\n"
        "│   │   ├── schemas.py         #   Pydantic schemas\n"
        "│   │   ├── database.py        #   DB engine, sessions\n"
        "│   │   ├── security.py        #   JWT, CSRF, rate limiting\n"
        "│   │   └── routes/            #   13 endpoint modules\n"
        "│   │\n"
        "│   ├── frontend/               # React SPA\n"
        "│   │   ├── src/pages/         #   10 page components\n"
        "│   │   ├── src/components/    #   Reusable UI components\n"
        "│   │   ├── src/hooks/         #   useAuth, useSSE\n"
        "│   │   └── src/api/           #   Axios client\n"
        "│   │\n"
        "│   ├── core/                   # AI & Hardware\n"
        "│   │   ├── face_engine.py     #   Recognition loop\n"
        "│   │   ├── camera.py          #   Camera capture\n"
        "│   │   ├── tracker.py         #   Multi-object tracking\n"
        "│   │   ├── led_controller.py  #   GPIO LED control\n"
        "│   │   └── event_bus.py       #   IPC communication\n"
        "│   │\n"
        "│   ├── setup/                  # Deployment configs\n"
        "│   │   ├── install.sh         #   One-script installer\n"
        "│   │   ├── nginx.conf         #   Reverse proxy\n"
        "│   │   ├── hostapd.conf       #   WiFi hotspot\n"
        "│   │   └── piface-*.service   #   3 systemd services\n"
        "│   │\n"
        "│   └── requirements.txt        # Python deps\n"
        "│\n"
        "├── seed_data.py                # Demo data generator\n"
        "├── README.md                   # Project documentation\n"
        "└── .gitignore"
    ))

    story.append(Spacer(1, 8 * mm))

    # Final footer
    story.append(SectionDivider())
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(
        "<b>PiFace360</b> — Built with edge AI for the real world.",
        ParagraphStyle('Final', parent=s_body, alignment=TA_CENTER, fontSize=11,
                       textColor=BLACK, fontName='Helvetica-Bold')
    ))
    story.append(Paragraph(
        "github.com/SKULLFIRE07/PiFace360",
        ParagraphStyle('FinalURL', parent=s_body, alignment=TA_CENTER, fontSize=9,
                       textColor=LIGHT_GRAY)
    ))

    # Build
    doc.build(story, onFirstPage=first_page, onLaterPages=header_footer)
    print(f"PDF generated: {OUTPUT}")


if __name__ == "__main__":
    build_pdf()
