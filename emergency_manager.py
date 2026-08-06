"""
Emergency escalation orchestrator.

Coordinates the two halves of the High/Critical path:
  - Hospital contact: hospital_manager.py — FULLY BUILT (this project's scope).
  - Family notifications + insurance/cost: still MOCK stubs owned by the
    teammate ("Family notifications", "Insurance lookup", "Insurance
    coverage and limit checking" — see AI_Health_Decision_System_Overview.md).

handle_emergency() returns an EmergencySummary so the web app can render the
full outcome on a page instead of only printing to the console/log.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cost_estimator
import hospital_manager
import insurance_manager
from database import db
from models import AssessmentRecord, AssessmentStatus, HospitalContactRecord, Patient, SymptomAssessment
from notifications import email as notify_email
from notifications import phone as notify_phone
from notifications import sms as notify_sms
from notifications import whatsapp as notify_whatsapp


@dataclass
class EmergencySummary:
    hospital: HospitalContactRecord
    notifications_sent: list[str] = field(default_factory=list)
    estimated_cost: float = 0.0
    coverage: "insurance_manager.CoverageResult | None" = None


def notify_emergency_contacts(patient: Patient, assessment: SymptomAssessment) -> list[str]:
    """MOCK — see notifications/*.py. Owned by teammate."""
    if not patient.emergency_contacts:
        print(f"[emergency] No emergency contacts on file for {patient.name}.")
        return ["No emergency contacts on file."]

    message = (
        f"URGENT: {patient.name} has been assessed with a {assessment.severity} "
        f"severity issue ({assessment.problem}) and emergency services/hospital "
        f"have been contacted. This is an automated alert from the AI Health "
        f"Decision Support System."
    )

    results: list[str] = []
    for contact in patient.emergency_contacts:
        channel = (contact.preferred_channel or "phone").lower()
        if channel == "email":
            ok = notify_email.send_email(contact.email, "Emergency alert", message)
        elif channel == "sms":
            ok = notify_sms.send_sms(contact.phone, message)
        elif channel == "whatsapp":
            ok = notify_whatsapp.send_whatsapp(contact.whatsapp or contact.phone, message)
        else:
            channel = "phone"
            ok = notify_phone.place_call(contact.phone, message)
        status = "sent" if ok else "skipped (missing contact info)"
        results.append(f"{contact.name} via {channel}: {status}")
    return results


def handle_emergency(
    patient: Patient, assessment: SymptomAssessment, record: AssessmentRecord
) -> EmergencySummary:
    """Full High/Critical escalation path: hospital + family + insurance/cost."""
    print("\n=== ESCALATING: High/Critical severity ===")

    hospital_contact = hospital_manager.contact_hospital(patient, assessment, record.id)

    notifications_sent = notify_emergency_contacts(patient, assessment)

    policy = insurance_manager.lookup_insurance(patient)
    estimated_cost = cost_estimator.estimate_cost(assessment)
    coverage = insurance_manager.check_coverage(policy, estimated_cost)
    print(
        f"[insurance] Estimated cost ${estimated_cost:,.2f} — "
        f"covered ${coverage.covered_amount:,.2f}, patient owes ${coverage.patient_owes:,.2f}. "
        f"{coverage.notes}"
    )

    if record.id is not None:
        db.update_assessment_status(record.id, AssessmentStatus.ESCALATED)
    print("=== Emergency workflow complete ===\n")

    return EmergencySummary(
        hospital=hospital_contact,
        notifications_sent=notifications_sent,
        estimated_cost=estimated_cost,
        coverage=coverage,
    )
