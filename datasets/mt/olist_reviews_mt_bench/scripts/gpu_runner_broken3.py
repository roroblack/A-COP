"""
Re-runs the 3 models that produced garbage via broken GGUF quantization
(HY-MT1.5-1.8B, Seed-X-PPO-7B, Seed-X-Instruct-7B), now using their official,
non-quantized HuggingFace checkpoints via transformers, to see their real quality.

Usage: python3 gpu_runner_broken3.py <pt_en|pt_ko> <model_label>
pt_en reads sample.jsonl's src_pt -> writes hyp_en (compare against ref_en for BLEU)
pt_ko reads sample.jsonl's src_pt -> writes hyp_ko
"""
import json, os, sys

os.environ.setdefault("HF_HOME", "/workspace/mt_bench/hf_cache")

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

AXIS = sys.argv[1]
LABEL = sys.argv[2]
assert AXIS in {"pt_en", "pt_ko"}
TGT_LANG = "English" if AXIS == "pt_en" else "Korean"
TGT_CODE = "en" if AXIS == "pt_en" else "ko"
OUT_FIELD = "hyp_en" if AXIS == "pt_en" else "hyp_ko"

OUT_DIR = os.environ.get("OUT_DIR_OVERRIDE", f"results_broken3_{AXIS}")
os.makedirs(OUT_DIR, exist_ok=True)
OUT_PATH = os.path.join(OUT_DIR, f"{LABEL}.jsonl")

REPOS = {
    "HY-MT1.5-1.8B": "tencent/HY-MT1.5-1.8B",
    "Seed-X-PPO-7B": "ByteDance-Seed/Seed-X-PPO-7B",
    "Seed-X-Instruct-7B": "ByteDance-Seed/Seed-X-Instruct-7B",
}
hf_repo = REPOS[LABEL]


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
                hyp = (r.get(OUT_FIELD) or "").strip()
                if hyp:
                    done.add(r["idx"])
            except Exception:
                pass
    return done & sample_idx


tok = AutoTokenizer.from_pretrained(hf_repo)
model = AutoModelForCausalLM.from_pretrained(hf_repo, torch_dtype=torch.float16, device_map="auto")
model.eval()

rows = load_samples()
sample_idx = {r["idx"] for r in rows}
done = completed_indices(sample_idx)

with open(OUT_PATH, "a", encoding="utf-8") as out_f:
    for row in rows:
        if row["idx"] in done:
            continue
        text = row["src_pt"]
        if LABEL == "HY-MT1.5-1.8B":
            messages = [{"role": "user", "content":
                         f"Translate the following segment into {TGT_LANG}, without additional explanation.\n\n{text}"}]
            input_ids = tok.apply_chat_template(messages, tokenize=True, add_generation_prompt=False,
                                                 return_tensors="pt")
            # Newer transformers versions can return a BatchEncoding instead
            # of a bare tensor here - normalize to a plain input_ids tensor.
            if hasattr(input_ids, "input_ids"):
                input_ids = input_ids.input_ids
            input_ids = input_ids.to(model.device)
            with torch.inference_mode():
                out_ids = model.generate(input_ids, max_new_tokens=150, temperature=0.7, top_p=0.6,
                                          top_k=20, repetition_penalty=1.05, do_sample=True)
            hyp = tok.decode(out_ids[0][input_ids.shape[1]:], skip_special_tokens=True)
        else:
            # Seed-X: no chat template, raw string + trailing target-language tag, beam search.
            prompt = f"Translate the following Portuguese sentence into {TGT_LANG}:\n{text} <{TGT_CODE}>"
            inputs = tok(prompt, return_tensors="pt").to(model.device)
            with torch.inference_mode():
                out_ids = model.generate(**inputs, num_beams=4, max_new_tokens=150, do_sample=False)
            hyp = tok.decode(out_ids[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
        hyp = hyp.strip()
        out_f.write(json.dumps({"idx": row["idx"], "src_pt": text, OUT_FIELD: hyp}, ensure_ascii=False) + "\n")
        out_f.flush()
        print(f"[{row['idx']}] {text[:40]!r} -> {hyp[:60]!r}", flush=True)

print(f"[done] {LABEL} {AXIS}", flush=True)
