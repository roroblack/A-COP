"""Domain vocabulary for the response generation/review cross-cutting team."""
from __future__ import annotations

import re
from decimal import Decimal
from typing import Pattern

from app.core.verification import QuantityRule, VerificationPolicy


# Business language, rather than the generic review engine, owns this vocabulary.
FORBIDDEN_WORDS = frozenset(
    {"guaranteed", "guarantee", "always", "never", "100%", "무조건", "반드시 보장", "절대"}
)

PII_PATTERNS: tuple[Pattern[str], ...] = (
    re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b"),
    re.compile(r"(?<!\d)(?:\+?\d[\d .()-]{7,}\d)(?!\d)"),
    re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)"),
)

TONE_PROFILES = {
    "professional": "차분하고 명확하며 고객에게 과도한 약속을 하지 않는 문장",
    "empathetic": "고객의 불편을 인정하되 사실과 다음 행동을 분리하는 문장",
}

RESPONSE_VERIFICATION_POLICY = VerificationPolicy(
    references={"payment_id": "payments", "policy_ref": "policies"},
    quantities=(
        QuantityRule("refund_amount", "payment_id", "amount_cents", scale=Decimal(100)),
    ),
    ignored=frozenset({"tone", "tone_ok", "status", "final_response_text", "answer", "claims"}),
)

__all__ = [
    "FORBIDDEN_WORDS",
    "PII_PATTERNS",
    "TONE_PROFILES",
    "RESPONSE_VERIFICATION_POLICY",
]
