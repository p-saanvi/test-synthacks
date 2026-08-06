"""
SQLite persistence layer.

Stores patients, their emergency contacts, each symptom assessment with its
current workflow status (pending -> monitoring -> recovered/escalated ->
completed), and each hospital contact attempt (pending -> contacted ->
confirmed/failed). This is the "state management" piece of the
decision-support flow: if the process restarts mid-monitoring or mid-retry,
progress survives.
"""

from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

import config
from models import (
    AssessmentRecord,
    AssessmentStatus,
    EmergencyContact,
    HospitalContactRecord,
    HospitalContactStatus,
    Patient,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    insurance_id TEXT
);

CREATE TABLE IF NOT EXISTS emergency_contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    name TEXT NOT NULL,
    relationship TEXT,
    phone TEXT,
    email TEXT,
    whatsapp TEXT,
    preferred_channel TEXT DEFAULT 'phone'
);

CREATE TABLE IF NOT EXISTS assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    symptoms_text TEXT NOT NULL,
    problem TEXT NOT NULL,
    severity TEXT NOT NULL,
    remedy TEXT NOT NULL,
    reaction_time INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS hospital_contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assessment_id INTEGER NOT NULL REFERENCES assessments(id),
    hospital_name TEXT NOT NULL,
    distance_km REAL NOT NULL,
    eta_minutes INTEGER NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    confirmation_id TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
"""


def _ensure_parent_dir(path: str) -> None:
    parent = Path(path).parent
    if str(parent) not in ("", "."):
        parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    _ensure_parent_dir(config.DATABASE_PATH)
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(SCHEMA)


# --- Patients ----------------------------------------------------------------

def _row_to_patient(conn: sqlite3.Connection, row: sqlite3.Row) -> Patient:
    contacts = conn.execute(
        "SELECT * FROM emergency_contacts WHERE patient_id = ?", (row["id"],)
    ).fetchall()
    return Patient(
        id=row["id"],
        name=row["name"],
        insurance_id=row["insurance_id"],
        emergency_contacts=[
            EmergencyContact(
                name=c["name"],
                relationship=c["relationship"] or "",
                phone=c["phone"],
                email=c["email"],
                whatsapp=c["whatsapp"],
                preferred_channel=c["preferred_channel"] or "phone",
            )
            for c in contacts
        ],
    )


def get_patient_by_name(name: str) -> Optional[Patient]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM patients WHERE name = ?", (name,)
        ).fetchone()
        if row is None:
            return None
        return _row_to_patient(conn, row)


def get_patient_by_id(patient_id: int) -> Optional[Patient]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM patients WHERE id = ?", (patient_id,)
        ).fetchone()
        if row is None:
            return None
        return _row_to_patient(conn, row)


def create_patient(patient: Patient) -> Patient:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO patients (name, insurance_id) VALUES (?, ?)",
            (patient.name, patient.insurance_id),
        )
        patient_id = cur.lastrowid
        for c in patient.emergency_contacts:
            conn.execute(
                """INSERT INTO emergency_contacts
                   (patient_id, name, relationship, phone, email, whatsapp, preferred_channel)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (patient_id, c.name, c.relationship, c.phone, c.email, c.whatsapp, c.preferred_channel),
            )
        patient.id = patient_id
        return patient


def get_or_create_patient(patient: Patient) -> Patient:
    existing = get_patient_by_name(patient.name)
    if existing:
        return existing
    return create_patient(patient)


# --- Assessments ---------------------------------------------------------------

def save_assessment(record: AssessmentRecord) -> AssessmentRecord:
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO assessments
               (patient_id, symptoms_text, problem, severity, remedy, reaction_time,
                status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.patient_id,
                record.symptoms_text,
                record.problem,
                record.severity,
                record.remedy,
                record.reaction_time,
                record.status,
                record.created_at,
                record.updated_at,
            ),
        )
        record.id = cur.lastrowid
        return record


def update_assessment_status(assessment_id: int, status: AssessmentStatus) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE assessments SET status = ?, updated_at = ? WHERE id = ?",
            (status.value, time.time(), assessment_id),
        )


def _row_to_assessment(r: sqlite3.Row) -> AssessmentRecord:
    return AssessmentRecord(
        id=r["id"],
        patient_id=r["patient_id"],
        symptoms_text=r["symptoms_text"],
        problem=r["problem"],
        severity=r["severity"],
        remedy=r["remedy"],
        reaction_time=r["reaction_time"],
        status=r["status"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


def get_assessment(assessment_id: int) -> Optional[AssessmentRecord]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM assessments WHERE id = ?", (assessment_id,)
        ).fetchone()
        return _row_to_assessment(row) if row else None


def get_patient_history(patient_id: int) -> list[AssessmentRecord]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM assessments WHERE patient_id = ? ORDER BY created_at DESC",
            (patient_id,),
        ).fetchall()
        return [_row_to_assessment(r) for r in rows]


# --- Hospital contacts ---------------------------------------------------------

def _row_to_hospital_contact(r: sqlite3.Row) -> HospitalContactRecord:
    return HospitalContactRecord(
        id=r["id"],
        assessment_id=r["assessment_id"],
        hospital_name=r["hospital_name"],
        distance_km=r["distance_km"],
        eta_minutes=r["eta_minutes"],
        attempts=r["attempts"],
        status=r["status"],
        confirmation_id=r["confirmation_id"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


def save_hospital_contact(record: HospitalContactRecord) -> HospitalContactRecord:
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO hospital_contacts
               (assessment_id, hospital_name, distance_km, eta_minutes, attempts,
                status, confirmation_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.assessment_id,
                record.hospital_name,
                record.distance_km,
                record.eta_minutes,
                record.attempts,
                record.status,
                record.confirmation_id,
                record.created_at,
                record.updated_at,
            ),
        )
        record.id = cur.lastrowid
        return record


def update_hospital_contact(
    contact_id: int,
    status: HospitalContactStatus,
    attempts: int,
    confirmation_id: Optional[str] = None,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """UPDATE hospital_contacts
               SET status = ?, attempts = ?, confirmation_id = COALESCE(?, confirmation_id),
                   updated_at = ?
               WHERE id = ?""",
            (status.value, attempts, confirmation_id, time.time(), contact_id),
        )


def get_hospital_contact_by_assessment(assessment_id: int) -> Optional[HospitalContactRecord]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM hospital_contacts WHERE assessment_id = ? ORDER BY id DESC LIMIT 1",
            (assessment_id,),
        ).fetchone()
        return _row_to_hospital_contact(row) if row else None
