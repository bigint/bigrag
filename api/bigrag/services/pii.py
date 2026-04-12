"""Regex-based PII redaction.

Light-weight alternative to presidio so self-hosters don't need a
Java-heavy dependency. Covers the patterns that actually matter for
most support / helpdesk corpora: email, phone (E.164 + North American),
credit-card-like 16 digits, US SSN, and passport-ish 9-alphanumeric.

Not a substitute for a dedicated DLP pipeline — but a pragmatic
default that won't embed customer CC numbers into Milvus.
"""

from __future__ import annotations

import re

_EMAIL = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
# E.164 or NANP: +1-555-555-5555, (555) 555-5555, 555.555.5555, etc.
_PHONE = re.compile(
    r"(?<!\w)(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}(?!\w)"
)
_SSN = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")
# Cards: 13-19 digits with optional hyphens/spaces. Passes Luhn to
# reduce false positives on long random numbers.
_CARD = re.compile(r"(?<!\d)(?:\d[\s-]?){13,19}(?!\d)")
# 9-char alphanumerics surrounded by word boundaries — passport-style.
_PASSPORT = re.compile(r"(?<!\w)[A-Z]{1,2}\d{6,8}(?!\w)")


def _luhn(digits: str) -> bool:
    s = [int(c) for c in digits if c.isdigit()]
    if len(s) < 13 or len(s) > 19:
        return False
    total = 0
    parity = len(s) % 2
    for i, d in enumerate(s):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def redact(text: str) -> str:
    """Replace matched PII with typed placeholders."""
    text = _EMAIL.sub("[EMAIL]", text)
    text = _PHONE.sub("[PHONE]", text)
    text = _SSN.sub("[SSN]", text)

    def _card_sub(m: re.Match) -> str:
        digits = re.sub(r"\D", "", m.group(0))
        if _luhn(digits):
            return "[CARD]"
        return m.group(0)

    text = _CARD.sub(_card_sub, text)
    text = _PASSPORT.sub("[PASSPORT]", text)
    return text


def has_pii(text: str) -> bool:
    """True if redact() would change ``text``."""
    return redact(text) != text
