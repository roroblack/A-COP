"""발표 시나리오 Case 2건을 demo tenant 에 남긴다 (삭제하지 않는다).

쇼핑몰 도메인의 seed 데이터에서 실제 고객·주문·배송 행을 조회해 발표용 Case를
만든다. 상태 전이는 ``transition_case()``로만 수행하며, 재실행 시 이 스크립트가
만든 Case만 지우고 같은 고정 Case ID로 다시 만든다.

    python -m scripts.seed_demo_cases
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, UUID, uuid5

from psycopg.types.json import Json

from app.core.settings import get_settings
from app.core.transition import transition_case
from app.domain.events import EventType
from app.infrastructure.db.session import get_connection

SEEDED_BY = "scripts.seed_demo_cases"
MARKER = {"seeded_by": SEEDED_BY, "note": "발표 시연용. LLM 호출 없이 고정값으로 만든 Case"}

SCENARIO_1 = "demo-scenario-1-delivered-but-not-received"
SCENARIO_2 = "demo-scenario-2-exchange-period-question"


def _reset(conn, tenant: str, external_id: str) -> UUID:
    """seed.py가 만든 고객을 찾고, 그 고객의 기존 발표 Case만 지운다."""
    with conn.cursor() as cur:
        cur.execute("SELECT customer_id FROM customers WHERE tenant_id=%s AND external_id=%s", (tenant, external_id))
        row = cur.fetchone()
        if row is None:
            raise RuntimeError(f"scripts.seed가 만든 고객을 찾을 수 없습니다: {external_id}")
        customer_id = row[0]
        cur.execute("SELECT case_id FROM customer_cases WHERE tenant_id=%s AND customer_id=%s", (tenant, customer_id))
        case_ids = [r[0] for r in cur.fetchall()]
        for case_id in case_ids:
            cur.execute("DELETE FROM action_approvals WHERE action_id IN (SELECT action_id FROM action_requests WHERE tenant_id=%s AND case_id=%s)", (tenant, case_id))
            cur.execute("DELETE FROM action_requests WHERE tenant_id=%s AND case_id=%s", (tenant, case_id))
            cur.execute("DELETE FROM case_events WHERE tenant_id=%s AND case_id=%s", (tenant, case_id))
            cur.execute("DELETE FROM customer_cases WHERE tenant_id=%s AND case_id=%s", (tenant, case_id))
        return customer_id


def _fixed_case_id(tenant: str, scenario: str) -> UUID:
    """시나리오 이름으로 결정적인 case_id를 만든다."""
    return uuid5(NAMESPACE_URL, f"acop://{tenant}/demo/{scenario}")


def _create(conn, tenant: str, customer_id: UUID, case_id: UUID, subject: str) -> UUID:
    """초기 Case를 만들고, 이후 상태 전이는 모두 transition_case()로 수행한다."""
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO customer_cases (case_id, tenant_id, customer_id, status, subject, state_json) "
            "VALUES (%s,%s,%s,'new',%s,%s) RETURNING case_id",
            (case_id, tenant, customer_id, subject, Json(dict(MARKER))),
        )
        return cur.fetchone()[0]


def _step(conn, tenant: str, case_id: UUID, version: int, event: EventType, payload: dict) -> int:
    with conn.transaction():
        transition_case(conn, tenant_id=tenant, case_id=case_id, expected_version=version,
                        event_type=event, payload=payload, actor_type="seed", actor_id=SEEDED_BY)
    return version + 1


def _observed_at() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_order(conn, tenant: str, external_id: str, order_no: str) -> tuple:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT o.order_id, o.order_no, o.total_cents, o.item_count, o.status "
            "FROM orders o JOIN customers c USING(customer_id) "
            "WHERE o.tenant_id=%s AND c.external_id=%s AND o.order_no=%s",
            (tenant, external_id, order_no),
        )
        row = cur.fetchone()
    if row is None:
        raise RuntimeError(f"seed.py가 만든 주문을 찾을 수 없습니다: {external_id}/{order_no}")
    return row


def scenario_1(conn, tenant: str) -> tuple[UUID, int]:
    """배송완료 미수령 → 환불 제안 → waiting_approval에서 멈춘다."""
    customer_id = _reset(conn, tenant, "cust_01")
    order_id, order_no, total_cents, item_count, order_status = _require_order(conn, tenant, "cust_01", "ORD-0101")
    if order_status != "delivered":
        raise RuntimeError(f"시나리오 1 주문 상태가 delivered가 아닙니다: {order_no}/{order_status}")

    with conn.cursor() as cur:
        cur.execute(
            "SELECT shipment_id, status, delivered_at FROM shipments "
            "WHERE tenant_id=%s AND order_id=%s ORDER BY shipped_at LIMIT 1",
            (tenant, order_id),
        )
        shipment = cur.fetchone()
    if shipment is None or shipment[1] != "delivered" or shipment[2] is None:
        raise RuntimeError(f"시나리오 1 배송완료 행을 찾을 수 없습니다: {order_no}")
    shipment_id, shipment_status, delivered_at = shipment
    observed_at = _observed_at()

    case_id = _create(conn, tenant, customer_id, _fixed_case_id(tenant, SCENARIO_1),
                      "배송완료로 표시됐지만 상품을 받지 못한 주문의 환불 제안")
    v = _step(conn, tenant, case_id, 0, EventType.CREATED,
              {"channel": "web", "message": "배송완료로 떴는데 상품을 못 받았습니다. 확인 부탁드립니다."})
    v = _step(conn, tenant, case_id, v, EventType.CLASSIFIED,
              {"intent": "shipping", "issue_code": "delivered_but_not_received", "sentiment": "negative"})
    v = _step(conn, tenant, case_id, v, EventType.ROUTED,
              {"owner_team_id": "order_shipping", "capability": "order.investigate"})

    evidence = [
        {"source_type": "policy_chunk", "source_id": "doc_01#환불 금액의 산정",
         "claim": "받지 못한 상품의 수량만큼 환불액을 계산하고 원 주문 총액을 넘지 않도록 한다.",
         "observed_at": observed_at},
        {"source_type": "order", "source_id": str(order_id),
         "claim": f"order_no={order_no}, status={order_status}, total_cents={total_cents}, item_count={item_count}",
         "observed_at": observed_at},
        {"source_type": "shipment", "source_id": str(shipment_id),
         "claim": f"status={shipment_status}, delivered_at={delivered_at.isoformat()}",
         "observed_at": observed_at},
    ]
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO action_requests (tenant_id, case_id, action_type, arguments_json, idempotency_key, status) "
            "VALUES (%s,%s,%s,%s,%s,'pending_approval') RETURNING action_id",
            (tenant, case_id, "refund.request", Json({"order_id": str(order_id), "seeded_by": SEEDED_BY,
                                                        "evidence": evidence}),
             f"{tenant}:{SCENARIO_1}:refund:{order_no}"),
        )
        action_id = cur.fetchone()[0]

    v = _step(conn, tenant, case_id, v, EventType.APPROVAL_REQUIRED,
              {"action_id": str(action_id), "action_type": "refund.request",
               "reason": "배송완료 상태의 주문과 배송완료 시각이 확인됐지만 고객은 상품을 받지 못했다고 신고하여 환불 제안을 만들었습니다. 근거 확인 후 승인이 필요합니다."})
    conn.commit()
    return case_id, v


def scenario_2(conn, tenant: str) -> tuple[UUID, int]:
    """교환 기한 문의 → 정책 안내 → resolved 종단."""
    customer_id = _reset(conn, tenant, "cust_02")
    with conn.cursor() as cur:
        cur.execute(
            "SELECT o.order_id, o.order_no, o.total_cents, o.item_count, o.status, o.ordered_at "
            "FROM orders o JOIN customers c USING(customer_id) "
            "WHERE o.tenant_id=%s AND c.external_id=%s AND o.order_no=%s",
            (tenant, "cust_02", "ORD-0201"),
        )
        order = cur.fetchone()
    if order is None:
        raise RuntimeError("seed.py가 만든 주문을 찾을 수 없습니다: cust_02/ORD-0201")
    order_id, order_no, total_cents, item_count, order_status, ordered_at = order
    observed_at = _observed_at()

    case_id = _create(conn, tenant, customer_id, _fixed_case_id(tenant, SCENARIO_2),
                      "상품 교환 신청 기한 문의")
    v = _step(conn, tenant, case_id, 0, EventType.CREATED,
              {"channel": "chat", "message": "받은 상품 사이즈가 안 맞아서 교환하고 싶은데 기한이 어떻게 되나요?"})
    v = _step(conn, tenant, case_id, v, EventType.CLASSIFIED,
              {"intent": "exchange", "issue_code": "exchange_period_question", "sentiment": "neutral"})
    v = _step(conn, tenant, case_id, v, EventType.ROUTED,
              {"owner_team_id": "return_exchange", "capability": "return.diagnose"})
    v = _step(conn, tenant, case_id, v, EventType.COMPLETED,
              {"answer_ref": "seed-answer-exchange-period-0002",
               "resolution": "교환 신청은 반품과 동일하게 계약내용 서면을 받은 날부터 7일이 기본이며, 상품 하자나 표시·광고 상이 사유라면 별도 특례 기한을 확인합니다.",
               "evidence": [
                   {"source_type": "policy_chunk", "source_id": "doc_15#교환 기한의 원칙",
                    "claim": "교환 신청 기한은 반품과 동일하게 계약내용 서면을 받은 날부터 7일을 기본으로 한다.",
                    "observed_at": observed_at},
                   {"source_type": "order", "source_id": str(order_id),
                    "claim": f"order_no={order_no}, status={order_status}, total_cents={total_cents}, item_count={item_count}, ordered_at={ordered_at.isoformat()}",
                    "observed_at": observed_at},
               ]})
    conn.commit()
    return case_id, v


def main() -> int:
    tenant = get_settings().tenant_id
    with get_connection() as conn:
        case1, v1 = scenario_1(conn, tenant)
        case2, v2 = scenario_2(conn, tenant)
        with conn.cursor() as cur:
            cur.execute("SELECT case_id, status, version FROM customer_cases WHERE tenant_id=%s AND case_id=ANY(%s) ORDER BY subject", (tenant, [case1, case2]))
            rows = cur.fetchall()
            cur.execute("SELECT count(*) FROM customer_cases WHERE tenant_id=%s", (tenant,))
            total = cur.fetchone()[0]
    print(json.dumps({
        "tenant_id": tenant,
        "scenario_1": {"case_id": str(case1), "expected_version": v1},
        "scenario_2": {"case_id": str(case2), "expected_version": v2},
        "observed": [{"case_id": str(r[0]), "status": r[1], "version": r[2]} for r in rows],
        "cases_in_tenant": total,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
