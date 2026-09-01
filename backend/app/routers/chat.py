import uuid
import copy
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from database import SessionLocal
from models import Patient, Department, TimeSlot, Doctor
from auth import decode_access_token
from triage_engine import TriageEngine
from booking_engine import book_appointment, NoAvailableSlotError
import llm_service_mock as llm_service

router = APIRouter(prefix="/chat", tags=["chat"])
engine = TriageEngine()

# In-memory session store: { session_id: {...state...} }
# NOTE for report: for production this should move to Redis or a DB table
# (e.g. persisting to TriageSession as the conversation progresses), but
# in-memory is sufficient to demonstrate the full flow for a PFE.
SESSIONS: dict = {}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class StartChatRequest(BaseModel):
    token: str


class StartChatResponse(BaseModel):
    session_id: str
    message: str


class ChatMessageRequest(BaseModel):
    session_id: str
    message: str
    category: Optional[str] = None  # set when the user clicks a category button


class ChatMessageResponse(BaseModel):
    message: str
    finished: bool
    result: Optional[dict] = None
    allergy_warning: Optional[str] = None
    appointment: Optional[dict] = None


class CategoryOption(BaseModel):
    category: str
    label: str


class CategoriesResponse(BaseModel):
    categories: list[CategoryOption]


class BackRequest(BaseModel):
    session_id: str


class BackResponse(BaseModel):
    message: str
    can_go_back: bool
    category_reset: bool


