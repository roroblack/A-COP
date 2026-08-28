"""
Runs the 5 T5/CTranslate2 models that were abandoned on x600 (env issues),
now on a Linux box with a real GPU (20GB VRAM). Also can run TranslateGemma-27B
via transformers directly (bypassing the broken Ollama GGUF path).

Usage: python3 gpu_runner_t5_ct2.py <pt_ko|en_ko> <model_label>
Reads ./sample.jsonl (idx, score, src_pt, ref_en). Writes results_extra_<axis>/<label>.jsonl
"""
import json, os, sys, subprocess

os.environ.setdefault("HF_HOME", "/workspace/mt_bench/hf_cache")

AXIS = sys.argv[1]
LABEL = sys.argv[2]
assert AXIS in {"pt_ko", "en_ko"}

SRC_FIELD = "src_pt" if AXIS == "pt_ko" else "ref_en"
OUT_DIR = os.environ.get("OUT_DIR_OVERRIDE", f"results_extra_{AXIS}")
os.makedirs(OUT_DIR, exist_ok=True)
OUT_PATH = os.path.join(OUT_DIR, f"{LABEL}.jsonl")


def load_samples():
    rows = []
    with open(os.environ.get("SAMPLE_FILE", "sample.jsonl"), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def completed_indices(sample_idx):
    done = set()
    if not os.path.exists(OUT_PATH):
        return done
    with open(OUT_PATH, encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
                hyp = (r.get("hyp_ko") or "").strip()
                if hyp:
                    done.add(r["idx"])
            except Exception:
                pass
    return done & sample_idx


def run_t5(hf_repo, prefix):
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(hf_repo)
    model = AutoModelForSeq2SeqLM.from_pretrained(hf_repo, torch_dtype=torch.float16).to("cuda")
    model.eval()
    rows = load_samples()
    sample_idx = {r["idx"] for r in rows}
    done = completed_indices(sample_idx)
    with open(OUT_PATH, "a", encoding="utf-8") as out_f:
        for row in rows:
            if row["idx"] in done:
                continue
            text = row[SRC_FIELD]
            inp = f"{prefix}{text}" if prefix else text
            inputs = tok(inp, return_tensors="pt", truncation=True, max_length=200).to("cuda")
            with torch.inference_mode():
                out_ids = model.generate(**inputs, max_new_tokens=100)
            hyp = tok.decode(out_ids[0], skip_special_tokens=True)
            out_f.write(json.dumps({"idx": row["idx"], "src": text, "hyp_ko": hyp}, ensure_ascii=False) + "\n")
            out_f.flush()
            print(f"[{row['idx']}] {text[:40]!r} -> {hyp[:60]!r}", flush=True)


def ensure_ct2_converted(hf_repo, ct2_dir, trust_remote_code=False):
    if os.path.isdir(ct2_dir) and os.listdir(ct2_dir):
        return
    cmd = ["ct2-transformers-converter", "--model", hf_repo, "--output_dir", ct2_dir,
           "--quantization", "int8_float16"]
    if trust_remote_code:
        cmd += ["--trust_remote_code"]
    print("converting:", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def run_ct2_nllb(hf_repo, ct2_dir):
    import ctranslate2, transformers
    ensure_ct2_converted(hf_repo, ct2_dir, trust_remote_code=True)
    src_lang = "eng_Latn" if AXIS == "en_ko" else "por_Latn"
    tok = transformers.AutoTokenizer.from_pretrained(hf_repo, src_lang=src_lang)
    translator = ctranslate2.Translator(ct2_dir, device="cuda")
    rows = load_samples()
    sample_idx = {r["idx"] for r in rows}
    done = completed_indices(sample_idx)
    with open(OUT_PATH, "a", encoding="utf-8") as out_f:
        for row in rows:
            if row["idx"] in done:
                continue
            text = row[SRC_FIELD]
            src_tokens = tok.convert_ids_to_tokens(tok.encode(text))
            result = translator.translate_batch([src_tokens], target_prefix=[["kor_Hang"]])
            out_tokens = result[0].hypotheses[0][1:]
            hyp = tok.decode(tok.convert_tokens_to_ids(out_tokens), skip_special_tokens=True)
            out_f.write(json.dumps({"idx": row["idx"], "src": text, "hyp_ko": hyp}, ensure_ascii=False) + "\n")
            out_f.flush()
            print(f"[{row['idx']}] {text[:40]!r} -> {hyp[:60]!r}", flush=True)


def run_ct2_marian(hf_repo, ct2_dir):
    import ctranslate2, transformers
    ensure_ct2_converted(hf_repo, ct2_dir)
    tok = transformers.AutoTokenizer.from_pretrained(hf_repo)
    translator = ctranslate2.Translator(ct2_dir, device="cuda")
    rows = load_samples()
    sample_idx = {r["idx"] for r in rows}
    done = completed_indices(sample_idx)
    with open(OUT_PATH, "a", encoding="utf-8") as out_f:
        for row in rows:
            if row["idx"] in done:
                continue
            text = row[SRC_FIELD]
            src_tokens = tok.convert_ids_to_tokens(tok.encode(text))
            result = translator.translate_batch([src_tokens])
            out_tokens = result[0].hypotheses[0]
            hyp = tok.decode(tok.convert_tokens_to_ids(out_tokens), skip_special_tokens=True)
            out_f.write(json.dumps({"idx": row["idx"], "src": text, "hyp_ko": hyp}, ensure_ascii=False) + "\n")
            out_f.flush()
            print(f"[{row['idx']}] {text[:40]!r} -> {hyp[:60]!r}", flush=True)


def run_translategemma_27b():
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    hf_repo = "google/translategemma-27b-it"
    src_lang = "English" if AXIS == "en_ko" else "Portuguese"
    tok = AutoTokenizer.from_pretrained(hf_repo)
    model = AutoModelForCausalLM.from_pretrained(
        hf_repo,
        quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16),
        device_map="auto",
    )
    model.eval()
    rows = load_samples()
    sample_idx = {r["idx"] for r in rows}
    done = completed_indices(sample_idx)
    with open(OUT_PATH, "a", encoding="utf-8") as out_f:
        for row in rows:
            if row["idx"] in done:
                continue
            text = row[SRC_FIELD]
            prompt = f"Translate the following text from {src_lang} to Korean:\n{text}"
            messages = [{"role": "user", "content": prompt}]
            inputs = tok.apply_chat_template(messages, add_generation_prompt=True, return_tensors="pt").to("cuda")
            with torch.inference_mode():
                out_ids = model.generate(inputs, max_new_tokens=100, do_sample=False)
            hyp = tok.decode(out_ids[0][inputs.shape[1]:], skip_special_tokens=True)
            out_f.write(json.dumps({"idx": row["idx"], "src": text, "hyp_ko": hyp}, ensure_ascii=False) + "\n")
            out_f.flush()
            print(f"[{row['idx']}] {text[:40]!r} -> {hyp[:60]!r}", flush=True)


REGISTRY = {
    "MADLAD-400-3B": lambda: run_t5("google/madlad400-3b-mt", "<2ko> "),
    "MADLAD-400-10B": lambda: run_t5("google/madlad400-10b-mt", "<2ko> "),
    "seongs-ke-t5-base": lambda: run_t5("seongs/ke-t5-base-aihub-koen-translation-integrated-10m-en-to-ko", ""),
    "NLLB-200-3.3B": lambda: run_ct2_nllb("facebook/nllb-200-3.3B", "/workspace/mt_bench/ct2_models/nllb200_3.3B"),
    "Helsinki-opus-mt-tc-big-en-ko": lambda: run_ct2_marian("Helsinki-NLP/opus-mt-tc-big-en-ko", "/workspace/mt_bench/ct2_models/opus_en_ko"),
    "TranslateGemma-27B": run_translategemma_27b,
}

if LABEL not in REGISTRY:
    print(f"Unknown label {LABEL}. Available: {list(REGISTRY)}", file=sys.stderr)
    sys.exit(2)

REGISTRY[LABEL]()
print(f"[done] {LABEL}", flush=True)
