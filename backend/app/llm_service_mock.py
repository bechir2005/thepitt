"""
MOCK LLM service — for free local development and testing.

This has the EXACT same function signatures as the real llm_service.py
(which calls the Claude API). It uses simple keyword matching and basic
heuristics instead of a real LLM, so the whole chat flow can be built and
tested without spending any money.

To switch to the real API later: just change the import in routers/chat.py
from `import llm_service_mock as llm_service` back to `import llm_service`.
"""

import re


# ---------- Category classification (keyword-based) ----------

CATEGORY_KEYWORDS = {
    "chest_pain": ["chest", "heart", "cardiac"],
    "breathing_issues": ["breath", "breathing", "wheez", "asthma", "suffoc"],
    "injury_trauma": ["injury", "broke", "broken", "fell", "fall", "cut", "bleeding", "accident"],
    "fever_infection": ["fever", "temperature", "infection", "hot", "chills"],
    "general_pain": ["pain", "hurts", "ache", "sore"],
    "mental_health": ["anxious", "anxiety", "depress", "sad", "stress", "panic"],
    "pediatric_specific": ["child", "kid", "baby", "toddler", "son", "daughter"],
    "routine_checkup": ["checkup", "check-up", "follow-up", "followup", "prescription", "renewal"],
}


def classify_category(patient_message: str, available_categories: list) -> str:
    text = patient_message.lower()
    valid_ids = {c["category"] for c in available_categories}

    for category, keywords in CATEGORY_KEYWORDS.items():
        if category not in valid_ids:
            continue
        if any(kw in text for kw in keywords):
            return category

    return "general_pain"


# ---------- Structured answer extraction (regex/keyword-based) ----------

YES_WORDS = ["yes", "yeah", "yep", "correct", "true", "affirmative"]
NO_WORDS = ["no", "nope", "not really", "false", "negative"]


def extract_structured_answer(question_text: str, question_type: str, patient_message: str):
    text = patient_message.lower().strip()

    if question_type == "yes_no":
        if any(w in text for w in YES_WORDS):
            return "yes"
        if any(w in text for w in NO_WORDS):
            return "no"
        # Ambiguous — don't guess. Returning None causes the engine to
        # report "no valid transition," which the chat router turns into
        # a clarification request instead of silently assuming an answer.
        # This matters most for red-flag questions, where guessing wrong
        # in either direction is worse than just asking again.
        return None

    if question_type in ("scale_1_10",):
        match = re.search(r"\b(10|[1-9])\b", text)
        if match:
            return int(match.group(1))
        if any(w in text for w in ["unbearable", "worst", "severe", "really bad"]):
            return 9
        if any(w in text for w in ["moderate", "medium"]):
            return 5
        if any(w in text for w in ["mild", "slight", "a little"]):
            return 2
        return 5

    if question_type in ("duration_minutes", "duration_days"):
        match = re.search(r"\b(\d+)\b", text)
        if match:
            return int(match.group(1))
        if "hour" in text:
            hrs = re.search(r"(\d+)\s*hour", text)
            hours = int(hrs.group(1)) if hrs else 1
            return hours * 60 if question_type == "duration_minutes" else 1
        return 30 if question_type == "duration_minutes" else 1

    if question_type == "categorical":
        for word in ["significant", "severe"]:
            if word in text:
                return "significant"
        for word in ["moderate", "medium"]:
            if word in text:
                return "moderate"
        for word in ["mild", "slight"]:
            if word in text:
                return "mild"
        for word in ["checkup", "check-up", "check up"]:
            if word in text:
                return "checkup"
        for word in ["follow up", "follow-up", "followup"]:
            if word in text:
                return "follow_up"
        for word in ["prescription", "renewal", "refill"]:
            if word in text:
                return "prescription"
        return text.split()[0] if text.split() else "mild"

    return text


# ---------- Allergy conflict check (keyword-based) ----------

def check_allergy_conflict(patient_message: str, known_allergies: list) -> dict:
    text = patient_message.lower()
    for allergy in known_allergies:
        if allergy.lower() in text:
            return {
                "conflict": True,
                "matched_allergy": allergy,
                "note": (
                    f"You mentioned something related to '{allergy}', which is "
                    "listed as a known allergy on your record. Please confirm "
                    "with staff before taking any related medication."
                ),
            }
    return {"conflict": False, "matched_allergy": None, "note": None}


# ---------- Greeting generation (templated) ----------

def generate_greeting(patient_first_name: str, medical_history: list, is_minor: bool, guardian_name: str = None) -> str:
    if is_minor and guardian_name:
        return (
            f"Hello {guardian_name}, welcome. I'll be helping you with "
            f"{patient_first_name}'s visit today. What's the reason for the visit?"
        )
    return f"Hello {patient_first_name}, welcome back. What brings you in today?"