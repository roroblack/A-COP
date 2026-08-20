import json

OUT = r"C:\Users\Yeon\acop_voc_corpus\output\naver_shopping_sentiment.jsonl"

line_count = 0
label_dist = {"positive": 0, "negative": 0}
rating_dist = {1: 0, 2: 0, 4: 0, 5: 0}
mismatch = 0
invalid_json = 0
missing_keys = 0

with open(OUT, "r", encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        line = line.rstrip("\n")
        if not line:
            continue
        line_count += 1
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            invalid_json += 1
            continue
        if not all(k in obj for k in ("rating", "label", "text")):
            missing_keys += 1
            continue
        rating = obj["rating"]
        label = obj["label"]
        rating_dist[rating] = rating_dist.get(rating, 0) + 1
        label_dist[label] = label_dist.get(label, 0) + 1
        expected_label = "positive" if rating >= 4 else "negative"
        if label != expected_label:
            mismatch += 1

result = {
    "line_count": line_count,
    "invalid_json": invalid_json,
    "missing_keys": missing_keys,
    "label_rating_mismatch": mismatch,
    "label_distribution": label_dist,
    "rating_distribution": rating_dist,
    "all_checks_passed": (invalid_json == 0 and missing_keys == 0 and mismatch == 0),
}

print(json.dumps(result, ensure_ascii=False, indent=2))
