"""
Seed script: Creates 20 employees with attendance events, daily summaries,
leave records, and holidays for demo purposes.
"""

import random
import struct
import sys
from datetime import datetime, date, timedelta, timezone

import numpy as np

# Ensure the project is importable
sys.path.insert(0, ".")

from piface.backend.database import SessionLocal, init_db
from piface.backend.models import (
    AttendanceEvent,
    DailySummary,
    Holiday,
    LeaveRecord,
    Person,
)

# ---------------------------------------------------------------------------
# 20 realistic employees
# ---------------------------------------------------------------------------
EMPLOYEES = [
    {"name": "Aryan Budukh",     "employee_id": "EMP001", "department": "Engineering",   "job_title": "Lead Developer",       "phone": "+1-555-0101"},
    {"name": "Reeva Shah",       "employee_id": "EMP002", "department": "Engineering",   "job_title": "Software Engineer",    "phone": "+1-555-0102"},
    {"name": "Priya Sharma",     "employee_id": "EMP003", "department": "Engineering",   "job_title": "Backend Developer",    "phone": "+1-555-0103"},
    {"name": "Raj Patel",        "employee_id": "EMP004", "department": "Engineering",   "job_title": "Frontend Developer",   "phone": "+1-555-0104"},
    {"name": "Ananya Singh",     "employee_id": "EMP005", "department": "Engineering",   "job_title": "DevOps Engineer",      "phone": "+1-555-0105"},
    {"name": "Vikram Desai",     "employee_id": "EMP006", "department": "Engineering",   "job_title": "QA Engineer",          "phone": "+1-555-0106"},
    {"name": "Neha Gupta",       "employee_id": "EMP007", "department": "Product",       "job_title": "Product Manager",      "phone": "+1-555-0107"},
    {"name": "Aditya Joshi",     "employee_id": "EMP008", "department": "Product",       "job_title": "UX Designer",          "phone": "+1-555-0108"},
    {"name": "Sneha Kulkarni",   "employee_id": "EMP009", "department": "Product",       "job_title": "UI Designer",          "phone": "+1-555-0109"},
    {"name": "Rohan Mehta",      "employee_id": "EMP010", "department": "Sales",         "job_title": "Sales Manager",        "phone": "+1-555-0110"},
    {"name": "Kavita Reddy",     "employee_id": "EMP011", "department": "Sales",         "job_title": "Account Executive",    "phone": "+1-555-0111"},
    {"name": "Amit Verma",       "employee_id": "EMP012", "department": "Sales",         "job_title": "Business Development", "phone": "+1-555-0112"},
    {"name": "Deepa Nair",       "employee_id": "EMP013", "department": "HR",            "job_title": "HR Manager",           "phone": "+1-555-0113"},
    {"name": "Sanjay Kumar",     "employee_id": "EMP014", "department": "HR",            "job_title": "Recruiter",            "phone": "+1-555-0114"},
    {"name": "Meera Iyer",       "employee_id": "EMP015", "department": "Finance",       "job_title": "Finance Manager",      "phone": "+1-555-0115"},
    {"name": "Karthik Rao",      "employee_id": "EMP016", "department": "Finance",       "job_title": "Accountant",           "phone": "+1-555-0116"},
    {"name": "Pooja Bhatt",      "employee_id": "EMP017", "department": "Marketing",     "job_title": "Marketing Lead",       "phone": "+1-555-0117"},
    {"name": "Nikhil Saxena",    "employee_id": "EMP018", "department": "Marketing",     "job_title": "Content Writer",       "phone": "+1-555-0118"},
    {"name": "Ritu Agarwal",     "employee_id": "EMP019", "department": "Operations",    "job_title": "Operations Manager",   "phone": "+1-555-0119"},
    {"name": "Suresh Menon",     "employee_id": "EMP020", "department": "Operations",    "job_title": "Facilities Coord.",    "phone": "+1-555-0120"},
]


def _make_embedding(seed: int) -> bytes:
    """Generate a deterministic mock 512-d float32 embedding (2048 bytes)."""
    rng = np.random.default_rng(seed)
    vec = rng.standard_normal(512).astype(np.float32)
    vec = vec / np.linalg.norm(vec)
    return vec.tobytes()


