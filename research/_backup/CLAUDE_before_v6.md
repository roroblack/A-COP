# A-COP — 작업 규칙 (도메인)

**A-COP**(AI Customer Operations Platform)는 고객 메시지를 업무 **Case** 로 바꾸고,
현재 상태·정책·이력·피드백 분류를 **Context Pack** 으로 조합하여
**Billing/Subscription** 과 **Technical Entitlement** 업무를 **Agent Team** 이 처리하는
AI 연동형 고객운영 플랫폼이다. 개인 AI(ChatGPT·Claude·Gemini)가 REST/MCP 로 접속한다.

기준선 문서: `../A-COP_구현계획서_v5.md` (**읽기 전용 · 수정 금지**)

## 작업 시작 진입 규칙

**모든 작업은 파일을 변경하기 전에 루트 `RULE.md` 전체를 반드시 읽고 따른다.**
이 문서는 **도메인 안전 원칙**을, `RULE.md` 는 **계획·검증·리포트·분업 절차**를 정한다.
작업 대상과 직접 관련된 `docs/handoff/` 계약도 함께 확인하며,
적용 문서를 확인하지 못하면 변경을 시작하지 않는다.

---

## 0. 가장 중요한 규칙 — 근거 없이 확정하지 않고, 승인 없이 실행하지 않는다

이 서비스는 **"환불됩니다"라고 잘못 말하면 고객이 손해를 보고**,
**승인 없이 결제를 건드리면 되돌릴 수 없다.** 그래서 다른 어떤 규칙보다 이것이 앞선다.

### 0.1 근거(Evidence) 없으면 답하지 않는다
- **정책 근거를 못 대면 확정 답변을 만들지 않는다.** `waiting_input` 또는 `escalated` 가 정답인 경우가 있다.
- 모든 핵심 주장에는 `Evidence`(`source_type` · `source_id` · `observed_at`)가 붙어야 한다.
  근거 없는 문장은 답변에 넣지 않는다.
- RAG 가 죽었을 때 조용히 일반 지식으로 메우지 않는다 →
  `ContextPack.degraded=true` + `omissions` 기록. **신호 없는 축소는 폴백이다**(`RULE.md` §3.2).

### 0.2 side effect 는 제안(proposal)까지만이다
- **Team 은 side effect 를 실행하지 않는다.** `ActionProposal` 만 반환한다.
- 환불·구독 변경·권한 부여는 **Human Approval** 을 거친다. 승인자는 `action:approve` scope 가 있어야 한다.
- **MCP 는 read-only 다.** `open_support_case` 는 Case 생성·분류 시작까지이고,
  결제·환불·구독 변경을 하지 않는다. 쓰기는 REST + 승인 경로로만 간다.
- provider timeout 을 **성공으로 추정하지 않는다.** `unknown` 으로 남기고 자동 재실행하지 않는다.

### 0.3 상태는 한 문으로만 바뀐다
- `customer_cases` 를 직접 `UPDATE` 하지 않는다. **`transition_case()` 만이 진입점이다.**
- `case_events` 는 append-only 다. `UPDATE`/`DELETE` 하지 않는다.
- LangGraph checkpoint 로 **업무 상태를 되돌리지 않는다.** checkpoint 는 실행 snapshot,
  `customer_cases` 는 업무 상태의 권위 있는 projection 이다.

---

## 1. 데이터 원칙

### 지어내지 않는다
값을 모르면 **비워 둔다.** 추정으로 채우면 그 오류가 조용히 고객 답변까지 간다.
채운다면 무엇을 근거로 채웠는지 필드에 남긴다.

```
intent        분류 성공 시에만 채운다. 실패하면 NULL + classification_failed 이벤트
sentiment     동
issue_code    동
degraded      ContextPack 이 축소됐으면 true (숨기지 않는다)
omissions     무엇을 뺐는지 이름으로 남긴다
```

★**분류 실패는 조용히 넘기지 않는다.** v5 §2 — Case 생성 경로에서 감성·의도·이슈 분류가 실패하면
`classification_failed` 를 남기고 `escalated` 로 전환한다. 인라인 분류는 선택 기능이 아니다.

### tenant / customer 격리
모든 query 에 `tenant_id` 와 `customer_id`(또는 `case_id`) 조건을 적용한다.
조건 없는 조회 쿼리는 그 자체가 보안 결함이다 — `tests/security/` 가 검사한다.

### PII 는 저장 시 masking, LLM 에는 masked 만
원문 PII 는 masking 후 저장하고, LLM 에는 masked text 만 전달한다.
audit log 에 **API key 원문·결제 식별자 원문을 기록하지 않는다.**

### 산출물에 버전을 박는다
같은 입력이라도 프롬프트·모델이 바뀌면 결과가 달라진다. 덮어쓰지 않고 공존시킨다.

