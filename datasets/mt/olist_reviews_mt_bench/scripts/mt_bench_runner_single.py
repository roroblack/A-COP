"""Run exactly one extra MT benchmark model in this Python process.

Usage: python mt_bench_runner_single.py <pt_ko|en_ko> <model_label>
"""

import gc
import json
import os
import sys


USAGE = "Usage: python mt_bench_runner_single.py <pt_ko|en_ko> <model_label>"


def _completed_indices(out_path, sample_idx):
    done_idx = set()
    if not os.path.exists(out_path):
        return done_idx

    with open(out_path, encoding="utf-8") as in_f:
        for line in in_f:
            try:
                record = json.loads(line)
                hyp = record.get("hyp_ko")
                if isinstance(hyp, str) and hyp.strip() and not hyp.startswith("[ERROR:"):
                    done_idx.add(record["idx"])
            except (json.JSONDecodeError, KeyError, TypeError):
                # Match the resumable behavior of mt_bench_runner_extra.py:
                # malformed/incomplete records are retried rather than trusted.
                pass
    return done_idx & sample_idx


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in {"pt_ko", "en_ko"}:
        print(USAGE, file=sys.stderr)
        return 2

    axis, label = sys.argv[1:]

    # Import only after validating argv. The existing runner intentionally uses
    # sys.argv[1] to choose its axis-specific globals and model registry.
    import mt_bench_runner_extra as runner

    registry = runner.PT_KO_EXTRA if axis == "pt_ko" else runner.EN_KO
    matches = [model for model in registry if model["label"] == label]
    if not matches:
        available = ", ".join(model["label"] for model in registry)
        print(f"Unknown model label for {axis}: {label}", file=sys.stderr)
        print(f"Available labels: {available}", file=sys.stderr)
        return 2

    model = matches[0]
    rows = runner.load_samples()
    sample_idx = {row["idx"] for row in rows}
    out_path = os.path.join(runner.OUT_DIR, f"{label}.jsonl")
    done_idx = _completed_indices(out_path, sample_idx)

    if sample_idx <= done_idx:
        print(f"[skip] {label} already complete ({len(done_idx)}/{len(rows)})", flush=True)
        return 0

    print(
        f"[run] {label} kind={model['kind']} resume_from={len(done_idx)}/{len(rows)}",
        flush=True,
    )

    try:
        with open(out_path, "a", encoding="utf-8") as out_f:
            if model["kind"] == "ollama":
                runner.run_ollama(model, rows, done_idx, out_f)
            elif model["kind"] == "t5":
                runner.run_t5(model["repo"], model["prefix"], rows, done_idx, out_f)
            elif model["kind"] == "ct2_nllb":
                runner.run_ct2_nllb(model["repo"], model["ct2_dir"], rows, done_idx, out_f)
            elif model["kind"] == "ct2_marian":
                runner.run_ct2_marian(model["repo"], model["ct2_dir"], rows, done_idx, out_f)
            else:
                raise ValueError(f"Unsupported backend kind: {model['kind']}")
    except Exception as exc:
        print(f"[FAIL] {label}: {exc}", file=sys.stderr, flush=True)
        return 1
    finally:
        # The process exits after this one model; this cleanup also helps release
        # resources promptly during normal interpreter shutdown.
        gc.collect()
        torch = sys.modules.get("torch")
        if torch is not None and torch.cuda.is_available():
            torch.cuda.empty_cache()

    print(f"[done] {label}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
