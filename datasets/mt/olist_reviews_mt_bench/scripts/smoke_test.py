import json, urllib.request, time

src = "Recebi bem antes do prazo estipulado."
prompt = f"Translate this from Portuguese to English:\nPortuguese: {src}\nEnglish:"

payload = {
    "model": "hf.co/mradermacher/MiLMMT-46-1B-v0.1-GGUF:Q4_K_M",
    "prompt": prompt,
    "raw": True,
    "stream": False,
    "options": {"temperature": 0.0, "num_predict": 100, "stop": ["\n\n"]},
}
req = urllib.request.Request(
    "http://127.0.0.1:11434/api/generate",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
)
t0 = time.time()
with urllib.request.urlopen(req, timeout=60) as resp:
    data = json.loads(resp.read().decode("utf-8"))
print("elapsed:", round(time.time() - t0, 2), "s")
print("response:", repr(data.get("response")))
