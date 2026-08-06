"""Single-file version of the diagnosis/triage part of the app.

Flow:
  1. (Stand-in for your teammate's sign-up part) load the patient profile
     (name, gender, height, weight, emergency contacts, insurance, location
     + nearby hospitals).
  2. Ask the customer to describe their issue in detail.
  3. Qwen3-14B decides: AMBULANCE / REMEDY / REQUEST_MEDIA.
  4. If REQUEST_MEDIA, ask for a photo/video path, describe it with
     Qwen2.5-VL (vision model), and re-run the triage decision with that
     extra context.
  5. AMBULANCE -> simulated dispatch/log (no real call is placed).
     REMEDY     -> print the remedy advice + safety disclaimer.

This is a prototype decision-support tool, not a medical device.

Setup:
  pip install requests opencv-python-headless python-dotenv truststore
  set OPENROUTER_API_KEY=sk-or-...   (PowerShell: $env:OPENROUTER_API_KEY = "...")
  python triage_app.py
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Some networks (corporate proxies, sandboxed dev environments) intercept TLS
# with their own root CA that isn't in Python's bundled certifi store, even
# though it's trusted by the OS. This makes requests use the OS trust store
# instead, matching what curl/the browser already trust.
import truststore

truststore.inject_into_ssl()

import requests
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
TRIAGE_MODEL = os.environ.get("TRIAGE_MODEL", "qwen/qwen3-14b")
VISION_MODEL = os.environ.get("VISION_MODEL", "qwen/qwen2.5-vl-72b-instruct")

DEFAULT_LOG_PATH = Path(__file__).resolve().parent / "dispatch_log.jsonl"
MAX_MEDIA_ROUNDS = 1  # how many times we'll ask for a photo/video before failing safe

DISCLAIMER = (
    "This is a prototype decision-support tool, not a medical device and not "
    "a substitute for professional medical advice. If you believe this is a "
    "life-threatening emergency, call your local emergency number now."
)

EMERGENCY_REMINDER = (
    "This app is a prototype and does not place real emergency calls. "
    "If this is a life-threatening emergency, call your local emergency "
    "number (e.g. 911 / 112 / 999) right now, in addition to anything this "
    "app does."
)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
MAX_MEDIA_FILE_SIZE_MB = 25


# --------------------------------------------------------------------------
# Patient profile
#
# This mirrors what the sign-up / onboarding part of the app is expected to
# hand off to the triage part. Replace `load_patient_profile()` with the
# real handoff once your teammate's module is ready -- the field names
# below are the contract between the two parts.
# --------------------------------------------------------------------------

@dataclass
class EmergencyContact:
    name: str
    phone: str
    relationship: str = ""


@dataclass
class Hospital:
    name: str
    phone: str
    address: str = ""
    distance_km: Optional[float] = None


@dataclass
class PatientProfile:
    name: str
    gender: str
    height_cm: float
    weight_kg: float
    location: str
    emergency_contacts: list[EmergencyContact] = field(default_factory=list)
    insurance_provider: Optional[str] = None
    insurance_id: Optional[str] = None
    nearby_hospitals: list[Hospital] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "PatientProfile":
        contacts = [
            EmergencyContact(**c) if isinstance(c, dict) else c
            for c in data.get("emergency_contacts", [])
        ]
        hospitals = [
            Hospital(**h) if isinstance(h, dict) else h
            for h in data.get("nearby_hospitals", [])
        ]
        return cls(
            name=data["name"],
            gender=data["gender"],
            height_cm=float(data["height_cm"]),
            weight_kg=float(data["weight_kg"]),
            location=data.get("location", ""),
            emergency_contacts=contacts,
            insurance_provider=data.get("insurance_provider"),
            insurance_id=data.get("insurance_id"),
            nearby_hospitals=hospitals,
        )

    def to_dict(self) -> dict:
        return asdict(self)

    def summary_for_prompt(self) -> str:
        return "\n".join([
            f"Name: {self.name}",
            f"Gender: {self.gender}",
            f"Height: {self.height_cm} cm",
            f"Weight: {self.weight_kg} kg",
            f"Location: {self.location}",
        ])

    def full_summary(self) -> str:
        """Everything on file for this patient, for display to the user --
        not just the subset used in the triage prompt."""
        lines = [
            f"Name: {self.name}",
            f"Gender: {self.gender}",
            f"Height: {self.height_cm} cm",
            f"Weight: {self.weight_kg} kg",
            f"Location: {self.location}",
        ]
        for c in self.emergency_contacts:
            rel = f", {c.relationship}" if c.relationship else ""
            lines.append(f"Emergency Contact: {c.name}{rel} - {c.phone}")
        if self.insurance_provider:
            lines.append(f"Insurance: {self.insurance_provider} (ID: {self.insurance_id or 'n/a'})")
        for h in self.nearby_hospitals:
            lines.append(f"Nearby Hospital: {h.name} - {h.phone}")
        return "\n".join(lines)


# Fallback profile, only used if patient_info.txt is missing or unreadable.
MOCK_PROFILE = PatientProfile(
    name="Jane Doe",
    gender="female",
    height_cm=165,
    weight_kg=60,
    location="221B Example Street, Springfield",
    emergency_contacts=[
        EmergencyContact(name="John Doe", phone="+1-555-0101", relationship="spouse"),
    ],
    insurance_provider="Goodlife Insurance",
    insurance_id="GLI-12345",
    nearby_hospitals=[
        Hospital(name="Manipal Hospital", phone="+1-555-0100",
                 address="1 Hospital Way, Springfield", distance_km=3.2),
    ],
)

PATIENT_INFO_PATH = Path(__file__).resolve().parent / "patient_info.txt"


def _parse_patient_info_text(text: str) -> dict:
    """Turns 'Label: value' lines into a {lowercased label: value} dict.
    Blank lines and lines starting with # are ignored."""
    fields: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip().lower()] = value.strip()
    return fields


