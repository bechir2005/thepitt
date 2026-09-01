from pydantic import BaseModel
from typing import Optional, List
import datetime


# ---------- Requests ----------

class LoginRequest(BaseModel):
    id_card_number: str


class GuardianLoginRequest(BaseModel):
    minor_id_card: str
    guardian_id_card: str


# ---------- Responses ----------

class PatientOut(BaseModel):
    id: int
    id_card_number: str
    first_name: str
    last_name: str
    date_of_birth: datetime.datetime
    is_minor: bool
    allergies: List[str] = []
    medical_history: List[str] = []

    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    status: str                     # "ok" | "minor_requires_guardian"
    message: Optional[str] = None
    token: Optional[str] = None
    patient: Optional[PatientOut] = None


class GuardianLoginResponse(BaseModel):
    status: str                     # "ok" | "error"
    message: Optional[str] = None
    token: Optional[str] = None
    acting_user: Optional[PatientOut] = None   # the guardian
    patient: Optional[PatientOut] = None       # the minor (subject of care)