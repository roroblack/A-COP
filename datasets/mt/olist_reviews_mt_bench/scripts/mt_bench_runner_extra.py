"""
Extra MT models runner - handles 3 backends: ollama / transformers_t5 / ctranslate2.
Usage: python mt_bench_runner_extra.py <pt_ko|en_ko>

pt_ko: source field src_pt, target Korean, reuses ../processed/sample.jsonl (or ./sample.jsonl locally)
en_ko: source field ref_en, target Korean, same sample file
"""
import json, os, sys, subprocess, urllib.request
from concurrent.futures import ThreadPoolExecutor

os.environ.setdefault("HF_HOME", "F:\\_proj\\hf_cache")

AXIS = sys.argv[1] if len(sys.argv) > 1 else "pt_ko"
if AXIS not in {"pt_ko", "en_ko"}:
    raise SystemExit("Usage: python mt_bench_runner_extra.py <pt_ko|en_ko>")
SAMPLE_FILE = os.environ.get("SAMPLE_FILE", "sample.jsonl")
OUT_DIR = os.environ.get("OUT_DIR_OVERRIDE", f"results_extra_{AXIS}")
os.makedirs(OUT_DIR, exist_ok=True)

SRC_FIELD = "src_pt" if AXIS == "pt_ko" else "ref_en"
SRC_LANG_NAME = "Portuguese" if AXIS == "pt_ko" else "English"

OLLAMA_URL = "http://127.0.0.1:11434"
WATCHDOG_TIMEOUT = 60
CALL_TIMEOUT = 50
_executor = ThreadPoolExecutor(max_workers=4)


def load_samples():
    rows = []
    seen_idx = set()
    with open(SAMPLE_FILE, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            if row["idx"] in seen_idx:
                raise ValueError(f"duplicate idx in {SAMPLE_FILE}: {row['idx']}")
            seen_idx.add(row["idx"])
            rows.append(row)
    return rows


def _do_call(url, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                  headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=CALL_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def watchdog_call(url, payload):
    fut = _executor.submit(_do_call, url, payload)
    return fut.result(timeout=WATCHDOG_TIMEOUT)


def ollama_chat(model, user_content, system=None):
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user_content})
    payload = {"model": model, "messages": messages,
               "stream": False, "think": False, "options": {"num_predict": 200, "temperature": 0}}
    try:
        r = watchdog_call(f"{OLLAMA_URL}/api/chat", payload)
        content = r.get("message", {}).get("content", "").strip()
        if not content:
            raise RuntimeError("Ollama returned an empty message")
        return content
    except Exception as e:
        raise RuntimeError(f"Ollama chat request failed: {e}") from e


def ollama_raw(model, prompt, stop=None):
    payload = {"model": model, "prompt": prompt, "raw": True, "stream": False,
               "options": {"num_predict": 200, "temperature": 0, "stop": stop or []}}
    try:
        r = watchdog_call(f"{OLLAMA_URL}/api/generate", payload)
        content = r.get("response", "").strip()
        if not content:
            raise RuntimeError("Ollama returned an empty response")
        return content
    except Exception as e:
        raise RuntimeError(f"Ollama raw request failed: {e}") from e


# ---- backend: ollama ----
def run_ollama(m, rows, done_idx, out_f):
    mode = m.get("mode", "chat")
    prompt_fn = m["prompt"]
    for row in rows:
        if row["idx"] in done_idx:
            continue
        text = row[SRC_FIELD]
        try:
            if mode == "chat":
                hyp = ollama_chat(m["tag"], prompt_fn(text), system=m.get("system"))
            else:
                hyp = ollama_raw(m["tag"], prompt_fn(text), stop=m.get("stop"))
        except Exception as e:
            # Record the failure but keep going - one bad row (timeout, empty
            # message) must not abort the remaining 299 rows for this model.
            hyp = ""
            print(f"  [row {row['idx']} FAILED] {e}")
        out_f.write(json.dumps({"idx": row["idx"], "src": text, "hyp_ko": hyp}, ensure_ascii=False) + "\n")
        out_f.flush()
        done_idx.add(row["idx"])


