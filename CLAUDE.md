# A-COP — 작업 규칙 (도메인)

**A-COP**(AI Customer Operations Platform)는 고객 메시지를 업무 **Case** 로 바꾸고,
현재 상태·정책·이력·피드백 분류를 **Context Pack** 으로 조합하여
**Billing/Subscription** 과 **Technical Entitlement** 업무를 **Agent Team** 이 처리하는
AI 연동형 고객운영 플랫폼이다. 개인 AI(ChatGPT·Claude·Gemini)가 REST/MCP 로 접속한다.

기준선 문서: `../plan/A-COP_구현계획서_v8.md` (**읽기 전용 · 수정 금지**)
v5·v6·v7 등 이전 버전은 `../plan/archive/`의 보존본이며 수정하지 않는다. ★**DoD 는 1 → 29 항목이다**(v8 §27).

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

★**분류 실패는 조용히 넘기지 않는다.** v6 §3-A — Case 생성 경로에서 감성·의도·이슈 분류가 실패하면
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
  모집단 일반화·장기 drift·실제 손실률·SLA 를 증명하지 않는다(v6 §15-8).
- 평균만 보고하지 않는다. **paired bootstrap 95% CI 와 McNemar** 를 함께 낸다.
- **holdout 20건으로 프롬프트를 고치지 않는다.** 만지는 순간 holdout 이 아니다.
- 중요한 판단은 **Codex 와 교차검증**한다. 반박당하면 실측으로 가린다.
- **동일 요청 10회 → side effect 1회**. idempotency 는 말이 아니라 테스트로 증명한다.

---

## 5. 지금 상태 (2026-08-17)

> ★상태표의 숫자는 **문서가 아니라 디스크·DB 를 세어** 갱신한다.

