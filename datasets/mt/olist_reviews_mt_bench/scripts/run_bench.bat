@echo off
REM x600(GPU 워크스테이션) 전용 실행 스크립트. F:\_proj\mt_bench는 x600 로컬 경로이며
REM 이 datasets 폴더 레이아웃과는 무관하다 - 실행 방법을 그대로 남겨둔 기록용이다.
REM 다른 머신에서 재현하려면 mt_bench_runner.py를 scripts/에서 실행하면 된다
REM (SAMPLE_FILE/OUT_DIR은 이미 ../processed/를 가리키도록 고쳐져 있음).
cd /d F:\_proj\mt_bench
python -X utf8 mt_bench_runner.py > run.log 2> run.err.log
