@echo off
setlocal

if "%~2"=="" (
    echo Usage: run_single_model.bat AXIS LABEL 1>&2
    exit /b 2
)

set OLLAMA_MODELS=F:\_proj\ollama_model
set HF_HOME=F:\_proj\hf_cache
cd /d "%~dp0"
F:\_proj\mt_bench\venv312\Scripts\python.exe mt_bench_runner_single.py "%~1" "%~2" >> "run_single_%~2.log" 2>> "run_single_%~2.err.log"
exit /b %errorlevel%
