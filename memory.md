# test-synthacks — Project Memory

## What this is
A healthcare app built by 3 people, now integrated into one flow: a user
signs up on **Health 360**, fills in their profile + emergency contacts +
insurance, then hands off into the **AI Health Decision Support System**
(Flask) which analyzes their symptoms with a real LLM (Qwen3-14B) and
either gives home-remedy advice or escalates to a simulated hospital
contact — notifying emergency contacts and estimating insurance-covered
cost along the way.

See the root [`README.md`](./README.md) for full setup/run instructions for
both apps. This file is the "what connects to what" overview.

## Who built what
- **Health 360** (Node.js + Express, `server/` + `public/`): signup/login,
  Terms & Conditions, onboarding form (personal info + emergency contacts +
  insurance provider), and the database both apps share.
- **AI Health Decision Support System** (Flask, root-level `.py` files +
  `templates/`): decision engine (remedy vs. emergency), hospital contact
  workflow with retry/confirmation tracking, mock family
  notifications/insurance/cost-estimate stubs.
- **qwen_triage.py**: the real AI brain — Qwen3-14B (+ Qwen2.5-VL for
  photos/video, not yet wired into the web UI) via OpenRouter, deciding
  REMEDY / AMBULANCE / REQUEST_MEDIA from a patient profile + symptom
  description. Wired in through `llm_interface.py`.

## Stack
- Health 360: plain HTML/CSS/JavaScript + Node.js/Express
- AI Health Decision Support System: Flask (Python) + Jinja2 templates
- **One shared SQLite database**: `server/health360.db`. Health 360 owns
  `users`/`profiles`/`emergency_contacts`; the Flask app owns `assessments`/
  `hospital_contacts` on top of it, keyed by the same user id. See
  `database/db.py`'s docstring — either app can create the DB fresh, so
  there's no required startup order.

## End-to-end user flow
1. **Health 360** (http://localhost:4000) — Sign In / Create Account → T&C
   → onboarding (name, gender, age, height, weight, location, emergency
   contacts) → insurance provider name → "You're all set!" page with a
   **Continue to Symptom Check** link.
2. That link is `http://localhost:5000/?user_id=<their id>` — opens the
   **Flask app** already signed in, reading the exact same profile out of
   the shared database. Nothing is re-asked.
3. User describes their symptoms → `qwen_triage.triage()` (Qwen3-14B)
   decides REMEDY / AMBULANCE / REQUEST_MEDIA (mapped into the existing
   `SymptomAssessment` shape by `llm_interface.py`, using the model's own
   `urgency` field as the severity signal decision_engine.py routes on).
   `REQUEST_MEDIA` fails safe to the emergency path (no photo/video upload
   UI yet).
4. **Low/medium severity** → remedy shown, monitoring page, check in later
   (recovered = done; not better = escalates).
5. **High/critical severity** → emergency page: real hospital
   selection + contact attempt with retry/confirmation tracking
   (`hospital_manager.py`), mock emergency-contact notifications, mock
   insurance coverage + cost estimate.
6. **History** page lists all past assessments and their status.

Quick-severity test buttons on the Flask assess page bypass the LLM call
entirely (no `OPENROUTER_API_KEY` needed) — useful for testing the decision
engine / hospital workflow in isolation.

## Database tables (shared SQLite — server/health360.db)
- `users`: id, email, username, password_hash, created_at
- `profiles`: id, user_id, name, gender, age, height_cm, weight_kg,
  location, insurance_provider, insurance_id, created_at, updated_at
- `emergency_contacts`: id, user_id, name, relationship, phone, email,
  whatsapp, preferred_channel, created_at
- `assessments` (Flask-owned): id, patient_id (= user_id), symptoms_text,
  problem, severity, remedy, reaction_time, status, created_at, updated_at
- `hospital_contacts` (Flask-owned): id, assessment_id, hospital_name,
  distance_km, eta_minutes, attempts, status, confirmation_id, created_at,
  updated_at

## Required setup
- Node side: `cd server && npm install` — no API keys needed.
- Flask side: `python -m venv .venv && pip install -r requirements.txt`,
  then copy `.env.example` to `.env` and set `OPENROUTER_API_KEY` (get one
  at https://openrouter.ai/keys) — required for real symptom analysis to
  work. Everything else (hospital contact, notifications, insurance/cost,
  quick-severity test buttons) works with no API key.

## Still mocked (owned by whoever picks these up next)
- `insurance_manager.py` — fake insurance lookup + coverage calc (real
  insurer integration not built)
- `cost_estimator.py` — fake severity-based cost estimate
- `notifications/*.py` — print-based stand-ins for email/SMS/WhatsApp/phone
- Photo/video follow-up (`REQUEST_MEDIA` from qwen_triage.py) has no upload
  UI yet — currently fails safe to the emergency path instead

## Status
Fully integrated and tested end-to-end (signup → onboarding → insurance →
handoff → symptom triage → both the remedy path and the emergency/hospital
path, plus the no-API-key fallback). See git history for the integration
commit.