| 단계 | 상태 |
|---|---|
| 저장소 골격 | **완료** — `RULE.md`·`CLAUDE.md`·`docs/` 9개 폴더. git init(main) |
| 실행계획서 | **완료** — `docs/plans/2026-08-12_1507_A-COP_실행계획서_v1.md` (P0~P10, DoD 18항목 배분) |
| handoff 계약 | **완료** — `docs/handoff/01`~`06` + `_prompts/` |
| 환경 (실측 2026-08-12) | **PostgreSQL 16.14** `127.0.0.1:5433` (conda env `pgv`, 서비스 아님) · `vector`·`pgcrypto` **설치 완료** · **Docker 없음** · Python 3.12.7 · codex CLI 있음 |
| DB 스키마 | **완료** — `acop` DB. **18 테이블**(v6 §22 의 14 + mock 4). UNIQUE 3종·인덱스 3종·extension 2종 **DB 직접 조회로 확인**. 마이그레이션 재실행 안전 |
| seed 데이터 | **완료** — demo customers 10 · subscriptions 10 · payments 30(14일 분포) · entitlements 10 · incidents 3. 시나리오1(해지 후 결제) 2명 · 시나리오2(Pro/Free 불일치) 1명. 테스트 후 `tenants=1`(격리 확인) |
| REST / MCP | **인수** — route **6개**(2026-08-17: `/v1/outbox/{message_id}/resolve` 추가) + `/health`, MCP tool 3개 전부 `mcp:read`. 테스트 **74건**(scope matrix 6종 parametrize · 동일요청 10회→`action_requests` 1행 · 남의 Case→404 · MCP 가 payments/subscriptions 를 안 건드림 · 409 렌더링). ★1차는 `os.getenv` 로 설정을 읽어 **인증 전 요청이 500** 이었다 → [디버그](docs/reports/debugs/2026-08-12_1830_S-API가_실행되지_않는다.md) |
| Core 런타임 | **완료** — 계약(v6 §21 전체)·전이표(21 이벤트/24 전이)·순수 리듀서·`transition_case()` 단일 진입점. **테스트 57건 통과** |
| RAG corpus | ★**v5 재작업 중 — 4회 거부.** v1 보일러플레이트 / v2 중앙유사도 0.460 / v3 **지표 우회**(무작위 토큰 주입) / v4 문체는 맞았으나 **청크 평균 56자**(계약 200~600). 인수 게이트 = `python -m scripts.check_corpus` |
| Context Broker | **완료** — 12,000 토큰 tiktoken **실측** 절삭, 섹션별 예산·제거 순서, `degraded`/`omissions` 강제 |
| RAG 적재·검색 | **완료** — `knowledge_documents` 25 · `knowledge_chunks` **300** · 1536d. 시나리오 질의가 정답 문서를 **1·2위**로 검색(doc_06 0.52 / doc_14 0.41), scope 필터·tenant 격리 동작. ★검색이 한동안 **100% 실패**하고 있었다(`%s::vector` 캐스트 누락) → [디버그](docs/reports/debugs/2026-08-12_2010_RAG검색이_한번도_동작한적이_없다.md) |
| Agent Team | **완료** — Billing/Technical 2종. manifest 계약 일치, LLM 주입 가능, **Core 격리 위반 0**(AST 검사) |
| Feedback Analytics | **완료** — 인라인 분류(실패 시 `classification_failed`+escalated) + 일일 배치. 급증식은 v6 §7-A 그대로 |
| Controller · WAIT/RESUME · Outbox | **완료** — 통합테스트 8종. ★`resuming→completed` 를 상태기계가 런타임 거부해 **진짜 결함을 잡았다** → [디버그](docs/reports/debugs/2026-08-12_2230_Controller가_resuming에서_resumed를_건너뛴다.md) |
| 운영 UI | **완료** — `/ui/{cases,approvals,voc,trace}` 4개 화면 200 확인. VOC 데이터 없을 때 "없음"을 정직하게 표시 |
| 평가 하네스 | **완료** — golden **60** / holdout **20**(보존), runner 3종, judge rubric, bootstrap/McNemar |
| A2A / Graph (신계획서) | **완료** — `TeamExecutorPort`·`LocalTeamExecutor`·`A2ATeamExecutor`·Agent Card·`GraphStorePort`·`SqlGraphAdapter`(재귀 CTE) **7/7**. Controller 가 Port 경유(`LOCAL`↔`A2A` 교체점) |
| 모듈화 · Composer GUI | **완료** — `config/project.yaml` 이 조립의 단일 입력. 모듈 7 / 컴포넌트 9 / Port 6 (`docs/handoff/08`). `/ui/composer` 는 `composer_ui` 토글로 404↔200. ★GUI 자신도 끌 수 있다 |
| 평가 실행 | **완료** — 3군 × 180행 = **540 관측.** A 0/180 · B 6/180 · **Proposed 40/180**, grounding 0.00 / 2.22 / **3.98**. ★결함 5건을 벗겨낸 뒤의 수치다(DoD-15) |
| ablation | **완료** — 5종. ★RAG·Context Broker 제거 시 grounding **3.98→0.00**, 총점 13→5, degraded 60/60. 나머지 3종은 **이 지표로 차이 미관측** — "효과 없음"이 아니라 **지표가 재지 않는 것**이다(DoD-15) |
| judge 검증 | **부분** — 540행 전량에서 **근거 없이 grounding 점수를 받은 행 0건**(`eval/check_judge.py`, 0 아니면 exit 1). ★**사람 라벨 20건은 여전히 미측정** — 기계 검사는 agreement 를 대신하지 못한다 |
| 발표 시나리오 seed | **완료** — `scripts/seed_demo_cases.py`. case_id 를 `uuid5` 로 고정해 재실행해도 URL 이 안 죽는다. 시나리오1 은 `waiting_approval` 에서 멈춰 둔다(발표에서 사람이 누른다) |
| 운영 UI 품질 | **완료** — 디자인 시스템(`app/presentation/ui/theme.py`), 상태별 의미색·다크모드·375px 가로밀림 0. ★JSON 덤프를 표·분포로. `unknown` 은 가장 센 위험색(돈이 나갔는지 모르는 상태) |
| Composer GUI | **완료** — 모듈·Port·Team 추가/제거 · **컴포넌트 9 는 잠김**. 실행 순서 구조도가 **현재 선언을 따라간다**. 계약 `docs/handoff/09` |
| ★**개발 콘솔 분리** | **완료** (2026-08-17) — 조립 조회·DoD·평가 대시보드(`/ui/`·`/ui/quality`·`/ui/experiments`·`/ui/runs`·`/ui/admin`, `app/console/**`)를 **전부 지웠다.** 별도 프로그램 `final_project_ui` 가 read-only 로 그 역할을 한다. basement 에 남긴 건 `GET /introspection`(scope `ops:introspect`) 하나뿐 — 조립 상태를 JSON 으로 낸다. 계약 `docs/handoff/11`·`12` |
| ★**Composer 쓰기 채널** | **완료** (2026-08-17) — `/ui/composer` HTML 폼은 `composer_ui` 토글로 릴리스 때 끈다. **그 다음엔 어떻게 쓰나** 라는 질문의 답: `POST /composer/validate`·`/composer/apply`(scope `composer:write`)를 **토글과 무관하게 항상 등록**해 뒀다. `composer_service.py` 가 검증·원자적 쓰기(`os.replace`)·`base_revision` 낙관적 동시성(불일치 시 `409 revision_conflict`)의 유일한 통로 — HTML 폼도 이제 이걸 부른다(예전엔 폼이 직접 파일 I/O 를 해서 고정 임시 파일명 충돌·revision 미확인 결함이 있었다). Codex 교차검증 `docs/reports/2026-08-17_S-COMPOSER-WRITE-CHANNEL_검토.md`, 계약 `docs/handoff/13` |
| 개발 서버 | **완료** — `.claude/launch.json` 의 `acop-ui`(`--reload`). `/` → `/ops/cases` 307 |
| 릴리스 체크리스트 | **완료** — `docs/release_checklist.md`. ★판정은 **RC 아님** |
| ★**할루시네이션 방어** (v7 §9-E) | **완료** — 제안의 식별자·금액을 **DB 와 대조**해 실행 전 차단. 검증 2회(제안 시점 + 승인 직전). 거부 시 `escalated` + 실패필드·**hash** 감사. `app/core/verification.py`(순수) + `proposal_guard.py`(재조회) |
| VOC Team | **완료** (v7 §0 변경 4) — `FeedbackAnalyticsTeam` 이 `run_daily_feedback()` 을 감싼다. `accepted_case_types=[]` 로 Controller 라우팅 격리. `scripts/run_daily_feedback.py` 는 Team 을 거치되 CLI 출력 계약은 그대로(DoD-10) |
| **테스트 총계** | **334 passed · skipped 0 · failed 0** (2026-08-17. -m "not live" 로 실 LLM 1건 기본 제외) |
| ★**Docker · AWS 배포 모듈화** | **1단계 완료, 2단계는 초안(가정 명시, 확정 아님)** (둘 다 Codex, 2026-08-17). 1단계: `Dockerfile` + `docker/compose.yml`(conda `pgv` 경로 병행, 대체 아님) + 배포 계약 `docs/handoff/14`. 2단계: `infra/aws/`(Terraform 골격 — ECS Fargate·RDS+pgvector·Secrets Manager 가정) + `.github/workflows/deploy.yml`. ★이 기계엔 Docker·Terraform 둘 다 미설치라 build/run/validate/apply 전부 미검증 — 문법·정적 확인만 했다. AWS 컴퓨트·매니지드 서비스 교체·비밀 관리·CI/CD 는 **가정일 뿐 사용자 확답 전** — 확답 오면 `infra/aws/`만 갱신, 계획 `docs/plans/2026-08-17_Docker_AWS_배포_모듈화_계획.md` §2 |
| **DoD (v8 §27, 1~28항목 평가됨)** | **evidence 28/28 · 통과 24 · 부분통과 4 · 미착수 0** (`python -m scripts.verify_dod` 재실행 2026-08-17 확인 — 이전 판 "통과 21·미착수 1"은 갱신 누락이었다. 21·26·27은 이미 통과로 넘어가 있었다). 남은 4건 = **15·17**(둘 다 같은 차단항목 — 사람 라벨 20건 대비 judge agreement 미측정. ★도구는 준비됨: `eval/label_holdout_template.py` + `eval/stats/agreement.py`(exact-match+Cohen's kappa), 이 저장소 유일한 사람이 `eval/reports/holdout_human_labels_template.jsonl` 20건을 채워야 판정이 바뀐다 — 라벨 값은 지어내지 않았다) · **23**(consumer idempotency, 대상 1종뿐 — ★게이트 추가함 `tests/architecture/test_consumer_idempotency_gate.py`, 새 consumer 가 테스트 없이 늘면 즉시 실패. 판정 자체는 여전히 부분통과, consumer 가 하나뿐이라는 사실은 안 바뀜) · **28**(방어지표 5종은 완료, 파인튜닝 자체는 미착수). **29번(Response Generation & Review 검증)은 v8에서 신설된 항목으로 이 구현에서는 아직 평가되지 않았다.** |
| **M1·M2·M3 게이트** | **전부 도달**. ★단 **RC 는 아니다** — judge 가 사람과 얼마나 맞는지 모르는 상태로 내보낼 수 없다 |

> ★**Codex 산출물은 두 번 다 검수에서 걸렸다**(범위 삭감 2건). 인수 전 `RULE.md` §3.6-3 4종 검사를 거른 적이 없어야 한다.
> ★**건수만 세는 검증은 이 프로젝트에서 두 번 실패했다.** 코퍼스는 `check_corpus.py`, seed 는 DB 직접 조회로 센다.

### 임시 파일은 한 곳에만 만든다

★**상위 폴더(`final_workspace/`)에 `.tmp_*` 를 흩뿌리지 않는다.**
문서 렌더링·변환 중간산출물이 `.tmp_jh_render`·`.tmp_lo_profile` 처럼 쌓여
작업 폴더가 어질러진 적이 있다(2026-08-16 정리).

```
final_workspace/.tmp/        ← 변환·렌더링 등 워크스페이스 임시물은 전부 여기
```

저장소 안에서 쓰는 스크래치는 저장소 밖 세션 임시 폴더를 쓰고,
**저장소에 커밋되지 않게** 한다. 남기고 싶은 산출물이면 `docs/` 아래 제자리에 둔다.

### 환경 주의사항

- **PostgreSQL 은 Windows 서비스가 아니다.** conda env `pgv` 에서 뜬 프로세스다.
  재부팅 후 안 떠 있을 수 있다 → `docs/manuals/` 참조.
- **Docker 가 설치돼 있지 않다.** `docker/compose.yml` 로 DB 를 띄우는 v6 §13 전제는
  이 기계에서 성립하지 않는다. 로컬 PG 를 쓰고, compose 파일은 재현용으로만 남긴다.
- OpenAI 임베딩 `text-embedding-3-small` = **1536차원** 으로 v6 §22 DDL `vector(1536)` 과 일치한다.
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

# 평가 (v6 §15-7)
python -m eval.runners.proposed --dataset eval/datasets/golden.jsonl --repeats 3 --seed 7
python -m eval.stats.bootstrap --input eval/reports/raw.jsonl --n 10000
python -m eval.stats.mcnemar --input eval/reports/pairs.jsonl
```

---

## 7. 문서

- 프로세스 규칙: `RULE.md` (**작업 전 필독**)
- 기준선 계획: `../plan/A-COP_구현계획서_v8.md` (읽기 전용, v6은 `../plan/archive/`의 보존본)
- 실행계획: `docs/plans/`
- 계약: `docs/handoff/`
- 리포트: `docs/reports/` · 결함: `docs/reports/debugs/`
- DoD 검증 로그: `docs/evidence/`
- 결정 기록은 **리포트로 남긴다.** 코드 주석만으로는 "왜"가 사라진다.
