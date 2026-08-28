Implemented the isolated single-model runner and conservative MADLAD-10B loading.

Changed files:

- [mt_bench_runner_single.py](C:\Users\playdata2\Documents\final_workspace\datasets\mt\olist_reviews_mt_bench\scripts\mt_bench_runner_single.py:1) — runs exactly one registry model, preserves resumability, and returns nonzero on failure.
- [mt_bench_runner_extra.py](C:\Users\playdata2\Documents\final_workspace\datasets\mt\olist_reviews_mt_bench\scripts\mt_bench_runner_extra.py:126) — limits MADLAD-10B to 10GiB GPU/14GiB CPU and enables low-memory, disk-backed state-dict loading.
- [run_single_model.bat](C:\Users\playdata2\Documents\final_workspace\datasets\mt\olist_reviews_mt_bench\scripts\run_single_model.bat:1) — Task Scheduler-friendly wrapper with separate logs and exit-code propagation.
- [mt_bench_runner_single_report.md](C:\Users\playdata2\Documents\final_workspace\datasets\mt\olist_reviews_mt_bench\scripts\mt_bench_runner_single_report.md:1) — change report and final recommendation.

Usage:

```bat
run_single_model.bat en_ko MADLAD-400-10B
```

Plain FP16 is not viable for MADLAD-10B on this hardware. The implemented 8-bit strategy is safer; if it still fails, do not increase the CPU allowance. Use a smaller model or a pre-converted quantized backend.

Validation passed: both Python files compile, invalid CLI usage exits with code 2, and the batch wrapper propagates code 2. No model was loaded during testing.