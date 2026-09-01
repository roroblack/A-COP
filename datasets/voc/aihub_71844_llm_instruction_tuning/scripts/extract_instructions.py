"""AI Hub 71844(상담 LLM instruction tuning) 을 instruction/input/output 로 편다.

    python scripts/extract_instructions.py

내는 것:
    processed/instructions.jsonl   instruction 단위 표본
    processed/stats.json           ★전체 분모와 표본 수

원본은 상담 한 건이 파일 하나이고, 그 안에 `instructions[].data[]` 로 여러 개의
지시문이 달려 있다. 여기서는 **지시문 하나를 한 행으로** 편다.

★**세 기업(액티벤처·엘지유플러스·하나카드)을 뭉치지 않는다.** 여행·통신·카드로
  업종이 다르고, A-COP 의 커머스 상담과 겹치는 정도도 다르다. `source` 로 갈라
  두고 stats 에 업종별 건수를 적는다 — 쓰는 쪽이 무엇을 넣을지 고를 수 있게.

★이 데이터는 **DoD-28(파인튜닝 경로)** 의 재료다. 고객 응대 문장을 그대로
  베껴 쓰라는 뜻이 아니다 — 지시문·입력·출력의 형태를 익히는 데 쓴다.

★원본은 이미 비식별화돼 있다(이름·날짜·금액 자리가 `▲▲` 로 가려져 있다).
  그래도 `processed/` 는 저장소에 올리지 않는다(`datasets/README.md` 규칙).
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
SAMPLE_PER_GROUP = 300


def main() -> int:
    PROCESSED.mkdir(exist_ok=True)
    rng = random.Random(SEED)

    totals = Counter()
    per_source = defaultdict(Counter)
    task_counts = Counter()
    category_counts = Counter()
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
                for consultation in payload:
                    totals["consultations"] += 1
                    source = str(consultation.get("source") or "")
                    per_source[source]["consultations"] += 1
                    category = str(consultation.get("consulting_category") or "")
                    category_counts[category] += 1

                    for block in (consultation.get("instructions") or []):
                        tuning_type = str(block.get("tuning_type") or "")
                        for item in (block.get("data") or []):
                            totals["instructions"] += 1
                            per_source[source]["instructions"] += 1
                            task = str(item.get("task") or "")
                            task_category = str(item.get("task_category") or "")
                            task_counts[f"{task}/{task_category}"] += 1

                            instruction = str(item.get("instruction") or "").strip()
                            output = str(item.get("output") or "").strip()
                            if not instruction or not output:
                                # ★조용히 넘기지 않는다. 지시문이나 정답이 비면
                                #   학습에 못 쓰는 행인데, 세지 않으면 분모만 커진다.
                                totals["incomplete"] += 1
                                continue

                            totals["kept"] += 1
                            group = (source, tuning_type)
                            seen[group] += 1
                            row = {
                                "source_dataset": "aihub_71844",
                                "split": split,
                                "source": source,
                                "source_id": str(consultation.get("source_id") or ""),
                                "consulting_category": category,
                                "tuning_type": tuning_type,
                                "task": task,
                                "task_category": task_category,
                                "instruction": instruction,
                                "input": str(item.get("input") or "").strip(),
                                "output": output,
                            }
                            bucket = reservoir[group]
                            if len(bucket) < SAMPLE_PER_GROUP:
                                bucket.append(row)
                            else:
                                slot = rng.randrange(seen[group])
                                if slot < SAMPLE_PER_GROUP:
                                    bucket[slot] = row

    samples = [r for bucket in reservoir.values() for r in bucket]
    samples.sort(key=lambda r: (r["source"], r["tuning_type"], r["source_id"],
                                r["instruction"][:40]))
    (PROCESSED / "instructions.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in samples), encoding="utf-8")

    stats = {
        "totals": dict(totals),
        "sample_size": len(samples),
        "sample_per_group": SAMPLE_PER_GROUP,
        "seed": SEED,
        "per_source": {k: dict(v) for k, v in sorted(per_source.items())},
        "task_counts": dict(task_counts.most_common()),
        "consulting_categories": dict(category_counts.most_common()),
        "note": ("세 기업은 업종이 다르다(여행·통신·카드). 뭉치지 않고 source 로 "
                 "갈라 둔다. instruction 이나 output 이 빈 행은 학습에 못 쓰므로 "
                 "빼고, 뺀 수를 totals.incomplete 에 적는다."),
    }
    (PROCESSED / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2),
                                          encoding="utf-8")

    print(f"상담 {totals['consultations']:,}건 · 지시문 {totals['instructions']:,}개")
    print(f"  못 쓰는 행(지시문/정답 빔) {totals['incomplete']:,} · "
          f"남긴 {totals['kept']:,} → 표본 {len(samples):,}")
    print("  기업별: " + str({k: v["instructions"] for k, v in per_source.items()}))
    print(f"  task 종류 {len(task_counts)}: {dict(task_counts.most_common(6))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
