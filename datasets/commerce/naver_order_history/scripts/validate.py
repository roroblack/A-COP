#!/usr/bin/env python3
"""정규화된 네이버 주문 JSONL을 draft-07 스키마로 검증한다."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator


DATASET_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = DATASET_DIR / "order_schema.json"
DEFAULT_INPUT = DATASET_DIR / "processed" / "orders.jsonl"


def value_has_type(value: Any, expected: str) -> bool:
    checks = {
        "null": lambda item: item is None,
        "object": lambda item: isinstance(item, dict),
        "array": lambda item: isinstance(item, list),
        "string": lambda item: isinstance(item, str),
        "boolean": lambda item: isinstance(item, bool),
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "number": lambda item: isinstance(item, (int, float)) and not isinstance(item, bool),
    }
    return expected in checks and checks[expected](value)


def minimal_errors(value: Any, schema: dict[str, Any], path: str = "$") -> Iterator[str]:
    expected = schema.get("type")
    if expected is not None:
        expected_types = [expected] if isinstance(expected, str) else expected
        if not any(value_has_type(value, item) for item in expected_types):
            yield f"{path}: 타입 오류, 기대={expected_types}, 실제={type(value).__name__}"
            return
        if value is None:
            return

    if isinstance(value, dict):
        for required in schema.get("required", []):
            if required not in value:
                yield f"{path}.{required}: 필수 필드 누락"
        properties = schema.get("properties", {})
        for key, item in value.items():
            if key in properties:
                yield from minimal_errors(item, properties[key], f"{path}.{key}")
            elif schema.get("additionalProperties") is False:
                yield f"{path}.{key}: 허용되지 않은 필드"
            elif isinstance(schema.get("additionalProperties"), dict):
                yield from minimal_errors(item, schema["additionalProperties"], f"{path}.{key}")

    if isinstance(value, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                yield from minimal_errors(item, item_schema, f"{path}[{index}]")
        if schema.get("uniqueItems") and len({json.dumps(item, sort_keys=True) for item in value}) != len(value):
            yield f"{path}: 배열 항목이 중복됨"

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            yield f"{path}: 최소 길이 {schema['minLength']} 미만"
        if "pattern" in schema and re.fullmatch(schema["pattern"], value) is None:
            yield f"{path}: 패턴 불일치"
        if schema.get("format") == "date-time":
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    raise ValueError("시간대 없음")
            except ValueError:
                yield f"{path}: ISO 8601 시간대 포함 date-time이 아님"

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            yield f"{path}: 최솟값 {schema['minimum']} 미만"


def jsonschema_errors(value: Any, schema: dict[str, Any]) -> list[str] | None:
    try:
        from jsonschema import Draft7Validator, FormatChecker
    except ImportError:
        return None
    validator = Draft7Validator(schema, format_checker=FormatChecker())
    errors: list[str] = []
    for error in sorted(validator.iter_errors(value), key=lambda item: list(item.absolute_path)):
        location = "$" + "".join(
            f"[{part}]" if isinstance(part, int) else f".{part}" for part in error.absolute_path
        )
        errors.append(f"{location}: {error.message}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    args = parser.parse_args()

    try:
        with args.schema.open("r", encoding="utf-8") as handle:
            schema = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"오류: 스키마를 읽을 수 없음: {exc}", file=sys.stderr)
        return 2
    if schema.get("$schema") != "http://json-schema.org/draft-07/schema#":
        print("오류: draft-07 스키마가 아님", file=sys.stderr)
        return 2

    try:
        handle = args.input.open("r", encoding="utf-8-sig")
    except OSError as exc:
        print(f"오류: 입력 파일을 읽을 수 없음: {exc}", file=sys.stderr)
        return 2

    checked = 0
    failed = 0
    backend = "jsonschema"
    with handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            checked += 1
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                failed += 1
                print(f"줄 {line_number} $: JSON 파싱 오류: {exc}")
                continue
            errors = jsonschema_errors(value, schema)
            if errors is None:
                backend = "내장 최소 검증"
                errors = list(minimal_errors(value, schema))
            if errors:
                failed += 1
                for error in errors:
                    print(f"줄 {line_number} {error}")

    print(f"검증 방식: {backend}")
    print(f"검증 레코드: {checked}")
    print(f"실패 레코드: {failed}")
    if failed:
        return 1
    print("검증 성공")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
