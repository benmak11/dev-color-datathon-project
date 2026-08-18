"""Check that every figure in a narrated answer came from the payload.

This is production code, not test code. It runs on every answer the app
renders, before the reader sees the sentence. It lived in `checks.py` during
the build, which put a runtime guard inside the test file and made the
dependency read backwards.

The model is instructed never to invent a number. During live testing it did
anyway, on 4 of 5 runs, with figures close enough to the truth to read as
correct. An instruction is not a mechanism. This is the mechanism.
"""

import re

NUMBER_PATTERN = re.compile(r"\d[\d,]*(?:\.\d+)?")


def normalise(token):
    """'1,000' and '1000' are the same number. '9.10' and '9.1' are too."""
    token = token.replace(",", "")
    if "." in token:
        token = token.rstrip("0").rstrip(".")
    return token or "0"


def _forms_of(value):
    """The ways a writer might reasonably render one payload number."""
    forms = {str(value), f"{value:,}"}
    if isinstance(value, float):
        forms |= {
            f"{value:.0f}",
            f"{value:.1f}",
            f"{value:.2f}",
            f"{value:,.0f}",
            f"{value:,.1f}",
        }
    return {normalise(form) for form in forms}


def payload_numbers(payload):
    """Every number the payload actually contains, in every renderable form.

    Deliberately does NOT expand a rate into its percentage. Payloads ship a
    `_display` string for every rate, so the readable form is already present
    as text. Auto-expanding would widen the allowed set enough to let an
    invented figure through, which is the one thing this check exists to stop.
    """
    allowed = set()

    def walk(node):
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
        elif isinstance(node, bool):
            pass  # bools are ints in Python; they are not figures
        elif isinstance(node, (int, float)):
            allowed.update(_forms_of(node))
        elif isinstance(node, str):
            for token in NUMBER_PATTERN.findall(node):
                allowed.add(normalise(token))

    walk(payload)
    return allowed


def provenance_check(narration, payload):
    """Return (ok, unbacked_tokens) for one narrated answer.

    Fails closed: any token that cannot be traced means the caller suppresses
    the prose and shows the table on its own.
    """
    allowed = payload_numbers(payload)
    unbacked = [
        token
        for token in NUMBER_PATTERN.findall(narration)
        if normalise(token) not in allowed
    ]
    return not unbacked, unbacked