def _make_face_image(name: str) -> bytes:
    """Generate a simple colored JPEG with the person's initials using OpenCV."""
    try:
        import cv2

        # Deterministic color based on name
        h = hash(name) % 360
        # Create HSV image and convert to BGR
        img = np.zeros((200, 200, 3), dtype=np.uint8)
        # Use a nice background color
        colors = [
            (52, 152, 219),   # blue
            (46, 204, 113),   # green
            (231, 76, 60),    # red
            (155, 89, 182),   # purple
            (241, 196, 15),   # yellow
            (230, 126, 34),   # orange
            (26, 188, 156),   # teal
            (52, 73, 94),     # dark blue
        ]
        color = colors[hash(name) % len(colors)]
        img[:] = color

        # Add initials
        initials = "".join(w[0].upper() for w in name.split()[:2])
        font = cv2.FONT_HERSHEY_SIMPLEX
        text_size = cv2.getTextSize(initials, font, 2.0, 3)[0]
        x = (200 - text_size[0]) // 2
        y = (200 + text_size[1]) // 2
        cv2.putText(img, initials, (x, y), font, 2.0, (255, 255, 255), 3)

        _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])
        return buf.tobytes()
    except ImportError:
        # Minimal 1x1 JPEG fallback
        return bytes([
            0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00,
            0x01, 0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00,
            0xFF, 0xDB, 0x00, 0x43, 0x00, *([0x01] * 64),
            0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01, 0x00, 0x01, 0x01, 0x01, 0x11, 0x00,
            0xFF, 0xC4, 0x00, 0x1F, 0x00,
            0x00, 0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01,
            0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
            0x08, 0x09, 0x0A, 0x0B,
            0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01, 0x00, 0x00,
            0x3F, 0x00, 0x7B, 0x40,
            0xFF, 0xD9,
        ])


