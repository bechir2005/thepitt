from triage_engine import TriageEngine

engine = TriageEngine()

print("Available categories:")
for c in engine.list_categories():
    print(f"  - {c['category']}: {c['label']}")

print("\n--- Simulating a chest_pain session ---\n")

state = engine.start_session("chest_pain")
print(f"Q: {state['question_text']}")

# Simulate: no radiating pain -> pain level 9 -> yes shortness of breath -> should hit EMERGENCY
state = engine.answer(state, "no")
print(f"Q: {state['question_text']}")

state = engine.answer(state, 9)
print(f"Q: {state['question_text']}")

state = engine.answer(state, "yes")

print("\nFinal result:")
print(state["result"])
print("\nExtracted fields:")
print(state["extracted_fields"])
print("\nRed flag triggered:", state["red_flag_triggered"])

print("\n--- Testing global red flag scan ---")
text = "I feel dizzy and my face is drooping on one side"
level = engine.scan_for_global_red_flags(text)
print(f"Text: '{text}' -> forced severity level: {level}")