"""
MOCK insurance lookup + coverage checking.

Owned by teammate responsibilities ("Insurance lookup", "Insurance coverage
and limit checking"). This stub returns plausible fake data so the emergency
workflow can be exercised end-to-end. Replace with a real insurer
integration / internal insurance DB when that work is picked up.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from models import Patient


@dataclass
class InsurancePolicy:
    insurance_id: str
    provider: str
    coverage_limit: float
    copay_percent: float  # fraction the patient pays, e.g. 0.2 = 20%


@dataclass
class CoverageResult:
    is_covered: bool
    covered_amount: float
    patient_owes: float
    notes: str = ""


# Fake in-memory "insurance directory" for demo purposes.
_MOCK_POLICIES: dict[str, InsurancePolicy] = {
    "DEMO-1000": InsurancePolicy("DEMO-1000", "MockHealth Insurance Co.", coverage_limit=50000, copay_percent=0.2),
}


def lookup_insurance(patient: Patient) -> Optional[InsurancePolicy]:
    if not patient.insurance_id:
        print(f"[insurance:MOCK] No insurance_id on file for {patient.name}")
        return None
    policy = _MOCK_POLICIES.get(patient.insurance_id)
    if policy is None:
        # Unknown ID: fabricate a generic policy so the demo flow keeps working.
        policy = InsurancePolicy(patient.insurance_id, "Unknown Provider (mock)", coverage_limit=25000, copay_percent=0.3)
    print(f"[insurance:MOCK] Found policy {policy.insurance_id} ({policy.provider})")
    return policy


def check_coverage(policy: Optional[InsurancePolicy], estimated_cost: float) -> CoverageResult:
    if policy is None:
        return CoverageResult(
            is_covered=False,
            covered_amount=0.0,
            patient_owes=estimated_cost,
            notes="No active policy on file — patient responsible for full estimated cost.",
        )
    covered_amount = min(estimated_cost, policy.coverage_limit) * (1 - policy.copay_percent)
    patient_owes = estimated_cost - covered_amount
    return CoverageResult(
        is_covered=covered_amount > 0,
        covered_amount=round(covered_amount, 2),
        patient_owes=round(patient_owes, 2),
        notes=f"Copay {policy.copay_percent:.0%}, limit ${policy.coverage_limit:,.2f}.",
    )
