"""
Seed script for the hospital PFE database.

Run from thepitt/backend with the venv active:
    python -m app.seed
or, if run directly from inside app/:
    python seed.py
"""

import datetime
from database import SessionLocal, engine, Base
from models import (
    Clinic,
    Department,
    Doctor,
    TimeSlot,
    Patient,
)

# Make sure tables exist (no-op if Alembic already created them)
Base.metadata.create_all(bind=engine)

db = SessionLocal()

try:
    print("Clearing existing data (if any)...")
    # Delete in reverse dependency order to avoid FK errors
    db.query(TimeSlot).delete()
    db.query(Doctor).delete()
    db.query(Department).delete()
    db.query(Clinic).delete()
    db.query(Patient).delete()
    db.commit()

    print("Creating clinics...")
    clinic_a = Clinic(
        name="Clinique El Amen",
        address="12 Avenue Habib Bourguiba, Sousse",
        phone="73 200 100",
    )
    clinic_b = Clinic(
        name="Polyclinique Les Oliviers",
        address="45 Rue de la Republique, Sfax",
        phone="74 300 200",
    )
    db.add_all([clinic_a, clinic_b])
    db.commit()
    db.refresh(clinic_a)
    db.refresh(clinic_b)

    print("Creating departments...")
    cardio_a = Department(clinic_id=clinic_a.id, name="Cardiology")
    gp_a = Department(clinic_id=clinic_a.id, name="General Practice")
    pediatrics_a = Department(clinic_id=clinic_a.id, name="Pediatrics")
    pulmonology_a = Department(clinic_id=clinic_a.id, name="Pulmonology")
    orthopedics_a = Department(clinic_id=clinic_a.id, name="Orthopedics")

    neuro_b = Department(clinic_id=clinic_b.id, name="Neurology")
    gp_b = Department(clinic_id=clinic_b.id, name="General Practice")
    psychiatry_b = Department(clinic_id=clinic_b.id, name="Psychiatry")

    db.add_all([
        cardio_a, gp_a, pediatrics_a, pulmonology_a, orthopedics_a,
        neuro_b, gp_b, psychiatry_b,
    ])
    db.commit()
    for d in [
        cardio_a, gp_a, pediatrics_a, pulmonology_a, orthopedics_a,
        neuro_b, gp_b, psychiatry_b,
    ]:
        db.refresh(d)

    print("Creating doctors...")
    dr_amri = Doctor(department_id=cardio_a.id, name="Amri", title="Dr.")
    dr_bouzid = Doctor(department_id=gp_a.id, name="Bouzid", title="Dr.")
    dr_chaabane = Doctor(department_id=pediatrics_a.id, name="Chaabane", title="Dr.")
    dr_dhaouadi = Doctor(department_id=neuro_b.id, name="Dhaouadi", title="Dr.")
    dr_essid = Doctor(department_id=gp_b.id, name="Essid", title="Dr.")
    dr_fki = Doctor(department_id=pulmonology_a.id, name="Fki", title="Dr.")
    dr_gharbi = Doctor(department_id=orthopedics_a.id, name="Gharbi", title="Dr.")
    dr_hamdi = Doctor(department_id=psychiatry_b.id, name="Hamdi", title="Dr.")

    db.add_all([
        dr_amri, dr_bouzid, dr_chaabane, dr_dhaouadi, dr_essid,
        dr_fki, dr_gharbi, dr_hamdi,
    ])
    db.commit()
    for doc in [
        dr_amri, dr_bouzid, dr_chaabane, dr_dhaouadi, dr_essid,
        dr_fki, dr_gharbi, dr_hamdi,
    ]:
        db.refresh(doc)

    print("Creating time slots (next 5 days, 2 slots/day per doctor)...")
    doctors = [
        dr_amri, dr_bouzid, dr_chaabane, dr_dhaouadi, dr_essid,
        dr_fki, dr_gharbi, dr_hamdi,
    ]
    today = datetime.datetime.now().replace(minute=0, second=0, microsecond=0)

    slots = []
    for day_offset in range(1, 6):  # next 5 days
        day = today + datetime.timedelta(days=day_offset)
        for doc in doctors:
            morning_start = day.replace(hour=9)
            afternoon_start = day.replace(hour=14)
            slots.append(
                TimeSlot(
                    doctor_id=doc.id,
                    start_time=morning_start,
                    end_time=morning_start + datetime.timedelta(minutes=30),
                    is_booked=False,
                )
            )
            slots.append(
                TimeSlot(
                    doctor_id=doc.id,
                    start_time=afternoon_start,
                    end_time=afternoon_start + datetime.timedelta(minutes=30),
                    is_booked=False,
                    is_priority_reserved=True,  # afternoon slot reserved for urgent cases
                )
            )
    db.add_all(slots)
    db.commit()

    print("Creating patients...")

    # 1. A standard adult patient, no allergies
    patient_adult = Patient(
        id_card_number="09876543",
        first_name="Ahmed",
        last_name="Ben Ali",
        date_of_birth=datetime.datetime(1990, 5, 12),
        is_minor=False,
        guardian_id=None,
        phone="20111222",
        medical_history=["Hypertension diagnosed 2021"],
        allergies=[],
    )
    db.add(patient_adult)
    db.commit()
    db.refresh(patient_adult)

    # 2. Adult patient WITH an allergy (to test the conflict-flag feature)
    patient_allergy = Patient(
        id_card_number="08765432",
        first_name="Sonia",
        last_name="Trabelsi",
        date_of_birth=datetime.datetime(1985, 3, 22),
        is_minor=False,
        guardian_id=None,
        phone="20333444",
        medical_history=["Asthma"],
        allergies=["penicillin", "peanuts"],
    )
    db.add(patient_allergy)
    db.commit()
    db.refresh(patient_allergy)

    # 3. A guardian (adult) ...
    patient_guardian = Patient(
        id_card_number="07654321",
        first_name="Karim",
        last_name="Jlassi",
        date_of_birth=datetime.datetime(1982, 8, 30),
        is_minor=False,
        guardian_id=None,
        phone="20555666",
        medical_history=[],
        allergies=[],
    )
    db.add(patient_guardian)
    db.commit()
    db.refresh(patient_guardian)

    # ... and their minor child, linked via guardian_id
    patient_minor = Patient(
        id_card_number="06543210",
        first_name="Yassine",
        last_name="Jlassi",
        date_of_birth=datetime.datetime(2015, 1, 10),  # 11 years old
        is_minor=True,
        guardian_id=patient_guardian.id,
        phone=None,
        medical_history=["Seasonal allergies"],
        allergies=["dust"],
    )
    db.add(patient_minor)
    db.commit()
    db.refresh(patient_minor)

    print("\nSeed complete.")
    print(f"  Clinics: {db.query(Clinic).count()}")
    print(f"  Departments: {db.query(Department).count()}")
    print(f"  Doctors: {db.query(Doctor).count()}")
    print(f"  Time slots: {db.query(TimeSlot).count()}")
    print(f"  Patients: {db.query(Patient).count()}")
    print("\nTest accounts:")
    print(f"  Adult (no allergies):   ID {patient_adult.id_card_number} - {patient_adult.first_name} {patient_adult.last_name}")
    print(f"  Adult (has allergies):  ID {patient_allergy.id_card_number} - {patient_allergy.first_name} {patient_allergy.last_name}")
    print(f"  Guardian:               ID {patient_guardian.id_card_number} - {patient_guardian.first_name} {patient_guardian.last_name}")
    print(f"  Minor (linked to above):ID {patient_minor.id_card_number} - {patient_minor.first_name} {patient_minor.last_name}")

except Exception as e:
    db.rollback()
    print(f"Seed failed: {e}")
    raise
finally:
    db.close()