```
prompts        (prompt_key, version) UNIQUE + sha256 immutable
llm_calls      prompt_id FK 로 어떤 프롬프트가 만든 답인지 추적
eval/reports/  run_id + seed + model + prompt snapshot 을 파일명·메타에 박는다
```

---

## 2. 계약 원칙

- `app/core/contracts.py` 는 `docs/handoff/01_계약_Pydantic.md` 의 **구현체**다. 둘이 어긋나면 결함이다.
- 모든 계약 모델은 `model_config = ConfigDict(extra='forbid')` 를 쓴다. 조용한 필드 유입을 막는다.
- **Core 는 Team 내부를 import 하지 않는다.** `TeamManifest` 와 `execute()` 만 쓴다.
- Team 은 `TeamManifest.allowed_tools` 밖의 tool 을 호출할 수 없다. Registry 가 거부한다.

---

## 3. 코드 원칙

- **오진 위에 수정을 쌓지 않는다.** 하나 고치면 그것만 검증하고 다음으로 간다.
- **조용한 스킵을 만들지 않는다.** `except: continue` 는 실패를 세어 보고해야 한다.
  세지 않으면 분모가 줄어 성공률이 실제보다 좋아 보인다.
- **회귀가 의심되면 옛 커밋을 먼저 실행한다.** 추측보다 빠르다.
- **오진했던 내용을 주석에 남긴다.** 다음 사람이 되풀이하지 않도록.
- 오류 메시지가 사실을 잘못 전하지 않게 한다 (상태 충돌을 "LLM 실패"로 보고하면 한참 헤맨다).
- 가드레일 수치는 `config/guardrails.yaml` 한 곳에만 둔다 (`RULE.md` §3.1).

---

## 4. 검증 원칙

- **백엔드·테스트 통과만으로 "구현 완료"라 하지 않는다.** UI 가 있으면 매 단계 **실제로 열어서** 확인한다.
- **표본이 작으면 작다고 말한다.** golden 60건 × 3회는 **방향성과 불확실성**을 말할 뿐,
  모집단 일반화·장기 drift·실제 손실률·SLA 를 증명하지 않는다(v5 §15-8).
- 평균만 보고하지 않는다. **paired bootstrap 95% CI 와 McNemar** 를 함께 낸다.
- **holdout 20건으로 프롬프트를 고치지 않는다.** 만지는 순간 holdout 이 아니다.
- 중요한 판단은 **Codex 와 교차검증**한다. 반박당하면 실측으로 가린다.
- **동일 요청 10회 → side effect 1회**. idempotency 는 말이 아니라 테스트로 증명한다.

---

## 5. 지금 상태 (2026-08-12)

> ★상태표의 숫자는 **문서가 아니라 디스크·DB 를 세어** 갱신한다.

