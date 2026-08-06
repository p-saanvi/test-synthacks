"""
MOCK symptom analysis (stand-in for the real LLM integration).

Owned by teammate responsibilities ("AI (LLM) integration", "Prompt
engineering", "Parsing structured JSON responses" — see
AI_Health_Decision_System_Overview.md). This scope is the decision engine +
hospital contact workflow, not symptom analysis, so this stub uses simple
keyword matching instead of a real model call — no API key, no network call,
no cost. It returns the same SymptomAssessment shape a real LLM would, so
decision_engine.py and hospital_manager.py can be built/tested end-to-end
without depending on an LLM provider.

A fully working, tested OpenRouter + LLM implementation is kept in
llm_interface_openrouter.py, ready to swap in when that responsibility is
picked up (see its docstring for how).
"""

from __future__ import annotations

from models import SymptomAssessment

# Ordered most- to least-severe: first matching keyword set wins.
_CRITICAL_KEYWORDS = [
    "chest pain", "can't breathe", "cannot breathe", "difficulty breathing",
    "unconscious", "unresponsive", "severe bleeding", "heavy bleeding",
    "stroke", "slurred speech", "face drooping", "suicidal", "overdose",
    "anaphylaxis", "seizure", "not breathing",
]
_HIGH_KEYWORDS = [
    "high fever", "severe pain", "persistent vomiting", "broken bone",
    "fracture", "worsening", "dehydrated", "confusion", "allergic reaction",
    "severe headache", "blood in",
]
_MEDIUM_KEYWORDS = [
    "fever", "vomiting", "dizzy", "dizziness", "rash", "migraine",
    "moderate pain", "persistent", "nausea", "sore throat",
]


class LLMResponseError(RuntimeError):
    """Raised when symptom analysis cannot produce a valid assessment."""


def assess_symptoms(symptoms_text: str) -> SymptomAssessment:
    """
    MOCK: classify free-text symptoms by keyword matching instead of calling
    an LLM. Kept intentionally simple — this is not the part of the system
    being built out here (see module docstring).
    """
    text = (symptoms_text or "").strip().lower()
    if not text:
        raise LLMResponseError("No symptoms text provided.")

    if any(k in text for k in _CRITICAL_KEYWORDS):
        return SymptomAssessment(
            problem="Potential medical emergency",
            severity="critical",
            remedy="Seek emergency medical care immediately — do not wait.",
            reaction_time=60,
        )
    if any(k in text for k in _HIGH_KEYWORDS):
        return SymptomAssessment(
            problem="Symptoms warranting prompt care",
            severity="high",
            remedy="Contact a hospital promptly for evaluation.",
            reaction_time=180,
        )
    if any(k in text for k in _MEDIUM_KEYWORDS):
        return SymptomAssessment(
            problem="Mild-to-moderate symptoms",
            severity="medium",
            remedy="Rest, hydrate, and monitor closely. Seek care if symptoms worsen.",
            reaction_time=1800,
        )
    return SymptomAssessment(
        problem="Minor symptoms",
        severity="low",
        remedy="Rest and monitor at home. No red-flag symptoms detected.",
        reaction_time=3600,
    )
