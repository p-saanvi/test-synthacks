# AI Health Decision Support System

A Flask web app implementing the workflow described in
`AI_Health_Decision_System_Overview.md`: a user describes their symptoms,
symptom analysis produces a structured triage assessment, and a decision
engine routes to either a home-remedy + monitoring flow or an emergency
escalation flow that contacts a hospital.

> **Not medical advice.** This is a decision-support tool, not a replacement
> for professional medical advice or emergency services.

## Scope: what's fully implemented vs. mocked

This build's actual scope is **the decision engine (remedy vs. hospital) and
the hospital-contact workflow** — not symptom analysis. Those two pieces are
fully built and tested; everything else (symptom analysis/LLM, family
notifications, insurance) is a working mock stub so the whole flow runs
end-to-end. Swap the mocks for real integrations without touching the rest
of the system.

| File | Status |
|---|---|
| `decision_engine.py` | ✅ Full — severity routing (remedy vs. emergency) |
| `hospital_manager.py` | ✅ Full — hospital selection, contact attempts with retry, confirmation tracking, persisted state |
| `remedy_manager.py` | ✅ Full — remedy state transitions (monitoring → recovered/escalated) |
| `models.py` | ✅ Full — data models, incl. pydantic schema for the symptom assessment |
| `database/db.py` | ✅ Full — SQLite state management (patients, contacts, assessments, hospital contacts) |
| `app.py` + `templates/` | ✅ Full — Flask web app (onboarding, symptom form, monitoring page, emergency page, history) |
| `llm_interface.py` | 🟡 Mock — keyword-based symptom classifier, stands in for real LLM/prompt-engineering work |
| `llm_interface_openrouter.py` | 🔵 Reference — a fully working, tested OpenRouter+LLM implementation, on standby to swap in (see its docstring) |
| `emergency_manager.py` | Orchestrator — calls `hospital_manager.py` (real) + family notifications/insurance (mocked) |
| `insurance_manager.py` | 🟡 Mock — fake insurance lookup & coverage calc |
| `cost_estimator.py` | 🟡 Mock — fake severity-based cost estimate |
| `notifications/*.py` | 🟡 Mock — print-based stand-ins for email/SMS/WhatsApp/phone |

Every mock file has a docstring flagging it as a stub with notes on what a
real integration would need. Mocked sections are also labeled in the UI.

## Setup

```bash
cd ai-health-decision-system
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

No API key is required to run the app — symptom analysis is a local mock
(no network call). `.env` only matters if you swap in
`llm_interface_openrouter.py` later, or want to change Flask/hospital-retry
settings.

## Run

```bash
python app.py
```

Then open http://localhost:5000 in your browser.

1. Enter your name — first time creates a profile (insurance ID + up to two
   emergency contacts, all optional except a contact's name).
2. Describe your symptoms — symptom analysis (mock) returns `problem`,
   `severity`, `remedy`, `reaction_time`. Try phrases like "chest pain" or
   "can't breathe" to trigger a critical/emergency path, or "mild headache"
   for the remedy path.
3. **Low/Medium severity** → you land on a monitoring page showing the
   remedy and a check-in button (no forced waiting — check in whenever
   you're ready). "Recovered" completes the case; "Not better / worse"
   escalates to the emergency flow.
4. **High/Critical severity** → you're taken straight to the emergency page:
   real hospital selection + contact attempt (with retry/confirmation
   tracking), mock family notifications, mock insurance/cost estimate.
5. **History** page lists all past assessments and their status.

## Project structure

```
ai-health-decision-system/
├── app.py                       # Flask app / routes
├── config.py                     # env-based configuration
├── decision_engine.py            # severity -> remedy/emergency routing            [full]
├── hospital_manager.py           # hospital selection, contact + retry, tracking    [full]
├── remedy_manager.py             # monitoring/complete/escalate state transitions   [full]
├── emergency_manager.py          # orchestrates hospital (real) + family/insurance (mock)
├── llm_interface.py              # [mock] keyword-based symptom classifier
├── llm_interface_openrouter.py   # [reference] real OpenRouter+LLM implementation, on standby
├── insurance_manager.py          # [mock] insurance lookup + coverage check
├── cost_estimator.py             # [mock] cost estimate
├── models.py                     # Pydantic/dataclass data models
├── templates/                    # Jinja2 templates for the web UI
│   ├── base.html
│   ├── start.html                 # sign in / identify patient
│   ├── onboard.html               # new-patient profile + emergency contacts
│   ├── assess.html                # symptom form + recent history
│   ├── monitor.html               # remedy + check-in
│   ├── emergency.html             # escalation summary
│   └── history.html
├── static/style.css
├── notifications/
│   ├── email.py                    # [mock]
│   ├── sms.py                      # [mock]
│   ├── whatsapp.py                  # [mock]
│   └── phone.py                     # [mock]
└── database/
    ├── db.py                       # SQLite access layer
    └── patients.db                   # created on first run
```

## Notes on design decisions

- **Hospital contact is the core built piece**: `hospital_manager.py` picks a
  hospital (critical cases prefer trauma/cardiac-capable facilities; others
  go to the nearest general/urgent facility), attempts contact with
  configurable retry (`HOSPITAL_CONTACT_MAX_RETRIES`), and persists every
  attempt to SQLite (`hospital_contacts` table) so progress — including
  attempt count and final confirmation ID — survives a restart. The hospital
  *directory* is simulated data (no real hospital API exists), but the
  selection/retry/tracking logic around it is real.
- **Symptom analysis is intentionally a stub**: `llm_interface.py` is
  keyword-based so the decision engine and hospital workflow can be
  built/tested without any LLM dependency, cost, or API key. A fully working
  OpenRouter implementation (tested end-to-end against a free model) is kept
  in `llm_interface_openrouter.py` for whoever picks up that responsibility.
- **State management**: assessment status moves through
  `pending -> monitoring -> recovered/escalated -> completed`, and hospital
  contact status moves through `pending -> contacted -> confirmed/failed` —
  both persisted in SQLite. Session identity is a simple name-based cookie
  session — there's no password auth, matching the "decision-support demo"
  scope of this project.
- **Non-blocking monitoring**: unlike a CLI that could `sleep()`, the web app
  never blocks a request on `reaction_time` — the monitor page shows a
  cosmetic countdown but lets the patient check in at any time via a button.

## Next steps (from "Future Improvements" in the overview)

Voice input, GPS-based hospital lookup, wearable integration, medical
history support, and risk score/confidence estimation are not implemented
here — the architecture (`hospital_manager.py`'s `select_hospital()` is the
natural place for real GPS-based lookup) should make these straightforward
to add incrementally.
