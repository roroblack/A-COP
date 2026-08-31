"""팀원 제출본을 `processed/` 로 합친다.

    python scripts/merge_incoming.py                 # 기본: raw/_incoming_20260829
    python scripts/merge_incoming.py raw/_incoming_X

★두 형식을 **한 파일에 섞지 않는다.**

  네이버 API 조회분과 쿠팡 화면 수집분은 필드 이름 몇 개가 겹칠 뿐 뜻이 다르다.
  쿠팡 쪽 `status` 는 `tracking_schema.json` 의 enum(in_transit/complete/…)이
  아니라 **"8/2(금) 도착" 같은 화면 라벨**이고, `level`·`complete`·`courier_code`
  가 아예 없으며, 이벤트에 `time`·`level` 대신 `raw` 가 있다. 억지로 한 스키마에
  밀어 넣으면 "배송 상태" 라는 말의 뜻이 두 가지가 되고, 그걸 읽는 쪽은 그걸
  모른다. 그래서 파일을 나눈다:

    processed/tracking.jsonl          네이버 API 조회 결과 (tracking_schema.json)
    processed/tracking_coupang.jsonl  쿠팡 화면 수집 결과 (tracking_coupang_schema.json)

★건수만 세지 않는다. 빠뜨린 것·중복으로 버린 것·스키마에 안 맞는 것을 **각각
  세어서 보고한다.** 조용히 건너뛰면 분모가 줄어 성공률이 실제보다 좋아 보인다.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "processed"
DEFAULT_INCOMING = ROOT / "raw" / "_incoming_20260829"

NAVER_OUT = PROCESSED / "tracking.jsonl"
COUPANG_OUT = PROCESSED / "tracking_coupang.jsonl"

NAVER_KEYS = ["courier", "courier_code", "tracking_number", "status", "item_name",
              "estimate", "level", "complete", "events", "queried_at", "error"]
NAVER_STATUS = {"in_transit", "complete", "no_history", "not_found", "error"}

COUPANG_KEYS = ["order_id", "shipment_box_id", "tracking_number", "courier",
                "status_label", "events", "queried_at", "source"]


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path}:{number} 을(를) 읽지 못했다: {exc}")
    return rows


def is_naver(rows: list[dict]) -> bool:
    return bool(rows) and "courier_code" in rows[0] and "level" in rows[0]


def better(a: dict, b: dict) -> dict:
    """같은 운송장이 둘일 때 무엇을 남기나.

    ★이력이 있는 쪽을 남긴다. 둘 다 있거나 둘 다 없으면 나중에 조회한 쪽이다 —
      배송은 진행되므로 뒤에 조회한 것이 더 많이 안다.
    """
    a_events, b_events = len(a.get("events") or []), len(b.get("events") or [])
    if a_events != b_events:
        return a if a_events > b_events else b
    return a if str(a.get("queried_at", "")) >= str(b.get("queried_at", "")) else b


def check_naver(row: dict) -> str | None:
    missing = [k for k in NAVER_KEYS if k not in row]
    if missing:
        return f"필드 없음: {', '.join(missing)}"
    if row["status"] not in NAVER_STATUS:
        return f"status 가 enum 밖: {row['status']!r}"
    if not str(row.get("tracking_number") or "").strip():
        return "운송장 번호가 비었다"
    return None


def merge_naver(incoming: Path) -> None:
    sources: dict[str, list[dict]] = {}
    if NAVER_OUT.exists():
        sources[f"(기존) {NAVER_OUT.name}"] = read_jsonl(NAVER_OUT)
    for path in sorted(incoming.glob("naver_tracking*")):
        rows = read_jsonl(path)
        if not is_naver(rows):
            print(f"  ! {path.name}: 네이버 형식이 아니다 — 건너뛴다")
            continue
        sources[path.name] = rows

    merged: dict[str, dict] = {}
    rejected: list[tuple[str, str]] = []
    duplicates = 0
    print("네이버 API 조회분")
    for name, rows in sources.items():
        history = sum(1 for r in rows if r.get("events"))
        bad = 0
        for row in rows:
            problem = check_naver(row)
            if problem:
                rejected.append((name, problem))
                bad += 1
                continue
            key = row["tracking_number"]
            if key in merged:
                duplicates += 1
                merged[key] = better(merged[key], row)
            else:
                merged[key] = row
        print(f"  {name[:44]:46s} {len(rows):5d}행 · 이력 {history:3d} · 형식오류 {bad}")

    rows = [merged[k] for k in sorted(merged)]
    NAVER_OUT.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    status = Counter(r["status"] for r in rows)
    print(f"  → {NAVER_OUT.relative_to(ROOT)} {len(rows)}건 "
          f"(중복 합침 {duplicates} · 형식오류 버림 {len(rejected)})")
    print(f"    status: {dict(status)} · 이력 있는 건 {sum(1 for r in rows if r.get('events'))}")
    for name, problem in rejected[:5]:
        print(f"    ! {name}: {problem}")
    if len(rejected) > 5:
        print(f"    ! … 외 {len(rejected) - 5}건")


def merge_coupang(incoming: Path) -> None:
    merged: dict[tuple, dict] = {}
    duplicates = 0
    print("\n쿠팡 화면 수집분")
    files = [p for p in sorted(incoming.glob("*.json"))]
    if not files:
        print("  없음")
        return
    for path in files:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            print(f"  ! {path.name}: 리스트가 아니다 — 건너뛴다")
            continue
        source = path.stem
        history = 0
        for record in raw:
            events = [{"kind": e.get("kind", ""), "where": e.get("where", ""),
                       "timeString": e.get("timeString", ""), "raw": e.get("raw", "")}
                      for e in (record.get("events") or [])]
            history += bool(events)
            row = {
                "order_id": str(record.get("order_id") or ""),
                "shipment_box_id": str(record.get("shipment_box_id") or ""),
                "tracking_number": str(record.get("tracking_number") or ""),
                "courier": str(record.get("courier") or ""),
                # ★`status` 로 두지 않는다 — 네이버 쪽 `status` 는 enum 인데 여기 값은
                #   "8/2(금) 도착" 같은 화면 문구다. 같은 이름을 쓰면 읽는 쪽이 같은
                #   뜻으로 읽는다.
                "status_label": str(record.get("status") or ""),
                "events": events,
                "queried_at": str(record.get("queried_at") or ""),
                "source": source,
            }
            key = (row["order_id"], row["shipment_box_id"], row["tracking_number"])
            if key in merged:
                duplicates += 1
                merged[key] = better(merged[key], row)
            else:
                merged[key] = row
        print(f"  {path.name[:44]:46s} {len(raw):5d}행 · 이력 {history}")

    rows = [merged[k] for k in sorted(merged)]
    COUPANG_OUT.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    couriers = Counter(r["courier"][:12] for r in rows)
    print(f"  → {COUPANG_OUT.relative_to(ROOT)} {len(rows)}건 (중복 합침 {duplicates})")
    print(f"    이력 있는 건 {sum(1 for r in rows if r['events'])} "
          f"· 운송장 비어 있음 {sum(1 for r in rows if not r['tracking_number'])}")
    print(f"    courier: {dict(couriers)}")
    print("    ★이력이 있는 건이 전체의 일부다 — 쿠팡 화면은 배송 완료 후 이력을 "
          "감춘다. 없는 것을 '조회 실패' 로 읽지 않는다.")


def main() -> int:
    incoming = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INCOMING
    if not incoming.is_dir():
        raise SystemExit(f"제출본 폴더가 없다: {incoming}")
    PROCESSED.mkdir(exist_ok=True)
    print(f"제출본: {incoming}\n")
    merge_naver(incoming)
    merge_coupang(incoming)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
