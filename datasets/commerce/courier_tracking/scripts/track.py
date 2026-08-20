"""네이버 택배조회 내부 API로 배송 이력을 수집한다."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

from naver_parcel_api import (
    NaverParcelClient,
    failure_result,
    find_courier,
    load_courier_codes,
)


DATASET_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = DATASET_ROOT / "raw"
LOG_PATH = RAW_DIR / "_track_log.txt"


@dataclass
class Statistics:
    attempted: int = 0
    with_history: int = 0
    no_history: int = 0
    unsupported: int = 0
    errors: int = 0
    resumed: int = 0
    error_types: Counter[str] = field(default_factory=Counter)


def log(message: str) -> None:
    """진행 상황을 UTF-8 파일과 콘솔에 남긴다."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    with LOG_PATH.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(f"[{timestamp}] {message}\n")
    print(message)


def load_orders(path: Path) -> list[dict[str, Any]]:
    """JSON 또는 JSONL 주문 파일을 읽는다."""
    if path.suffix.casefold() == ".jsonl":
        records: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8-sig") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError(f"{line_number}번째 JSONL 값이 객체가 아닙니다.")
                records.append(value)
        return records

    with path.open("r", encoding="utf-8-sig") as stream:
        value = json.load(stream)
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        for key in ("orders", "items", "data", "results"):
            nested = value.get(key)
            if isinstance(nested, list):
                return [item for item in nested if isinstance(item, dict)]
        return [value]
    raise ValueError("주문 파일의 최상위 값은 객체 또는 배열이어야 합니다.")


def first_text(source: dict[str, Any], keys: Iterable[str]) -> str | None:
    for key in keys:
        value = source.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def extract_shipment(order: dict[str, Any]) -> tuple[str | None, str | None]:
    """네이버 원본 형식과 정규화 형식에서 배송 정보를 찾는다."""
    shipping = order.get("shipping")
    if not isinstance(shipping, dict):
        shipping = {}
    courier = first_text(
        order, ("CourierCompany", "courier_company", "courier", "carrier")
    ) or first_text(shipping, ("carrier", "courier", "courier_company"))
    number = first_text(
        order,
        ("TrackingNumber", "tracking_number", "invoice_number", "waybill_number"),
    ) or first_text(
        shipping, ("tracking_number", "invoice_number", "waybill_number")
    )
    return courier, number


def build_entries(args: argparse.Namespace) -> list[tuple[str | None, str]]:
    if not args.from_orders:
        return [(args.courier, args.number)]
    entries: list[tuple[str | None, str]] = []
    for index, order in enumerate(load_orders(args.from_orders), 1):
        courier, number = extract_shipment(order)
        if not number:
            log(f"주문 {index}: 송장번호가 없어 건너뜁니다.")
            continue
        entries.append((courier, number))
    return entries


def load_completed_numbers(path: Path) -> set[str]:
    """오늘 결과 파일에서 이미 저장된 송장번호를 읽는다."""
    completed: set[str] = set()
    if not path.exists():
        return completed
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict) and value.get("tracking_number"):
                completed.add(str(value["tracking_number"]))
    return completed


def append_result(path: Path, result: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(result, ensure_ascii=False) + "\n")


def update_statistics(stats: Statistics, result: dict[str, Any]) -> None:
    error = result["error"]
    if result["events"]:
        stats.with_history += 1
    elif error in {"no_history", "not_found"}:
        stats.no_history += 1
    elif error == "unsupported_courier":
        stats.unsupported += 1
    else:
        stats.errors += 1
    if error:
        stats.error_types[error] += 1


def print_statistics(stats: Statistics) -> None:
    print("\n조회 통계")
    print(f"총 시도: {stats.attempted}")
    print(f"이력 있음: {stats.with_history}")
    print(f"이력 없음(만료 추정): {stats.no_history}")
    print(f"미지원 택배사: {stats.unsupported}")
    print(f"오류: {stats.errors}")
    print(f"재개로 건너뜀: {stats.resumed}")
    for error in (
        "no_history",
        "not_found",
        "unsupported_courier",
        "timeout",
        "script_error",
        "key_expired",
    ):
        print(f"  {error}: {stats.error_types[error]}")


def run(args: argparse.Namespace) -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    output_path = RAW_DIR / f"tracking_{date.today().isoformat()}.jsonl"
    completed = load_completed_numbers(output_path) if args.resume else set()
    couriers = load_courier_codes()
    stats = Statistics()

    try:
        with NaverParcelClient(args.delay_min, args.delay_max, log) as client:
            for courier_name, number in build_entries(args):
                if number in completed:
                    stats.resumed += 1
                    log(f"{number}: 이미 저장된 송장이라 건너뜁니다.")
                    continue
                stats.attempted += 1
                courier = find_courier(courier_name, couriers)
                if courier is None:
                    label = courier_name or "택배사명 없음"
                    result = failure_result(label, "", number, "unsupported_courier")
                    append_result(output_path, result)
                    update_statistics(stats, result)
                    log(f"{number}: 지원하지 않는 택배사({label})입니다.")
                    continue

                log(f"조회 시작: {courier['text']} {number}")
                result = client.track(courier["text"], courier["code"], number)
                append_result(output_path, result)
                completed.add(number)
                update_statistics(stats, result)
                if result["error"]:
                    log(f"조회 결과: {number} {result['error']}")
                else:
                    log(f"조회 완료: {number} 이력 {len(result['events'])}건")
    except RuntimeError as exc:
        log(f"실행 실패: {exc}")
        print_statistics(stats)
        return 2

    print_statistics(stats)
    print(f"결과 파일: {output_path}")
    print(f"로그 파일: {LOG_PATH}")
    return 1 if stats.errors or stats.unsupported else 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="네이버 API 기반 택배 배송 조회기")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--number", help="조회할 송장번호")
    source.add_argument("--from-orders", type=Path, help="네이버 주문 JSON 또는 JSONL")
    parser.add_argument("--courier", help="택배사명")
    parser.add_argument("--resume", action="store_true", help="오늘 저장한 송장을 건너뜀")
    parser.add_argument("--delay-min", type=float, default=0.8, help="최소 조회 대기 초")
    parser.add_argument("--delay-max", type=float, default=2.0, help="최대 조회 대기 초")
    args = parser.parse_args(argv)
    if args.number and not args.courier:
        parser.error("--number를 사용할 때는 --courier가 필요합니다.")
    if args.delay_min < 0.5 or args.delay_max < 0.5:
        parser.error("대기 시간은 1.0초 미만으로 설정할 수 없습니다.")
    if args.delay_max < args.delay_min:
        parser.error("--delay-max는 --delay-min보다 작을 수 없습니다.")
    return args


if __name__ == "__main__":
    try:
        sys.exit(run(parse_args()))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        log(f"입력 처리 실패: {type(exc).__name__}: {exc}")
        sys.exit(2)
