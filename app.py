"""
Flask web app entry point for the AI Health Decision Support System.

Flow (see README.md / AI_Health_Decision_System_Overview.md):

    User describes symptoms (web form)
            |
            v
    LLM analyzes symptoms (llm_interface.py)
            |
            v
    Structured JSON (models.SymptomAssessment)
            |
            v
    Decision Engine (decision_engine.py)
       +----+----+
       |         |
    Low/Medium  High/Critical
       |         |
     Remedy     Emergency
   (monitor page,        (emergency_manager.py:
    checked in later)     hospital + family + insurance/cost)
"""

from __future__ import annotations

import time

from flask import Flask, flash, redirect, render_template, request, session, url_for

import config
import decision_engine
import emergency_manager
import llm_interface
import remedy_manager
from database import db
from models import AssessmentRecord, EmergencyContact, Patient, SymptomAssessment

app = Flask(__name__)
app.secret_key = config.FLASK_SECRET_KEY

db.init_db()

CONTACT_SLOTS = 2  # number of emergency-contact form rows on the onboarding page

# Quick-severity test buttons: bypass symptom analysis entirely and feed a
# canned assessment straight into the decision engine / hospital workflow.
# For testing decision_engine.py + hospital_manager.py in isolation while a
# teammate builds the real severity/diagnosis piece separately.
_QUICK_TEST_ASSESSMENTS: dict[str, SymptomAssessment] = {
    "low": SymptomAssessment(
        problem="Test case: low severity",
        severity="low",
        remedy="Rest and monitor at home.",
        reaction_time=3600,
    ),
    "medium": SymptomAssessment(
        problem="Test case: medium severity",
        severity="medium",
        remedy="Rest, hydrate, and monitor closely.",
        reaction_time=1800,
    ),
    "high": SymptomAssessment(
        problem="Test case: high severity",
        severity="high",
        remedy="Contact a hospital promptly for evaluation.",
        reaction_time=180,
    ),
    "critical": SymptomAssessment(
        problem="Test case: critical severity",
        severity="critical",
        remedy="Seek emergency medical care immediately.",
        reaction_time=60,
    ),
}


def current_patient() -> Patient | None:
    patient_id = session.get("patient_id")
    if not patient_id:
        return None
    return db.get_patient_by_id(patient_id)


@app.context_processor
def inject_patient():
    return {"nav_patient": current_patient()}


@app.route("/", methods=["GET", "POST"])
def start():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Please enter your name.")
            return redirect(url_for("start"))
        existing = db.get_patient_by_name(name)
        if existing:
            session["patient_id"] = existing.id
            return redirect(url_for("assess"))
        return redirect(url_for("onboard", name=name))

    if current_patient():
        return redirect(url_for("assess"))
    return render_template("start.html")


@app.route("/onboard", methods=["GET", "POST"])
def onboard():
    name = request.values.get("name", "").strip()
    if not name:
        return redirect(url_for("start"))

    if request.method == "POST":
        insurance_id = request.form.get("insurance_id", "").strip() or None
        contacts: list[EmergencyContact] = []
        for i in range(1, CONTACT_SLOTS + 1):
            cname = request.form.get(f"contact_name_{i}", "").strip()
            if not cname:
                continue
            contacts.append(
                EmergencyContact(
                    name=cname,
                    relationship=request.form.get(f"contact_relationship_{i}", "").strip(),
                    phone=request.form.get(f"contact_phone_{i}", "").strip() or None,
                    email=request.form.get(f"contact_email_{i}", "").strip() or None,
                    whatsapp=request.form.get(f"contact_whatsapp_{i}", "").strip() or None,
                    preferred_channel=request.form.get(f"contact_channel_{i}", "phone"),
                )
            )
        patient = db.get_or_create_patient(
            Patient(id=None, name=name, insurance_id=insurance_id, emergency_contacts=contacts)
        )
        session["patient_id"] = patient.id
        flash(f"Welcome, {patient.name} — your profile is set up.")
        return redirect(url_for("assess"))

    return render_template("onboard.html", name=name, contact_slots=range(1, CONTACT_SLOTS + 1))


