"""
MOCK notification channel — WhatsApp.

Owned by teammate responsibilities ("Family notifications"). This stub
simulates sending so the rest of the system can be built/tested end-to-end.
Replace the body of send_whatsapp() with a real provider integration
(e.g. WhatsApp Business API / Twilio) when that work is picked up.
"""

from __future__ import annotations


def send_whatsapp(to_number: str | None, message: str) -> bool:
    if not to_number:
        print(f"[whatsapp] SKIPPED (no number on file) — message={message!r}")
        return False
    print(f"[whatsapp:MOCK] To: {to_number}\n{message}\n")
    return True
