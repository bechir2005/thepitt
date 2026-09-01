from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import SessionLocal
from models import Patient
from schemas import (
    LoginRequest,
    GuardianLoginRequest,
    LoginResponse,
    GuardianLoginResponse,
    PatientOut,
)
from auth import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    patient = (
        db.query(Patient)
        .filter(Patient.id_card_number == payload.id_card_number)
        .first()
    )

    if not patient:
        raise HTTPException(
            status_code=404,
            detail="ID card number not recognized. Please check the number or register.",
        )

    if patient.is_minor:
        return LoginResponse(
            status="minor_requires_guardian",
            message=(
                f"This ID belongs to a minor ({patient.first_name}). "
                "Please provide the guardian's ID card number to continue."
            ),
            token=None,
            patient=None,
        )

    token = create_access_token(
        {"sub": str(patient.id), "acting_as": patient.id}
    )
    return LoginResponse(
        status="ok",
        message=f"Welcome back, {patient.first_name}.",
        token=token,
        patient=PatientOut.model_validate(patient),
    )


@router.post("/login-as-guardian", response_model=GuardianLoginResponse)
def login_as_guardian(payload: GuardianLoginRequest, db: Session = Depends(get_db)):
    minor = (
        db.query(Patient)
        .filter(Patient.id_card_number == payload.minor_id_card)
        .first()
    )
    guardian = (
        db.query(Patient)
        .filter(Patient.id_card_number == payload.guardian_id_card)
        .first()
    )

    if not minor or not guardian:
        raise HTTPException(status_code=404, detail="One or both ID cards not recognized.")

    if not minor.is_minor:
        raise HTTPException(
            status_code=400,
            detail="The first ID card does not belong to a minor.",
        )

    if guardian.is_minor:
        raise HTTPException(
            status_code=400,
            detail="The guardian ID card must belong to a registered adult.",
        )

    if minor.guardian_id != guardian.id:
        raise HTTPException(
            status_code=403,
            detail="This adult is not the registered guardian for this minor.",
        )

    token = create_access_token(
        {"sub": str(guardian.id), "acting_as": minor.id}
    )
    return GuardianLoginResponse(
        status="ok",
        message=(
            f"Welcome, {guardian.first_name}. "
            f"You are booking on behalf of {minor.first_name}."
        ),
        token=token,
        acting_user=PatientOut.model_validate(guardian),
        patient=PatientOut.model_validate(minor),
    )