# `mt_bench_runner_extra.py` review

## Fixed

- **MADLAD-400-10B VRAM OOM:** loading roughly 20-21 GB of FP16 weights directly on a 12 GB RTX 4070 SUPER cannot fit. The 10B path now uses 8-bit `bitsandbytes`, `device_map="auto"`, a 10 GiB GPU budget, and CPU overflow/offload. Install recent `transformers`, `accelerate`, and `bitsandbytes` on the remote box. The smaller T5 models remain FP16 on CUDA.
- **T5 generation inputs:** the tokenizer's full `BatchEncoding` is now moved to the embedding device and passed to `generate`, so `attention_mask` is retained. `AutoModelForSeq2SeqLM` is used for all three T5-family checkpoints.
- **Resume correctness:** only nonempty, non-error hypotheses for indices in the current sample count as complete. Foreign/stale indices can no longer make a file look complete; duplicate sample indices fail early; indices are added to the in-memory completed set after each write; transient or empty Ollama responses are no longer written as completed translations.
- **Ollama model identifiers:** four undocumented bare local aliases were replaced with resolvable Hugging Face GGUF tags for MiLMMT-46-12B, MiLMMT-46-4B, Tower-Plus-9B, and GemmaX2-28-2B.
- **CT2 decoding:** decoded NLLB and Marian output now explicitly skips special tokens.
- **CLI validation:** invalid axis values now fail with a usage message instead of silently running `en_ko`.

## Checked and already correct

- CTranslate2's official NLLB example uses tokenizer ID-to-token conversion, `target_prefix=[[tgt_lang]]`, removes the forced first target token with `[1:]`, then converts tokens back to IDs for decoding. The existing NLLB flow follows that convention. `kor_Hang`, `eng_Latn`, and `por_Latn` are valid FLORES-200 codes.
- MADLAD expects a target-language token prepended to each source sentence. `<2ko> ` is the correct Korean-target form.
- The Hugging Face repositories `google/madlad400-10b-mt`, `google/madlad400-3b-mt`, `facebook/nllb-200-3.3B`, `Helsinki-NLP/opus-mt-tc-big-en-ko`, and `seongs/ke-t5-base-aihub-koen-translation-integrated-10m-en-to-ko` exist and match the intended architectures/directions.
- The Ollama request is a valid `POST /api/chat` body: `model`, a `messages` array, `stream: false`, `think: false`, and generation `options` are supported.

## References

- [CTranslate2 Transformers/NLLB example](https://opennmt.net/CTranslate2/guides/transformers.html#nllb)
- [MADLAD-400-3B model card and usage](https://huggingface.co/google/madlad400-3b-mt)
- [MADLAD-400-10B model card](https://huggingface.co/google/madlad400-10b-mt)
- [NLLB-200-3.3B model card](https://huggingface.co/facebook/nllb-200-3.3B)
- [Ollama chat API](https://docs.ollama.com/api/chat)
- [Transformers bitsandbytes guide](https://huggingface.co/docs/transformers/quantization/bitsandbytes)
