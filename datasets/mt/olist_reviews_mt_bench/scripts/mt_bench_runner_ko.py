import json, time, subprocess, urllib.request, concurrent.futures, traceback, os

SAMPLE_FILE = "../processed/sample.jsonl"
OUT_DIR = "../processed/results_ko"
GEN_URL = "http://127.0.0.1:11434/api/generate"
CHAT_URL = "http://127.0.0.1:11434/api/chat"
CALL_TIMEOUT = 30

MODELS = [
    {"label": "HY-MT1.5-1.8B",     "params": "1.8B", "tag": "hf.co/tencent/HY-MT1.5-1.8B-GGUF:Q4_K_M",              "tier": "small",  "mode": "chat",
     "prompt": lambda s: f"Translate the following segment into Korean, without additional explanation.\n\n{s}"},
    {"label": "Tower-Plus-2B",     "params": "2B",   "tag": "hf.co/DZgas/Tower-Plus-2B-GGUF:Q4_K_M",                "tier": "small",  "mode": "chat",
     "prompt": lambda s: f"Translate the following Portuguese source text to Korean:\nPortuguese: {s}\nKorean: "},
    {"label": "GemmaX2-28-2B",     "params": "2B",   "tag": "hf.co/mradermacher/GemmaX2-28-2B-v0.1-GGUF:Q4_K_M",    "tier": "small",  "mode": "raw",
     "prompt": lambda s: f"Translate this from Portuguese to Korean:\nPortuguese: {s}\nKorean:"},
    {"label": "MiLMMT-46-1B",      "params": "1B",   "tag": "hf.co/mradermacher/MiLMMT-46-1B-v0.1-GGUF:Q4_K_M",     "tier": "small",  "mode": "raw",
     "prompt": lambda s: f"Translate this from Portuguese to Korean:\nPortuguese: {s}\nKorean:"},

    {"label": "TranslateGemma-4B", "params": "4B",   "tag": "hf.co/mradermacher/translategemma-4b-it-GGUF:Q4_K_M", "tier": "medium", "mode": "chat",
     "prompt": lambda s: f"Translate the following text from Portuguese to Korean:\n{s}"},
    {"label": "MiLMMT-46-4B",      "params": "4B",   "tag": "hf.co/mradermacher/MiLMMT-46-4B-v0.1-GGUF:Q4_K_M",     "tier": "medium", "mode": "raw",
     "prompt": lambda s: f"Translate this from Portuguese to Korean:\nPortuguese: {s}\nKorean:"},

    {"label": "Hunyuan-MT-7B",     "params": "7B",   "tag": "hf.co/mradermacher/Hunyuan-MT-7B-GGUF:Q4_K_M",         "tier": "large", "mode": "chat",
     "prompt": lambda s: f"Translate the following segment into Korean, without additional explanation.\n\n{s}"},
    {"label": "HY-MT1.5-7B",       "params": "7B",   "tag": "hf.co/tencent/HY-MT1.5-7B-GGUF:Q4_K_M",                "tier": "large", "mode": "chat",
     "prompt": lambda s: f"Translate the following segment into Korean, without additional explanation.\n\n{s}"},
    {"label": "Seed-X-PPO-7B",     "params": "7B",   "tag": "hf.co/mradermacher/Seed-X-PPO-7B-GGUF:Q4_K_M",         "tier": "large", "mode": "raw",
     "prompt": lambda s: f"Translate the following Portuguese sentence into Korean:\n{s} <ko>"},
    {"label": "Seed-X-Instruct-7B","params": "7B",   "tag": "hf.co/mradermacher/Seed-X-Instruct-7B-GGUF:Q4_K_M",    "tier": "large", "mode": "raw",
     "prompt": lambda s: f"Translate the following Portuguese sentence into Korean:\n{s} <ko>"},
    {"label": "LMT-60-8B",         "params": "8B",   "tag": "hf.co/mradermacher/LMT-60-8B-GGUF:Q4_K_M",             "tier": "large", "mode": "chat",
     "prompt": lambda s: f"Translate the following text from Portuguese into Korean:\nPortuguese: {s}\nKorean:"},
    {"label": "Tower-Plus-9B",     "params": "9B",   "tag": "hf.co/mradermacher/Tower-Plus-9B-GGUF:Q4_K_M",         "tier": "large", "mode": "chat",
     "prompt": lambda s: f"Translate the following Portuguese source text to Korean:\nPortuguese: {s}\nKorean: "},
    {"label": "GemmaX2-28-9B",     "params": "9B",   "tag": "hf.co/mradermacher/GemmaX2-28-9B-v0.1-GGUF:Q4_K_M",    "tier": "large", "mode": "raw",
     "prompt": lambda s: f"Translate this from Portuguese to Korean:\nPortuguese: {s}\nKorean:"},
    {"label": "TranslateGemma-12B","params": "12B",  "tag": "hf.co/mradermacher/translategemma-12b-it-i1-GGUF:i1-Q4_K_M", "tier": "large", "mode": "chat",
     "prompt": lambda s: f"Translate the following text from Portuguese to Korean:\n{s}"},
    {"label": "MiLMMT-46-12B",     "params": "12B",  "tag": "hf.co/mradermacher/MiLMMT-46-12B-v0.1-GGUF:Q4_K_M",    "tier": "large", "mode": "raw",
     "prompt": lambda s: f"Translate this from Portuguese to Korean:\nPortuguese: {s}\nKorean:"},
]

