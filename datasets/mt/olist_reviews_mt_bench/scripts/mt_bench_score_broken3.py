import json, glob, os
import sacrebleu

sample = {}
with open("../processed/sample.jsonl", encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        sample[r["idx"]] = r

rows_out = []
for path in sorted(glob.glob("../processed/results_broken3_pt_en/*.jsonl")):
    label = os.path.basename(path)[:-6]
    hyps, refs = [], []
    empty = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            hyp = (r.get("hyp_en") or "").strip()
            ref = sample[r["idx"]]["ref_en"]
            if not hyp:
                empty += 1
                hyp = ""
            hyps.append(hyp)
            refs.append(ref)
    bleu = sacrebleu.corpus_bleu(hyps, [refs])
    chrf = sacrebleu.corpus_chrf(hyps, [refs])
    rows_out.append({"label": label, "n": len(hyps), "empty": empty,
                      "bleu": round(bleu.score, 2), "chrf": round(chrf.score, 2)})

rows_out.sort(key=lambda x: -x["bleu"])
print(f"{'model':<20} {'n':>5} {'empty':>6} {'bleu':>7} {'chrf':>7}")
for r in rows_out:
    print(f"{r['label']:<20} {r['n']:>5} {r['empty']:>6} {r['bleu']:>7} {r['chrf']:>7}")

with open("../processed/leaderboard_result_broken3_pt_en.json", "w", encoding="utf-8") as f:
    json.dump(rows_out, f, ensure_ascii=False, indent=1)
print("\nsaved leaderboard_result_broken3_pt_en.json")
