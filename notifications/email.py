"""
MOCK notification channel — Email.

Owned by teammate responsibilities ("Family notifications"). This stub
simulates sending so the rest of the system can be built/tested end-to-end.
Replace the body of send_email() with a real provider integration
(e.g. SendGrid, SES, SMTP) when that work is picked up.
"""

from __future__ import annotations


def send_email(to_address: str | None, subject: str, body: str) -> bool:
    if not to_address:
        print(f"[email] SKIPPED (no address on file) — subject={subject!r}")
        return False
    print(f"[email:MOCK] To: {to_address}\nSubject: {subject}\n{body}\n")
    return True
