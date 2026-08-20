import glob, os

for path in sorted(glob.glob("../processed/results_ko/*.jsonl")):
    with open(path, encoding="utf-8") as f:
        n = sum(1 for _ in f)
    print(f"{os.path.basename(path):<28} {n}")