CAVEATS = {
    "TranslateGemma-4B": "Structured typed-field API not reproducible via Ollama chat; best-effort plain instruction used.",
    "TranslateGemma-12B": "Same caveat as TranslateGemma-4B.",
    "MiLMMT-46-12B": "GGUF quant is v0.1 checkpoint, not v1.0.",
    "MiLMMT-46-4B": "GGUF quant is v0.1 checkpoint, not v1.0.",
    "MiLMMT-46-1B": "GGUF quant is v0.1 checkpoint, not v1.0.",
    "GemmaX2-28-2B": "Korean support not explicitly confirmed from model card (28-language set unspecified); verify via hangul_ratio diagnostic.",
    "GemmaX2-28-9B": "Same caveat as GemmaX2-28-2B.",
    "HY-MT1.5-1.8B": "In the earlier PT->EN run this GGUF quant produced garbled/unrelated output on manual inspection; re-testing here for PT->KO to see if it's language-specific or a broken quant in general.",
    "Seed-X-PPO-7B": "Same caveat as HY-MT1.5-1.8B: PT->EN run showed broken output on manual testing.",
    "Seed-X-Instruct-7B": "Same caveat as HY-MT1.5-1.8B: PT->EN run showed broken output on manual testing.",
}


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def load_sample():
    rows = []
    with open(SAMPLE_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


PULL_URL = "http://127.0.0.1:11434/api/pull"
PULL_WATCHDOG_TIMEOUT = 1800


def _do_pull_http(tag):
    payload = {"model": tag, "stream": False}
    req = urllib.request.Request(PULL_URL, data=json.dumps(payload).encode("utf-8"),
                                  headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=PULL_WATCHDOG_TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data


def ollama_pull(tag):
    log(f"pulling {tag} (via HTTP API) ...")
    fut = _watchdog_pool.submit(_do_pull_http, tag)
    try:
        data = fut.result(timeout=PULL_WATCHDOG_TIMEOUT)
    except Exception as e:
        log(f"PULL FAILED {tag}: {type(e).__name__}: {e}")
        return False
    if "error" in data:
        log(f"PULL FAILED {tag}: {data['error']}")
        return False
    log(f"pulled {tag} OK (status={data.get('status','')})")
    return True


def _do_raw(tag, prompt):
    payload = {
        "model": tag, "prompt": prompt, "raw": True, "stream": False,
        "options": {"temperature": 0.0, "num_predict": 150, "stop": ["\n\n", "Portuguese:", "Korean:\nPortuguese"]},
        "keep_alive": "10m",
    }
    req = urllib.request.Request(GEN_URL, data=json.dumps(payload).encode("utf-8"),
                                  headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=CALL_TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("response", "").strip()


NO_THINK_MODELS = {"LMT-60-8B"}


def _do_chat(tag, user_content, label=None):
    payload = {
        "model": tag,
        "messages": [{"role": "user", "content": user_content}],
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": 150},
        "keep_alive": "10m",
    }
    if label in NO_THINK_MODELS:
        payload["think"] = False
    req = urllib.request.Request(CHAT_URL, data=json.dumps(payload).encode("utf-8"),
                                  headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=CALL_TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    msg = data.get("message", {})
    content = (msg.get("content") or "").strip()
    if not content:
        content = (msg.get("thinking") or "").strip()
    return content


WATCHDOG_TIMEOUT = 40
_watchdog_pool = concurrent.futures.ThreadPoolExecutor(max_workers=64, thread_name_prefix="wd")


def call_raw(tag, prompt):
    fut = _watchdog_pool.submit(_do_raw, tag, prompt)
    return fut.result(timeout=WATCHDOG_TIMEOUT)


def call_chat(tag, user_content, label=None):
    fut = _watchdog_pool.submit(_do_chat, tag, user_content, label)
    return fut.result(timeout=WATCHDOG_TIMEOUT)


def load_done_idx(out_path):
    done = set()
    if os.path.exists(out_path):
        with open(out_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    done.add(json.loads(line)["idx"])
                except Exception:
                    pass
    return done


def run_model(model, sample):
    label, tag, mode = model["label"], model["tag"], model["mode"]
    out_path = f"{OUT_DIR}/{label}.jsonl"
    done_idx = load_done_idx(out_path)
    todo = [row for row in sample if row["idx"] not in done_idx]
    if not todo:
        log(f"{label}: already fully done ({len(done_idx)} rows), skipping")
        return label, 0
    log(f"{label}: resuming, {len(done_idx)} already done, {len(todo)} remaining")
    errors = 0
    t0 = time.time()
    with open(out_path, "a", encoding="utf-8") as f:
        for i, row in enumerate(todo):
            prompt_text = model["prompt"](row["src_pt"])
            try:
                hyp = call_raw(tag, prompt_text) if mode == "raw" else call_chat(tag, prompt_text, label)
            except Exception as e:
                hyp = ""
                errors += 1
                if errors <= 5:
                    log(f"{label}: error on idx={row['idx']}: {type(e).__name__}: {e}")
            f.write(json.dumps({"idx": row["idx"], "src_pt": row["src_pt"], "hyp_ko": hyp}, ensure_ascii=False) + "\n")
            f.flush()
            if (i + 1) % 10 == 0:
                log(f"{label}: {i+1}/{len(todo)} (of {len(todo)} remaining) done ({time.time()-t0:.0f}s elapsed, {errors} errors)")
    dt = time.time() - t0
    log(f"{label}: FINISHED remaining {len(todo)} rows in {dt:.0f}s, {errors} errors -> {out_path}")
    return label, errors


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    sample = load_sample()
    log(f"loaded {len(sample)} sample rows (PT -> KO run)")
    with open(f"{OUT_DIR}/_caveats.json", "w", encoding="utf-8") as f:
        json.dump(CAVEATS, f, ensure_ascii=False, indent=1)

    tiers = {"small": [], "medium": [], "large": []}
    for m in MODELS:
        tiers[m["tier"]].append(m)

    for tier_name in ["small", "medium", "large"]:
        models = tiers[tier_name]
        if not models:
            continue
        log(f"=== TIER {tier_name}: {[m['label'] for m in models]} ===")
        for m in models:
            ollama_pull(m["tag"])
        max_workers = len(models) if tier_name != "large" else 1
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
            futs = {ex.submit(run_model, m, sample): m for m in models}
            for fut in concurrent.futures.as_completed(futs):
                m = futs[fut]
                try:
                    fut.result()
                except Exception:
                    log(f"{m['label']}: CRASHED\n{traceback.format_exc()}")

    log("ALL TIERS DONE")


if __name__ == "__main__":
    main()