def load_patient_profile_from_text(path: Path = PATIENT_INFO_PATH) -> PatientProfile:
    """Reads patient details from a plain-text file (see patient_info.txt)
    instead of hardcoded Python -- this is a stand-in for the real handoff
    from the sign-up/onboarding part."""
    fields = _parse_patient_info_text(path.read_text(encoding="utf-8"))

    def number(key: str) -> Optional[float]:
        raw = fields.get(key, "")
        digits = "".join(ch for ch in raw if ch.isdigit() or ch == ".")
        return float(digits) if digits else None

    contacts = []
    if fields.get("emergency contact name"):
        contacts.append(EmergencyContact(
            name=fields.get("emergency contact name", ""),
            phone=fields.get("emergency contact phone", ""),
            relationship=fields.get("emergency contact relationship", ""),
        ))

    hospitals = []
    if fields.get("nearby hospital name"):
        hospitals.append(Hospital(
            name=fields.get("nearby hospital name", ""),
            phone=fields.get("nearby hospital phone", ""),
            address=fields.get("nearby hospital address", ""),
            distance_km=number("nearby hospital distance (km)"),
        ))

    return PatientProfile(
        name=fields.get("name", ""),
        gender=fields.get("gender", ""),
        height_cm=number("height (cm)") or 0.0,
        weight_kg=number("weight (kg)") or 0.0,
        location=fields.get("location", ""),
        emergency_contacts=contacts,
        insurance_provider=fields.get("insurance provider") or None,
        insurance_id=fields.get("insurance id") or None,
        nearby_hospitals=hospitals,
    )


def load_patient_profile() -> PatientProfile:
    # TODO: once the real sign-up/onboarding handoff exists, use that
    # instead. Until then, this reads patient_info.txt (plain text, no
    # code needed to edit) and falls back to MOCK_PROFILE if that file is
    # missing or can't be parsed.
    try:
        return load_patient_profile_from_text()
    except Exception as exc:  # noqa: BLE001
        print(f"Could not load patient_info.txt ({exc}); using built-in mock profile instead.")
        return MOCK_PROFILE


# --------------------------------------------------------------------------
# Media helpers -- turn an uploaded photo/video into base64 image payloads
# --------------------------------------------------------------------------

def encode_image_to_data_uri(image_path: str | Path) -> str:
    path = Path(image_path)
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    data = path.read_bytes()
    b64 = base64.b64encode(data).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def extract_frames_as_data_uris(video_path: str | Path, num_frames: int = 3) -> list[str]:
    """Samples a handful of evenly spaced frames from a video. Requires
    opencv-python(-headless)."""
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError(
            "Video analysis requires opencv-python-headless. "
            "Install it with `pip install opencv-python-headless`."
        ) from exc

    path = Path(video_path)
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video file: {path}")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    num_frames = max(1, min(num_frames, total_frames))
    frame_indices = [int(total_frames * i / num_frames) for i in range(num_frames)]

    data_uris = []
    for idx in frame_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = cap.read()
        if not ok:
            continue
        ok, buf = cv2.imencode(".jpg", frame)
        if not ok:
            continue
        b64 = base64.b64encode(buf.tobytes()).decode("utf-8")
        data_uris.append(f"data:image/jpeg;base64,{b64}")
    cap.release()

    if not data_uris:
        raise RuntimeError(f"Could not extract any frames from video: {path}")
    return data_uris


