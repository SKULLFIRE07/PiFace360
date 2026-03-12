"""
PiFace Attendance System - Pydantic v2 Schemas

Request / response models for the FastAPI layer.  Fully standalone (no
SQLAlchemy imports).
"""

import datetime as _dt
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

# Type aliases to avoid shadowing by field names (e.g. a field called "date")
_Date = _dt.date
_DateTime = _dt.datetime


# ===================================================================
# Person
# ===================================================================
class PersonBase(BaseModel):
    name: str
    department: Optional[str] = None
    job_title: Optional[str] = None
    phone: Optional[str] = None


class PersonCreate(PersonBase):
    employee_id: Optional[str] = None


class PersonResponse(PersonBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: Optional[str] = None
    is_unknown: bool = False
    enrolled_at: Optional[_DateTime] = None
    is_active: bool = True


# ===================================================================
# AttendanceEvent
# ===================================================================
class AttendanceEventCreate(BaseModel):
    person_id: int
    event_type: str = Field(..., pattern="^(IN|OUT)$")
    timestamp: _DateTime


class AttendanceEventUpdate(BaseModel):
    event_type: Optional[str] = Field(default=None, pattern="^(IN|OUT)$")
    timestamp: Optional[_DateTime] = None


class AttendanceEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    person_id: int
    event_type: str
    timestamp: _DateTime
    confidence: Optional[float] = None
    snapshot_path: Optional[str] = None
    direction_vector: Optional[str] = None
    date: Optional[_Date] = None
    is_manual: bool = False
    corrected_by: Optional[int] = None


# ===================================================================
# DailySummary
# ===================================================================
class DailySummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    person_id: int
    date: _Date
    first_in_time: Optional[_DateTime] = None
    last_out_time: Optional[_DateTime] = None
    total_in_out_events: Optional[int] = None
    total_hours_worked: Optional[float] = None
    longest_break_minutes: Optional[int] = None
    total_break_minutes: Optional[int] = None
    is_late: Optional[bool] = None
    is_early_leave: Optional[bool] = None
    overtime_minutes: Optional[int] = None
    status: Optional[str] = None


# ===================================================================
# SystemSetting
# ===================================================================
class SettingUpdate(BaseModel):
    key: str
    value: str


class SettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    value: Optional[str] = None
    updated_at: Optional[_DateTime] = None


# ===================================================================
# Auth
# ===================================================================
class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ===================================================================
# LeaveRecord
# ===================================================================
class LeaveRecordCreate(BaseModel):
    person_id: int
    date: _Date
    leave_type: str
    note: Optional[str] = None


class LeaveRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    person_id: int
    date: _Date
    leave_type: str
    note: Optional[str] = None


# ===================================================================
# Holiday
# ===================================================================
class HolidayCreate(BaseModel):
    date: _Date
    name: str


class HolidayResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: _Date
    name: str


# ===================================================================
# Calibration
# ===================================================================
class CalibrationSet(BaseModel):
    in_vector: list[float]
    out_vector: list[float]


# ===================================================================
# System Status
# ===================================================================
class SystemStatusResponse(BaseModel):
    uptime: str
    db_size_mb: float
    disk_free_mb: float
    cpu_temp: Optional[float] = None
    camera_status: str
    last_detection: Optional[_DateTime] = None


# ===================================================================
# Unknown rename
# ===================================================================
class UnknownRename(BaseModel):
    name: str
    employee_id: Optional[str] = None
    department: Optional[str] = None
    job_title: Optional[str] = None
    phone: Optional[str] = None


# ===================================================================
# Generic API wrapper
# ===================================================================
class ApiResponse(BaseModel):
    success: bool
    data: Any = None
    error: Optional[str] = None


# ===================================================================
# Report
# ===================================================================
class ReportGenerateRequest(BaseModel):
    date: str
