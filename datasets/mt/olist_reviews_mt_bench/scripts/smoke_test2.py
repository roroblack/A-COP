import json, urllib.request, time, subprocess

tag = "hf.co/DZgas/Tower-Plus-2B-GGUF:Q4_K_M"
print("pulling...")
r = subprocess.run(["ollama", "pull", tag], capture_output=True, text=True, timeout=600)
print(r.returncode, r.stderr[-300:] if r.returncode else "ok")

src = "Recebi bem antes do prazo estipulado."
prompt = f"Translate the following Portuguese source text to English:\nPortuguese: {src}\nEnglish: "

payload = {
    "model": tag,
    "messages": [{"role": "user", "content": prompt}],
    "stream": False,
    "options": {"temperature": 0.0, "num_predict": 100},
}
req = urllib.request.Request(
    "http://127.0.0.1:11434/api/chat",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
)
t0 = time.time()
with urllib.request.urlopen(req, timeout=60) as resp:
    data = json.loads(resp.read().decode("utf-8"))
print("elapsed:", round(time.time() - t0, 2), "s")
print("response:", repr(data.get("message", {}).get("content")))
