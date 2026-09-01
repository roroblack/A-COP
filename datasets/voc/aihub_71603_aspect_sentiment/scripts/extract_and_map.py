"""AI Hub 71603(속성기반 감성분석) 을 A-COP 감성 어휘로 옮긴다.

    python scripts/extract_and_map.py

내는 것:
    processed/reviews.jsonl      리뷰 표본 (문장 감성 + 속성별 감성)
    processed/aspect_vocab.json  속성 어휘 전량과 건수
    processed/stats.json         ★전체 분모와 표본 수

★A-COP 어휘의 정본은 `final_project_cs/app/modules/customer_ops/feedback.py` 의
  SENTIMENTS(positive·neutral·negative)다. 원본 극성 1/0/-1 을 그대로 옮긴다.

★**`GeneralPolarity` 가 비어 있는 행이 16,984건 있다.** 이걸 0(중립)으로 채우면
  "중립" 이 실제보다 부풀고, 그 오차가 분류기 학습까지 간다. 비운 채로 두고
  (`mapped_sentiment: null`) 몇 건인지 stats 에 적는다(`CLAUDE.md` §1).

★**SNS 와 쇼핑몰을 섞어서 한 덩어리로 부르지 않는다.** 쇼핑몰(189,669)은 실제
  구매자 리뷰지만 SNS(35,616)는 인플루언서 홍보 글이다. 둘을 "고객 목소리" 로
  뭉치면 사실이 아니다. 지우지는 않는다 — 감성 분류기 학습에는 쓸 수 있으므로
  `source` 로 갈라 두고 쓰는 쪽이 고르게 한다.
"""
from __future__ import annotations

import json
import random
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "processed"
SEED = 7
SAMPLE_PER_GROUP = 500

POLARITY = {"1": "positive", "0": "neutral", "-1": "negative"}


def polarity(value: object) -> str | None:
    """★모르면 `None` 이다. 0 으로 채우지 않는다."""
    if value is None:
        return None
    return POLARITY.get(str(value).strip())


def main() -> int:
    PROCESSED.mkdir(exist_ok=True)
    rng = random.Random(SEED)

    totals = Counter()
    per_source = defaultdict(Counter)
    sentiment_counts = Counter()
    aspect_counts = Counter()
    aspect_polarity = Counter()
    reservoir: dict[tuple, list[dict]] = defaultdict(list)
    seen = Counter()

    archives = sorted(ROOT.glob("raw/**/*라벨링데이터*/*.zip"))
    if not archives:
        raise SystemExit("라벨링데이터 zip 을 찾지 못했다")

    for archive in archives:
        split = "validation" if "Validation" in str(archive) else "train"
        with zipfile.ZipFile(archive) as bundle:
            for name in bundle.namelist():
                if not name.lower().endswith(".json"):
                    continue
                try:
                    payload = json.loads(bundle.open(name).read().decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    totals["unreadable_file"] += 1
                    continue
                if isinstance(payload, dict):
                    payload = [payload]
                for record in payload:
                    totals["rows"] += 1
                    source = str(record.get("Source") or "")
                    per_source[source]["rows"] += 1

                    text = (record.get("RawText") or "").strip()
                    if not text:
                        totals["empty_text"] += 1
                        continue

                    mapped = polarity(record.get("GeneralPolarity"))
                    if mapped is None:
                        totals["missing_general_polarity"] += 1
                    sentiment_counts[mapped or "null"] += 1

                    aspects = []
                    for aspect in (record.get("Aspects") or []):
                        label = str(aspect.get("Aspect") or "").strip()
                        aspect_mapped = polarity(aspect.get("SentimentPolarity"))
                        aspect_counts[label] += 1
                        aspect_polarity[aspect_mapped or "null"] += 1
                        aspects.append({
                            "aspect": label,
                            "text": str(aspect.get("SentimentText") or "").strip(),
                            "polarity_raw": str(aspect.get("SentimentPolarity") or ""),
                            "mapped_sentiment": aspect_mapped,
                        })

                    totals["kept"] += 1
                    per_source[source]["kept"] += 1
                    group = (source, str(record.get("Domain") or ""), mapped or "null")
                    seen[group] += 1
                    row = {
                        "source_dataset": "aihub_71603",
                        "split": split,
                        "source": source,
                        "domain": str(record.get("Domain") or ""),
                        "main_category": str(record.get("MainCategory") or ""),
                        "product_name": str(record.get("ProductName") or ""),
                        "text": text,
                        "general_polarity_raw": str(record.get("GeneralPolarity")),
                        "mapped_sentiment": mapped,
                        "aspects": aspects,
                    }
                    bucket = reservoir[group]
                    if len(bucket) < SAMPLE_PER_GROUP:
                        bucket.append(row)
                    else:
                        slot = rng.randrange(seen[group])
                        if slot < SAMPLE_PER_GROUP:
                            bucket[slot] = row

    samples = [r for bucket in reservoir.values() for r in bucket]
    samples.sort(key=lambda r: (r["source"], r["domain"], r["mapped_sentiment"] or "~",
                                r["text"][:40]))
    (PROCESSED / "reviews.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in samples), encoding="utf-8")

    (PROCESSED / "aspect_vocab.json").write_text(json.dumps({
        "aspect_counts": dict(aspect_counts.most_common()),
        "aspect_polarity": dict(aspect_polarity),
        "polarity_mapping": POLARITY,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    stats = {
        "totals": dict(totals),
        "sample_size": len(samples),
        "sample_per_group": SAMPLE_PER_GROUP,
        "seed": SEED,
        "per_source": {k: dict(v) for k, v in sorted(per_source.items())},
        "sentiment_counts": dict(sentiment_counts.most_common()),
        "distinct_aspects": len(aspect_counts),
        "note": ("SNS 는 인플루언서 홍보 글, 쇼핑몰은 실제 구매자 리뷰다. "
                 "'고객 목소리'로 뭉치지 않는다. GeneralPolarity 가 비어 있는 행은 "
                 "0(중립)으로 채우지 않고 null 로 둔다."),
    }
    (PROCESSED / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2),
                                          encoding="utf-8")

    print(f"전체 {totals['rows']:,}행 → 남긴 {totals['kept']:,}행 · 표본 {len(samples):,}행")
    print("  source: " + str({k: v["rows"] for k, v in per_source.items()}))
    print(f"  sentiment: {dict(sentiment_counts)}")
    print(f"  ★GeneralPolarity 빈 행 {totals['missing_general_polarity']:,}건 — "
          "채우지 않고 null 로 뒀다")
    print(f"  속성 어휘 {len(aspect_counts)}종 · 속성 라벨 {sum(aspect_counts.values()):,}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
