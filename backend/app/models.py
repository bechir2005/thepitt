from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, JSON, Text, Enum
)
from sqlalchemy.orm import relationship
from database import Base
import datetime
import enum


# ---------- Clinic ----------
class Clinic(Base):
    __tablename__ = "clinics"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    address = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    departments = relationship("Department", back_populates="clinic")


# ---------- Department ----------
class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False)
    name = Column(String, nullable=False)  # e.g. "Cardiology", "Pediatrics"

    clinic = relationship("Clinic", back_populates="departments")
    doctors = relationship("Doctor", back_populates="department")


# ---------- Doctor ----------
class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, index=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)
    name = Column(String, nullable=False)
    title = Column(String, default="Dr.")

    department = relationship("Department", back_populates="doctors")
    time_slots = relationship("TimeSlot", back_populates="doctor")


# ---------- TimeSlot ----------
class TimeSlot(Base):
    __tablename__ = "time_slots"

    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    is_booked = Column(Boolean, default=False)
    is_priority_reserved = Column(Boolean, default=False)

    doctor = relationship("Doctor", back_populates="time_slots")
    appointment = relationship("Appointment", back_populates="time_slot", uselist=False)


# ---------- Patient ----------
class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    id_card_number = Column(String, unique=True, index=True, nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    date_of_birth = Column(DateTime, nullable=False)
    is_minor = Column(Boolean, default=False)
    guardian_id = Column(Integer, ForeignKey("patients.id"), nullable=True)
    phone = Column(String, nullable=True)
    medical_history = Column(JSON, default=list)
    allergies = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    guardian = relationship("Patient", remote_side=[id], backref="dependents")
    triage_sessions = relationship(
        "TriageSession", back_populates="patient", foreign_keys="TriageSession.patient_id"
    )
    appointments = relationship("Appointment", back_populates="patient")


# ---------- Severity Enum ----------
class SeverityLevel(enum.IntEnum):
    EMERGENCY = 1
    URGENT = 2
    SEMI_URGENT = 3
    ROUTINE = 4


# ---------- AppointmentStatus Enum ----------
class AppointmentStatus(str, enum.Enum):
    booked = "booked"
    completed = "completed"
    cancelled = "cancelled"
    no_show = "no_show"


# ---------- TriageSession ----------
class TriageSession(Base):
    __tablename__ = "triage_sessions"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    acting_user_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    symptom_category = Column(String, nullable=True)
    conversation_log = Column(JSON, default=list)
    extracted_fields = Column(JSON, default=dict)
    red_flag_triggered = Column(Boolean, default=False)
    severity_result = Column(Integer, nullable=True)  # maps to SeverityLevel
    recommended_department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    patient = relationship("Patient", back_populates="triage_sessions", foreign_keys=[patient_id])
    acting_user = relationship("Patient", foreign_keys=[acting_user_id])
    recommended_department = relationship("Department")
    appointment = relationship("Appointment", back_populates="triage_session", uselist=False)


# ---------- Appointment ----------
class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    time_slot_id = Column(Integer, ForeignKey("time_slots.id"), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False)
    triage_session_id = Column(Integer, ForeignKey("triage_sessions.id"), nullable=True)
    severity_level = Column(Integer, nullable=True)
    status = Column(Enum(AppointmentStatus), default=AppointmentStatus.booked)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    patient = relationship("Patient", back_populates="appointments")
    time_slot = relationship("TimeSlot", back_populates="appointment")
    department = relationship("Department")
    triage_session = relationship("TriageSession", back_populates="appointment")