import json, glob, os, re, sys

HANGUL_RE = re.compile(r"[가-힣]")
ANY_ALPHA_RE = re.compile(r"[^\s\W]", re.UNICODE)

AXIS = sys.argv[1] if len(sys.argv) > 1 else "en_ko"
IN_DIR = f"../processed/results_extra_{AXIS}"
OUT_FILE = f"../processed/leaderboard_result_extra_{AXIS}.json"

rows_out = []
for path in sorted(glob.glob(f"{IN_DIR}/*.jsonl")):
    label = os.path.basename(path)[:-6]
    n = empty = 0
    hangul_chars = total_chars = 0
    samples = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            hyp = (r.get("hyp_ko") or "").strip()
            n += 1
            if not hyp:
                empty += 1
                continue
            h = len(HANGUL_RE.findall(hyp))
            t = len(ANY_ALPHA_RE.findall(hyp))
            hangul_chars += h
            total_chars += max(t, 1)
            if len(samples) < 3:
                samples.append({"src": r.get("src", r.get("src_pt")), "hyp_ko": hyp})
    ratio = round(hangul_chars / total_chars, 3) if total_chars else 0.0
    rows_out.append({
        "label": label, "n": n, "empty": empty,
        "hangul_ratio": ratio, "samples": samples,
    })

rows_out.sort(key=lambda x: -x["hangul_ratio"])

print(f"{'model':<24} {'n':>5} {'empty':>6} {'hangul_ratio':>13}  verdict")
for r in rows_out:
    verdict = "OK" if r["hangul_ratio"] >= 0.5 else ("SUSPECT" if r["hangul_ratio"] >= 0.15 else "LIKELY BROKEN")
    print(f"{r['label']:<24} {r['n']:>5} {r['empty']:>6} {r['hangul_ratio']:>13}  {verdict}")

with open(OUT_FILE, "w", encoding="utf-8") as f:
    json.dump(rows_out, f, ensure_ascii=False, indent=1)
print(f"\nsaved {OUT_FILE}")
