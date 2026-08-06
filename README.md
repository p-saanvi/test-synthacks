# test-synthacks

This is a test to see if 2 boys and 1 girl can solve the healthcare crisis.

This repo holds two apps, built by different people, now wired together into
one flow:

- **[Health 360](#health-360)** (`server/`, `public/`) — a Node.js signup /
  onboarding web app: account creation, personal profile + emergency
  contacts, insurance capture. This is the front door — sign up here first.
- **[AI Health Decision Support System](#ai-health-decision-support-system)**
  (root-level `.py` files, `templates/`, `static/`, `notifications/`,
  `database/`) — a Flask app implementing real symptom triage (Qwen3-14B via
  OpenRouter, see `qwen_triage.py`), a decision engine (home remedy vs.
  emergency), and hospital-contact logic with retry and confirmation
  tracking.

**They share one SQLite database** (`server/health360.db`) instead of each
keeping their own — see `database/db.py`'s docstring. Health 360 owns
account/profile/contact data; the Flask app owns assessments and hospital
contact records on top of it. After finishing onboarding + insurance on
Health 360, its "Continue to Symptom Check" link takes you straight into the
Flask app already signed in, with your profile already loaded — no
re-entering anything. Each app still runs as its own server (Health 360 on
:4000, the Flask app on :5000); only the database and that handoff link
connect them.

---

## Health 360

See [`memory.md`](./memory.md) for a full project overview (flow, data model,
and the AI hand-off API contract).

### Running locally

```bash
cd server
npm install
node server.js
```

The server starts at http://localhost:4000 and serves the website itself
(from `/public`) as well as the API. A `health360.db` SQLite file is created
automatically in `server/` the first time you run it — no extra setup needed.

Then open http://localhost:4000 in your browser and either **Create Account**
or **Sign In**. Once onboarding + insurance are done, click **Continue to
Symptom Check** to hand off into the Flask app below with the same profile.

### Project layout

- `server/` — Node.js + Express backend, SQLite database (`health360.db`,
  shared with the Flask app below), and the API (auth, profile, emergency
  contacts, and the `/api/ai/*` routes that hand off to the triage app).
- `public/` — plain HTML/CSS/JS frontend pages (no framework).

---

## AI Health Decision Support System

A Flask web app implementing the workflow described in
`AI_Health_Decision_System_Overview.md`: a user (already signed up on Health
360) describes their symptoms, real symptom analysis (Qwen3-14B via
OpenRouter — see `qwen_triage.py`) produces a structured triage decision,
and a decision engine routes to either a home-remedy + monitoring flow or an
emergency escalation flow that contacts a hospital.

> **Not medical advice.** This is a decision-support tool, not a replacement
> for professional medical advice or emergency services.

### Scope: what's fully implemented vs. mocked

| File | Status |
|---|---|
| `decision_engine.py` | ✅ Full — severity routing (remedy vs. emergency) |
| `hospital_manager.py` | ✅ Full — hospital selection, contact attempts with retry, confirmation tracking, persisted state |
| `remedy_manager.py` | ✅ Full — remedy state transitions (monitoring → recovered/escalated) |
| `models.py` | ✅ Full — data models, incl. pydantic schema for the symptom assessment |
| `database/db.py` | ✅ Full — shared SQLite access layer (reads Health 360's profile/contacts, owns assessments + hospital contacts) |
| `app.py` + `templates/` | ✅ Full — Flask web app (symptom form, monitoring page, emergency page, history) |
| `llm_interface.py` + `qwen_triage.py` | ✅ Full — real symptom analysis via Qwen3-14B (OpenRouter). Requires `OPENROUTER_API_KEY`; photo/video follow-up (`REQUEST_MEDIA`) fails safe to the emergency path since there's no upload UI yet |
| `llm_interface_openrouter.py` | 🔵 Reference — an alternate real LLM implementation (different model/prompt), kept on standby, not wired into `app.py` (see its docstring) |
| `emergency_manager.py` | Orchestrator — calls `hospital_manager.py` (real) + family notifications/insurance (mocked) |
| `insurance_manager.py` | 🟡 Mock — fake insurance lookup & coverage calc |
| `cost_estimator.py` | 🟡 Mock — fake severity-based cost estimate |
| `notifications/*.py` | 🟡 Mock — print-based stand-ins for email/SMS/WhatsApp/phone |

Every mock file has a docstring flagging it as a stub with notes on what a
real integration would need. Mocked sections are also labeled in the UI.

### Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Set `OPENROUTER_API_KEY` in `.env` — symptom analysis calls Qwen3-14B (and
Qwen2.5-VL if photo/video support is added later) via OpenRouter, so it's
required to analyze real symptom text. Without it, the app still runs fine:
sign-in, the quick-severity test buttons, hospital contact, notifications,
and insurance/cost all work with no API key — only the "describe your
symptoms" form needs one, and fails with a clear on-page message if it's
missing rather than crashing.

### Run

```bash
python app.py
```

This shares its database with Health 360 (`server/health360.db`) — **sign up
and finish onboarding + insurance on Health 360 first** (http://localhost:4000),
then use its "Continue to Symptom Check" link, which opens
http://localhost:5000/?user_id=... already signed in with your profile
loaded. Visiting http://localhost:5000 directly with no account link just
points you back to Health 360.

1. Describe your symptoms — Qwen3-14B returns a decision (`REMEDY` /
   `AMBULANCE` / `REQUEST_MEDIA`, mapped to `problem`/`severity`/`remedy`/
   `reaction_time`). Try phrases like "chest pain" or "can't breathe" to
   trigger the emergency path, or "mild headache" for the remedy path. The
   **quick-severity test buttons** bypass the LLM call entirely if you want
   to test the decision engine / hospital workflow without an API key.
2. **Low/Medium severity** → you land on a monitoring page showing the
   remedy and a check-in button (no forced waiting — check in whenever
   you're ready). "Recovered" completes the case; "Not better / worse"
   escalates to the emergency flow.
3. **High/Critical severity** → you're taken straight to the emergency page:
   real hospital selection + contact attempt (with retry/confirmation
   tracking), mock family notifications, mock insurance/cost estimate.
4. **History** page lists all past assessments and their status.

### Project structure

```
├── app.py                       # Flask app / routes
├── config.py                     # env-based configuration
├── decision_engine.py            # severity -> remedy/emergency routing            [full]
├── hospital_manager.py           # hospital selection, contact + retry, tracking    [full]
├── remedy_manager.py             # monitoring/complete/escalate state transitions   [full]
├── emergency_manager.py          # orchestrates hospital (real) + family/insurance (mock)
├── llm_interface.py              # adapts qwen_triage.py's output into SymptomAssessment
├── qwen_triage.py                 # real triage engine: Qwen3-14B (+ Qwen2.5-VL), via OpenRouter
├── llm_interface_openrouter.py   # [reference] alternate real LLM implementation, on standby
├── insurance_manager.py          # [mock] insurance lookup + coverage check
├── cost_estimator.py             # [mock] cost estimate
├── models.py                     # Pydantic/dataclass data models
├── templates/                    # Jinja2 templates for the web UI
│   ├── base.html
│   ├── start.html                 # entry point for the Health 360 handoff link
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
    └── db.py                       # shared SQLite access layer (see its docstring)
```

### Notes on design decisions

- **Hospital contact is the core built piece**: `hospital_manager.py` picks a
  hospital (critical cases prefer trauma/cardiac-capable facilities; others
  go to the nearest general/urgent facility), attempts contact with
  configurable retry (`HOSPITAL_CONTACT_MAX_RETRIES`), and persists every
  attempt to SQLite (`hospital_contacts` table) so progress — including
  attempt count and final confirmation ID — survives a restart. The hospital
  *directory* is simulated data (no real hospital API exists), but the
  selection/retry/tracking logic around it is real.
- **Symptom analysis is real**: `qwen_triage.py` calls Qwen3-14B via
  OpenRouter and decides `REMEDY` / `AMBULANCE` / `REQUEST_MEDIA` directly;
  `llm_interface.py` adapts that into the `SymptomAssessment` shape
  `decision_engine.py` expects (using the model's own `urgency` field as the
  severity signal), so nothing downstream needed to change. `REQUEST_MEDIA`
  fails safe to the emergency path — no photo/video upload UI exists yet,
  same fallback qwen_triage's original standalone CLI used. An alternate
  real implementation (different model/prompt, not wired in) is kept in
  `llm_interface_openrouter.py` for reference.
- **State management**: assessment status moves through
  `pending -> monitoring -> recovered/escalated -> completed`, and hospital
  contact status moves through `pending -> contacted -> confirmed/failed` —
  both persisted in SQLite. Session identity comes from Health 360's account
  system (a `user_id` handed off via link — see `app.py`'s `start()`), not a
  separate login here.
- **Non-blocking monitoring**: unlike a CLI that could `sleep()`, the web app
  never blocks a request on `reaction_time` — the monitor page shows a
  cosmetic countdown but lets the patient check in at any time via a button.

### Next steps (from "Future Improvements" in the overview)

Voice input, GPS-based hospital lookup, wearable integration, medical
history support, and risk score/confidence estimation are not implemented
here — the architecture (`hospital_manager.py`'s `select_hospital()` is the
natural place for real GPS-based lookup) should make these straightforward
to add incrementally.
