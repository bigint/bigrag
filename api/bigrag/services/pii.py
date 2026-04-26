from __future__ import annotations

import re

_EMAIL = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE = re.compile(r"(?<!\w)(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}(?!\w)")
_SSN = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")
_CARD = re.compile(r"(?<!\d)(?:\d[\s-]?){13,19}(?!\d)")
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

    return redact(text) != text