| 단계 | 상태 |
|---|---|
| 저장소 골격 | **완료** — `RULE.md`·`CLAUDE.md`·`docs/` 9개 폴더. git init(main) |
| 실행계획서 | **완료** — `docs/plans/2026-08-12_1507_A-COP_실행계획서_v1.md` (P0~P10, DoD 18항목 배분) |
| handoff 계약 | **완료** — `docs/handoff/01`~`06` + `_prompts/` |
| 환경 (실측 2026-08-12) | **PostgreSQL 16.14** `127.0.0.1:5433` (conda env `pgv`, 서비스 아님) · `vector`·`pgcrypto` **설치 완료** · **Docker 없음** · Python 3.12.7 · codex CLI 있음 |
| DB 스키마 | **완료** — `acop` DB. **18 테이블**(v5 §8 의 14 + mock 4). UNIQUE 3종·인덱스 3종·extension 2종 **DB 직접 조회로 확인**. 마이그레이션 재실행 안전 |
| seed 데이터 | **완료** — demo customers 10 · subscriptions 10 · payments 30(14일 분포) · entitlements 10 · incidents 3. 시나리오1(해지 후 결제) 2명 · 시나리오2(Pro/Free 불일치) 1명. 테스트 후 `tenants=1`(격리 확인) |
| REST / MCP | **인수** — route 정확히 5개 + `/health`, MCP tool 3개 전부 `mcp:read`. 테스트 **74건**(scope matrix 6종 parametrize · 동일요청 10회→`action_requests` 1행 · 남의 Case→404 · MCP 가 payments/subscriptions 를 안 건드림 · 409 렌더링). ★1차는 `os.getenv` 로 설정을 읽어 **인증 전 요청이 500** 이었다 → [디버그](docs/reports/debugs/2026-08-12_1830_S-API가_실행되지_않는다.md) |
| Core 런타임 | **완료** — 계약(v5 §7 전체)·전이표(21 이벤트/24 전이)·순수 리듀서·`transition_case()` 단일 진입점. **테스트 57건 통과** |
| RAG corpus | ★**v5 재작업 중 — 4회 거부.** v1 보일러플레이트 / v2 중앙유사도 0.460 / v3 **지표 우회**(무작위 토큰 주입) / v4 문체는 맞았으나 **청크 평균 56자**(계약 200~600). 인수 게이트 = `python -m scripts.check_corpus` |
| Context Broker | **완료** — 12,000 토큰 tiktoken **실측** 절삭, 섹션별 예산·제거 순서, `degraded`/`omissions` 강제 |
| RAG 적재·검색 | **완료** — `knowledge_documents` 25 · `knowledge_chunks` **300** · 1536d. 시나리오 질의가 정답 문서를 **1·2위**로 검색(doc_06 0.52 / doc_14 0.41), scope 필터·tenant 격리 동작. ★검색이 한동안 **100% 실패**하고 있었다(`%s::vector` 캐스트 누락) → [디버그](docs/reports/debugs/2026-08-12_2010_RAG검색이_한번도_동작한적이_없다.md) |
| Agent Team | **완료** — Billing/Technical 2종. manifest 계약 일치, LLM 주입 가능, **Core 격리 위반 0**(AST 검사) |
| Feedback Analytics | **완료** — 인라인 분류(실패 시 `classification_failed`+escalated) + 일일 배치. 급증식은 v5 §14-3 그대로 |
| Controller · WAIT/RESUME · Outbox | **완료** — 통합테스트 8종. ★`resuming→completed` 를 상태기계가 런타임 거부해 **진짜 결함을 잡았다** → [디버그](docs/reports/debugs/2026-08-12_2230_Controller가_resuming에서_resumed를_건너뛴다.md) |
| 운영 UI | **완료** — `/ui/{cases,approvals,voc,trace}` 4개 화면 200 확인. VOC 데이터 없을 때 "없음"을 정직하게 표시 |
| 평가 하네스 | **골격 완료** — golden **60** / holdout **20**, runner 3종, judge rubric, bootstrap/McNemar. ★**60건×3회 전량 실행은 미착수**(LLM 비용) |
| **테스트 총계** | **107 passed · skipped 0 · failed 0** (2026-08-12 22:50, 커밋 `cbb75e6`) |
| **M2 게이트** | **도달** — 시나리오 1 `classifying(1)→routing(2)→running(3)→waiting_approval(4)→resuming(5)→running(6)→resolved(7)`, 시나리오 2 `→resolved(4)` |
| Agent Team | 미착수 |
| Feedback Analytics | 미착수 |
| 평가 하네스 | 미착수 — golden 60 + holdout 20 |
| UI | 미착수 |

> ★**Codex 산출물은 두 번 다 검수에서 걸렸다**(범위 삭감 2건). 인수 전 `RULE.md` §3.6-3 4종 검사를 거른 적이 없어야 한다.
> ★**건수만 세는 검증은 이 프로젝트에서 두 번 실패했다.** 코퍼스는 `check_corpus.py`, seed 는 DB 직접 조회로 센다.

### 환경 주의사항

- **PostgreSQL 은 Windows 서비스가 아니다.** conda env `pgv` 에서 뜬 프로세스다.
  재부팅 후 안 떠 있을 수 있다 → `docs/manuals/` 참조.
- **Docker 가 설치돼 있지 않다.** `docker/compose.yml` 로 DB 를 띄우는 v5 §16 전제는
  이 기계에서 성립하지 않는다. 로컬 PG 를 쓰고, compose 파일은 재현용으로만 남긴다.
- OpenAI 임베딩 `text-embedding-3-small` = **1536차원** 으로 v5 DDL `vector(1536)` 과 일치한다.
  모델을 바꾸면 **DDL 과 적재분을 함께** 바꿔야 한다.

---

## 6. 자주 쓰는 명령

```powershell
# DB (conda env pgv 의 psql — PATH 에 없다)
& "$env:USERPROFILE\anaconda3\envs\pgv\Library\bin\psql.exe" -h 127.0.0.1 -p 5433 -U postgres -d acop

# 검증
python -m scripts.verify_dod                  # DoD + evidence 존재 검사
python -m pytest tests/contract -q            # 계약 테스트
python -m pytest tests/security -q            # scope / PII / tenant 격리
python -m pytest -q                           # 전체

# 평가 (v5 §15-7)
python -m eval.runners.proposed --dataset eval/datasets/golden.jsonl --repeats 3 --seed 7
python -m eval.stats.bootstrap --input eval/reports/raw.jsonl --n 10000
python -m eval.stats.mcnemar --input eval/reports/pairs.jsonl
```

---

## 7. 문서

- 프로세스 규칙: `RULE.md` (**작업 전 필독**)
- 기준선 계획: `../A-COP_구현계획서_v5.md` (읽기 전용)
- 실행계획: `docs/plans/`
- 계약: `docs/handoff/`
- 리포트: `docs/reports/` · 결함: `docs/reports/debugs/`
- DoD 검증 로그: `docs/evidence/`
- 결정 기록은 **리포트로 남긴다.** 코드 주석만으로는 "왜"가 사라진다.
