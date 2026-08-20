@echo off
REM x600(GPU 워크스테이션) 전용 실행 스크립트. F:\_proj\mt_bench는 x600 로컬 경로이며
REM 이 datasets 폴더 레이아웃과는 무관하다 - 실행 방법을 그대로 남겨둔 기록용이다.
cd /d F:\_proj\mt_bench
python -X utf8 mt_bench_runner_ko.py > run_ko.log 2> run_ko.err.log
