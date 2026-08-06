"""
Hospital contact workflow — FULLY BUILT (this project's actual scope, along
with decision_engine.py).

No real hospital API exists yet, so the hospital directory itself is a local
simulated dataset — but the logic around it (nearest/best-match selection,
contact attempts with retry, confirmation tracking, and persistence so state
survives a restart) is real, tested application logic, not a placeholder.

Swap _HOSPITAL_DIRECTORY / _place_contact_attempt for a real dispatch API
integration later without touching decision_engine.py, app.py, or the DB
schema — contact_hospital() is the only entry point callers need.
"""

from __future__ import annotations

from database import db
from models import (
    Hospital,
    HospitalContactRecord,
    HospitalContactStatus,
    Patient,
    SymptomAssessment,
)

import config

# Local simulated hospital directory (name, specialties, distance, phone).
# A real integration would replace this with a lookup against an actual
# hospital/dispatch API or GPS-based directory (see "Future Improvements" in
# AI_Health_Decision_System_Overview.md: "GPS-based nearest hospital lookup").
_HOSPITAL_DIRECTORY: list[Hospital] = [
    Hospital(
        name="Riverside General Hospital",
        specialty_tags=["general", "emergency"],
        distance_km=3.2,
        phone="+1-555-0101",
    ),
    Hospital(
        name="St. Mary's Trauma Center",
        specialty_tags=["trauma", "critical", "cardiac", "emergency"],
        distance_km=6.8,
        phone="+1-555-0102",
    ),
    Hospital(
        name="Northside Urgent Care",
        specialty_tags=["general", "urgent"],
        distance_km=1.5,
        phone="+1-555-0103",
    ),
    Hospital(
        name="City Children's Hospital",
        specialty_tags=["pediatric", "general"],
        distance_km=8.1,
        phone="+1-555-0104",
    ),
]

_CRITICAL_TAGS = {"trauma", "critical", "cardiac"}


def select_hospital(assessment: SymptomAssessment) -> Hospital:
    """
    Pick the best hospital for this case: critical cases prefer a
    trauma/cardiac-capable facility (nearest among those); everything else
    goes to the nearest hospital that handles general/emergency/urgent care.
    """
    if assessment.severity_enum.value == "critical":
        candidates = [h for h in _HOSPITAL_DIRECTORY if _CRITICAL_TAGS & set(h.specialty_tags)]
    else:
        candidates = [
            h for h in _HOSPITAL_DIRECTORY
            if {"general", "emergency", "urgent"} & set(h.specialty_tags)
        ]
    if not candidates:
        candidates = _HOSPITAL_DIRECTORY

    return min(candidates, key=lambda h: h.distance_km)


def _estimate_eta_minutes(distance_km: float) -> int:
    """Rough simulated travel-time estimate (no real traffic/routing data)."""
    return max(5, round(distance_km * 2.5))


def _place_contact_attempt(attempt_number: int) -> bool:
    """
    Simulate one contact attempt (phone/dispatch call to the hospital).
    Returns True if the hospital confirmed. Deterministic (not random) so the
    retry path is reliably demonstrable/testable — see
    config.HOSPITAL_SIMULATED_FAILURES_BEFORE_SUCCESS.
    """
    return attempt_number > config.HOSPITAL_SIMULATED_FAILURES_BEFORE_SUCCESS


def contact_hospital(
    patient: Patient, assessment: SymptomAssessment, assessment_id: int
) -> HospitalContactRecord:
    """
    Select a hospital and attempt to contact it, retrying up to
    config.HOSPITAL_CONTACT_MAX_RETRIES times. Persists progress after every
    attempt so the outcome (and how many attempts it took) survives a
    restart, not just the final result.
    """
    hospital = select_hospital(assessment)
    contact = HospitalContactRecord(
        id=None,
        assessment_id=assessment_id,
        hospital_name=hospital.name,
        distance_km=hospital.distance_km,
        eta_minutes=_estimate_eta_minutes(hospital.distance_km),
        attempts=0,
        status=HospitalContactStatus.PENDING.value,
    )
    contact = db.save_hospital_contact(contact)
    print(
        f"[hospital] Selected {hospital.name} ({hospital.distance_km} km, "
        f"ETA {contact.eta_minutes} min) for {patient.name} — {assessment.problem} "
        f"({assessment.severity})"
    )

    for attempt in range(1, config.HOSPITAL_CONTACT_MAX_RETRIES + 1):
        confirmed = _place_contact_attempt(attempt)

        if confirmed:
            confirmation_id = f"HC-{contact.id:05d}-{attempt}"
            contact.attempts = attempt
            contact.status = HospitalContactStatus.CONFIRMED.value
            contact.confirmation_id = confirmation_id
            db.update_hospital_contact(
                contact.id,
                status=HospitalContactStatus.CONFIRMED,
                attempts=attempt,
                confirmation_id=confirmation_id,
            )
            print(f"[hospital] Attempt {attempt}: {hospital.name} confirmed ({confirmation_id})")
            return contact

        print(f"[hospital] Attempt {attempt}: no answer from {hospital.name}, retrying...")
        contact.attempts = attempt
        db.update_hospital_contact(
            contact.id, status=HospitalContactStatus.CONTACTED, attempts=attempt
        )

    contact.status = HospitalContactStatus.FAILED.value
    db.update_hospital_contact(
        contact.id, status=HospitalContactStatus.FAILED, attempts=contact.attempts
    )
    print(
        f"[hospital] Failed to reach {hospital.name} after "
        f"{config.HOSPITAL_CONTACT_MAX_RETRIES} attempts."
    )
    return contact
