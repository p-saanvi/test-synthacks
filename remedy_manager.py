"""
Remedy workflow for Low/Medium severity assessments.

The web app shows the recommended home remedy immediately and puts the
assessment into "monitoring" state. The patient checks back in later (the
page shows a countdown based on the LLM's `reaction_time`, but check-in is
never blocked/forced). If they report they haven't recovered, the case is
escalated via emergency_manager, matching the workflow diagram:

    Remedy -> Monitor -> Recovered? -- yes --> Complete
                              \\-- no ---> Emergency
"""

from __future__ import annotations

from database import db
from models import AssessmentRecord, AssessmentStatus


def start_remedy(record: AssessmentRecord) -> None:
    """Mark the assessment as being monitored after the remedy was shown."""
    if record.id is not None:
        db.update_assessment_status(record.id, AssessmentStatus.MONITORING)


def complete(record: AssessmentRecord) -> None:
    """Patient checked in and reported recovery."""
    if record.id is not None:
        db.update_assessment_status(record.id, AssessmentStatus.COMPLETED)


def escalate(record: AssessmentRecord) -> None:
    """Patient checked in and reported no improvement — about to escalate."""
    if record.id is not None:
        db.update_assessment_status(record.id, AssessmentStatus.ESCALATED)
