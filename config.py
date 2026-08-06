"""
Central configuration for the AI Health Decision Support System.

Loads settings from environment variables (via a .env file if present).
Copy .env.example to .env and fill in your own values before running.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_REPO_ROOT = Path(__file__).resolve().parent


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


# --- OpenRouter / LLM settings ------------------------------------------------
# The active symptom analysis (llm_interface.py -> qwen_triage.py) reads
# OPENROUTER_API_KEY / TRIAGE_MODEL / VISION_MODEL from the environment
# directly rather than through this module. The settings below are for
# llm_interface_openrouter.py, an alternate reference implementation kept on
# standby (see its docstring) — not currently wired into app.py.

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

# Shared with the Health 360 sign-up/onboarding app (Node.js) — one database,
# one source of truth for user/patient data. See database/db.py's docstring.
DATABASE_PATH = os.getenv(
    "DATABASE_PATH", str(_REPO_ROOT / "server" / "health360.db")
)


# --- Web app -----------------------------------------------------------------

FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-me")
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "true").lower() in ("1", "true", "yes")
FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))

# Where to send someone who isn't signed up yet / hasn't finished onboarding —
# account creation and profile setup are owned by the Health 360 app, not
# this one. See app.py's start().
HEALTH360_URL = os.getenv("HEALTH360_URL", "http://localhost:4000")

# The LLM returns a `reaction_time` in seconds — how long to wait before
# checking in on a Low/Medium severity patient (e.g. 1800s = 30 min). The web
# app shows this as a countdown but does not block on it — the patient can
# check in whenever they like via the "Check in now" button.
