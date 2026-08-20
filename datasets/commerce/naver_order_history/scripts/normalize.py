#!/usr/bin/env python3
"""네이버 주문 크롤러 출력을 A-COP 주문 JSONL로 정규화한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable


KST = timezone(timedelta(hours=9))
DATASET_DIR = Path(__file__).resolve().parents[1]
DEFAULT_RAW_DIR = DATASET_DIR / "raw"
DEFAULT_OUTPUT = DATASET_DIR / "processed" / "orders.jsonl"
DEFAULT_TRACKING_DIR = DATASET_DIR.parent / "courier_tracking" / "raw"

FULL_DATETIME_PATTERN = re.compile(
    r"^\s*(\d{4})\s*\.\s*(\d{1,2})\s*\.\s*(\d{1,2})\s*\.?\s+"
    r"(\d{1,2}):(\d{2})(?::(\d{2}))?\s*$"
)
FULL_DATE_PATTERN = re.compile(
    r"^\s*(\d{4})\s*\.\s*(\d{1,2})\s*\.\s*(\d{1,2})\s*\.?"
    r"(?:\s*\([^)]+\))?\s*$"
)
YEARLESS_PATTERNS = (
    re.compile(
        r"^\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일(?:\s*\([^)]+\))?\s*"
        r"(\d{1,2}):(\d{2})(?:\s*배송완료)?\s*$"
    ),
    re.compile(
        r"^\s*(\d{1,2})\s*\.\s*(\d{1,2})\s*\.?"
        r"(?:\s*\([^)]+\))?\s*(\d{1,2}):(\d{2})\s*$"
    ),
    re.compile(
        r"^\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일(?:\s*\([^)]+\))?\s*.+$"
    ),
)

PII_KEYS = {
    "recipient", "recipientname", "receiver", "receivername", "customername",
    "detailedaddress", "recipientaddress", "receiveraddress", "deliveryaddress",
    "shippingaddress", "addressdetail", "phone", "phonenumber", "telephone", "tel",
    "mobile", "mobilenumber", "recipientphone", "receiverphone",
}


@dataclass
class Stats:
    input_count: int = 0
    output_count: int = 0
    duplicate_count: int = 0
    quantity_defaults: int = 0
    date_failures: int = 0


def iso_seconds(value: datetime) -> str:
    return value.astimezone(KST).isoformat(timespec="seconds")


def parse_full_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        parsed = None
    if parsed is not None:
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=KST)
        return parsed.astimezone(KST)

    match = FULL_DATETIME_PATTERN.fullmatch(value)
    if match is None:
        return None
    year, month, day, hour, minute, second = match.groups()
    return datetime(
        int(year), int(month), int(day), int(hour), int(minute), int(second or 0), tzinfo=KST
    )


def parse_full_date(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    match = FULL_DATE_PATTERN.fullmatch(value)
    if match is None:
        return None
    year, month, day = (int(part) for part in match.groups())
    return datetime(year, month, day, tzinfo=KST)


def parse_yearless_datetime(value: Any, year: int) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    match = next((p.fullmatch(value) for p in YEARLESS_PATTERNS if p.fullmatch(value)), None)
    if match is None:
        return None
    parts = [int(part) for part in match.groups()]
    month, day = parts[:2]
    hour, minute = parts[2:] if len(parts) == 4 else (0, 0)
    return datetime(year, month, day, hour, minute, tzinfo=KST)


def parsed_source(
    raw: dict[str, Any],
    key: str,
    parser: Callable[..., datetime | None],
    stats: Stats,
    warnings: list[str],
    *args: Any,
) -> datetime | None:
    value = raw.get(key)
    if value in (None, ""):
        return None
    try:
        parsed = parser(value, *args)
    except (TypeError, ValueError):
        parsed = None
    if parsed is None:
        stats.date_failures += 1
        warnings.append(f"date_parse_failed:{key}")
        print(f"경고: {key} 날짜 파싱 실패: {value!r}", file=sys.stderr)
    return parsed


def clean_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def first_value(raw: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in raw and raw[key] not in (None, ""):
            return raw[key]
    return None


def parse_amount(value: Any) -> int | float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    cleaned = re.sub(r"[^0-9.\-]", "", str(value).replace(",", ""))
    if not cleaned:
        return None
    try:
        number = float(cleaned)
    except ValueError:
        return None
    return int(number) if number.is_integer() else number


def parse_quantity(value: Any, stats: Stats, warnings: list[str]) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 1:
        return value
    if isinstance(value, str) and value.strip().isdigit() and int(value) >= 1:
        return int(value)
    stats.quantity_defaults += 1
    warnings.append("quantity_missing_or_invalid:defaulted_to_1")
    return 1


def parse_bool(value: Any, default: bool | None = None) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "y", "1", "예", "있음"}:
            return True
        if normalized in {"false", "no", "n", "0", "아니요", "없음"}:
            return False
    return default


def snake_case(name: str) -> str:
    separated = re.sub(r"(?<!^)(?=[A-Z])", "_", name)
    return re.sub(r"[^a-z0-9]+", "_", separated.lower()).strip("_")


def pii_hashes(raw: dict[str, Any]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for key, value in raw.items():
        normalized_key = re.sub(r"[^a-z0-9]", "", key.lower())
        is_name = (
            normalized_key in {"recipient", "receiver"}
            or any(role in normalized_key for role in ("recipient", "receiver", "customer"))
            and "name" in normalized_key
        )
        is_contact = any(token in normalized_key for token in ("phone", "telephone", "mobile"))
        is_pii = normalized_key in PII_KEYS or is_name or is_contact or "address" in normalized_key
        if is_pii and value not in (None, ""):
            hashes[snake_case(key)] = hashlib.sha256(str(value).strip().encode("utf-8")).hexdigest()
    return hashes


def stable_hash(parts: Iterable[Any]) -> str:
    canonical = "\x1f".join("" if part is None else str(part).strip() for part in parts)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def raw_reference(file_path: Path, index: int, raw: dict[str, Any]) -> str:
    canonical = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"{file_path.name}#{index}:sha256:{digest}"


def choose_shipping_status(raw: dict[str, Any], warnings: list[str]) -> str | None:
    overall = clean_string(raw.get("DeliveryStatus"))
    location = clean_string(raw.get("DeliveryLocationStatus"))
    if overall and location and overall != location:
        warnings.append("shipping_status_mismatch:preferred_DeliveryLocationStatus")
    return location or overall


def parse_paid_at(
    raw: dict[str, Any], fallback: datetime, stats: Stats, warnings: list[str]
) -> tuple[datetime | None, datetime | None]:
    ordered_at = parsed_source(raw, "OrderedAt", parse_full_datetime, stats, warnings)
    if ordered_at is not None:
        return ordered_at, ordered_at
    if raw.get("PaymentDate") in (None, ""):
        return None, None
    warnings.append("year_inferred:PaymentDate")
    paid_at = parsed_source(
        raw, "PaymentDate", parse_yearless_datetime, stats, warnings, fallback.year
    )
    return paid_at, paid_at


def parse_completed_at(
    raw: dict[str, Any], ordered_at: datetime | None, stats: Stats, warnings: list[str]
) -> datetime | None:
    value = raw.get("DeliveryCompleteDate")
    if value in (None, ""):
        return None
    try:
        complete = parse_full_datetime(value)
    except (TypeError, ValueError):
        complete = None
    if complete is not None:
        return complete
    if ordered_at is None:
        stats.date_failures += 1
        warnings.append("date_parse_failed:DeliveryCompleteDate")
        return None

    # 연도가 없는 배송 완료일은 주문 연도로 만든다.
    # 주문 시각보다 이르면 연말을 넘긴 배송으로 보고 다음 해로 보정한다.
    try:
        complete = parse_yearless_datetime(value, ordered_at.year)
    except (TypeError, ValueError):
        complete = None
    if complete is None:
        stats.date_failures += 1
        warnings.append("date_parse_failed:DeliveryCompleteDate")
        print(f"경고: DeliveryCompleteDate 날짜 파싱 실패: {value!r}", file=sys.stderr)
        return None
    if complete.date() < ordered_at.date():
        complete = complete.replace(year=complete.year + 1)
    warnings.append("year_inferred:DeliveryCompleteDate")
    return complete


def normalize_tracking_events(events: Any) -> list[dict[str, str | None]]:
    if not isinstance(events, list):
        return []
    return [
        {
            "kind": clean_string(event.get("kind")),
            "where": clean_string(event.get("where")),
            "timeString": clean_string(event.get("timeString")),
        }
        for event in events
        if isinstance(event, dict)
    ]


def load_tracking_events(tracking_dir: Path) -> dict[str, list[dict[str, str | None]]]:
    result: dict[str, list[dict[str, str | None]]] = {}
    if not tracking_dir.is_dir():
        return result
    for file_path in sorted(tracking_dir.glob("tracking_*.jsonl")):
        try:
            with file_path.open("r", encoding="utf-8-sig") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    value = json.loads(line)
                    number = clean_string(value.get("tracking_number")) if isinstance(value, dict) else None
                    if number:
                        result[number] = normalize_tracking_events(value.get("events"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
    return result


def normalize_record(
    raw: dict[str, Any],
    file_path: Path,
    index: int,
    fallback: datetime,
    stats: Stats,
    tracking_events: dict[str, list[dict[str, str | None]]],
) -> dict[str, Any]:
    warnings: list[str] = []
    product_name = clean_string(raw.get("ProductName")) or "상품명 없음"
    quantity = parse_quantity(raw.get("Quantity"), stats, warnings)
    product_price = parse_amount(raw.get("ProductPrice"))
    product_total = product_price * quantity if product_price is not None else None

    paid_at, ordered_at = parse_paid_at(raw, fallback, stats, warnings)
    completed_at = parse_completed_at(raw, ordered_at, stats, warnings)
    confirmed_at = parsed_source(raw, "PurchaseConfirmedAt", parse_full_date, stats, warnings)
    exception_at = parsed_source(raw, "ShippingExceptionDate", parse_full_datetime, stats, warnings)
    return_deadline = parsed_source(raw, "ReturnDeadlineDate", parse_full_datetime, stats, warnings)
    refund_calculated = parsed_source(raw, "RefundCalculatedDate", parse_full_datetime, stats, warnings)

    tracking_number = clean_string(raw.get("TrackingNumber"))
    order_id = clean_string(first_value(raw, "OrderId", "OrderID", "OrderNumber", "order_id", "orderNo"))
    if order_id is None:
        order_id = "alt_" + stable_hash((product_name, paid_at, tracking_number))
        warnings.append("order_id_generated_from_product_paid_at_tracking")

    return {
        "order_id": order_id,
        "order_status": clean_string(first_value(raw, "OrderStatus", "OrderState")),
        "seller_name": clean_string(first_value(raw, "SellerName", "MerchantName")),
        "product": {
            "name": product_name,
            "option": clean_string(first_value(raw, "ProductOption", "OptionName")),
            "quantity": quantity,
            "unit_price": product_price,
            "total_price": product_total,
        },
        "payment": {
            "amount": parse_amount(raw.get("TotalAmount")),
            "method": clean_string(first_value(raw, "PaymentMethod", "PayMethod")),
            "status": clean_string(first_value(raw, "PaymentStatus", "PayStatus")),
            "paid_at": iso_seconds(paid_at) if paid_at else None,
        },
        "shipping": {
            "carrier": clean_string(raw.get("CourierCompany")),
            "tracking_number": tracking_number,
            "status": choose_shipping_status(raw, warnings),
            "region": clean_string(raw.get("DeliveryRegion")),
            "fee": parse_amount(raw.get("ShippingFee")),
            "completed_at": iso_seconds(completed_at) if completed_at else None,
            "events": tracking_events.get(tracking_number, []) if tracking_number else [],
            "exception": {
                "code": clean_string(first_value(raw, "ShippingExceptionCode", "DeliveryExceptionCode")),
                "detail": clean_string(first_value(raw, "ShippingExceptionDetail", "DeliveryExceptionDetail")),
                "occurred_at": iso_seconds(exception_at) if exception_at else None,
            },
        },
        "cs": {
            "has_inquiry": bool(parse_bool(first_value(raw, "HasInquiry", "has_inquiry"), False)),
            "return_status": clean_string(first_value(raw, "ReturnStatus", "return_status")),
            "return_eligible": parse_bool(first_value(raw, "ReturnEligible", "return_eligible")),
            "return_reason_code": clean_string(first_value(raw, "ReturnReasonCode", "return_reason_code")),
            "purchase_confirmed_at": iso_seconds(confirmed_at) if confirmed_at else None,
            "return_deadline_at": iso_seconds(return_deadline) if return_deadline else None,
            "refund": {
                "status": clean_string(first_value(raw, "RefundStatus", "refund_status")),
                "gross_amount": parse_amount(first_value(raw, "RefundGrossAmount", "refund_gross_amount")),
                "deduction_amount": parse_amount(first_value(raw, "RefundDeductionAmount", "refund_deduction_amount")),
                "refundable_amount": parse_amount(first_value(raw, "RefundableAmount", "refundable_amount")),
                "calculated_at": iso_seconds(refund_calculated) if refund_calculated else None,
            },
        },
        "_source": {
            "crawled_at": iso_seconds(fallback),
            "raw_ref": raw_reference(file_path, index, raw),
            "pii_hashes": pii_hashes(raw),
            "normalization_warnings": list(dict.fromkeys(warnings)),
        },
    }


def load_records(file_path: Path) -> list[dict[str, Any]]:
    if file_path.suffix.lower() == ".jsonl":
        records: list[dict[str, Any]] = []
        with file_path.open("r", encoding="utf-8-sig") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError(f"{file_path}:{line_number}: JSON 객체가 아님")
                records.append(value)
        return records
    with file_path.open("r", encoding="utf-8-sig") as handle:
        value = json.load(handle)
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list) and all(isinstance(record, dict) for record in value):
        return value
    raise ValueError(f"{file_path}: 최상위 값이 JSON 객체 또는 객체 배열이 아님")


def discover_input_files(raw_dir: Path, input_path: Path | None) -> list[Path]:
    return [input_path] if input_path is not None else sorted(raw_dir.glob("*.json"))


def normalize_all(
    files: list[Path], output_path: Path, tracking_events: dict[str, list[dict[str, str | None]]]
) -> Stats:
    stats = Stats()
    seen_order_ids: set[str] = set()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = output_path.with_suffix(output_path.suffix + ".tmp")
    with temporary_output.open("w", encoding="utf-8", newline="\n") as output:
        for file_path in files:
            try:
                records = load_records(file_path)
            except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
                print(f"경고: 파일 처리 실패, 건너뜀: {exc}", file=sys.stderr)
                continue
            fallback = datetime.fromtimestamp(file_path.stat().st_mtime, tz=KST)
            for index, raw in enumerate(records):
                stats.input_count += 1
                normalized = normalize_record(raw, file_path, index, fallback, stats, tracking_events)
                order_id = normalized["order_id"]
                if order_id in seen_order_ids:
                    stats.duplicate_count += 1
                    continue
                seen_order_ids.add(order_id)
                output.write(json.dumps(normalized, ensure_ascii=False, separators=(",", ":")) + "\n")
                stats.output_count += 1
    temporary_output.replace(output_path)
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--input", type=Path, help="특정 JSON 또는 JSONL 파일만 처리")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--with-tracking", action="store_true", help="택배 배송 이력 결합")
    args = parser.parse_args()

    if args.input is not None and not args.input.is_file():
        print(f"오류: 입력 파일이 없음: {args.input}", file=sys.stderr)
        return 2
    if args.input is None and not args.raw_dir.is_dir():
        print(f"오류: raw 디렉터리가 없음: {args.raw_dir}", file=sys.stderr)
        return 2
    files = discover_input_files(args.raw_dir, args.input)
    if not files:
        print(f"안내: {args.raw_dir} 바로 아래에 처리할 JSON 파일이 없습니다.")
        return 0

    tracking_events = load_tracking_events(DEFAULT_TRACKING_DIR) if args.with_tracking else {}
    stats = normalize_all(files, args.output, tracking_events)
    print(f"입력 건수: {stats.input_count}")
    print(f"출력 건수: {stats.output_count}")
    print(f"중복 제외 건수: {stats.duplicate_count}")
    print(f"수량 기본값 적용 건수: {stats.quantity_defaults}")
    print(f"날짜 파싱 실패 건수: {stats.date_failures}")
    print(f"출력 파일: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
