import json, glob, os
import sacrebleu

PUBLISHED = {
    "Hunyuan-MT-7B": (92.21, 87.24),
    "HY-MT1.5-7B": (91.77, 87.06),
    "HY-MT1.5-1.8B": (89.95, 84.97),
    "TranslateGemma-12B": (89.88, 85.85),
    "MiLMMT-46-12B": (89.07, 86.01),
    "MiLMMT-46-4B": (87.27, 84.30),
    "Tower-Plus-9B": (86.78, 84.44),
    "TranslateGemma-4B": (85.97, 82.51),
    "GemmaX2-28-9B": (84.69, 81.87),
    "Seed-X-PPO-7B": (83.58, 81.42),
    "Tower-Plus-2B": (81.83, 80.54),
    "MiLMMT-46-1B": (80.71, 79.32),
    "GemmaX2-28-2B": (80.09, 78.51),
    "Seed-X-Instruct-7B": (79.96, 77.72),
    "LMT-60-8B": (None, None),
}

rows_out = []
for path in sorted(glob.glob("../processed/results/*.jsonl")):
    label = os.path.basename(path)[:-6]
    refs, hyps = [], []
    empty = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            hyp = r["hyp_en"].strip()
            if not hyp:
                empty += 1
            hyps.append(hyp)
            refs.append(r["ref_en"])
    if not hyps:
        continue
    bleu = sacrebleu.corpus_bleu(hyps, [refs])
    chrf = sacrebleu.corpus_chrf(hyps, [refs])
    pub_comet, pub_bleu = PUBLISHED.get(label, (None, None))
    rows_out.append({
        "label": label, "n": len(hyps), "empty": empty,
        "bleu": round(bleu.score, 2), "chrf": round(chrf.score, 2),
        "published_comet22": pub_comet, "published_bleu": pub_bleu,
    })

rows_out.sort(key=lambda x: -x["bleu"])

print(f"{'model':<20} {'n':>5} {'empty':>6} {'our_BLEU':>9} {'our_chrF':>9} {'pub_COMET22':>12} {'pub_BLEU':>9}")
for r in rows_out:
    pc = r["published_comet22"] if r["published_comet22"] is not None else "-"
    pb = r["published_bleu"] if r["published_bleu"] is not None else "-"
    print(f"{r['label']:<20} {r['n']:>5} {r['empty']:>6} {r['bleu']:>9} {r['chrf']:>9} {str(pc):>12} {str(pb):>9}")

with open("../processed/leaderboard_result.json", "w", encoding="utf-8") as f:
    json.dump(rows_out, f, ensure_ascii=False, indent=1)
print("\nsaved leaderboard_result.json")
