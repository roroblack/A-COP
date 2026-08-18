# 2026-08-18 — Composer v2 JWT · Response Review Team 산출물 검수

Codex 두 스트림(`S-COMPOSER-V2-JWT`, `S-RESPONSE-REVIEW-TEAM`)이 병렬로 완료한
산출물을 RULE.md §3.6-3 (계약 위반·범위 삭감·근거 오류·수치 불일치 4종 검사)
절차로 검수했다. Composer v2 는 계약·코드·문서·테스트가 일치해 결함을 찾지
못했다. Response Review Team 에서는 실제 운영에 영향을 주는 결함 1건과,
DoD 검증 파이프라인의 갱신 누락 2건을 발견해 고쳤다.

## 1. Response Review Team — 고객 원문에 REV 규칙을 잘못 적용

`app/modules/customer_ops/response_review.py`의 `execute()`가 시작부에서
`task.input_text`(=`case["subject"]`, `controller.py:87`가 그대로 넘기는
**고객의 원문 메시지** — `cases.py:86`의 `subject=request.message`)를
금칙어·PII 정규식으로 먼저 스캔해, 위반이 있으면 GEN(응답 생성) 시도조차
없이 즉시 `escalated` 로 보내는 `preflight` 코드가 있었다.

**문제**: REV 의 4항목(과잉약속·근거인용·PII·톤)은 v8 §8-B 와 `docs/handoff/04`
§3(흐름: GEN 초안 → 결정론 REV → LLM 톤 REV)가 명시하듯 **이 Team 이 생성한
응답**을 검증하는 규칙이다. 고객이 보낸 원문을 검열하는 규칙이 아니다.
그런데 고객 문의에는 본인 확인을 위해 전화번호·이메일을 적는 일이 흔하고,
"절대 안 돼요" 같은 표현도 일상적인 한국어다 — preflight 는 이런 정상적인
고객 메시지를 응답 생성 시도조차 없이 escalate 시켰다. 이 Team 을 실제
Case 흐름에 연결하면(현재는 `accepted_case_types=[]`로 미연결), 고객이
연락처를 적기만 해도 아무 응답도 만들지 않고 무조건 사람에게 넘기는
결과가 됐을 것이다 — Team 의 존재 이유를 무력화하는 결함이다.

재현: `make_task()` 의 `input_text` 는 고정 문자열이라 기존 테스트로는
드러나지 않았다. `case["subject"]`가 실제로 고객 원문임을 `controller.py:87`
과 `cases.py:86`을 대조해 확인한 뒤, `PII_PATTERNS`/`FORBIDDEN_WORDS` 가
`task.input_text` 에 바로 적용되는 코드 경로를 읽어서 확정했다.

**수정**: preflight 블록을 제거했다(`app/modules/customer_ops/response_review.py`).
결정론 REV 는 이제 `_generate()` 가 만든 응답 초안에만 적용된다.
"결정론 검사가 LLM 검사보다 먼저" 라는 v8 §8-B 요구는 톤 LLM 호출 전에
응답 초안의 결정론 검사가 먼저 도는 것으로 여전히 성립한다 — 별도
preflight 가 없어도 무너지지 않는다.

이 결함을 만든 테스트(`test_deterministic_input_rejection_happens_before_llm`,
고객 원문을 검사 대상으로 삼음)를 올바른 대상(생성된 응답 초안)을 검사하는
`test_deterministic_review_runs_before_tone_llm` 으로 교체했다 — 결정론
위반이 있는 **초안**에서 `response.review_tone` 이 호출되지 않는 것을
직접 관측한다.

```powershell
python -m pytest tests/unit/teams/test_response_review_team.py -q
```
```text
8 passed in 2.77s
```

## 2. DoD-29 가 `scripts/verify_dod.py` 에 등록되지 않았다