def seed():
    init_db()
    db = SessionLocal()

    # Check if data already exists
    existing = db.query(Person).filter(Person.is_active.is_(True), Person.is_unknown.is_(False)).count()
    if existing >= 20:
        print(f"Already {existing} employees in DB. Skipping seed.")
        db.close()
        return

    # Clear existing seed data if partial
    if existing > 0:
        print(f"Found {existing} existing employees. Adding remaining...")

    today = date.today()
    random.seed(42)

    person_ids = []

    # --- Create employees ---
    for i, emp in enumerate(EMPLOYEES):
        # Skip if employee_id already exists
        exists = db.query(Person).filter(Person.employee_id == emp["employee_id"]).first()
        if exists:
            person_ids.append(exists.id)
            continue

        person = Person(
            name=emp["name"],
            employee_id=emp["employee_id"],
            department=emp["department"],
            job_title=emp["job_title"],
            phone=emp["phone"],
            face_embedding=_make_embedding(seed=1000 + i),
            face_image=_make_face_image(emp["name"]),
            is_unknown=False,
            is_active=True,
            enrolled_at=datetime.now(timezone.utc) - timedelta(days=random.randint(30, 180)),
        )
        db.add(person)
        db.flush()
        person_ids.append(person.id)
        print(f"  Created: {emp['name']} ({emp['employee_id']}) - {emp['department']}")

    db.commit()
    print(f"\n✓ {len(person_ids)} employees ready.\n")

    # --- Create attendance events for past 14 days ---
    print("Creating attendance events...")
    events_created = 0

    for day_offset in range(14, -1, -1):  # 14 days ago to today
        d = today - timedelta(days=day_offset)

        # Skip weekends
        if d.weekday() >= 5:
            continue

        for pid in person_ids:
            # 85% chance of being present on any given day
            if random.random() > 0.85:
                continue

            # IN event: 8:00-9:30 AM
            in_hour = random.randint(8, 9)
            in_min = random.randint(0, 59) if in_hour == 8 else random.randint(0, 30)
            in_time = datetime(d.year, d.month, d.day, in_hour, in_min, 0, tzinfo=timezone.utc)

            # OUT event: 5:00-7:00 PM
            out_hour = random.randint(17, 19)
            out_min = random.randint(0, 59)
            out_time = datetime(d.year, d.month, d.day, out_hour, out_min, 0, tzinfo=timezone.utc)

            # Check if events already exist
            existing_ev = db.query(AttendanceEvent).filter(
                AttendanceEvent.person_id == pid,
                AttendanceEvent.date == d,
            ).first()
            if existing_ev:
                continue

            in_event = AttendanceEvent(
                person_id=pid,
                event_type="IN",
                timestamp=in_time,
                confidence=round(random.uniform(0.85, 0.99), 4),
                date=d,
                is_manual=False,
            )
            out_event = AttendanceEvent(
                person_id=pid,
                event_type="OUT",
                timestamp=out_time,
                confidence=round(random.uniform(0.85, 0.99), 4),
                date=d,
                is_manual=False,
            )
            db.add(in_event)
            db.add(out_event)
            events_created += 2

            # Daily summary
            hours_worked = round((out_time - in_time).total_seconds() / 3600, 2)
            is_late = in_hour >= 9 and in_min > 15

            existing_summary = db.query(DailySummary).filter(
                DailySummary.person_id == pid,
                DailySummary.date == d,
            ).first()
            if not existing_summary:
                summary = DailySummary(
                    person_id=pid,
                    date=d,
                    first_in_time=in_time,
                    last_out_time=out_time,
                    total_in_out_events=2,
                    total_hours_worked=hours_worked,
                    longest_break_minutes=random.randint(30, 60),
                    total_break_minutes=random.randint(30, 90),
                    is_late=is_late,
                    is_early_leave=out_hour < 17,
                    overtime_minutes=max(0, (out_hour - 17) * 60 + out_min) if out_hour >= 17 else 0,
                    status="PRESENT",
                )
                db.add(summary)

    db.commit()
    print(f"  ✓ {events_created} attendance events created.\n")

    # --- Leave records ---
    print("Creating leave records...")
    leaves_created = 0
    leave_types = ["SICK", "CASUAL", "ANNUAL", "PERSONAL"]

    for pid in random.sample(person_ids, min(8, len(person_ids))):
        # Random leave day in past 14 days (weekday)
        for _ in range(random.randint(1, 2)):
            day_offset = random.randint(1, 14)
            leave_date = today - timedelta(days=day_offset)
            if leave_date.weekday() >= 5:
                continue

            existing_leave = db.query(LeaveRecord).filter(
                LeaveRecord.person_id == pid,
                LeaveRecord.date == leave_date,
            ).first()
            if existing_leave:
                continue

            leave = LeaveRecord(
                person_id=pid,
                date=leave_date,
                leave_type=random.choice(leave_types),
                note=random.choice([
                    "Doctor appointment",
                    "Family event",
                    "Personal day",
                    "Not feeling well",
                    "Travel",
                    None,
                ]),
            )
            db.add(leave)

            # Also add daily summary as ON_LEAVE
            existing_summary = db.query(DailySummary).filter(
                DailySummary.person_id == pid,
                DailySummary.date == leave_date,
            ).first()
            if existing_summary:
                existing_summary.status = "ON_LEAVE"
            else:
                db.add(DailySummary(
                    person_id=pid,
                    date=leave_date,
                    status="ON_LEAVE",
                ))
            leaves_created += 1

    db.commit()
    print(f"  ✓ {leaves_created} leave records created.\n")

    # --- Holidays ---
    print("Creating holidays...")
    holidays = [
        (date(2026, 1, 26), "Republic Day"),
        (date(2026, 3, 14), "Holi"),
        (date(2026, 8, 15), "Independence Day"),
        (date(2026, 10, 2), "Gandhi Jayanti"),
        (date(2026, 10, 20), "Diwali"),
        (date(2026, 12, 25), "Christmas"),
    ]
    holidays_created = 0
    for hdate, hname in holidays:
        existing_h = db.query(Holiday).filter(Holiday.date == hdate).first()
        if not existing_h:
            db.add(Holiday(date=hdate, name=hname))
            holidays_created += 1

    db.commit()
    print(f"  ✓ {holidays_created} holidays created.\n")

    # --- Summary ---
    total_emp = db.query(Person).filter(Person.is_active.is_(True), Person.is_unknown.is_(False)).count()
    total_events = db.query(AttendanceEvent).count()
    total_leaves = db.query(LeaveRecord).count()
    total_holidays = db.query(Holiday).count()

    print("=" * 50)
    print(f"  Employees:         {total_emp}")
    print(f"  Attendance Events: {total_events}")
    print(f"  Leave Records:     {total_leaves}")
    print(f"  Holidays:          {total_holidays}")
    print("=" * 50)
    print("\n✓ Seed data complete! Start the backend and frontend to see it.\n")

    db.close()


if __name__ == "__main__":
    seed()
