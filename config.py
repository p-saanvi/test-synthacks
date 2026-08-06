"""
Central configuration for the AI Health Decision Support System.

Loads settings from environment variables (via a .env file if present).
Copy .env.example to .env and fill in your own values before running.
"""

import os

from dotenv import load_dotenv

load_dotenv()


# --- Hospital contact (this project's actual scope) --------------------------

# How many times to attempt contacting the selected hospital before giving up
# and marking the contact as failed.
HOSPITAL_CONTACT_MAX_RETRIES = int(os.getenv("HOSPITAL_CONTACT_MAX_RETRIES", "3"))

# Simulated attempts before a contact succeeds (no real hospital API exists
# yet — see hospital_manager.py). 0 = confirms on the first attempt; 1 = the
# first attempt simulates a busy/no-answer line and the second succeeds, etc.
# Demonstrates the retry/confirmation-tracking logic deterministically.
HOSPITAL_SIMULATED_FAILURES_BEFORE_SUCCESS = int(
    os.getenv("HOSPITAL_SIMULATED_FAILURES_BEFORE_SUCCESS", "1")
)


# --- OpenRouter / LLM settings (reference only — see llm_interface.py) -------
# Not used by the active symptom-analysis mock; kept for
# llm_interface_openrouter.py, the real implementation on standby for when
# that responsibility is picked up.

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

# Model used for symptom analysis. As of this writing OpenRouter has no
# free-tier Qwen model (its Qwen catalog is paid-only — verified live against
# https://openrouter.ai/api/v1/models), so this defaults to a free model from
# another provider instead: OpenAI's open-weight gpt-oss-20b, which is solid
# at following the JSON-only instructions this app relies on. Override via
# OPENROUTER_MODEL any time — check https://openrouter.ai/models?max_price=0
# for the current list of free models (Qwen included, if it reappears).
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-oss-20b:free")

# Optional headers OpenRouter uses for its leaderboard/attribution. Not required.
OPENROUTER_SITE_URL = os.getenv("OPENROUTER_SITE_URL", "")
OPENROUTER_SITE_NAME = os.getenv("OPENROUTER_SITE_NAME", "AI Health Decision Support System")

LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))


# --- Database --------------------------------------------------------------

DATABASE_PATH = os.getenv("DATABASE_PATH", os.path.join("database", "patients.db"))


# --- Web app -----------------------------------------------------------------

FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-me")
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "true").lower() in ("1", "true", "yes")
FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))

# The LLM returns a `reaction_time` in seconds — how long to wait before
# checking in on a Low/Medium severity patient (e.g. 1800s = 30 min). The web
# app shows this as a countdown but does not block on it — the patient can
# check in whenever they like via the "Check in now" button.
