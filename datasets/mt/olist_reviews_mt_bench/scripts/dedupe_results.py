import json, sys, glob

for fn in sys.argv[1:]:
    seen = {}
    with open(fn, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            seen[r["idx"]] = line
    with open(fn, "w", encoding="utf-8") as f:
        for idx in sorted(seen):
            f.write(seen[idx] + "\n")
    print(fn, len(seen))
