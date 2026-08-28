# Single-model runner changes

- Added `mt_bench_runner_single.py`, which accepts exactly one axis and one model label, imports the existing registries and backend functions from `mt_bench_runner_extra.py`, preserves per-model JSONL resume behavior, and returns a nonzero exit code for invalid arguments or a backend failure. Each invocation loads at most one model and then exits, so model/CPU/GPU state cannot accumulate across models.
- Added `run_single_model.bat`. It changes to the script directory (important for Task Scheduler), accepts `AXIS` and `LABEL`, appends stdout/stderr to separate per-label logs, and propagates Python's exit code.
- Changed MADLAD-400-10B loading from an impossible 48 GiB CPU allowance to 14 GiB while retaining a 10 GiB GPU ceiling. Added low-CPU-memory loading and disk-backed state-dict offloading during load to reduce transient RAM peaks.

## MADLAD-400-10B recommendation

Keep 8-bit quantization with automatic CPU offload, a 10 GiB GPU limit, and a 14 GiB CPU limit. Plain FP16 is approximately 20 GB for weights alone and is not viable on either 12 GB VRAM or the deliberately reduced system-RAM budget. Run this model by itself, with other GPU/model processes stopped, and never concurrently with another benchmark. The tighter limits favor a clean out-of-memory failure over committing enough memory to drive Windows into paging-file thrash. Even with these safeguards, 10B is close to this machine's practical limit; if it still fails, do not raise the RAM allowance—use a smaller model or a pre-converted 4-bit/8-bit inference backend instead.
