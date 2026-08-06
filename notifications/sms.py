"""
MOCK notification channel — SMS.

Owned by teammate responsibilities ("Family notifications"). This stub
simulates sending so the rest of the system can be built/tested end-to-end.
Replace the body of send_sms() with a real provider integration
(e.g. Twilio) when that work is picked up.
"""

from __future__ import annotations


def send_sms(to_number: str | None, message: str) -> bool:
    if not to_number:
        print(f"[sms] SKIPPED (no phone number on file) — message={message!r}")
        return False
    print(f"[sms:MOCK] To: {to_number}\n{message}\n")
    return True
