# Health 360 — Project Memory

## What this is
"Health 360" is a health-profile web app. A user signs up, agrees to T&Cs,
fills in their personal + emergency contact info, tells us their insurance
provider, and all of that gets handed off to a backend AI. The AI's job
(built separately, NOT in this repo's scope) is to find nearby hospitals —
filtered so that hospitals not covered by the user's insurance are excluded
from the results.

## Who's building what
- **This repo** (me): the whole website — signup/login, Terms & Conditions,
  onboarding form, database, and the "slot" that hands data to the AI.
- **Friend's part**: the actual AI (planned: open-source model like
  Qwen-12B) that receives the profile + insurance data and returns a
  filtered list of nearby, in-network hospitals.

## Stack
- Frontend: plain HTML/CSS/JavaScript (no framework)
- Backend: Node.js + Express
- Database: SQLite (file-based, auto-created on first run)

## User flow (in order)
1. Landing page — "Health 360" heading, Sign In / Create Account
2. Create Account → Terms & Conditions panel (must Accept) → email, username,
   password → account created
3. Sign In → email OR username + password
4. Onboarding (first time only) → name, gender, age, height, weight,
   location, + one or more emergency/family contacts → Submit saves this
5. Insurance page → asks for insurance provider name (e.g. Policybazaar) —
   this happens BEFORE the AI hand-off
6. AI hand-off → app sends profile + location + insurance together to the
   AI. This order matters: insurance must be known before hospital search
   happens, so results can be filtered to only insurance-accepted hospitals.
7. Returning users: anything already saved in the database is never asked
   again — login skips straight past onboarding/insurance if already filled in.

## Database tables (SQLite)
- `users`: id, email, username, password_hash, created_at
- `profiles`: id, user_id, name, gender, age, height_cm, weight_kg,
  location, insurance_provider, created_at, updated_at
- `emergency_contacts`: id, user_id, name, relationship, phone, email
  (a user can have multiple contacts)

## The "AI slot" — API contract for the friend building the AI
Two placeholder endpoints exist on the Node server. They currently just log
and store data — replace the *internals*, keep the *shape*, and the rest of
the site keeps working unchanged:

- `POST /api/ai/send-insurance` — called right after the user submits their
  insurance provider name. Payload: `{ userId, insuranceProvider }`
- `POST /api/ai/send-profile` — called after insurance is saved. Payload:
  `{ userId, name, gender, age, heightCm, weightKg, location,
  insuranceProvider, emergencyContacts: [...] }`
  This is where real hospital search + insurance-based filtering should go.
  Expected eventual response shape: `{ hospitals: [{ name, address,
  distanceKm, acceptsInsurance: true }, ...] }`

## Status
Currently in the planning stage — implementation hasn't started yet.
