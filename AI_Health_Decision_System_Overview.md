# AI Health Decision Support System

## Project Overview

This project is an AI-assisted health decision support system that helps
assess a user's symptoms and decide the appropriate next step.

The system has two main outcomes: - **Low/Medium Severity:** Recommend a
home remedy and monitor recovery. - **High/Critical Severity:** Escalate
the case by contacting a hospital and notifying the user's emergency
contacts.

> **Note:** This system is intended as a decision-support tool and is
> **not** a replacement for professional medical advice or emergency
> services.

## Team Responsibilities

### My Responsibilities

-   AI (LLM) integration using OpenRouter
-   Prompt engineering
-   Parsing structured JSON responses
-   Decision engine
-   Remedy workflow
-   State management

### Teammate Responsibilities

-   Hospital communication
-   Family notifications (Email, SMS, WhatsApp, Phone)
-   Insurance lookup
-   Insurance coverage and limit checking

## Workflow

``` text
User describes symptoms
        |
        v
LLM analyzes symptoms
        |
        v
Structured JSON
        |
        v
Decision Engine
        |
   +----+----+
   |         |
Low/Medium  High/Critical
   |         |
Remedy     Emergency
   |         |
Monitor    Hospital + Family
   |         |
Recovered? Insurance + Cost
   |
Yes -> Complete
No  -> Emergency
```

## Expected LLM Output

``` json
{
  "problem": "Migraine",
  "severity": "medium",
  "remedy": "Rest, hydrate, and take an appropriate over-the-counter pain reliever if suitable.",
  "reaction_time": 1800
}
```

## Severity Levels

  Severity   Action
  ---------- -------------------------------
  Low        Home remedy
  Medium     Home remedy + monitor
  High       Contact hospital
  Critical   Immediate hospital assistance

## Project Structure

``` text
project/
├── main.py
├── decision_engine.py
├── llm_interface.py
├── remedy_manager.py
├── emergency_manager.py
├── insurance_manager.py
├── cost_estimator.py
├── models.py
├── notifications/
│   ├── email.py
│   ├── sms.py
│   ├── whatsapp.py
│   └── phone.py
└── database/
    └── patients.db
```

## Technologies

-   Python
-   OpenRouter API
-   Large Language Model (LLM)
-   SQLite
-   Email/SMS/WhatsApp integrations

## Future Improvements

-   Voice input
-   GPS-based nearest hospital lookup
-   Wearable device integration
-   Medical history support
-   Risk score and confidence estimation
