"""
Booking engine: takes a triage result (severity + department) and reserves
an actual TimeSlot, creating an Appointment record.

Design:
- Level 1 (Emergency): no booking — patient is instructed to go to the ER.
- Level 2 (Urgent): earliest slot, PREFERRING priority-reserved slots.
- Level 3 (Semi-urgent): earliest slot, no preference.
- Level 4 (Routine): earliest slot, AVOIDING priority-reserved slots
  (those are kept free for urgent walk-ins).
"""

from sqlalchemy.orm import Session
from sqlalchemy import asc
from models import TimeSlot, Doctor, Appointment, AppointmentStatus


class NoAvailableSlotError(Exception):
    pass


def book_appointment(
    db: Session,
    patient_id: int,
    department_id: int,
    severity_level: int,
    triage_session_id: int = None,
) -> Appointment:
    if severity_level == 1:
        raise ValueError(
            "Severity level 1 (Emergency) should never be booked — "
            "the patient must be directed to the ER instead."
        )

    query = (
        db.query(TimeSlot)
        .join(Doctor, TimeSlot.doctor_id == Doctor.id)
        .filter(Doctor.department_id == department_id)
        .filter(TimeSlot.is_booked == False)  # noqa: E712
    )

    if severity_level == 2:
        # Urgent: prefer priority-reserved slots first, then fall back to any slot
        priority_slot = (
            query.filter(TimeSlot.is_priority_reserved == True)  # noqa: E712
            .order_by(asc(TimeSlot.start_time))
            .first()
        )
        chosen_slot = priority_slot or query.order_by(asc(TimeSlot.start_time)).first()

    elif severity_level == 4:
        # Routine: avoid priority-reserved slots, leave them free for urgent cases
        chosen_slot = (
            query.filter(TimeSlot.is_priority_reserved == False)  # noqa: E712
            .order_by(asc(TimeSlot.start_time))
            .first()
        )
        # Fallback: if somehow only priority slots remain, take one anyway
        if not chosen_slot:
            chosen_slot = query.order_by(asc(TimeSlot.start_time)).first()

    else:
        # Semi-urgent (level 3): earliest available, no preference
        chosen_slot = query.order_by(asc(TimeSlot.start_time)).first()

    if not chosen_slot:
        raise NoAvailableSlotError(
            f"No available time slots found for department_id={department_id}."
        )

    # Reserve it
    chosen_slot.is_booked = True

    appointment = Appointment(
        patient_id=patient_id,
        time_slot_id=chosen_slot.id,
        department_id=department_id,
        severity_level=severity_level,
        status=AppointmentStatus.booked,
        triage_session_id=triage_session_id,
    )

    db.add(appointment)
    db.commit()
    db.refresh(appointment)

    return appointment