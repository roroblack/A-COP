import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

print("loading tokenizer...", flush=True)
tok = AutoTokenizer.from_pretrained("google/madlad400-3b-mt")
print("tokenizer ok", flush=True)

print("loading model (cpu, fp32)...", flush=True)
model = AutoModelForSeq2SeqLM.from_pretrained("google/madlad400-3b-mt", dtype=torch.float32)
print("model ok", flush=True)

ids = tok("<2ko> hello", return_tensors="pt").input_ids
print("tokenized", flush=True)
out = model.generate(ids, max_new_tokens=20)
print("RESULT:", tok.decode(out[0], skip_special_tokens=True), flush=True)