def media_to_data_uris(media_path: str | Path) -> list[str]:
    path = Path(media_path)

    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > MAX_MEDIA_FILE_SIZE_MB:
        raise ValueError(
            f"File is {size_mb:.1f} MB, which is over the {MAX_MEDIA_FILE_SIZE_MB} MB "
            "limit. Please upload a smaller photo/video."
        )

    ext = path.suffix.lower()
    if ext in IMAGE_EXTENSIONS:
        return [encode_image_to_data_uri(path)]
    if ext in VIDEO_EXTENSIONS:
        return extract_frames_as_data_uris(path)
    raise ValueError(f"Unsupported media type: {ext}")


# --------------------------------------------------------------------------
# Vision step -- Qwen3-14B is text-only, so when it can't make a safe call
# from the description alone, the app asks for a photo/video and this
# describes it with a vision-language model. That description feeds back
# into the text triage step; the VLM never makes the ambulance/remedy call.
# --------------------------------------------------------------------------

VISION_SYSTEM_PROMPT = """You are a visual observation assistant supporting a \
medical triage system. Look at the provided image(s) (they may be frames from \
a short video) and describe ONLY what is objectively visible: e.g. location \
and appearance of an injury, skin color/swelling/bleeding, visible posture or \
distress, apparent severity cues.

Do NOT diagnose, do NOT suggest treatment, and do NOT decide whether this is \
an emergency -- another system handles that. If the image is unclear, blurry, \
or does not show anything medically relevant, say so plainly.

Respond with a short, factual paragraph (3-6 sentences)."""


