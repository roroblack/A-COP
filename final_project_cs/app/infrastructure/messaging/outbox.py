"""Outbox-backed MessageBrokerPort. It does not implement Redis Streams."""
from __future__ import annotations

from typing import Any, Callable
from uuid import UUID

from psycopg.types.json import Json

from app.infrastructure.db.session import get_connection


class OutboxBrokerAdapter:
    def __init__(self, connection_factory: Callable = get_connection) -> None:
        self.connection_factory = connection_factory

    async def publish(self, topic: str, payload: dict[str, Any], dedupe_key: str) -> str:
        with self.connection_factory() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute("SELECT tenant_id FROM customer_cases WHERE case_id=%s LIMIT 1", (payload.get("case_id"),))
                    row = cur.fetchone()
                    tenant_id = payload.get("tenant_id") or (row[0] if row else None)
                    if tenant_id is None:
                        raise ValueError("tenant_id is required for outbox publish")
                    cur.execute("INSERT INTO outbox(tenant_id,topic,dedupe_key,payload_json) VALUES(%s,%s,%s,%s) "
                                "ON CONFLICT(topic,dedupe_key) DO NOTHING RETURNING message_id", (tenant_id, topic, dedupe_key, Json(payload)))
                    inserted = cur.fetchone()
        return str(inserted[0]) if inserted else dedupe_key

    async def ack(self, message_id: str) -> None:
        with self.connection_factory() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute("UPDATE outbox SET status='delivered', locked_at=NULL WHERE message_id=%s", (message_id,))
