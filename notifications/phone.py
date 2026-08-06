"""
MOCK notification channel — Phone call.

Owned by teammate responsibilities ("Family notifications"). This stub
simulates placing a call so the rest of the system can be built/tested
end-to-end. Replace the body of place_call() with a real provider
integration (e.g. Twilio Voice) when that work is picked up.
"""

from __future__ import annotations


def place_call(to_number: str | None, message: str) -> bool:
    if not to_number:
        print(f"[phone] SKIPPED (no number on file) — message={message!r}")
        return False
    print(f"[phone:MOCK] Calling {to_number} with automated message:\n{message}\n")
    return True