def describe_media(data_uris: list[str], patient_context: str = "") -> str:
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise RuntimeError("OPENROUTER_API_KEY environment variable is not set.")

    content = []
    if patient_context:
        content.append({"type": "text", "text": f"Context: {patient_context}"})
    content.append({"type": "text", "text": "Describe what is visible in relation to the patient's issue."})
    for uri in data_uris:
        content.append({"type": "image_url", "image_url": {"url": uri}})

    payload = {
        "model": VISION_MODEL,
        "messages": [
            {"role": "system", "content": VISION_SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        "temperature": 0.2,
    }
    headers = {
        "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
        "Content-Type": "application/json",
    }

    resp = requests.post(OPENROUTER_URL, headers=headers, data=json.dumps(payload), timeout=60)
    resp.raise_for_status()
    result = resp.json()
    return result["choices"][0]["message"]["content"].strip()


# --------------------------------------------------------------------------
# Triage decision -- Qwen3-14B decides REMEDY / HOME_VISIT / AMBULANCE /
# REQUEST_MEDIA
#
# Safety design:
# - AMBULANCE is reserved for genuinely life-threatening emergencies. The
#   model is instructed to err toward AMBULANCE only when it can't rule out
#   one of those specific dangerous conditions -- not for ordinary symptoms.
# - If the API call fails or the response can't be parsed, we fail SAFE by
#   defaulting to AMBULANCE rather than silently returning a remedy.
# --------------------------------------------------------------------------

TRIAGE_SYSTEM_PROMPT = """You are a cautious pre-hospital triage assistant embedded in \
a health app. You are NOT a doctor and this is NOT a medical diagnosis.

Decide exactly one of these three actions:

- "REMEDY": the issue is minor and self-limiting -- e.g. an ordinary fever, \
a single episode of vomiting, a headache, a mild stomach ache, a common cold, \
a small cut, a minor bruise. Give a clear, specific diagnosis (what it likely \
is) and self-care plan: tell them to rest and drink water, plus an \
appropriate over-the-counter medicine for that specific symptom, for example:
  * Fever -> a paracetamol-based medicine (e.g. Dolo 650)
  * Common cold -> a cough syrup, plus a multivitamin syrup to support recovery
  * Headache -> rest and hydrate first; if it still hurts, apply a balm \
(e.g. a menthol/pain-relief balm) to the forehead/temples
  * Mild stomach ache -> an antacid, plus a probiotic food like curd/yogurt \
or an over-the-counter probiotic supplement. If it worsens, tell them to \
call the hospital.
  * Single episode of vomiting -> ORS/electrolytes for fluid loss
For anything not covered by these examples, use similar general OTC \
guidance appropriate to the specific symptom. Always add a line to call the \
hospital or seek professional care if it worsens or doesn't improve within \
a reasonable time.

- "AMBULANCE": reserved ONLY for genuinely life-threatening emergencies -- \
e.g. heart attack signs (chest pain/pressure, pain radiating to the arm/jaw, \
sweating, shortness of breath), a ruptured or bursting appendix (sudden \
severe abdominal pain with rigidity/worsening fever), a cardiac event, \
stroke signs (face drooping, arm weakness, slurred speech), severe \
uncontrolled bleeding, loss of consciousness, severe allergic reaction \
(anaphylaxis), major trauma, or suspected poisoning/overdose. Do NOT choose \
AMBULANCE for ordinary, non-alarming symptoms like a typical fever, a single \
vomiting episode, a normal headache, or mild stomach ache -- those belong in \
REMEDY instead. When genuinely uncertain whether something IS one of these \
true emergencies, still err toward AMBULANCE.

- "REQUEST_MEDIA": the text description alone is too vague or ambiguous to \
safely decide between the above, AND a photo or short video could plausibly \
help (e.g. a visible rash, wound, swelling, or something the patient \
struggles to describe in words). Explain briefly what you want to see and why.

Rules:
- Never invent facts not given to you.
- Use the patient profile (age-relevant details, weight, etc.) only as \
supporting context, not as the primary basis for the decision.
- If you already received a vision description of a photo/video, use it \
as additional evidence and do not choose REQUEST_MEDIA again.
- Respond with ONLY a single JSON object matching this schema, no other text:
{
  "decision": "REMEDY" | "AMBULANCE" | "REQUEST_MEDIA",
  "urgency": "low" | "medium" | "high" | "critical",
  "reasoning": "1-3 sentence internal reasoning",
  "remedy_advice": "string or null -- required if decision is REMEDY",
  "media_request_reason": "string or null -- required if decision is REQUEST_MEDIA"
}"""

DECISIONS = {"REMEDY", "AMBULANCE", "REQUEST_MEDIA"}


@dataclass
class TriageResult:
    decision: str  # "REMEDY" | "AMBULANCE" | "REQUEST_MEDIA"
    urgency: str
    reasoning: str
    remedy_advice: Optional[str] = None
    media_request_reason: Optional[str] = None
    fail_safe: bool = False  # True if this came from an error fallback, not the model


def _build_user_prompt(profile: PatientProfile, description: str, vision_description: Optional[str]) -> str:
    parts = [
        "Patient profile:",
        profile.summary_for_prompt(),
        "",
        "Patient's own description of the issue:",
        description.strip(),
    ]
    if vision_description:
        parts += ["", "Visual observation from submitted photo/video:", vision_description.strip()]
    return "\n".join(parts)


def triage(profile: PatientProfile, description: str, vision_description: Optional[str] = None) -> TriageResult:
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise RuntimeError("OPENROUTER_API_KEY environment variable is not set.")

    user_prompt = _build_user_prompt(profile, description, vision_description)
    payload = {
        "model": TRIAGE_MODEL,
        "messages": [
            {"role": "system", "content": TRIAGE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(OPENROUTER_URL, headers=headers, data=json.dumps(payload), timeout=60)
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"]
        data = json.loads(raw)
        decision = data["decision"]
        if decision not in DECISIONS:
            raise ValueError(f"Unexpected decision value: {decision}")
        return TriageResult(
            decision=decision,
            urgency=data.get("urgency", "unknown"),
            reasoning=data.get("reasoning", ""),
            remedy_advice=data.get("remedy_advice"),
            media_request_reason=data.get("media_request_reason"),
        )
    except Exception as exc:  # noqa: BLE001 -- deliberate broad catch for fail-safe
        # Fail SAFE: if the model call/parse fails, don't silently hand back
        # a remedy. Default to recommending emergency care.
        return TriageResult(
            decision="AMBULANCE",
            urgency="unknown",
            reasoning=f"Triage engine error, failing safe: {exc}",
            fail_safe=True,
        )


# --------------------------------------------------------------------------
# Simulated ambulance dispatch
#
# This does NOT call any real hospital, emergency number, or dispatch API.
# It logs a clearly-labeled dispatch event (console + JSONL file) so the
# flow can be demoed end-to-end. Swap `notify_hospital` for a real
# integration (hospital webhook, SMS to the hospital's line, etc.) only
# once you have an actual endpoint and are ready to go beyond a demo.
# --------------------------------------------------------------------------

def notify_hospital(profile: PatientProfile, result: TriageResult) -> dict:
    hospital = profile.nearby_hospitals[0] if profile.nearby_hospitals else None
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": "SIMULATED_AMBULANCE_DISPATCH",
        "patient": {
            "name": profile.name,
            "gender": profile.gender,
            "location": profile.location,
        },
        "urgency": result.urgency,
        "reasoning": result.reasoning,
        "notified_hospital": {
            "name": hospital.name if hospital else None,
            "phone": hospital.phone if hospital else None,
        },
        "emergency_contacts_notified": [
            {"name": c.name, "phone": c.phone} for c in profile.emergency_contacts
        ],
        "insurance_notified": {
            "provider": profile.insurance_provider,
            "insurance_id": profile.insurance_id,
        },
    }


def dispatch_ambulance(profile: PatientProfile, result: TriageResult, log_path: Path = DEFAULT_LOG_PATH) -> dict:
    event = notify_hospital(profile, result)

    print("=" * 60)
    print("  SIMULATED AMBULANCE DISPATCH -- no real call is being made")
    print("=" * 60)
    print(f"Patient:   {profile.name} ({profile.gender})")
    print(f"Location:  {profile.location}")
    print(f"Urgency:   {result.urgency}")
    print(f"Reasoning: {result.reasoning}")
    if event["notified_hospital"]["name"]:
        print(f"Would call ambulance from: {event['notified_hospital']['name']} "
              f"({event['notified_hospital']['phone']})")
    else:
        print("Would call ambulance from: <no nearby hospital on file>")
    if event["emergency_contacts_notified"]:
        names = ", ".join(c["name"] for c in event["emergency_contacts_notified"])
        print(f"Would notify emergency contact(s): {names}")
    if event["insurance_notified"]["provider"]:
        print(f"Would contact insurance: {event['insurance_notified']['provider']} "
              f"(ID: {event['insurance_notified']['insurance_id']})")
    print("-" * 60)
    print(EMERGENCY_REMINDER)
    print("=" * 60)

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")

    return event


# --------------------------------------------------------------------------
# CLI flow
# --------------------------------------------------------------------------

def prompt_for_media_path() -> str | None:
    path = input("Enter the path to a photo or short video (or press Enter to skip): ").strip()
    return path or None


def run() -> None:
    print(DISCLAIMER)
    print()

    profile = load_patient_profile()
    print(f"Welcome, {profile.name}. Please describe what's going on in as much detail as you can.")
    description = input("> ").strip()

    print("\nYour profile on file:")
    print(profile.full_summary())

    vision_description = None
    media_rounds = 0

    while True:
        result = triage(profile, description, vision_description)
        print(f"\n[triage] decision={result.decision} urgency={result.urgency}")
        print(f"[triage] reasoning: {result.reasoning}")

        if result.decision == "AMBULANCE":
            dispatch_ambulance(profile, result)
            break

        elif result.decision == "REMEDY":
            print("\nSuggested self-care:")
            print(result.remedy_advice or "(no advice returned)")
            print(f"\n{EMERGENCY_REMINDER}")
            break

        elif result.decision == "REQUEST_MEDIA":
            print(f"\nThe assistant would like to see a photo or video: {result.media_request_reason}")

            if media_rounds >= MAX_MEDIA_ROUNDS:
                print("No usable media provided after a follow-up request -- failing safe.")
                dispatch_ambulance(
                    profile,
                    TriageResult(
                        decision="AMBULANCE",
                        urgency=result.urgency or "unknown",
                        reasoning="Could not resolve via text or media; failing safe.",
                        fail_safe=True,
                    ),
                )
                break

            media_path = prompt_for_media_path()
            media_rounds += 1
            if not media_path:
                print("No media provided; continuing with text description only.")
                media_rounds = MAX_MEDIA_ROUNDS  # avoid an infinite loop
                continue

            try:
                data_uris = media_to_data_uris(media_path)
                vision_description = describe_media(data_uris, patient_context=description)
                print(f"[vision] {vision_description}")
            except Exception as exc:  # noqa: BLE001
                print(f"Could not analyze media ({exc}); continuing with text description only.")
                media_rounds = MAX_MEDIA_ROUNDS
            continue

        else:
            print("Unexpected triage result; failing safe.")
            dispatch_ambulance(profile, result)
            break


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        sys.exit(1)
