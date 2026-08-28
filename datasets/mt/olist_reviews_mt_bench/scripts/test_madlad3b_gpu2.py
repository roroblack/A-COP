import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

print("loading tokenizer...", flush=True)
tok = AutoTokenizer.from_pretrained("google/madlad400-3b-mt")
print("tokenizer ok", flush=True)

print("loading model (gpu, fp16, device_map direct-to-gpu)...", flush=True)
torch.cuda.empty_cache()
model = AutoModelForSeq2SeqLM.from_pretrained(
    "google/madlad400-3b-mt",
    dtype=torch.float16,
    device_map={"": 0},
    low_cpu_mem_usage=True,
)
print("model ok, mem_allocated:", torch.cuda.memory_allocated() / 1e9, "GB", flush=True)
model.eval()

ids = tok("<2ko> The table top arrived all dented and beaten.", return_tensors="pt").input_ids.to("cuda")
print("tokenized", flush=True)
with torch.inference_mode():
    out = model.generate(ids, max_new_tokens=64)
print("RESULT:", tok.decode(out[0], skip_special_tokens=True), flush=True)
