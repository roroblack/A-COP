"""AI Hub 102(소상공인 고객 주문 QA) 를 A-COP 분류 체계로 옮긴다.

    python scripts/extract_and_map.py

zip 을 풀지 않고 스트리밍으로 읽는다(압축 해제 시 약 700MB).

내는 것:
    processed/customer_questions.jsonl   고객 질문 발화 표본
    processed/intent_mapping.json        무엇을 무엇으로 옮겼나
    processed/stats.json                 ★전체 분모와 표본 수를 같이 적는다

★A-COP 어휘의 정본은 `final_project_cs/app/modules/customer_ops/feedback.py` 다
  (INTENTS 5종 · SENTIMENTS 3종). 여기서 새 값을 만들지 않는다.

★**가르지 못하는 것은 가르지 않는다.** 원본 인텐트는 `교환|반품|환불` 을 **한
  라벨로 묶어** 두었다. A-COP 은 `return` 과 `exchange` 를 나누는데, 원본이 그
  구분을 갖고 있지 않으므로 어느 쪽으로 찍어도 그건 지어낸 값이다. 그래서
  `mapped_intent` 를 **null** 로 두고 `ambiguous_between` 에 후보를 적는다
  (`CLAUDE.md` §1 — 값을 모르면 비워 둔다).

★**오프라인 업종은 뺀다.** 음식점·카페·병원은 주문/배송/반품 흐름이 A-COP 의
  커머스 케이스와 다르다. 억지로 넣으면 "이 데이터가 커머스 VOC 다" 라는 말이
  사실이 아니게 된다. 뺀 건수는 stats 에 적는다 — 조용히 빼지 않는다.
"""
from __future__ import annotations

import csv
import io
import json
import random
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw"
PROCESSED = ROOT / "processed"
SEED = 7
SAMPLE_PER_GROUP = 400

SOURCES = [
    ("train", RAW / "Training" / "라벨링데이터_train.zip"),
    ("validation", RAW / "Validation" / "라벨링데이터_validation.zip"),
]

#: 원본 인텐트의 **앞머리**(`배송_날짜_질문` → `배송`)로 옮긴다. 218~249종이나
#:  되는 전체 라벨을 하나하나 적으면 새 라벨이 하나 늘 때마다 조용히 빠진다.
#:
#: ★첫 실행에서 7종이 `unmapped` 로 잡혔다(구매 28,298 · AS 26,818 · 포장 22,299 ·
#:   웹사이트 13,215 · 부가서비스 6,331 · 멤버십 2,655 · 예약 736). 그중 **구매는
#:   명백히 order 인데 빠져 있었다** — 세지 않았으면 3만 건 가까이가 조용히
#:   `other` 도 아닌 미분류로 남았을 것이다. 그래서 아래 표는 "본 것을 다 적는다":
#:   `other` 로 보내더라도 **그렇게 정했다는 사실**을 여기 남긴다. 미분류가 0이
#:   아니면 새 라벨이 생겼다는 뜻이다.
PREFIX_TO_INTENT = {
    "배송": "shipping",
    "주문": "order",
    "결제": "order",
    "구매": "order",
    "제품": "other",     # 상품 문의. A-COP 의 4개 업무 흐름 어디에도 안 붙는다
    "행사": "other",
    "매장": "other",
    "기타": "other",
    "AS": "other",       # 30716 전처리에서도 AS 는 A-COP 흐름에 안 맞아 뺐다
    "포장": "other",     # 배송으로 보내고 싶지만 원본은 포장 상태 문의다 — 추정하지 않는다
    "웹사이트": "other",
    "부가서비스": "other",
    "멤버십": "other",
    "예약": "other",
}
#: ★원본이 셋을 한 라벨로 묶어 둔 것. 갈라서 찍지 않는다.
AMBIGUOUS_PREFIXES = {"교환|반품|환불": ["return", "exchange"]}

#: 오프라인 업종 — 커머스 케이스와 흐름이 다르다.
EXCLUDED_CATEGORIES = {"음식점", "카페", "병원"}

SENTIMENT = {"m": "neutral", "n": "negative", "p": "positive"}

ENTITY_COLUMNS = ["가격", "수량", "크기", "장소", "조직", "사람", "시간", "날짜", "상품명"]


def decode_name(info: zipfile.ZipInfo) -> str:
    """zip 안 한글 파일명은 CP949 로 들어 있다."""
    for encoding in ("cp437", "latin-1"):
        try:
            return info.filename.encode(encoding).decode("cp949")
        except Exception:
            continue
    return info.filename


def category_of(filename: str) -> str:
    return filename.rsplit("/", 1)[-1].split("_")[0]


def map_intent(source_intent: str) -> tuple[str | None, str, list[str] | None]:
    prefix = source_intent.split("_", 1)[0].strip()
    if prefix in AMBIGUOUS_PREFIXES:
        return None, prefix, AMBIGUOUS_PREFIXES[prefix]
    return PREFIX_TO_INTENT.get(prefix), prefix, None


