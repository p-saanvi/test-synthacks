"""
Real symptom analysis — adapts qwen_triage.py's Qwen3-14B triage decision
into the SymptomAssessment shape decision_engine.py / remedy_manager.py /
emergency_manager.py already expect, so nothing downstream had to change.

qwen_triage.triage() decides REMEDY / AMBULANCE / REQUEST_MEDIA directly
(it doesn't reason in terms of decision_engine.py's low/medium/high/critical
severity scale) — this adapter maps that onto `severity` via the model's own
`urgency` field, which uses the same four levels. REQUEST_MEDIA fails safe
to a critical assessment: there's no photo/video upload step in the web app
yet, so — same as qwen_triage's own CLI does when no media is provided — we
don't leave the patient stuck, we route to the emergency path.

Requires OPENROUTER_API_KEY to be set (see qwen_triage.py's module
docstring for setup). The previous keyword-based mock this replaced is
still worth knowing about if you ever need to run/demo without an API key —
see git history.
"""

from __future__ import annotations

import os

import qwen_triage
from models import Patient, SymptomAssessment

_REACTION_TIME_BY_URGENCY = {
    "low": 3600,
    "medium": 1800,
    "high": 180,
    "critical": 60,
}


class LLMResponseError(RuntimeError):
    """Raised when symptom analysis cannot produce a valid assessment."""


def _patient_to_profile(patient: Patient) -> qwen_triage.PatientProfile:
    contacts = [
        qwen_triage.EmergencyContact(
            name=c.name, phone=c.phone or "", relationship=c.relationship
        )
        for c in patient.emergency_contacts
    ]
    return qwen_triage.PatientProfile(
        name=patient.name,
        gender=patient.gender or "unspecified",
        height_cm=patient.height_cm or 0.0,
        weight_kg=patient.weight_kg or 0.0,
        location=patient.location or "",
        emergency_contacts=contacts,
        insurance_provider=patient.insurance_provider,
        insurance_id=patient.insurance_id,
    )


def assess_symptoms(symptoms_text: str, patient: Patient) -> SymptomAssessment:
    text = (symptoms_text or "").strip()
    if not text:
        raise LLMResponseError("No symptoms text provided.")

    if not os.environ.get("OPENROUTER_API_KEY"):
        raise LLMResponseError(
            "OPENROUTER_API_KEY is not set. Copy .env.example to .env and add your key."
        )

    profile = _patient_to_profile(patient)
    result = qwen_triage.triage(profile, text)

    if result.decision == "REQUEST_MEDIA":
        return SymptomAssessment(
            problem="Needs in-person evaluation",
            severity="critical",
            remedy=(
                "The AI could not safely assess this from a text description alone "
                f"({result.media_request_reason or 'more detail needed'}) and this app "
                "doesn't support photo/video upload yet — seek in-person medical "
                "evaluation immediately."
            ),
            reaction_time=_REACTION_TIME_BY_URGENCY["critical"],
        )

    urgency = result.urgency if result.urgency in _REACTION_TIME_BY_URGENCY else (
        "critical" if result.decision == "AMBULANCE" else "medium"
    )
    problem = (result.reasoning or result.decision.replace("_", " ").title())[:120]
    if result.decision == "AMBULANCE":
        remedy = (
            result.remedy_advice
            or "This has been flagged as a potential emergency — seek immediate medical care."
        )
    else:
        remedy = result.remedy_advice or "Rest and monitor your symptoms."

    return SymptomAssessment(
        problem=problem,
        severity=urgency,
        remedy=remedy,
        reaction_time=_REACTION_TIME_BY_URGENCY[urgency],
    )
