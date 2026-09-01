"""
Add a single patient to the database WITHOUT wiping existing data
(unlike seed.py, which clears everything first).

Run from thepitt/backend/app with the venv active, and with DATABASE_URL
pointed at whichever database you want to add to (local or Render).

Usage:
    python add_patient.py
"""

import datetime
from database import SessionLocal
from models import Patient

db = SessionLocal()

try:
    print("=== Add a new patient ===\n")

    id_card_number = input("ID card number: ").strip()

    # Check it doesn't already exist
    existing = db.query(Patient).filter(Patient.id_card_number == id_card_number).first()
    if existing:
        print(f"\nA patient with ID card '{id_card_number}' already exists: "
              f"{existing.first_name} {existing.last_name} (id={existing.id}). Aborting.")
        exit()

    first_name = input("First name: ").strip()
    last_name = input("Last name: ").strip()

    dob_str = input("Date of birth (YYYY-MM-DD): ").strip()
    date_of_birth = datetime.datetime.strptime(dob_str, "%Y-%m-%d")

    today = datetime.datetime.now()
    age = today.year - date_of_birth.year - (
        (today.month, today.day) < (date_of_birth.month, date_of_birth.day)
    )
    is_minor = age < 18
    print(f"-> Computed age: {age}, is_minor: {is_minor}")

    guardian_id = None
    if is_minor:
        guardian_id_card = input(
            "This patient is a minor. Enter the GUARDIAN's existing ID card number: "
        ).strip()
        guardian = db.query(Patient).filter(
            Patient.id_card_number == guardian_id_card
        ).first()
        if not guardian:
            print(f"\nNo patient found with ID card '{guardian_id_card}'. "
                  "The guardian must already exist in the system. Aborting.")
            exit()
        if guardian.is_minor:
            print("\nThe guardian ID provided also belongs to a minor. Aborting.")
            exit()
        guardian_id = guardian.id
        print(f"-> Linked to guardian: {guardian.first_name} {guardian.last_name} (id={guardian.id})")

    phone = input("Phone number (optional, press Enter to skip): ").strip() or None

    history_raw = input(
        "Medical history, comma-separated (optional, e.g. 'Asthma, Hypertension'): "
    ).strip()
    medical_history = [h.strip() for h in history_raw.split(",") if h.strip()] if history_raw else []

    allergies_raw = input(
        "Allergies, comma-separated (optional, e.g. 'penicillin, peanuts'): "
    ).strip()
    allergies = [a.strip() for a in allergies_raw.split(",") if a.strip()] if allergies_raw else []

    new_patient = Patient(
        id_card_number=id_card_number,
        first_name=first_name,
        last_name=last_name,
        date_of_birth=date_of_birth,
        is_minor=is_minor,
        guardian_id=guardian_id,
        phone=phone,
        medical_history=medical_history,
        allergies=allergies,
    )

    db.add(new_patient)
    db.commit()
    db.refresh(new_patient)

    print(f"\n✅ Patient created successfully: {new_patient.first_name} "
          f"{new_patient.last_name} (id={new_patient.id}, ID card={new_patient.id_card_number})")

except Exception as e:
    db.rollback()
    print(f"\n❌ Failed to add patient: {e}")
finally:
    db.close()