@echo off
setlocal
set OLLAMA_MODELS=F:\_proj\ollama_model
cd /d F:\_proj\mt_bench
echo === pulling nayohan-llama3-8B === >> pull_new.log
ollama pull hf.co/afrideva/llama3-instrucTrans-enko-8b-GGUF:Q4_K_M >> pull_new.log 2>&1
echo === pulling Gugugo-koen-7B === >> pull_new.log
ollama pull hf.co/RichardErkhov/squarelike_-_Gugugo-koen-7B-V1.1-gguf:Q4_K_M >> pull_new.log 2>&1
echo === pulling TranslateGemma-27B (Q3_K_M for VRAM fit) === >> pull_new.log
ollama pull hf.co/mradermacher/translategemma-27b-it-GGUF:Q3_K_M >> pull_new.log 2>&1
echo === installing sentencepiece === >> pull_new.log
python -m pip install sentencepiece >> pull_new.log 2>&1
echo === DONE === >> pull_new.log
