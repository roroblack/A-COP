@echo off
setlocal
set OLLAMA_MODELS=F:\_proj\ollama_model
set HF_HOME=F:\_proj\hf_cache
cd /d F:\_proj\mt_bench
python mt_bench_runner_extra.py pt_ko >> run_extra_pt_ko.log 2>> run_extra_pt_ko.err.log
echo DONE >> run_extra_pt_ko.log
