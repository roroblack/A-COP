Reviewed and updated:

- [mt_bench_runner_extra.py](C:/Users/playdata2/Documents/final_workspace/datasets/mt/olist_reviews_mt_bench/scripts/mt_bench_runner_extra.py)
- [Review report](C:/Users/playdata2/Documents/final_workspace/datasets/mt/olist_reviews_mt_bench/scripts/mt_bench_runner_extra_review.md)

Key fixes:

- MADLAD-10B now uses 8-bit loading with CPU offload to fit 12GB VRAM.
- T5 generation passes the complete tokenizer output, including `attention_mask`.
- Resume logic ignores stale, empty, and error records and validates duplicate sample indices.
- Ollama failures are retryable rather than saved as completed translations.
- Four bare Ollama aliases were replaced with full GGUF identifiers.
- CT2 decoding explicitly removes special tokens.
- Invalid translation axes are rejected.

Confirmed as already correct against the [CTranslate2 NLLB example](https://opennmt.net/CTranslate2/guides/transformers.html#nllb), [MADLAD model card](https://huggingface.co/google/madlad400-3b-mt), and [Ollama API](https://docs.ollama.com/api/chat):

- NLLB `target_prefix=[["kor_Hang"]]` and `[1:]` removal
- `eng_Latn`, `por_Latn`, and `kor_Hang`
- MADLAD `<2ko> ` prefix
- Ollama `/api/chat` payload structure

Static compilation and invalid-axis behavior passed. Full inference could not be run locally without the remote models, GPU, and `sample.jsonl`. The remote environment will need recent `bitsandbytes`, `accelerate`, and `transformers`.