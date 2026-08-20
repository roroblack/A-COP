import json
import sys

SRC = r"C:\Users\Yeon\acop_voc_corpus\corpus\sentiment\naver_shopping.txt"
OUT = r"C:\Users\Yeon\acop_voc_corpus\output\naver_shopping_sentiment.jsonl"
STATS_OUT = r"C:\Users\Yeon\acop_voc_corpus\output\preprocess_stats.json"

total = 0
dup_removed = 0
rating3_removed = 0
empty_removed = 0
malformed = 0
written = 0
seen_text = set()

import os
os.makedirs(os.path.dirname(OUT), exist_ok=True)

with open(SRC, "r", encoding="utf-8") as f_in, open(OUT, "w", encoding="utf-8") as f_out:
    for line in f_in:
        line = line.rstrip("\n").rstrip("\r")
        if not line:
            continue
        total += 1
        parts = line.split("\t", 1)
        if len(parts) != 2:
            malformed += 1
            continue
        rating_str, text = parts
        try:
            rating = int(rating_str)
        except ValueError:
            malformed += 1
            continue
        if not text.strip():
            empty_removed += 1
            continue
        if rating == 3:
            rating3_removed += 1
            continue
        if rating not in (1, 2, 4, 5):
            malformed += 1
            continue
        if text in seen_text:
            dup_removed += 1
            continue
        seen_text.add(text)
        label = "positive" if rating >= 4 else "negative"
        f_out.write(json.dumps({"rating": rating, "label": label, "text": text}, ensure_ascii=False) + "\n")
        written += 1

stats = {
    "total_lines": total,
    "malformed_removed": malformed,
    "rating3_removed": rating3_removed,
    "empty_removed": empty_removed,
    "duplicate_removed": dup_removed,
    "written": written,
    "arithmetic_check": total == (malformed + rating3_removed + empty_removed + dup_removed + written),
}

with open(STATS_OUT, "w", encoding="utf-8") as f:
    json.dump(stats, f, ensure_ascii=False, indent=2)

print(json.dumps(stats, ensure_ascii=False, indent=2))
