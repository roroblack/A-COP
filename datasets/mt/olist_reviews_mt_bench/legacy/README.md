# legacy/

다른 세션이 `scripts/mt_bench_pt_en/`에 정리해뒀던 초기 버전. 원래 `../scripts/`와
같은 파이프라인의 이전 상태이며, 아래 차이 때문에 **참고용으로만** 남겨두고
`../scripts/`가 정본이다.

- 모델 14종 기준 (LMT-60-8B가 아직 "thinking" 필드 버그로 깨져 있던 시점)
- 실제 실행 결과(`results/`)가 없다 — 스크립트만 있고 한 번도 안 돌렸거나
  결과를 안 옮긴 것으로 보인다
- `mt_bench_sample.jsonl`은 있으나 `../processed/sample.jsonl`과 같은 로직
  (`mt_bench_prepare_sample.py`, seed=20260821)으로 만들어져 내용은 동일할 것으로
  추정된다 — 바이트 단위로 재검증하진 않았다
- `debug_test.py`, `debug_test2.py`, `debug_test3.py` — 여기 있는 스크립트 중
  `../scripts/`에는 없는 것들. Ollama API 응답 형식을 확인하던 초기 디버그 코드로 보인다
