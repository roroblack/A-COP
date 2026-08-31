#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""팀원 제출본을 네이버 주문 · 쿠팡 주문 · 배송 조회 세 파일로 합쳐 `_dist/` 에 넣는다.

    python datasets/commerce/build_team_merged.py
    python datasets/commerce/build_team_merged.py --no-mask   # 가리지 않고 그대로

원본 제출본을 그대로 보존한 것은 `build_team_submissions.py` 가 만드는 zip 이다.
이 스크립트는 **합쳐서 바로 쓰기 좋게 만든 파생본**이다. 둘은 목적이 다르다.

JSONL 로 낸다. 한 줄에 한 레코드라 수백만 줄이어도 부분만 읽을 수 있고,
합칠 때 배열을 통째로 메모리에 올리지 않아도 된다.

★출처를 레코드마다 박는다(`_submitter`, `_source_file`, `_platform`).
  합치고 나면 어느 파일에서 온 줄인지 알 방법이 없어진다. 나중에 한 사람 것만
  빼거나 다시 대조할 때 이게 없으면 처음부터 다시 합쳐야 한다.

★쿠팡 `DeliveryRequest` 의 자유입력을 가린다.
  공동현관 비밀번호는 쿠팡이 `#****` 로 가려서 내보내는데, **`기타사항 (...)` 안의
  자유입력은 안 가려진다.** 실측으로 `집앞우편함에열쇠로대문안에` 같은 집 열쇠 위치가
  51건 들어 있었다(2026-08-31). 배송지 구 정보와 같이 있으면 그대로 쓸 수 있는 정보다.
  팀 안에서 도는 파일이라도 이건 넘기지 않는다. 무엇을 가렸는지는 통계로 남긴다.
  원본이 필요하면 `--no-mask` 를 쓰거나 제출본 zip 을 본다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

COMMERCE = Path(__file__).resolve().parent
DIST = COMMERCE / "_dist"

NAVER_ORDERS = [
    ("cyw", "naver_order_history/raw/naver_2026-08-20_68건_cyw.json"),
    ("kjh", "naver_order_history/raw/naver_2026-08-21_102건_kjh.json"),
    ("syh", "naver_order_history/raw/naver_2026-08-21_44건_syh.json"),
    ("csw", "naver_order_history/raw/naver_2026-08-21_57건_csw.json"),
]
COUPANG_ORDERS = [
    ("cyw", "coupang_order_history/raw/coupang_order_history_20260821_195756_cyw.json"),
    ("syh", "coupang_order_history/raw/coupang_order_history_20260823_120424_syh.json"),
    ("csw", "coupang_order_history/raw/coupang_order_history_20260828_100851_csw.json"),
    ("scy", "coupang_order_history/raw/쿠팡 크롤링데이터 주문_scy.json"),
]
TRACKING = [
    ("cyw", "naver", "courier_tracking/raw/_incoming_20260829/naver_tracking_2026-08-20_cyw.jsonl"),
    ("kjh", "naver", "courier_tracking/raw/_incoming_20260829/naver_tracking_2026-08-21_kjh"),
    ("csw", "naver", "courier_tracking/raw/_incoming_20260829/naver_tracking_2026-08-28_csw.jsonl"),
    ("syh", "naver", "courier_tracking/raw/_incoming_20260829/naver_tracking_2026-08-28_syh.jsonl"),
    ("cyw", "coupang", "courier_tracking/raw/_incoming_20260829/coupang_tracking_20260821_195756_cyw.json"),
    ("syh", "coupang", "courier_tracking/raw/_incoming_20260829/coupang_tracking_20260823_120424_syh.json"),
    ("csw", "coupang", "courier_tracking/raw/_incoming_20260829/coupang_tracking_20260828_100851_csw.json"),
    ("scy", "coupang", "courier_tracking/raw/_incoming_20260829/쿠팡 크롤링데이터 배송_scy.json"),
]

#: `기타사항 (…)` 안의 자유입력. 쿠팡이 안 가리는 유일한 자리다.
FREE_TEXT = re.compile(r"(기타사항\s*\()([^)]*)(\))")


def load_records(path: Path) -> list[dict]:
    """JSON 배열 · {orders:[…]} · JSONL 세 형태를 모두 받는다."""
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return []
    if text.startswith("["):
        return [r for r in json.loads(text) if isinstance(r, dict)]
    if text.startswith("{"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict):
            for key in ("orders", "data", "records", "items"):
                if isinstance(data.get(key), list):
                    return [r for r in data[key] if isinstance(r, dict)]
            return [data]
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(r, dict):
            out.append(r)
    return out


def mask(record: dict, stats: dict) -> dict:
    value = record.get("DeliveryRequest")
    if not isinstance(value, str):
        return record
    masked, n = FREE_TEXT.subn(lambda m: m.group(1) + "가림" + m.group(3), value)
    if n:
        stats["masked_rows"] += 1
        stats["samples"].setdefault(value[:70], 0)
        stats["samples"][value[:70]] += 1
        record = dict(record)
        record["DeliveryRequest"] = masked
        record["_masked"] = ["DeliveryRequest.기타사항"]
    return record


def write(out: Path, rows) -> int:
    n = 0
    with out.open("w", encoding="utf-8", newline="\n") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
            n += 1
    return n


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def build(stamp: str, do_mask: bool) -> list[tuple[str, Path, int, dict]]:
    DIST.mkdir(exist_ok=True)
    results = []

    def collect(spec, platform_fixed=None):
        stats = {"masked_rows": 0, "samples": {}, "by_submitter": {}}
        rows = []
        for entry in spec:
            if platform_fixed:
                who, rel = entry
                platform = platform_fixed
            else:
                who, platform, rel = entry
            path = COMMERCE / rel
            if not path.is_file():
                raise SystemExit("파일이 없다: %s" % path)
            records = load_records(path)
            for r in records:
                r = dict(r)
                if do_mask:
                    r = mask(r, stats)
                r["_submitter"] = who
                r["_platform"] = platform
                r["_source_file"] = path.name
                rows.append(r)
            stats["by_submitter"][who] = stats["by_submitter"].get(who, 0) + len(records)
        return rows, stats

    for name, spec, fixed in [
        ("team_naver_orders", NAVER_ORDERS, "naver"),
        ("team_coupang_orders", COUPANG_ORDERS, "coupang"),
        ("team_courier_tracking", TRACKING, None),
    ]:
        rows, stats = collect(spec, fixed)
        out = DIST / ("%s_%s.jsonl" % (name, stamp))
        results.append((name, out, write(out, rows), stats))
    return results


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-mask", action="store_true",
                    help="쿠팡 기타사항 자유입력을 가리지 않는다")
    args = ap.parse_args()

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results = build(stamp, do_mask=not args.no_mask)

    print("가림: %s" % ("끔 (원본 그대로)" if args.no_mask else "켬 (쿠팡 기타사항 자유입력)"))
    for name, out, n, stats in results:
        print("\n%s" % out.name)
        print("  %d줄 · %.1f MB · sha256 %s" % (n, out.stat().st_size / 1048576, sha256(out)[:16]))
        print("  제출자별: %s" % ", ".join("%s %d" % kv for kv in sorted(stats["by_submitter"].items())))
        if stats["masked_rows"]:
            print("  가린 줄 %d개:" % stats["masked_rows"])
            for sample, c in sorted(stats["samples"].items(), key=lambda x: -x[1]):
                print("     x%-4d %s" % (c, sample))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