# ---- backend: transformers T5 (MADLAD, KE-T5) ----
def run_t5(hf_repo, prefix, rows, done_idx, out_f):
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(hf_repo)

    # This 12GB card consistently OOMs on T5 GPU inference here - WDDM alone
    # reserves ~1.2GB, and fp16 weights (3B: ~5GB, 10B: ~20GB) leave too
    # little/no headroom for generation. bitsandbytes 8-bit also crashes
    # natively (access violation) on this box's Windows/CUDA combo. CPU
    # inference is slower but has been verified to load and generate
    # correctly, so use it unconditionally for T5 models.
    # fp32 (~4B params -> ~16GB for the 3B model) is safe on this 24GB-RAM
    # box. The 10B model would need ~40GB in fp32 - use bf16 (~20GB) instead,
    # which is still tight; if this box's earlier full-system freeze taught
    # us anything, don't attempt the 10B model at all without headroom.
    cpu_dtype = torch.bfloat16 if hf_repo == "google/madlad400-10b-mt" else torch.float32
    model = AutoModelForSeq2SeqLM.from_pretrained(hf_repo, dtype=cpu_dtype)
    model.eval()
    for row in rows:
        if row["idx"] in done_idx:
            continue
        text = row[SRC_FIELD]
        inp = f"{prefix}{text}" if prefix else text
        inputs = tok(inp, return_tensors="pt", truncation=True, max_length=128)
        with torch.inference_mode():
            out_ids = model.generate(**inputs, max_new_tokens=64)
        hyp = tok.decode(out_ids[0], skip_special_tokens=True)
        out_f.write(json.dumps({"idx": row["idx"], "src": text, "hyp_ko": hyp}, ensure_ascii=False) + "\n")
        out_f.flush()
        done_idx.add(row["idx"])
    del model


# ---- backend: ctranslate2 (NLLB, opus-mt) ----
def ensure_ct2_converted(hf_repo, ct2_dir, model_type):
    if os.path.isdir(ct2_dir) and os.listdir(ct2_dir):
        return
    # int8 (not int8_float16, which needs a GPU) - this box's GPU is too
    # VRAM-tight, so ctranslate2 also runs on CPU here.
    cmd = ["ct2-transformers-converter", "--model", hf_repo, "--output_dir", ct2_dir, "--quantization", "int8"]
    if model_type == "nllb":
        cmd += ["--trust_remote_code"]
    print("converting:", " ".join(cmd))
    subprocess.run(cmd, check=True)


def run_ct2_nllb(hf_repo, ct2_dir, rows, done_idx, out_f):
    import ctranslate2, transformers
    ensure_ct2_converted(hf_repo, ct2_dir, "nllb")
    tok = transformers.AutoTokenizer.from_pretrained(hf_repo, src_lang="eng_Latn" if AXIS == "en_ko" else "por_Latn")
    translator = ctranslate2.Translator(ct2_dir, device="cpu")
    for row in rows:
        if row["idx"] in done_idx:
            continue
        text = row[SRC_FIELD]
        src_tokens = tok.convert_ids_to_tokens(tok.encode(text))
        result = translator.translate_batch([src_tokens], target_prefix=[["kor_Hang"]])
        out_tokens = result[0].hypotheses[0][1:]
        hyp = tok.decode(tok.convert_tokens_to_ids(out_tokens), skip_special_tokens=True)
        out_f.write(json.dumps({"idx": row["idx"], "src": text, "hyp_ko": hyp}, ensure_ascii=False) + "\n")
        out_f.flush()
        done_idx.add(row["idx"])


