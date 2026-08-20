"""raw/ 두 CSV에서 검증된 정렬 구간만 골라 processed/sample.jsonl(300쌍)을 만든다.

원본(original)과 참조번역(en-translated)은 review_score/review_comment 두 컬럼뿐이고
공유 ID가 없어 행 순서로만 대응된다. 두 파일의 행수가 다르므로(en-translated 쪽에
어딘가 행이 하나 끼어들어 있음) 앞에서부터 review_score가 일치하는 구간까지만
"검증된 정렬"로 보고, 그 구간에서만 샘플링한다.
"""
import csv, random, json

ORIG = "../raw/olist_order_reviews(original).csv"
TRAN = "../raw/olist_order_reviews_(en-translated).csv"
OUT = "../processed/sample.jsonl"
SAMPLE_N = 300
SEED = 20260821

orig = list(csv.DictReader(open(ORIG, encoding="utf-8-sig")))
trans = list(csv.DictReader(open(TRAN, encoding="utf-8-sig")))

n = min(len(orig), len(trans))
first_mismatch = next((i for i in range(n) if orig[i]["review_score"] != trans[i]["review_score"]), n)
print(f"orig={len(orig)} trans={len(trans)} verified aligned pairs=0..{first_mismatch-1} ({first_mismatch} rows)")

pairs = []
for i in range(first_mismatch):
    src = orig[i]["review_comment"].strip()
    ref = trans[i]["review_comment"].strip()
    if len(src) < 3 or len(ref) < 3:
        continue
    pairs.append({"idx": i, "score": orig[i]["review_score"], "src_pt": src, "ref_en": ref})

print(f"usable pairs after length filter: {len(pairs)}")

random.seed(SEED)
random.shuffle(pairs)
sample = pairs[:SAMPLE_N]
sample.sort(key=lambda x: x["idx"])

with open(OUT, "w", encoding="utf-8") as f:
    for row in sample:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")

print(f"wrote {len(sample)} sampled pairs to {OUT}")
