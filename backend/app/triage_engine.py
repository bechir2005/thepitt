"""
Triage engine: loads JSON decision trees and walks them one answer at a time.

Usage pattern (called from a router / chatbot layer):

    engine = TriageEngine()

    # Start a session for a category
    state = engine.start_session("chest_pain")
    # state = {"current_question": "q1", "text": "...", "extracted_fields": {}, ...}

    # Submit an answer, get the next step
    state = engine.answer(state, "no")
    # state either has another "current_question", or a "result" if the tree ended
"""

import json
import os
from typing import Optional

TRIAGE_TREES_DIR = os.path.join(os.path.dirname(__file__), "triage_trees")


class TriageEngine:
    def __init__(self):
        self._cache = {}

    # ---------- Loading ----------

    def _load_tree(self, category: str) -> dict:
        if category in self._cache:
            return self._cache[category]

        path = os.path.join(TRIAGE_TREES_DIR, f"{category}.json")
        if not os.path.exists(path):
            raise ValueError(f"No triage tree found for category '{category}'")

        with open(path, "r", encoding="utf-8") as f:
            tree = json.load(f)

        self._cache[category] = tree
        return tree

    def load_global_red_flags(self) -> list:
        path = os.path.join(TRIAGE_TREES_DIR, "global_red_flags.json")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("global_red_flags", [])

    def list_categories(self) -> list:
        """Returns all available category labels, for the bot's first question."""
        categories = []
        for filename in os.listdir(TRIAGE_TREES_DIR):
            if filename.endswith(".json") and filename != "global_red_flags.json":
                tree = self._load_tree(filename.replace(".json", ""))
                categories.append({"category": tree["category"], "label": tree["label"]})
        return categories

    # ---------- Session flow ----------

    def start_session(self, category: str) -> dict:
        tree = self._load_tree(category)
        first_q_id = tree["entry_question"]
        question = tree["questions"][first_q_id]

        return {
            "category": category,
            "current_question": first_q_id,
            "question_text": question["text"],
            "question_type": question["type"],
            "extracted_fields": {},
            "red_flag_triggered": False,
            "result": None,
        }

    def answer(self, state: dict, raw_answer) -> dict:
        """
        Takes the current state + the patient's raw answer to the current
        question, and returns the updated state (either the next question,
        or a final result).
        """
        tree = self._load_tree(state["category"])
        q_id = state["current_question"]
        question = tree["questions"][q_id]

        # Store the answer in extracted_fields if this question has a named field
        field_name = question.get("field", q_id)
        state["extracted_fields"][field_name] = raw_answer

        # Check red flag
        if question.get("red_flag_if") is not None:
            if self._normalize(raw_answer) == self._normalize(question["red_flag_if"]):
                state["red_flag_triggered"] = True

        # Determine the bucket this answer falls into (yes/no, scale range, duration, categorical)
        bucket = self._resolve_bucket(question, raw_answer)

        next_step = question["next"].get(bucket)
        if next_step is None:
            raise ValueError(
                f"No transition found for answer '{raw_answer}' (bucket '{bucket}') "
                f"on question '{q_id}' in category '{state['category']}'"
            )

        if next_step.startswith("RESULT_"):
            result = tree["results"][next_step]
            state["current_question"] = None
            state["question_text"] = None
            state["question_type"] = None
            state["result"] = {
                "severity_level": result["severity_level"],
                "label": result["label"],
                "action": result["action"],
                "recommended_department": result.get("recommended_department"),
            }
        else:
            next_question = tree["questions"][next_step]
            state["current_question"] = next_step
            state["question_text"] = next_question["text"]
            state["question_type"] = next_question["type"]

        return state

    # ---------- Answer bucket resolution ----------

    def _resolve_bucket(self, question: dict, raw_answer) -> Optional[str]:
        qtype = question["type"]

        if qtype == "yes_no":
            return self._normalize(raw_answer)  # "yes" or "no"

        if qtype in ("scale_1_10",):
            value = int(raw_answer)
            for bucket_range in question["next"].keys():
                if self._value_in_range(value, bucket_range):
                    return bucket_range
            return None

        if qtype == "duration_minutes":
            value = int(raw_answer)
            for bucket_range in question["next"].keys():
                if self._value_matches_threshold(value, bucket_range):
                    return bucket_range
            return None

        if qtype == "duration_days":
            value = int(raw_answer)
            for bucket_range in question["next"].keys():
                if self._value_matches_threshold(value, bucket_range):
                    return bucket_range
            return None

        if qtype == "categorical":
            return self._normalize(raw_answer)

        raise ValueError(f"Unknown question type: {qtype}")

    # ---------- Helpers ----------

    @staticmethod
    def _normalize(value) -> str:
        return str(value).strip().lower()

    @staticmethod
    def _value_in_range(value: int, range_str: str) -> bool:
        # e.g. "8-10", "4-7", "1-3"
        if "-" in range_str:
            low, high = range_str.split("-")
            return int(low) <= value <= int(high)
        return False

    @staticmethod
    def _value_matches_threshold(value: int, threshold_str: str) -> bool:
        # e.g. ">30", "<=30", ">3", "<=3"
        if threshold_str.startswith(">="):
            return value >= int(threshold_str[2:])
        if threshold_str.startswith("<="):
            return value <= int(threshold_str[2:])
        if threshold_str.startswith(">"):
            return value > int(threshold_str[1:])
        if threshold_str.startswith("<"):
            return value < int(threshold_str[1:])
        return False

    # ---------- Global red flag scanning (free text) ----------

    def scan_for_global_red_flags(self, free_text: str) -> Optional[int]:
        """
        Scans raw patient free-text (e.g. from the LLM layer) for global
        red-flag keywords. Returns the severity level to force (usually 1)
        if a match is found, otherwise None.

        Matching is done on a per-word basis (all significant words in the
        keyword phrase must appear somewhere in the text) rather than an
        exact substring match, since patients rarely phrase things using
        the exact keyword wording (e.g. "face is drooping" vs "face drooping").
        """
        text = free_text.lower()
        text_words = set(text.split())

        # Common filler words we don't require to match individually
        stopwords = {"is", "are", "was", "were", "a", "an", "the", "my", "on", "in", "of"}

        for flag in self.load_global_red_flags():
            keyword_words = [
                w for w in flag["keyword"].lower().split() if w not in stopwords
            ]
            if all(w in text_words for w in keyword_words):
                return flag["severity_level"]

        return None