"""
SQLite persistence layer.

This shares ONE database file with the Health 360 sign-up/onboarding app
(Node.js, in server/health360.db): Health 360 owns the `users`, `profiles`,
and `emergency_contacts` tables (a patient here IS a Health 360 user — this
module's `patient_id` is that same `user_id`), and this app owns
`assessments` and `hospital_contacts` on top of it. Either app can create
the database fresh (every CREATE TABLE below is IF NOT EXISTS and matches
server/db.js's schema exactly), so there's no ordering requirement for which
app starts first.

Stores each symptom assessment with its current workflow status (pending ->
monitoring -> recovered/escalated -> completed), and each hospital contact
attempt (pending -> contacted -> confirmed/failed). This is the "state
management" piece of the decision-support flow: if the process restarts
mid-monitoring or mid-retry, progress survives.
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

# Mirrors server/db.js exactly, so whichever app starts first can create the
# database from scratch without the other needing to run first.
SHARED_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT,
    gender TEXT,
    age INTEGER,
    height_cm REAL,
    weight_kg REAL,
    location TEXT,
    insurance_provider TEXT,
    insurance_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS emergency_contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    relationship TEXT NOT NULL,
    phone TEXT NOT NULL,
    email TEXT,
    whatsapp TEXT,
    preferred_channel TEXT DEFAULT 'phone',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

# Owned by this app.
TRIAGE_SCHEMA = """
CREATE TABLE IF NOT EXISTS assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL REFERENCES users(id),
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
        conn.executescript(SHARED_SCHEMA)
        conn.executescript(TRIAGE_SCHEMA)


# --- Patients (== Health 360 users) -------------------------------------------
#
# Patient creation/editing is owned by the Health 360 app (sign-up +
# onboarding) — this module only reads. A patient shows up here as soon as
# they've completed onboarding on Health 360, keyed by that same user id.

def _row_to_patient(conn: sqlite3.Connection, row: sqlite3.Row) -> Optional[Patient]:
    if row is None:
        return None
    contacts = conn.execute(
        "SELECT * FROM emergency_contacts WHERE user_id = ?", (row["user_id"],)
    ).fetchall()
    return Patient(
        id=row["user_id"],
        name=row["name"] or "",
        insurance_id=row["insurance_id"],
        insurance_provider=row["insurance_provider"],
        gender=row["gender"],
        age=row["age"],
        height_cm=row["height_cm"],
        weight_kg=row["weight_kg"],
        location=row["location"],
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


def get_patient_by_id(patient_id: int) -> Optional[Patient]:
    """patient_id here is the Health 360 user_id."""
    with get_connection() as conn:
        row = conn.execute(
            """SELECT p.* FROM profiles p WHERE p.user_id = ?""",
            (patient_id,),
        ).fetchone()
        return _row_to_patient(conn, row)


def is_profile_complete(patient_id: int) -> bool:
    """Mirrors Health 360's own isProfileComplete() check (public/api.js) —
    used to decide whether to send someone back to Health 360 to finish
    onboarding before they can use the triage app."""
    patient = get_patient_by_id(patient_id)
    return bool(
        patient
        and patient.name
        and patient.gender
        and patient.age
        and patient.height_cm
        and patient.weight_kg
        and patient.location
    )


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