def main() -> int:
    PROCESSED.mkdir(exist_ok=True)
    rng = random.Random(SEED)

    totals = Counter()
    per_category: dict[str, Counter] = defaultdict(Counter)
    intent_counts = Counter()
    sentiment_counts = Counter()
    unmapped_prefixes = Counter()
    # 표본은 (카테고리, 매핑결과) 별로 저수지 표집한다 — 전체를 메모리에 두지 않는다.
    reservoir: dict[tuple[str, str], list[dict]] = defaultdict(list)
    seen_per_group = Counter()

    for split, archive in SOURCES:
        if not archive.exists():
            raise SystemExit(f"원본이 없다: {archive}")
        with zipfile.ZipFile(archive) as bundle:
            for info in bundle.infolist():
                name = decode_name(info)
                category = category_of(name)
                with bundle.open(info) as handle:
                    stream = io.TextIOWrapper(handle, encoding="utf-8",
                                              errors="replace", newline="")
                    for row in csv.DictReader(stream):
                        totals["rows"] += 1
                        per_category[category]["rows"] += 1

                        if category in EXCLUDED_CATEGORIES:
                            totals["excluded_category"] += 1
                            continue
                        # ★공백이 붙은 값이 실제로 있다(`'c '` 156건). strip 없이
                        #   비교하면 그만큼이 조용히 빠진다.
                        if (row.get("발화자") or "").strip() != "c":
                            totals["not_customer"] += 1
                            continue
                        if (row.get("QA여부") or "").strip() != "q":
                            totals["not_question"] += 1
                            continue
                        text = (row.get("발화문") or "").strip()
                        if not text:
                            totals["empty_text"] += 1
                            continue

                        source_intent = (row.get("인텐트") or "").strip()
                        mapped, prefix, ambiguous = map_intent(source_intent)
                        if mapped is None and ambiguous is None:
                            unmapped_prefixes[prefix] += 1
                        sentiment_raw = (row.get("감성") or "").strip()
                        mapped_sentiment = SENTIMENT.get(sentiment_raw)
                        if mapped_sentiment is None:
                            totals["unknown_sentiment"] += 1

                        totals["kept"] += 1
                        per_category[category]["kept"] += 1
                        intent_counts[mapped or (f"ambiguous:{prefix}" if ambiguous
                                                 else f"unmapped:{prefix}")] += 1
                        sentiment_counts[mapped_sentiment or f"unknown:{sentiment_raw}"] += 1

                        group = (category, mapped or ("ambiguous" if ambiguous else "unmapped"))
                        seen_per_group[group] += 1
                        record = {
                            "source": "aihub_102",
                            "split": split,
                            "category": category,
                            "text": text,
                            "source_intent": source_intent,
                            "intent_prefix": prefix,
                            "mapped_intent": mapped,
                            "ambiguous_between": ambiguous,
                            "sentiment_raw": sentiment_raw,
                            "mapped_sentiment": mapped_sentiment,
                            "entities": {c: row[c].strip() for c in ENTITY_COLUMNS
                                         if (row.get(c) or "").strip()},
                            "consult_id": (row.get("상담번호") or "").strip(),
                            "turn_index": (row.get("상담내순번") or "").strip(),
                        }
                        bucket = reservoir[group]
                        if len(bucket) < SAMPLE_PER_GROUP:
                            bucket.append(record)
                        else:
                            # 저수지 표집 — 앞부분만 뽑히지 않게 한다
                            slot = rng.randrange(seen_per_group[group])
                            if slot < SAMPLE_PER_GROUP:
                                bucket[slot] = record

    samples = [r for bucket in reservoir.values() for r in bucket]
    samples.sort(key=lambda r: (r["category"], r["mapped_intent"] or "~", r["consult_id"],
                                r["turn_index"]))
    out = PROCESSED / "customer_questions.jsonl"
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in samples),
                   encoding="utf-8")

    (PROCESSED / "intent_mapping.json").write_text(json.dumps({
        "prefix_to_intent": PREFIX_TO_INTENT,
        "ambiguous_prefixes": AMBIGUOUS_PREFIXES,
        "excluded_categories": sorted(EXCLUDED_CATEGORIES),
        "sentiment": SENTIMENT,
        "note": ("원본 인텐트는 '대분류_속성_유형' 꼴이고 대분류만 본다. "
                 "'교환|반품|환불' 은 원본이 셋을 한 라벨로 묶어 둔 것이라 "
                 "return/exchange 로 가르지 않고 null 로 둔다."),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    stats = {
        "totals": dict(totals),
        "sample_size": len(samples),
        "sample_per_group": SAMPLE_PER_GROUP,
        "seed": SEED,
        "per_category": {k: dict(v) for k, v in sorted(per_category.items())},
        "mapped_intent_counts": dict(intent_counts.most_common()),
        "mapped_sentiment_counts": dict(sentiment_counts.most_common()),
        "unmapped_intent_prefixes": dict(unmapped_prefixes.most_common()),
    }
    (PROCESSED / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2),
                                          encoding="utf-8")

    print(f"전체 {totals['rows']:,}행")
    print(f"  제외 — 오프라인 업종 {totals['excluded_category']:,} · "
          f"상담원 발화 {totals['not_customer']:,} · 답변 턴 {totals['not_question']:,} · "
          f"빈 발화 {totals['empty_text']:,}")
    print(f"  남긴 고객 질문 {totals['kept']:,}행 → 표본 {len(samples):,}행")
    print(f"  intent: {dict(intent_counts.most_common(8))}")
    print(f"  sentiment: {dict(sentiment_counts)}")
    if unmapped_prefixes:
        print(f"  ★매핑 못한 인텐트 대분류 {len(unmapped_prefixes)}종: "
              f"{dict(unmapped_prefixes.most_common(10))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