def _route_assessment(patient: Patient, symptoms_text: str, assessment: SymptomAssessment):
    """
    Shared by the real symptom-analysis path and the quick-severity test
    buttons: save the assessment, run the decision engine, and go to the
    remedy/monitor page or the emergency page accordingly.
    """
    record = AssessmentRecord.from_assessment(patient.id, symptoms_text, assessment)
    record = db.save_assessment(record)

    action = decision_engine.decide(assessment)
    if action == decision_engine.Action.REMEDY:
        remedy_manager.start_remedy(record)
        return redirect(url_for("view_assessment", assessment_id=record.id))

    summary = emergency_manager.handle_emergency(patient, assessment, record)
    return render_template(
        "emergency.html", patient=patient, assessment=assessment, summary=summary
    )


@app.route("/assess", methods=["GET", "POST"])
def assess():
    patient = current_patient()
    if not patient:
        return redirect(url_for("start"))

    if request.method == "POST":
        symptoms_text = request.form.get("symptoms", "").strip()
        if not symptoms_text:
            flash("Please describe your symptoms.")
            return redirect(url_for("assess"))

        try:
            assessment = llm_interface.assess_symptoms(symptoms_text)
        except llm_interface.LLMResponseError as exc:
            flash(f"Could not get a valid assessment: {exc}")
            return redirect(url_for("assess"))

        return _route_assessment(patient, symptoms_text, assessment)

    history = db.get_patient_history(patient.id)
    return render_template("assess.html", patient=patient, history=history)


@app.route("/assess/quick", methods=["POST"])
def assess_quick():
    """Quick-severity test buttons — skip symptom analysis entirely."""
    patient = current_patient()
    if not patient:
        return redirect(url_for("start"))

    severity = request.form.get("severity", "").strip().lower()
    assessment = _QUICK_TEST_ASSESSMENTS.get(severity)
    if not assessment:
        flash("Unknown severity.")
        return redirect(url_for("assess"))

    return _route_assessment(patient, f"[Quick severity test: {severity}]", assessment)


@app.route("/assessment/<int:assessment_id>")
def view_assessment(assessment_id: int):
    patient = current_patient()
    if not patient:
        return redirect(url_for("start"))

    record = db.get_assessment(assessment_id)
    if not record or record.patient_id != patient.id:
        flash("Assessment not found.")
        return redirect(url_for("assess"))

    ready_at = record.created_at + record.reaction_time
    seconds_remaining = max(0, int(ready_at - time.time()))
    return render_template(
        "monitor.html", patient=patient, record=record, seconds_remaining=seconds_remaining
    )


@app.route("/assessment/<int:assessment_id>/checkin", methods=["POST"])
def checkin(assessment_id: int):
    patient = current_patient()
    if not patient:
        return redirect(url_for("start"))

    record = db.get_assessment(assessment_id)
    if not record or record.patient_id != patient.id:
        flash("Assessment not found.")
        return redirect(url_for("assess"))

    recovered = request.form.get("answer") == "recovered"

    if recovered:
        remedy_manager.complete(record)
        flash("Great — marked as recovered. Take care!")
        return redirect(url_for("assess"))

    remedy_manager.escalate(record)
    assessment = SymptomAssessment(
        problem=record.problem,
        severity=record.severity,
        remedy=record.remedy,
        reaction_time=record.reaction_time,
    )
    summary = emergency_manager.handle_emergency(patient, assessment, record)
    return render_template("emergency.html", patient=patient, assessment=assessment, summary=summary)


@app.route("/history")
def history():
    patient = current_patient()
    if not patient:
        return redirect(url_for("start"))
    records = db.get_patient_history(patient.id)
    return render_template("history.html", patient=patient, history=records)


@app.route("/logout")
def logout():
    session.clear()
    flash("Signed out.")
    return redirect(url_for("start"))


if __name__ == "__main__":
    app.run(debug=config.FLASK_DEBUG, port=config.FLASK_PORT)
