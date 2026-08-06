"""
Shared data models for the AI Health Decision Support System.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AssessmentStatus(str, Enum):
    PENDING = "pending"
    MONITORING = "monitoring"
    RECOVERED = "recovered"
    ESCALATED = "escalated"
    COMPLETED = "completed"


class HospitalContactStatus(str, Enum):
    PENDING = "pending"      # attempt in progress / not yet resolved
    CONTACTED = "contacted"  # an attempt was made but not yet confirmed
    CONFIRMED = "confirmed"  # hospital confirmed receipt / dispatch
    FAILED = "failed"        # exhausted retries without confirmation


class SymptomAssessment(BaseModel):
    """
    Structured output expected from the LLM. Mirrors the JSON schema in
    AI_Health_Decision_System_Overview.md:

        {
          "problem": "Migraine",
          "severity": "medium",
          "remedy": "Rest, hydrate, and take an appropriate over-the-counter
                      pain reliever if suitable.",
          "reaction_time": 1800
        }
    """

    problem: str = Field(..., min_length=1)
    severity: Literal["low", "medium", "high", "critical"]
    remedy: str = Field(..., min_length=1)
    reaction_time: int = Field(..., ge=0, description="Seconds until follow-up check")

    @field_validator("severity")
    @classmethod
    def normalize_severity(cls, v: str) -> str:
        return v.strip().lower()

    @property
    def severity_enum(self) -> Severity:
        return Severity(self.severity)


@dataclass
class EmergencyContact:
    name: str
    relationship: str = ""
    phone: Optional[str] = None
    email: Optional[str] = None
    whatsapp: Optional[str] = None
    preferred_channel: str = "phone"  # one of: email, sms, whatsapp, phone


@dataclass
class Patient:
    id: Optional[int]
    name: str
    insurance_id: Optional[str] = None
    emergency_contacts: list[EmergencyContact] = field(default_factory=list)
    # Full profile, as collected by the Health 360 sign-up/onboarding app
    # (shares this project's database — see database/db.py). Optional
    # because older code paths may still construct a bare Patient.
    gender: Optional[str] = None
    age: Optional[int] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    location: Optional[str] = None
    insurance_provider: Optional[str] = None


@dataclass
class AssessmentRecord:
    """A saved, stateful assessment tied to a patient (one DB row)."""

    id: Optional[int]
    patient_id: int
    symptoms_text: str
    problem: str
    severity: str
    remedy: str
    reaction_time: int
    status: str = AssessmentStatus.PENDING.value
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    @classmethod
    def from_assessment(
        cls, patient_id: int, symptoms_text: str, assessment: SymptomAssessment
    ) -> "AssessmentRecord":
        return cls(
            id=None,
            patient_id=patient_id,
            symptoms_text=symptoms_text,
            problem=assessment.problem,
            severity=assessment.severity,
            remedy=assessment.remedy,
            reaction_time=assessment.reaction_time,
        )


@dataclass
class Hospital:
    """An entry in the local simulated hospital directory."""

    name: str
    specialty_tags: list[str] = field(default_factory=list)
    distance_km: float = 0.0
    phone: str = ""


@dataclass
class HospitalContactRecord:
    """
    A saved, stateful record of an attempt to contact a hospital for a given
    assessment (one DB row). Tracks retries and the eventual outcome so the
    workflow's progress survives a restart, same as AssessmentRecord.
    """

    id: Optional[int]
    assessment_id: int
    hospital_name: str
    distance_km: float
    eta_minutes: int
    attempts: int = 0
    status: str = HospitalContactStatus.PENDING.value
    confirmation_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
