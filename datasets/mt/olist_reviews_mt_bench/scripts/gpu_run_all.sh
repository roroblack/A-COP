#!/bin/bash
set -uo pipefail
export HF_HOME=/workspace/mt_bench/hf_cache
cd /workspace/mt_bench
mkdir -p logs

run() {
  script="$1"; axis="$2"; label="$3"
  logfile="logs/${axis}_${label}.log"
  outfile="results_extra_${axis}/${label}.jsonl"
  [ -f "$outfile" ] || outfile="results_broken3_${axis}/${label}.jsonl"
  if [ -f "$outfile" ]; then
    n=$(wc -l < "$outfile" 2>/dev/null || echo 0)
    if [ "$n" -ge 300 ]; then
      echo "[skip] $axis/$label already has $n lines"
      return
    fi
  fi
  echo "=== $(date) running $script $axis $label ==="
  python3 -u "$script" "$axis" "$label" >> "$logfile" 2>&1
  echo "=== $(date) done $script $axis $label (exit $?) ==="
  # Free disk quota: this network volume has a tight quota, so drop the
  # downloaded model weights immediately after we're done with them.
  rm -rf /workspace/mt_bench/hf_cache/hub/models--*
  rm -rf /workspace/mt_bench/ct2_models/*
  df -h /workspace | tail -1
}

# MADLAD-400-10B (both axes) abandoned - ~40GB alone exceeds this volume's quota
run gpu_runner_t5_ct2.py en_ko MADLAD-400-3B
run gpu_runner_t5_ct2.py pt_ko NLLB-200-3.3B
run gpu_runner_t5_ct2.py en_ko seongs-ke-t5-base
run gpu_runner_t5_ct2.py en_ko NLLB-200-3.3B
run gpu_runner_t5_ct2.py en_ko Helsinki-opus-mt-tc-big-en-ko

run gpu_runner_broken3.py pt_en HY-MT1.5-1.8B
run gpu_runner_broken3.py pt_en Seed-X-PPO-7B
run gpu_runner_broken3.py pt_en Seed-X-Instruct-7B
run gpu_runner_broken3.py pt_ko HY-MT1.5-1.8B
run gpu_runner_broken3.py pt_ko Seed-X-PPO-7B
run gpu_runner_broken3.py pt_ko Seed-X-Instruct-7B

echo "ALL DONE $(date)"