def run_ct2_marian(hf_repo, ct2_dir, rows, done_idx, out_f):
    import ctranslate2, transformers
    ensure_ct2_converted(hf_repo, ct2_dir, "marian")
    tok = transformers.AutoTokenizer.from_pretrained(hf_repo)
    translator = ctranslate2.Translator(ct2_dir, device="cpu")
    for row in rows:
        if row["idx"] in done_idx:
            continue
        text = row[SRC_FIELD]
        src_tokens = tok.convert_ids_to_tokens(tok.encode(text))
        result = translator.translate_batch([src_tokens])
        out_tokens = result[0].hypotheses[0]
        hyp = tok.decode(tok.convert_tokens_to_ids(out_tokens), skip_special_tokens=True)
        out_f.write(json.dumps({"idx": row["idx"], "src": text, "hyp_ko": hyp}, ensure_ascii=False) + "\n")
        out_f.flush()
        done_idx.add(row["idx"])


# ---- model registry ----
# prompt formats verified against each model's HuggingFace card / the original
# PT->EN mt_bench_runner.py templates (retargeted to a Korean target).
_tgemma_prompt = lambda src: (lambda s: f"Translate the following text from {src} to Korean:\n{s}")
_towerplus_prompt = lambda src: (lambda s: f"Translate the following {src} source text to Korean:\n{src}: {s}\nKorean: ")
_raw_generic_prompt = lambda src: (lambda s: f"Translate this from {src} to Korean:\n{src}: {s}\nKorean:")

PT_KO_EXTRA = [
    {"label": "TranslateGemma-27B", "kind": "ollama", "tag": "hf.co/mradermacher/translategemma-27b-it-GGUF:Q3_K_M",
     "mode": "chat", "prompt": _tgemma_prompt("Portuguese")},
    {"label": "MADLAD-400-10B", "kind": "t5", "repo": "google/madlad400-10b-mt", "prefix": "<2ko> "},
    {"label": "MADLAD-400-3B", "kind": "t5", "repo": "google/madlad400-3b-mt", "prefix": "<2ko> "},
    {"label": "NLLB-200-3.3B", "kind": "ct2_nllb", "repo": "facebook/nllb-200-3.3B", "ct2_dir": "F:/_proj/ct2_models/nllb200_3.3B"},
]

EN_KO = [
    {"label": "TranslateGemma-27B", "kind": "ollama", "tag": "hf.co/mradermacher/translategemma-27b-it-GGUF:Q3_K_M",
     "mode": "chat", "prompt": _tgemma_prompt("English")},
    {"label": "TranslateGemma-12B", "kind": "ollama", "tag": "hf.co/mradermacher/translategemma-12b-it-i1-GGUF:i1-Q4_K_M",
     "mode": "chat", "prompt": _tgemma_prompt("English")},
    {"label": "MiLMMT-46-12B", "kind": "ollama", "tag": "hf.co/mradermacher/MiLMMT-46-12B-v0.1-GGUF:Q4_K_M",
     "mode": "raw", "prompt": _raw_generic_prompt("English")},
    # nayohan card's exact example: Korean system prompt + plain user turn with just the source sentence.
    {"label": "nayohan-llama3-8B", "kind": "ollama", "tag": "hf.co/afrideva/llama3-instrucTrans-enko-8b-GGUF:Q4_K_M",
     "mode": "chat", "system": "당신은 번역기 입니다. 영어를 한국어로 번역하세요.", "prompt": lambda s: s},
    {"label": "MiLMMT-46-4B", "kind": "ollama", "tag": "hf.co/mradermacher/MiLMMT-46-4B-v0.1-GGUF:Q4_K_M",
     "mode": "raw", "prompt": _raw_generic_prompt("English")},
    {"label": "TranslateGemma-4B", "kind": "ollama", "tag": "hf.co/mradermacher/translategemma-4b-it-GGUF:Q4_K_M",
     "mode": "chat", "prompt": _tgemma_prompt("English")},
    {"label": "MADLAD-400-10B", "kind": "t5", "repo": "google/madlad400-10b-mt", "prefix": "<2ko> "},
    {"label": "Tower-Plus-9B", "kind": "ollama", "tag": "hf.co/mradermacher/Tower-Plus-9B-GGUF:Q4_K_M",
     "mode": "chat", "prompt": _towerplus_prompt("English")},
    {"label": "Helsinki-opus-mt-tc-big-en-ko", "kind": "ct2_marian", "repo": "Helsinki-NLP/opus-mt-tc-big-en-ko", "ct2_dir": "F:/_proj/ct2_models/opus_en_ko"},
    {"label": "NLLB-200-3.3B", "kind": "ct2_nllb", "repo": "facebook/nllb-200-3.3B", "ct2_dir": "F:/_proj/ct2_models/nllb200_3.3B"},
    {"label": "seongs-ke-t5-base", "kind": "t5", "repo": "seongs/ke-t5-base-aihub-koen-translation-integrated-10m-en-to-ko", "prefix": ""},
    {"label": "GemmaX2-28-2B", "kind": "ollama", "tag": "hf.co/mradermacher/GemmaX2-28-2B-v0.1-GGUF:Q4_K_M",
     "mode": "raw", "prompt": _raw_generic_prompt("English")},
    # Gugugo card's fill-in-the-blank format: raw completion, "</끝>" stop marker after source.
    {"label": "Gugugo-koen-7B", "kind": "ollama", "tag": "hf.co/RichardErkhov/squarelike_-_Gugugo-koen-7B-V1.1-gguf:Q4_K_M",
     "mode": "raw", "prompt": lambda s: f"### 영어: {s}</끝>\n### 한국어:", "stop": ["</끝>", "\n###"]},
]
# davidkim205/iris-7b intentionally omitted - no premade GGUF, needs manual conversion (see status notes)