@router.post("/start", response_model=StartChatResponse)
def start_chat(payload: StartChatRequest, db: Session = Depends(get_db)):
    try:
        token_data = decode_access_token(payload.token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")

    acting_user_id = int(token_data["sub"])
    patient_id = int(token_data["acting_as"])

    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    acting_user = db.query(Patient).filter(Patient.id == acting_user_id).first()

    if not patient or not acting_user:
        raise HTTPException(status_code=404, detail="Patient record not found.")

    guardian_name = acting_user.first_name if acting_user.id != patient.id else None

    greeting = llm_service.generate_greeting(
        patient_first_name=patient.first_name,
        medical_history=patient.medical_history or [],
        is_minor=patient.is_minor,
        guardian_name=guardian_name,
    )

    session_id = str(uuid.uuid4())
    SESSIONS[session_id] = {
        "patient_id": patient.id,
        "acting_user_id": acting_user.id,
        "allergies": patient.allergies or [],
        "category": None,
        "engine_state": None,
        "history": [],  # stack of previous engine_state snapshots, for the Back button
        "conversation_log": [{"role": "assistant", "text": greeting}],
    }

    return StartChatResponse(session_id=session_id, message=greeting)


@router.get("/categories", response_model=CategoriesResponse)
def get_categories():
    return CategoriesResponse(categories=engine.list_categories())


@router.post("/message", response_model=ChatMessageResponse)
def send_message(payload: ChatMessageRequest, db: Session = Depends(get_db)):
    session = SESSIONS.get(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired.")

    session["conversation_log"].append({"role": "user", "text": payload.message})

    # 1. Global red flag scan on raw text — overrides everything if matched
    forced_level = engine.scan_for_global_red_flags(payload.message)
    if forced_level is not None:
        result = {
            "severity_level": forced_level,
            "label": "Emergency",
            "action": "instruct_er_immediately",
            "recommended_department": None,
        }
        session["engine_state"] = {"result": result}
        return ChatMessageResponse(
            message=(
                "Based on what you've described, this may be a medical emergency. "
                "Please go to the nearest emergency room immediately, or call emergency "
                "services. Do not wait for an appointment."
            ),
            finished=True,
            result=result,
        )

    # 2. Allergy conflict check (only meaningful once a category/context exists,
    #    but we check on every message since a patient might mention a med anytime)
    allergy_warning = None
    if session["allergies"]:
        conflict = llm_service.check_allergy_conflict(payload.message, session["allergies"])
        if conflict.get("conflict"):
            allergy_warning = (
                f"⚠️ Our records show an allergy to {conflict['matched_allergy']}. "
                f"{conflict.get('note', '')}"
            )

    # 3. No category chosen yet -> either use the explicit category (button click)
    #    or classify the free-text message into a category, then start the tree
    if session["category"] is None:
        if payload.category:
            categories = engine.list_categories()
            valid_ids = {c["category"] for c in categories}
            if payload.category not in valid_ids:
                raise HTTPException(status_code=400, detail="Unknown category.")
            category = payload.category
        else:
            categories = engine.list_categories()
            category = llm_service.classify_category(payload.message, categories)

        session["category"] = category
        session["history"] = []  # fresh tree, fresh history
        state = engine.start_session(category)
        session["engine_state"] = state

        session["conversation_log"].append({"role": "assistant", "text": state["question_text"]})
        return ChatMessageResponse(
            message=state["question_text"],
            finished=False,
            allergy_warning=allergy_warning,
        )

    # 4. Mid-tree -> extract structured answer for the CURRENT question, advance the engine
    state = session["engine_state"]

    # Save a snapshot BEFORE advancing, so the Back button can restore it
    session["history"].append(copy.deepcopy(state))

    structured_value = llm_service.extract_structured_answer(
        question_text=state["question_text"],
        question_type=state["question_type"],
        patient_message=payload.message,
    )

    try:
        state = engine.answer(state, structured_value)
    except ValueError as e:
        # Extraction gave something the engine couldn't map — ask again,
        # and drop the snapshot we just pushed since nothing actually advanced
        session["history"].pop()
        return ChatMessageResponse(
            message="Sorry, could you clarify that answer? " + state["question_text"],
            finished=False,
            allergy_warning=allergy_warning,
        )

    session["engine_state"] = state

    if state["result"] is not None:
        # Tree finished — resolve department name to a real Department if possible
        dept_name = state["result"]["recommended_department"]
        dept = None
        if dept_name:
            dept = db.query(Department).filter(Department.name == dept_name).first()

        final_message = _build_result_message(state["result"])
        appointment_details = None

        severity = state["result"]["severity_level"]

        if severity != 1 and dept is not None:
            try:
                appointment = book_appointment(
                    db=db,
                    patient_id=session["patient_id"],
                    department_id=dept.id,
                    severity_level=severity,
                    triage_session_id=None,  # not persisting TriageSession to DB yet
                )
                slot = (
                    db.query(TimeSlot)
                    .filter(TimeSlot.id == appointment.time_slot_id)
                    .first()
                )
                doctor = db.query(Doctor).filter(Doctor.id == slot.doctor_id).first()

                appointment_details = {
                    "appointment_id": appointment.id,
                    "doctor": f"{doctor.title} {doctor.name}",
                    "department": dept_name,
                    "start_time": slot.start_time.isoformat(),
                    "status": appointment.status.value,
                }
                final_message += (
                    f" You're booked with {doctor.title} {doctor.name} "
                    f"({dept_name}) on {slot.start_time.strftime('%A, %b %d at %H:%M')}."
                )
            except NoAvailableSlotError:
                final_message += (
                    " Unfortunately, no slots are currently available in that "
                    "department — please contact the clinic directly."
                )

        session["conversation_log"].append({"role": "assistant", "text": final_message})

        return ChatMessageResponse(
            message=final_message,
            finished=True,
            result={**state["result"], "department_id": dept.id if dept else None},
            allergy_warning=allergy_warning,
            appointment=appointment_details,
        )

    session["conversation_log"].append({"role": "assistant", "text": state["question_text"]})
    return ChatMessageResponse(
        message=state["question_text"],
        finished=False,
        allergy_warning=allergy_warning,
    )


@router.post("/back", response_model=BackResponse)
def go_back(payload: BackRequest):
    session = SESSIONS.get(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired.")

    if not session["history"]:
        # No answered questions to undo in the current tree.
        # Reset all the way to the category-picker step.
        session["category"] = None
        session["engine_state"] = None
        return BackResponse(
            message="Let's start over — what's the reason for your visit?",
            can_go_back=False,
            category_reset=True,
        )

    previous_state = session["history"].pop()
    session["engine_state"] = previous_state
    # category stays exactly as it was — going back within a tree never
    # changes which category/tree we're in, only which question we're on
    remaining = len(session["history"])

    return BackResponse(
        message=previous_state["question_text"],
        can_go_back=remaining > 0,
        category_reset=False,
    )


def _build_result_message(result: dict) -> str:
    level = result["severity_level"]
    if level == 1:
        return (
            "Based on your answers, this looks like it needs urgent emergency care. "
            "Please go to the nearest emergency room now."
        )
    elif level == 2:
        return (
            f"Based on your answers, we recommend an urgent same-day appointment "
            f"in {result['recommended_department']}. We'll find you the next available slot."
        )
    elif level == 3:
        return (
            f"Based on your answers, we recommend booking with {result['recommended_department']} "
            "soon. We'll show you the next available appointments."
        )
    else:
        return (
            f"This looks routine. We'll book you a standard appointment with "
            f"{result['recommended_department']}."
        )