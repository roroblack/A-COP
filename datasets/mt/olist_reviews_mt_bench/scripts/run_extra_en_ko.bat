@echo off
setlocal
set OLLAMA_MODELS=F:\_proj\ollama_model
set HF_HOME=F:\_proj\hf_cache
cd /d F:\_proj\mt_bench
set SKIP_LABELS=Helsinki-opus-mt-tc-big-en-ko,NLLB-200-3.3B,seongs-ke-t5-base
python mt_bench_runner_extra.py en_ko >> run_extra_en_ko.log 2>> run_extra_en_ko.err.log
echo DONE >> run_extra_en_ko.log
