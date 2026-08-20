# bab2min/corpus 네이버쇼핑 리뷰 전처리 리포트 (x600, 2026-08-20)

## 실행 환경 메모

원래 계획은 Codex(x600, gpt-5.6-luna)에게 이 작업 전체를 맡기는 것이었다. 시도 순서:

1. 1차 시도: `--skip-git-repo-check` 누락으로 codex가 시작부터 거부.
2. 2차 시도(플래그 추가): x600의 codex CLI가 0.135.0으로 구버전이라
   `gpt-5.6-luna` 모델을 인식 못 함(`requires a newer version of Codex`) — 실패를
   정직하게 보고하고 아무 파일도 안 건드림. `npm install -g @openai/codex@latest`로
   0.148.0으로 업데이트.
3. 3차 시도(업데이트 후): 라이선스 확인(`Public Domain` 웹검색으로 재확인)까지는
   스스로 해냈으나, 이후 모든 로컬 명령 실행이 `Failed to create unified exec
   process: timed out after 15000ms connecting runner pipe-in` 로 반복 실패 —
   Windows에서 sshd가 비대화형(서비스) 세션으로 도는 환경이라 codex의 샌드박스
   실행기가 파이프를 못 여는 것으로 보인다(권한/데스크톱 세션 문제로 추정,
   원인 확정은 안 함). `-s danger-full-access`로 우회하는 건 Claude Code 쪽
   안전 정책에서 차단됨 — 임의로 뚫지 않았다.

★결론: 이번 작업은 Codex 위임이 아니라 **Claude가 SSH로 직접** 실행했다.
git clone과 전처리 자체는 공개 저장소 읽기 + 로컬 텍스트 변환뿐이라 위험도가
낮다고 판단해 진행했다. codex CLI는 0.148.0으로 x600에 남아있으니, 이 환경
문제(파이프 타임아웃)를 팀이 따로 조사하면 다음부터는 다시 위임 가능하다.

## 0. 라이선스 확인

`https://github.com/bab2min/corpus` README 라이선스 섹션: **"Public Domain"**
(Claude가 이전 턴에서 WebFetch로 직접 확인, 이번 실행에서 Codex도 독립적으로
같은 결론에 도달함 — 2회 교차 확인).

## 1. 원본

- `git clone --depth 1 https://github.com/bab2min/corpus`
- `corpus/sentiment/naver_shopping.txt` — tab-separated, 1열=별점, 2열=리뷰 텍스트.
  가정과 실제 포맷 일치.
- 원본 크기: 20,823,547 bytes, 총 200,000행.

## 2. 전처리 결과

스크립트: `preprocess_naver_shopping.py` (원문 그대로 옮기며 중복/별점3/빈텍스트만
제외 — 번역·요약 없음)

| 항목 | 값 |
|---|---|
| 원본 총 행 수 | 200,000 |
| 포맷 이상(malformed) | 0 |
| 별점3 제외 | 0 (★원본 자체가 이미 1·2·4·5로만 구성돼 있었다 — bab2min이 수집 단계에서 3점을 뺀 것으로 보인다) |
| 빈 텍스트 제외 | 0 |
| 중복 텍스트 제외 | 92 |
| **최종 출력 행 수** | **199,908** |
| 산술 검산 (200000 = 0+0+0+92+199908) | **일치** |

## 3. 검증 (별도 스크립트 `verify_naver_shopping.py` 실행, 자기검증 아님)

```
python verify_naver_shopping.py
```
```json
{
  "line_count": 199908,
  "invalid_json": 0,
  "missing_keys": 0,
  "label_rating_mismatch": 0,
  "label_distribution": { "positive": 99953, "negative": 99955 },
  "rating_distribution": { "1": 36007, "2": 63948, "4": 18783, "5": 81170 },
  "all_checks_passed": true
}
```

- JSONL 199,908줄 전수 파싱 성공, 필수 키(rating/label/text) 결측 0건,
  label↔rating 불일치 0건.
- label 분포가 positive 99,953 : negative 99,955로 **거의 정확히 50:50** —
  bab2min이 애초에 균형 데이터로 수집한 것으로 보인다(참고: VOC 실사용
  데이터는 이렇게 균형잡혀 있지 않을 가능성이 높다 — 학습/평가 시 클래스
  불균형 보정이 필요할 수 있음을 유의).

## 4. 산출물 위치 (x600)

- `C:\Users\Yeon\acop_voc_corpus\output\naver_shopping_sentiment.jsonl` (199,908줄, 약 29.6MB)
- `C:\Users\Yeon\acop_voc_corpus\output\preprocess_stats.json`
- `C:\Users\Yeon\acop_voc_corpus\preprocess_naver_shopping.py`
- `C:\Users\Yeon\acop_voc_corpus\verify_naver_shopping.py`
- `C:\Users\Yeon\acop_voc_corpus\corpus\` — 원본 클론(읽기 전용으로 유지, 수정 안 함)

## 5. 하지 않은 것

- `final_project_cs`/`final_project_sample`/`program/` 등 어떤 프로젝트 저장소도
  건드리지 않았다 — x600의 독립 작업공간 안에서만 작업했다.
- git push, 원격 저장소 쓰기 없음.
- 텍스트 번역·요약·가공 없음 — 원문 그대로 옮겼다.