`CLAUDE.md` 는 "★DoD 는 1 → 29 항목이다(v8 §27)"라고 명시하고
`docs/evidence/DoD-29_ResponseGenerationReview.md` 도 만들어졌지만,
`scripts/verify_dod.py` 의 `ITEMS` 튜플은 여전히 28개뿐이었다 —
`python -m scripts.verify_dod` 를 돌리면 DoD-29 존재 자체가 검증 결과에
안 잡혔다. "건수만 세는 검증은 이 프로젝트에서 두 번 실패했다"(CLAUDE.md)는
바로 이런 갱신 누락을 두고 하는 말이다 — 문서는 29 라고 말하는데 게이트
스크립트는 28 에서 멈춰 있으면, 다음 사람이 `verify_dod` 결과만 보고
"DoD 는 28 개가 전부"라고 오판한다.

**수정**: `ITEMS` 에 `("Response Generation & Review Team", "DoD-29")` 추가.
동시에 `docs/evidence/DoD-29_ResponseGenerationReview.md` 를 다른 evidence
문서(`DoD-22` 등)와 같은 표준 형식(`판정: 통과` 줄 + 판정 근거 표 + 한계
절)으로 다시 썼다 — 원래 파일은 재현 명령과 실제 출력만 있고 `판정:` 줄이
없어서, 항목을 추가해도 스크립트가 "NOT PASS" 로 읽었다.

```powershell
python -m scripts.verify_dod
```
```text
evidence 있음 29/29 · 통과 25 · 부분통과 4 · 미착수 0 · 미작성 0
테스트: 364 passed, 0 skipped, 0 failed
```

## 3. Composer audit 로그가 테스트 실행마다 실제 `var/audit/` 를 오염시켰다

`app/presentation/api/composer.py` 의 `_append_audit()` 가 audit 파일
경로를 `Path(__file__).resolve().parents[3] / "var" / "audit" / "composer_events.jsonl"`
로 하드코딩하고 있었다. `_path()`(구성 선언 경로)는 `app.state.project_config_path`
로 테스트가 주입할 수 있는데, audit 경로는 그런 주입 지점이 없었다 —
그 결과 `tests/e2e/test_composer_write_channel.py` 를 포함해 `pytest` 를
한 번 돌릴 때마다 실제 저장소의 `var/audit/composer_events.jsonl` 에
`test-actor` 가 쓴 가짜 apply 이벤트가 계속 append 됐다(확인: 이 세션에서
몇 차례 테스트를 돌린 것만으로 16줄이 쌓여 있었다). audit 로그는 "누가
언제 무엇을 적용했는지" 를 남기는 것이 목적인데, 매 테스트 실행이 그
기록을 테스트 쓰레기로 채우면 감사 로그로서 가치가 없다.

**수정**:
- `_audit_path(request)` 헬퍼를 추가해 `app.state.composer_audit_path` 로
  주입 가능하게 하고, 기본값은 기존과 동일한 실제 경로로 유지했다.
- `tests/e2e/test_composer_write_channel.py` 의 `_client()` 가 각 테스트의
  임시 `config_dir` 안에 audit 파일을 쓰도록 `app.state.composer_audit_path`
  를 설정한다 — 테스트가 끝나면 `config_dir` fixture 가 통째로 지운다.
- `.gitignore` 에 `var/` 를 추가해, 혹시 남더라도 커밋되지 않게 했다.
- 이번 세션에서 쌓인 테스트 쓰레기 `var/audit/composer_events.jsonl`(16줄,
  전부 `test-actor`/임시 경로) 을 삭제했다 — 실제 운영 apply 기록은 아직
  하나도 없었으므로 손실은 없다.

```powershell
python -m pytest -q --ignore=tests/integration/rag
```
```text
360 passed, 1 deselected in 26.66s
```
테스트 실행 후 `var/` 디렉터리가 다시 생기지 않는 것을 확인했다
(`ls var/` → `No such file or directory`).

## 종합

```powershell
python -m pytest -q --ignore=tests/integration/rag   # 360 passed, 1 deselected (RAG 3건은 네트워크 차단, 무관)
python -m scripts.verify_dod                          # evidence 29/29, 통과 25, 부분통과 4, 미착수 0, 테스트 364 passed
```

Composer v2 JWT 스트림은 결함 없음. Response Review Team 스트림은 preflight
오진 1건(실제 운영 결함) + DoD 게이트 갱신 누락 1건 + audit 테스트 격리
누락 1건, 총 3건을 고쳤다.