MODELS = PT_KO_EXTRA if AXIS == "pt_ko" else EN_KO

# Optional: skip labels whose model/deps aren't downloaded/installed yet
# (comma-separated), e.g. SKIP_LABELS="TranslateGemma-27B,MADLAD-400-10B"
SKIP_LABELS = {s.strip() for s in os.environ.get("SKIP_LABELS", "").split(",") if s.strip()}


def main():
    rows = load_samples()
    sample_idx = {row["idx"] for row in rows}
    for m in MODELS:
        if m["label"] in SKIP_LABELS:
            print(f"[skip] {m['label']} (SKIP_LABELS - deps not ready)")
            continue
        out_path = os.path.join(OUT_DIR, f"{m['label']}.jsonl")
        done_idx = set()
        if os.path.exists(out_path):
            with open(out_path, encoding="utf-8") as f:
                for line in f:
                    try:
                        record = json.loads(line)
                        hyp = record.get("hyp_ko")
                        if isinstance(hyp, str) and hyp.strip() and not hyp.startswith("[ERROR:"):
                            done_idx.add(record["idx"])
                    except Exception:
                        pass
        done_idx &= sample_idx
        if sample_idx <= done_idx:
            print(f"[skip] {m['label']} already complete ({len(done_idx)}/{len(rows)})")
            continue
        print(f"[run] {m['label']} kind={m['kind']} resume_from={len(done_idx)}/{len(rows)}")
        with open(out_path, "a", encoding="utf-8") as out_f:
            try:
                if m["kind"] == "ollama":
                    run_ollama(m, rows, done_idx, out_f)
                elif m["kind"] == "t5":
                    run_t5(m["repo"], m["prefix"], rows, done_idx, out_f)
                elif m["kind"] == "ct2_nllb":
                    run_ct2_nllb(m["repo"], m["ct2_dir"], rows, done_idx, out_f)
                elif m["kind"] == "ct2_marian":
                    run_ct2_marian(m["repo"], m["ct2_dir"], rows, done_idx, out_f)
            except Exception as e:
                print(f"[FAIL] {m['label']}: {e}")
            else:
                print(f"[done] {m['label']}")


if __name__ == "__main__":
    main()
