"""
MOCK emergency-care cost estimator.

Owned by teammate responsibilities (supports insurance coverage checking).
Returns a rough, severity-based fake estimate. Replace with real pricing
data (hospital rate cards, region-based estimates, etc.) when that work is
picked up.
"""

from __future__ import annotations

from models import Severity, SymptomAssessment

_BASE_COST_BY_SEVERITY = {
    Severity.HIGH: 1500.0,
    Severity.CRITICAL: 6000.0,
}


def estimate_cost(assessment: SymptomAssessment) -> float:
    severity = assessment.severity_enum
    base = _BASE_COST_BY_SEVERITY.get(severity, 500.0)
    print(f"[cost_estimator:MOCK] Estimated cost for {severity.value} case: ${base:,.2f}")
    return base
