"""
Decision engine: routes a SymptomAssessment to the Remedy or Emergency path.

    Low/Medium  -> Remedy + monitor -> recovered? yes: complete, no: emergency
    High/Critical -> Emergency (hospital + family + insurance/cost)
"""

from __future__ import annotations

from enum import Enum

from models import Severity, SymptomAssessment


class Action(str, Enum):
    REMEDY = "remedy"
    EMERGENCY = "emergency"


_REMEDY_SEVERITIES = {Severity.LOW, Severity.MEDIUM}
_EMERGENCY_SEVERITIES = {Severity.HIGH, Severity.CRITICAL}


def decide(assessment: SymptomAssessment) -> Action:
    """Pure routing decision based on severity. See Severity Levels table
    in AI_Health_Decision_System_Overview.md."""
    severity = assessment.severity_enum
    if severity in _REMEDY_SEVERITIES:
        return Action.REMEDY
    if severity in _EMERGENCY_SEVERITIES:
        return Action.EMERGENCY
    # Unreachable given SymptomAssessment's Literal validation, but fail safe:
    raise ValueError(f"Unknown severity: {assessment.severity!r}")
