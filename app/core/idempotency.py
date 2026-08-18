"""Deterministic idempotency keys shared by Teams and server action writers."""
from __future__ import annotations

import hashlib
from typing import Any


def idempotency_key(*, tenant_id: str, request_id: str, action_type: str, business_subject: str) -> str:
    """Return the v5 §10-1 key: sha256(tenant_id + request_id + action_type + subject)."""
    material = f"{tenant_id}{request_id}{action_type}{business_subject}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def request_id_for_case(case: dict[str, Any]) -> str:
    """Use the originating request id, with a stable case id fallback for older cases."""
    state = case.get("state_json") or {}
    return str(state.get("request_id") or case["case_id"])

