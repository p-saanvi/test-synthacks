"""
REFERENCE IMPLEMENTATION — real LLM integration (OpenRouter) + prompt
engineering + structured JSON parsing.

Not owned by this scope (decision engine + hospital contact) and not wired
into app.py by default — see llm_interface.py for the mock currently in use.
This file is a fully working, tested implementation (OpenRouter + a free
model, verified end-to-end) kept here so whoever picks up the real "AI (LLM)
integration / Prompt engineering / Parsing structured JSON responses"
responsibility can drop it in as-is: `import llm_interface_openrouter as
llm_interface` in app.py, or rename this file to llm_interface.py.

Turns a free-text symptom description into the structured SymptomAssessment
defined in models.py, matching the schema documented in
AI_Health_Decision_System_Overview.md.
"""

from __future__ import annotations

import json

from openai import APIError, OpenAI
from pydantic import ValidationError

import config
from models import SymptomAssessment

SYSTEM_PROMPT = """You are a medical triage assistant embedded in a health \
decision-support system. You do NOT provide diagnoses or replace a doctor \
or emergency services — you produce a structured, conservative triage \
estimate that a downstream decision engine will act on.

Given a user's free-text description of their symptoms, respond with ONLY a \
single JSON object (no markdown fences, no commentary) matching exactly \
this schema:

{
  "problem": string,        // short name of the likely issue, e.g. "Migraine"
  "severity": string,       // one of: "low", "medium", "high", "critical"
  "remedy": string,         // a short, safe home-care suggestion appropriate
                             // for the severity (for high/critical, this
                             // should say to seek emergency care immediately)
  "reaction_time": integer  // seconds until a follow-up check makes sense
                             // (e.g. 1800 for 30 minutes). Use a small value
                             // (e.g. 60-300) for high/critical since they are
                             // escalated immediately rather than monitored.
}

Severity guidance:
- low: minor, self-limiting issue, home remedy is sufficient.
- medium: home remedy plus monitoring for worsening symptoms.
- high: symptoms warrant prompt hospital contact.
- critical: symptoms are potentially life-threatening; immediate hospital
  assistance is required.

When in doubt between two severities, err toward the MORE severe one — this \
system is a safety net, not a diagnostic tool. If the description mentions \
red-flag symptoms (e.g. chest pain, difficulty breathing, severe bleeding, \
stroke signs, loss of consciousness), classify as "high" or "critical".

Respond with the JSON object only.
"""


class LLMResponseError(RuntimeError):
    """Raised when the LLM cannot be coaxed into a valid, schema-matching response."""


def _client() -> OpenAI:
    if not config.OPENROUTER_API_KEY:
        raise LLMResponseError(
            "OPENROUTER_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    return OpenAI(base_url=config.OPENROUTER_BASE_URL, api_key=config.OPENROUTER_API_KEY)


def _extra_headers() -> dict:
    headers = {}
    if config.OPENROUTER_SITE_URL:
        headers["HTTP-Referer"] = config.OPENROUTER_SITE_URL
    if config.OPENROUTER_SITE_NAME:
        headers["X-Title"] = config.OPENROUTER_SITE_NAME
    return headers


def _extract_json(text: str) -> dict:
    """Best-effort extraction in case the model wraps JSON in prose/fences."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise json.JSONDecodeError("No JSON object found", text, 0)
    return json.loads(text[start : end + 1])


def assess_symptoms(symptoms_text: str) -> SymptomAssessment:
    """
    Send the user's symptom description to the LLM and return a validated
    SymptomAssessment. Retries with feedback if the model returns malformed
    or schema-invalid JSON.
    """
    client = _client()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": symptoms_text},
    ]

    last_error: str | None = None
    for attempt in range(1, config.LLM_MAX_RETRIES + 1):
        if last_error:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Your previous response was invalid: "
                        f"{last_error}\nRespond again with ONLY the corrected JSON object."
                    ),
                }
            )

        try:
            response = client.chat.completions.create(
                model=config.OPENROUTER_MODEL,
                messages=messages,
                temperature=config.LLM_TEMPERATURE,
                response_format={"type": "json_object"},
                extra_headers=_extra_headers(),
            )
        except APIError as exc:
            # Auth failures, insufficient credits, rate limits, network issues, etc.
            # These are not schema problems — surface them immediately rather than
            # retrying/burning attempts, and let the caller show a clean message.
            raise LLMResponseError(f"OpenRouter request failed: {exc}") from exc

        raw = response.choices[0].message.content or ""

        try:
            data = _extract_json(raw)
            return SymptomAssessment.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = str(exc)
            continue

    raise LLMResponseError(
        f"LLM did not return a valid assessment after {config.LLM_MAX_RETRIES} attempts: {last_error}"
    )
