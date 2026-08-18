"""쇼핑몰 CS 데모 데이터 (결정적).

★sample(구독·결제)에서 커머스로 갈아 끼운 파일이다
  (`docs/handoff/10_도메인_교체_가이드.md` §1-6).

  subscriptions/payments/entitlements/incidents
    → orders / order_items / shipments / returns

★모든 id 를 `uuid5` 로 만든다. 두 번 돌려도 같은 값이라
  화면 URL 과 판정 문서의 실측값이 매 실행마다 죽지 않는다.

시나리오 두 개를 데이터에 심어 둔다:
  1. 배송 완료로 찍혔는데 고객은 못 받았다 (cust_01, ORD-0101)
  2. 주문 수량보다 많은 반품 요청 (cust_04)
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID, uuid5

from app.infrastructure.db.session import get_connection

DEMO = "demo"
NAMESPACE = UUID("00000000-0000-0000-0000-000000000001")

#: 상품 카탈로그 — 10명 × 3주문에 돌려 쓴다
CATALOG = [
    ("SKU-TEE-01", "베이식 티셔츠", 19_900),
    ("SKU-CUP-02", "보온 텀블러", 24_500),
    ("SKU-BAG-03", "캔버스 백", 32_000),
    ("SKU-SHO-04", "러닝화", 89_000),
    ("SKU-CAP-05", "볼캡", 15_000),
]

CARRIERS = ["CJ대한통운", "한진택배", "우체국택배"]


def stable(name: str) -> UUID:
    return uuid5(NAMESPACE, name)


def at(day: date, hour: int = 12) -> datetime:
    return datetime.combine(day, time(hour), tzinfo=timezone.utc)


def ensure_customer(conn, external_id: str, email_hash: str) -> UUID:
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO customers (tenant_id, external_id, email_hash)
               VALUES (%s,%s,%s)
               ON CONFLICT (tenant_id, external_id)
               DO UPDATE SET email_hash=EXCLUDED.email_hash
               RETURNING customer_id""",
            (DEMO, external_id, email_hash),
        )
        return cur.fetchone()[0]


def main() -> None:
    today = date(2026, 8, 16)
    with get_connection() as conn, conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO tenants (tenant_id,name) VALUES (%s,%s) "
                "ON CONFLICT (tenant_id) DO UPDATE SET name=EXCLUDED.name",
                (DEMO, "Nimbus Mall"),
            )
        customers = [
            ensure_customer(conn, f"cust_{n:02d}", f"sha256:demo-cust-{n:02d}")
            for n in range(1, 11)
        ]

        orders: list[tuple[UUID, UUID, int, int]] = []   # (order_id, customer_id, total, items)
        with conn.cursor() as cur:
            for n, customer_id in enumerate(customers, 1):
                for seq in range(1, 4):
                    order_id = stable(f"order:cust_{n:02d}:{seq}")
                    sku, name, unit = CATALOG[(n + seq) % len(CATALOG)]
                    quantity = 1 + ((n + seq) % 3)
                    total = unit * quantity
                    ordered = today - timedelta(days=((n * 2 + seq) % 14))
                    # 배송 상태를 주문마다 다르게 둔다 — 화면에서 분포가 보이도록
                    status = ["delivered", "shipped", "paid"][seq - 1]
                    cur.execute(
                        """INSERT INTO orders
                           (order_id,tenant_id,customer_id,order_no,total_cents,item_count,status,ordered_at)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                           ON CONFLICT (order_id) DO UPDATE SET
                           total_cents=EXCLUDED.total_cents, item_count=EXCLUDED.item_count,
                           status=EXCLUDED.status, ordered_at=EXCLUDED.ordered_at""",
                        (order_id, DEMO, customer_id, f"ORD-{n:02d}{seq:02d}",
                         total, quantity, status, at(ordered, 10)),
                    )
                    cur.execute(
                        """INSERT INTO order_items
                           (order_item_id,tenant_id,order_id,sku,name,quantity,unit_cents)
                           VALUES (%s,%s,%s,%s,%s,%s,%s)
                           ON CONFLICT (order_item_id) DO UPDATE SET
                           quantity=EXCLUDED.quantity, unit_cents=EXCLUDED.unit_cents""",
                        (stable(f"item:cust_{n:02d}:{seq}"), DEMO, order_id, sku, name, quantity, unit),
                    )
                    orders.append((order_id, customer_id, total, quantity))

        # 배송 — delivered/shipped 주문에만 붙인다
        with conn.cursor() as cur:
            for idx, (order_id, customer_id, _total, _q) in enumerate(orders, 1):
                cur.execute("SELECT status, ordered_at FROM orders WHERE order_id=%s", (order_id,))
                status, ordered_at = cur.fetchone()
                if status == "paid":
                    continue
                shipped = ordered_at + timedelta(days=1)
                delivered = shipped + timedelta(days=2) if status == "delivered" else None
                cur.execute(
                    """INSERT INTO shipments
                       (shipment_id,tenant_id,customer_id,order_id,carrier,tracking_no,status,shipped_at,delivered_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (shipment_id) DO UPDATE SET
                       status=EXCLUDED.status, delivered_at=EXCLUDED.delivered_at""",
                    (stable(f"shipment:{order_id}"), DEMO, customer_id, order_id,
                     CARRIERS[idx % len(CARRIERS)], f"TRK{idx:09d}",
                     "delivered" if delivered else "in_transit", shipped, delivered),
                )

        # 반품 — 두 건만. 하나는 정상, 하나는 ★주문 수량을 넘는 요청
        with conn.cursor() as cur:
            normal_order, normal_customer, _t, normal_q = orders[6]
            cur.execute(
                """INSERT INTO returns
                   (return_id,tenant_id,customer_id,order_id,reason_code,quantity,status)
                   VALUES (%s,%s,%s,%s,'size_mismatch',%s,'requested')
                   ON CONFLICT (return_id) DO UPDATE SET quantity=EXCLUDED.quantity""",
                (stable("return:normal"), DEMO, normal_customer, normal_order, max(1, normal_q - 1)),
            )
            over_order, over_customer, _t2, over_q = orders[9]
            cur.execute(
                """INSERT INTO returns
                   (return_id,tenant_id,customer_id,order_id,reason_code,quantity,status)
                   VALUES (%s,%s,%s,%s,'defective',%s,'requested')
                   ON CONFLICT (return_id) DO UPDATE SET quantity=EXCLUDED.quantity""",
                (stable("return:over"), DEMO, over_customer, over_order, over_q + 2),
            )

    with get_connection() as conn, conn.cursor() as cur:
        counts = {}
        for table in ("customers", "orders", "order_items", "shipments", "returns"):
            cur.execute(f"SELECT count(*) FROM {table} WHERE tenant_id=%s", (DEMO,))
            counts[table] = cur.fetchone()[0]
    print(counts)


if __name__ == "__main__":
    main()
