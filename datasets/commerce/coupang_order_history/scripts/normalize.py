#!/usr/bin/env python3
"""Normalize Coupang extension exports into reproducible JSONL datasets."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ORDER_PREFIX = "coupang_order_history_"
TRACKING_PREFIX = "coupang_tracking_"


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def as_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def as_number(value: Any) -> int | float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    try:
        parsed = float(str(value).replace(",", "").strip())
    except ValueError:
        return None
    return int(parsed) if parsed.is_integer() else parsed


def as_datetime(value: Any, *, assume_kst: bool = False) -> str | None:
    text = as_string(value)
    if not text:
        return None
    normalized = text.replace(" ", "T", 1)
    if assume_kst and not re.search(r"(?:Z|[+-]\d{2}:?\d{2})$", normalized):
        normalized += "+09:00"
    try:
        return datetime.fromisoformat(normalized.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return None


def tracking_key(order_id: Any, shipment_box_id: Any) -> tuple[str, str]:
    return (as_string(order_id) or "", as_string(shipment_box_id) or "")


def newest_matching_pair(raw_dir: Path) -> tuple[Path, Path | None]:
    orders = sorted(
        (path for path in raw_dir.glob(f"{ORDER_PREFIX}*.json") if "fail" not in path.stem.lower()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not orders:
        raise FileNotFoundError(f"No {ORDER_PREFIX}*.json file found in {raw_dir}")
    for order_path in orders:
        suffix = order_path.stem[len(ORDER_PREFIX) :]
        tracking_path = raw_dir / f"{TRACKING_PREFIX}{suffix}.json"
        if tracking_path.exists():
            return order_path, tracking_path
    tracking = sorted(raw_dir.glob(f"{TRACKING_PREFIX}*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    return orders[0], tracking[0] if tracking else None


def load_orders(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    payload = read_json(path)
    if isinstance(payload, list):
        return payload, {}
    if not isinstance(payload, dict):
        raise ValueError(f"Unsupported order JSON root: {type(payload).__name__}")
    rows = payload.get("orders")
    if not isinstance(rows, list):
        rows = payload.get("orderData", {}).get("orders")
    if not isinstance(rows, list):
        raise ValueError("Order JSON does not contain an orders array")
    return rows, payload


def load_tracking(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    payload = read_json(path)
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("trackingData"), list):
        return payload["trackingData"]
    raise ValueError("Tracking JSON must be an array or contain trackingData")


def normalize_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": as_string(event.get("kind")),
        "where": as_string(event.get("where")),
        "timeString": as_string(event.get("timeString")),
    }


def build_tracking_index(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = tracking_key(row.get("order_id") or row.get("OrderId"), row.get("shipment_box_id") or row.get("_shipmentBoxId"))
        if not key[0]:
            continue
        events = row.get("events") or row.get("TrackingEvents") or []
        index[key] = {
            "order_id": key[0],
            "shipment_box_id": key[1] or None,
            "courier": as_string(row.get("courier") or row.get("CourierCompany")),
            "tracking_number": as_string(row.get("tracking_number") or row.get("TrackingNumber")),
            "status": as_string(row.get("status") or row.get("TrackingStatus") or row.get("DeliveryStatus")),
            "events": [normalize_event(event) for event in events if isinstance(event, dict)],
            "queried_at": as_string(row.get("queried_at")),
            "outcome": "collected" if events else "preShipment",
        }
    return index


def normalize(
    order_path: Path,
    tracking_path: Path | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    raw_orders, order_meta = load_orders(order_path)
    raw_tracking = load_tracking(tracking_path)
    tracking_index = build_tracking_index(raw_tracking)
    source_hash = sha256(order_path)
    crawled_at = as_string(order_meta.get("exportedAt")) or datetime.fromtimestamp(order_path.stat().st_mtime, timezone.utc).isoformat()
    normalized_orders: list[dict[str, Any]] = []
    box_order: list[tuple[str, str]] = []

    for index, row in enumerate(raw_orders):
        order_id = as_string(row.get("OrderId"))
        if not order_id:
            raise ValueError(f"Order row {index} has no OrderId")
        box_id = as_string(row.get("_shipmentBoxId"))
        key = tracking_key(order_id, box_id)
        tracking = tracking_index.get(key)
        if key not in box_order:
            box_order.append(key)
        quantity = int(as_number(row.get("Quantity")) or 1)
        product_total = as_number(row.get("ProductPrice"))
        unit_price = (product_total / quantity) if product_total is not None and quantity else as_number(row.get("UnitPrice"))
        events = tracking["events"] if tracking else []
        warnings: list[str] = []
        if tracking is None and row.get("_TrackingOutcome") == "collected":
            warnings.append("tracking_export_missing_for_collected_order")
        normalized_orders.append(
            {
                "order_id": order_id,
                "order_status": as_string(row.get("OrderStatus")),
                "seller_name": as_string(row.get("SellerName")),
                "product": {
                    "name": as_string(row.get("ProductName")) or "(상품명 없음)",
                    "option": None,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "total_price": product_total,
                },
                "payment": {
                    "amount": as_number(row.get("TotalAmount")),
                    "method": as_string(row.get("PaymentMethod")),
                    "status": "취소" if "취소" in str(row.get("OrderStatus") or "") else ("결제완료" if row.get("TotalAmount") is not None else None),
                    "paid_at": as_datetime(row.get("OrderedAtTime"), assume_kst=True),
                },
                "shipping": {
                    "carrier": (tracking or {}).get("courier") or as_string(row.get("CourierCompany")),
                    "tracking_number": (tracking or {}).get("tracking_number") or as_string(row.get("TrackingNumber")),
                    "status": (tracking or {}).get("status") or as_string(row.get("TrackingStatus") or row.get("DeliveryStatus") or row.get("OrderStatus")),
                    "region": as_string(row.get("DeliveryRegion")),
                    "fee": as_number(row.get("ShippingFee")),
                    "completed_at": as_datetime(row.get("DeliveryCompleteDate"), assume_kst=True),
                    "events": events,
                    "exception": {"code": None, "detail": None, "occurred_at": None},
                },
                "cs": {
                    "has_inquiry": False,
                    "return_status": None,
                    "return_eligible": None,
                    "return_reason_code": None,
                    "purchase_confirmed_at": None,
                    "return_deadline_at": None,
                    "refund": {
                        "status": None,
                        "gross_amount": None,
                        "deduction_amount": None,
                        "refundable_amount": None,
                        "calculated_at": None,
                    },
                },
                "_source": {
                    "crawled_at": crawled_at,
                    "raw_ref": f"{order_path.name}#{index}:sha256:{source_hash}",
                    "pii_hashes": {},
                    "normalization_warnings": warnings,
                },
            }
        )

    first_by_box: dict[tuple[str, str], dict[str, Any]] = {}
    for row in raw_orders:
        key = tracking_key(row.get("OrderId"), row.get("_shipmentBoxId"))
        first_by_box.setdefault(key, row)
    normalized_tracking = [tracking_index[key] for key in box_order if key in tracking_index]
    unique_orders = len({row["order_id"] for row in normalized_orders})
    stats = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "orders": {"path": f"raw/{order_path.name}", "sha256": source_hash},
            "tracking": None if tracking_path is None else {"path": f"raw/{tracking_path.name}", "sha256": sha256(tracking_path)},
        },
        "output": {
            "order_rows": len(normalized_orders),
            "unique_order_ids": unique_orders,
            "tracking_rows": len(normalized_tracking),
            "tracking_with_events": sum(bool(row["events"]) for row in normalized_tracking),
            "tracking_pre_shipment": sum(row["outcome"] == "preShipment" for row in normalized_tracking),
        },
        "excluded": {
            "cancelled_tracking_boxes": sum(
                1 for row in first_by_box.values() if "취소" in str(row.get("OrderStatus") or "")
            ),
            "tracking_number_missing_boxes": sum(
                1 for row in first_by_box.values()
                if "취소" not in str(row.get("OrderStatus") or "") and not row.get("TrackingNumber")
            ),
        },
    }
    return normalized_orders, normalized_tracking, stats


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    temporary.replace(path)


def main() -> int:
    dataset_dir = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--orders", type=Path, help="Order export JSON; defaults to newest matched raw pair")
    parser.add_argument("--tracking", type=Path, help="Tracking export JSON")
    parser.add_argument("--output-dir", type=Path, default=dataset_dir / "processed")
    args = parser.parse_args()
    if args.orders:
        order_path = args.orders.resolve()
        tracking_path = args.tracking.resolve() if args.tracking else None
    else:
        order_path, tracking_path = newest_matching_pair(dataset_dir / "raw")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    orders, tracking, stats = normalize(order_path, tracking_path)
    write_jsonl(args.output_dir / "orders.jsonl", orders)
    write_jsonl(args.output_dir / "tracking.jsonl", tracking)
    stats_path = dataset_dir / "preprocess_stats.json"
    temporary = stats_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(stats_path)
    print(json.dumps(stats["output"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
