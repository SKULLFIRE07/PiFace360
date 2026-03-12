"""
PiFace Attendance System - SQLAlchemy ORM Models

All database tables are defined here.
"""

from datetime import datetime, date as date_type

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from piface.backend.database import Base


# ---------------------------------------------------------------------------
# Person
# ---------------------------------------------------------------------------
class Person(Base):
    __tablename__ = "persons"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    employee_id = Column(String, unique=True, nullable=True)
    department = Column(String, nullable=True)
    job_title = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    face_embedding = Column(
        LargeBinary,
        nullable=False,
        info={"description": "512-dimensional float32 vector (2048 bytes)"},
    )
    face_image = Column(LargeBinary, nullable=True)
    is_unknown = Column(Boolean, default=False, nullable=False)
    unknown_index = Column(Integer, nullable=True)
    enrolled_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True, nullable=False)

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "length(face_embedding) = 2048",
            name="ck_persons_face_embedding_len",
        ),
        Index("ix_persons_is_active", "is_active"),
        Index("ix_persons_is_unknown", "is_unknown"),
    )

    # Relationships
    attendance_events = relationship(
        "AttendanceEvent", back_populates="person", lazy="dynamic"
    )
    daily_summaries = relationship(
        "DailySummary", back_populates="person", lazy="dynamic"
    )
    leave_records = relationship(
        "LeaveRecord", back_populates="person", lazy="dynamic"
    )

    def __repr__(self) -> str:
        return f"<Person id={self.id} name={self.name!r}>"


# ---------------------------------------------------------------------------
# AttendanceEvent
# ---------------------------------------------------------------------------
class AttendanceEvent(Base):
    __tablename__ = "attendance_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    person_id = Column(
        Integer,
        ForeignKey("persons.id", ondelete="RESTRICT"),
        nullable=False,
    )
    event_type = Column(String, nullable=False)  # "IN" or "OUT"
    timestamp = Column(DateTime, nullable=False)
    confidence = Column(Float, nullable=True)
    snapshot_path = Column(String, nullable=True)
    direction_vector = Column(String, nullable=True)  # JSON-encoded
    date = Column(Date, nullable=True)  # computed from timestamp in app layer
    is_manual = Column(Boolean, default=False, nullable=False)
    corrected_by = Column(Integer, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "event_type IN ('IN', 'OUT')",
            name="ck_attendance_events_event_type",
        ),
        Index("ix_attendance_events_person_date", "person_id", "date"),
        Index("ix_attendance_events_date", "date"),
    )

    # Relationships
    person = relationship("Person", back_populates="attendance_events")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Compute date from timestamp if not explicitly provided
        if self.date is None and self.timestamp is not None:
            if isinstance(self.timestamp, datetime):
                self.date = self.timestamp.date()

    def __repr__(self) -> str:
        return (
            f"<AttendanceEvent id={self.id} person_id={self.person_id} "
            f"type={self.event_type!r} ts={self.timestamp}>"
        )


# ---------------------------------------------------------------------------
# DailySummary
# ---------------------------------------------------------------------------
class DailySummary(Base):
    __tablename__ = "daily_summaries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    person_id = Column(
        Integer,
        ForeignKey("persons.id", ondelete="CASCADE"),
        nullable=False,
    )
    date = Column(Date, nullable=False)
    first_in_time = Column(DateTime, nullable=True)
    last_out_time = Column(DateTime, nullable=True)
    total_in_out_events = Column(Integer, nullable=True)
    total_hours_worked = Column(Float, nullable=True)
    longest_break_minutes = Column(Integer, nullable=True)
    total_break_minutes = Column(Integer, nullable=True)
    is_late = Column(Boolean, nullable=True)
    is_early_leave = Column(Boolean, nullable=True)
    overtime_minutes = Column(Integer, nullable=True)
    status = Column(String, nullable=True)  # PRESENT/ABSENT/HALF_DAY/ON_LEAVE/HOLIDAY

    __table_args__ = (
        UniqueConstraint("person_id", "date", name="uq_daily_summaries_person_date"),
        CheckConstraint(
            "status IN ('PRESENT', 'ABSENT', 'HALF_DAY', 'ON_LEAVE', 'HOLIDAY')",
            name="ck_daily_summaries_status",
        ),
    )

    # Relationships
    person = relationship("Person", back_populates="daily_summaries")

    def __repr__(self) -> str:
        return (
            f"<DailySummary id={self.id} person_id={self.person_id} "
            f"date={self.date} status={self.status!r}>"
        )


# ---------------------------------------------------------------------------
# SystemSetting
# ---------------------------------------------------------------------------
class SystemSetting(Base):
    __tablename__ = "system_settings"

    key = Column(String, primary_key=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<SystemSetting key={self.key!r}>"


# ---------------------------------------------------------------------------
# AuthUser
# ---------------------------------------------------------------------------
class AuthUser(Base):
    __tablename__ = "auth_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="admin", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<AuthUser id={self.id} username={self.username!r}>"


# ---------------------------------------------------------------------------
# AuditLog
# ---------------------------------------------------------------------------
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    action = Column(String, nullable=False)
    target_table = Column(String, nullable=True)
    target_id = Column(Integer, nullable=True)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    performed_by = Column(String, nullable=True)
    performed_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<AuditLog id={self.id} action={self.action!r}>"


# ---------------------------------------------------------------------------
# LeaveRecord
# ---------------------------------------------------------------------------
class LeaveRecord(Base):
    __tablename__ = "leave_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    person_id = Column(
        Integer,
        ForeignKey("persons.id", ondelete="CASCADE"),
        nullable=False,
    )
    date = Column(Date, nullable=False)
    leave_type = Column(String, nullable=False)
    note = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("person_id", "date", name="uq_leave_records_person_date"),
    )

    # Relationships
    person = relationship("Person", back_populates="leave_records")

    def __repr__(self) -> str:
        return (
            f"<LeaveRecord id={self.id} person_id={self.person_id} "
            f"date={self.date} type={self.leave_type!r}>"
        )


# ---------------------------------------------------------------------------
# Holiday
# ---------------------------------------------------------------------------
class Holiday(Base):
    __tablename__ = "holidays"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, unique=True, nullable=False)
    name = Column(String, nullable=False)

    def __repr__(self) -> str:
        return f"<Holiday id={self.id} date={self.date} name={self.name!r}>"


# ---------------------------------------------------------------------------
# SchemaMigration
# ---------------------------------------------------------------------------
class SchemaMigration(Base):
    __tablename__ = "schema_migrations"

    version = Column(Integer, primary_key=True)
    applied_at = Column(DateTime, default=datetime.utcnow)
    description = Column(String, nullable=True)

    def __repr__(self) -> str:
        return f"<SchemaMigration version={self.version}>"
