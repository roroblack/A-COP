# 구현 계획서
## A-COP: AI 연동형 모듈형 에이전틱 고객운영 플랫폼
### (부트캠프 주제 대응: 다중 에이전트 서빙 기반 고객 피드백 분석 및 맞춤형 응대 자동화 시스템)

---

## 0. 한 줄 요약
본 프로젝트는 고객 피드백을 Customer Case로 관리하고, 업무별 Agent Team Module이 Shared State·RAG·Memory를 기반으로 협업하는 모듈형 Agentic Customer Operations Platform을 구축한다.

사용자의 Personal AI는 REST/MCP를 통해 우리 Tool과 Resource를 사용할 수 있고, 독립적으로 배포된 Agent System은 A2A를 통해 업무 Task를 위임받을 수 있다. Context Broker는 Vector RAG와 Graph 관계 탐색을 결합해 관련 문서뿐 아니라 Case·Issue·Policy·Agent Team·Action 사이의 연결 근거까지 Context Pack에 포함한다.

PostgreSQL은 Case/Action 상태와 Transaction의 Source of Truth로 유지하고, Graph Store는 관계 탐색용 파생 Projection으로 사용한다.

---

## 1. 프로젝트명 정리

### 1-1. 짧게 부를 이름
- **A-COP**
- 풀네임: **AI 연동형 모듈형 에이전틱 고객운영 플랫폼**

### 1-2. 부트캠프 주제와의 연결 문장
- 본 프로젝트는 *다중 에이전트 서빙 기반 고객 피드백 분석 및 맞춤형 응대 자동화 시스템* 주제를 기반으로,
  **고객 피드백 분석 → 고객 Case 생성 → 전문 Agent Team 협업 → 맞춤형 응대 및 후속 처리**까지 확장한 구조이다.

---

## 2. 문제 정의

기존 고객지원 자동화 시스템은 대체로 다음 형태에 머무른다.

1. 고객 문의 수집
2. 감성/의도/이슈 분류
3. 관련 문서 검색(RAG)
4. 답변 생성
5. 답변 검수

이 구조는 일정 수준의 자동응대는 가능하지만, 다음과 같은 한계가 있다.

- **고정 파이프라인 한계**: 실제 고객 문제는 결제, 계정, 기술지원, 정책 등 여러 업무에 걸칠 수 있다.
- **상태 기반 처리 부족**: 고객 문제는 단일 답변으로 끝나지 않고, 확인 요청·재처리·보류·승인 등 상태 변화가 필요하다.
- **멀티에이전트 필요성 부족**: 단순히 단계별 LLM 호출에 Agent 이름만 붙이면 멀티에이전트의 당위성이 약하다.
- **외부 AI 연동 부재**: 사용자는 이미 ChatGPT, Claude, Gemini 같은 개인 AI를 사용하고 있으며, 우리 서비스는 사람 UI만 제공하는 구조가 일반적이다.

---

## 3. 프로젝트 목표

### 핵심 목표
1. 고객 피드백을 분석하여 **Customer Case**를 생성한다.
2. 고객 문제의 성격에 따라 **전문 Agent Team**에 동적으로 배정한다.
3. Agent Team은 **기업 지식(RAG)**, **과거 처리 이력(Memory)**, **실시간 상태(Shared State)** 를 바탕으로 협업한다.
4. 단순 응답 생성이 아니라 **조회 → 판단 → 후속 작업 요청 → 응답/에스컬레이션**까지 처리한다.
5. 사용자가 자기 개인 AI를 통해 접근할 수 있도록 **Agent API / MCP 인터페이스**를 제공한다.
6. 전체 시스템을 **모듈화된 Basement 구조**로 설계하여 향후 다른 도메인에도 재사용 가능하게 한다.

---

## 4. 핵심 아이디어

### 4-1. 기존 방식
고객 문의 → 분석 → 검색 → 답변 → 검수

### 4-2. 제안 방식
고객 문의 → **Case 생성** → **Context 구성** → **전문 Agent Team 협업** → **공유 상태 갱신** → **재계획 / 승인 / 응답**

### 4-3. 상위 개념
- **Basement(Core)**: Agent, Tool, State, Memory, RAG, Workflow를 공통 실행 기반으로 제공
- **Domain Module**: Customer Operations 도메인 로직 구현
- **External AI Access**: 개인 AI가 우리 Agent API / MCP를 통해 서비스 접근

---

## 5. 시스템 범위

### In Scope
- 고객 피드백 수집 및 정규화
- 감성 분석 / 의도 분류 / 이슈 분류
- Customer Case 생성 및 상태 관리
- 요구사항 분석을 통해 확정되는 업무 책임 단위 Agent Team Module
- 기업 지식 RAG
- 과거 처리 이력 기반 Memory
- Shared State 및 Agent 협업
- Human Approval(일부 작업)
- 외부 AI Agent용 API / MCP 인터페이스
- 웹 대시보드(운영자용)

### Out of Scope
- OCR / 이미지 판독 / 영상 분석
- 실제 복잡한 물류·택배 사진 판정
- 다수 도메인 완전 지원
- Production-scale 분산 시스템
- 모든 외부 AI 플랫폼별 정식 배포

---

## 6. 타깃 도메인(권장)
범위를 안정적으로 통제하기 위해 **가상의 SaaS 서비스 고객운영 시나리오**를 1차 도메인으로 권장한다.

### 예시 이슈
- 구독 해지 후 추가 결제
- Free/Pro 권한 동기화 오류
- Seat 수와 요금 불일치
- 환불 요청 가능 여부
- 반복되는 장애/불만 피드백 탐지

이 도메인은 OCR/이미지 없이 **DB/API/텍스트 정책만으로 정답과 상태를 구성**할 수 있다.

---

## 7. Agent Team Module 구성 원칙

Agent Team의 이름과 개수는 미리 고정하지 않는다.  
먼저 고객지원 업무를 Capability 단위로 분석한 뒤, 서로 다른 책임·권한·지식·Tool을 가져야 할 업무를 독립 Team Module로 정의한다.

### 7-1. Team Module 공통 원칙
- 각 Team은 하나의 독립 업무 목표(Capability)를 가진다.
- Team 내부 Agent 수는 고정하지 않는다.
- Team 내부에서 LangGraph/Subgraph를 사용할 수도 있고 사용하지 않을 수도 있다.
- Team별 RAG/Memory/Tool/Prompt 정책을 독립적으로 구성할 수 있다.
- Core는 Team 내부 구현을 모르고 Team Contract의 입력/출력만 사용한다.

### 7-2. 가능한 Team 예시
아래는 최종 확정 팀이 아니라 업무 분리 예시다.
- 구독/결제 문제 처리 Team
- 계정/권한/기술지원 Team
- 고객 피드백/VOC 분석 Team
- Complaint / Retention / Fraud Review 등 추가 Team

### 7-3. Agentic Controller
- 역할: Case 분배, 상태 전이, WAIT/RESUME, 재처리, 승인 요청, Agent Team 결과 통합
- 주요 입력: Shared State, classification/capability result, TeamResult
- 주요 출력: assignment, replan, next action, end/wait decision

---

## 8. Basement(Core) 설계

### 8-1. Agent Gateway
외부 사용자/Personal AI 요청이 내부 시스템으로 들어오는 **Trust Boundary**이다.
- OAuth Access Token 검증
- user/client 식별
- Scope 검사
- 요청 위험도 확인
- 승인된 요청만 Customer Case Layer로 전달

### 8-2. Customer Case Layer
한 번의 메시지를 장기 실행 가능한 **업무 Case**로 변환한다.
- case_id
- 현재 status / owner
- event/history
- approval state
- resume/checkpoint
- version

### 8-3. Agent Team Registry / Team Contract
Capability에 맞는 Team Module을 탐색하고 교체 가능성을 보장한다.
- Team Registry: team_id, capabilities, version, 활성 상태, scope 관리
- Team Contract: 표준 입력/출력 규칙
- Core는 Team 내부 구현을 직접 알지 않는다.

### 8-4. Context Broker
Agent가 판단하는 데 필요한 Context를 **선택·조합·정규화·압축**해 Context Pack으로 제공한다.
- RAG / Knowledge
- DB Current State
- Case History
- Memory
- Team별 Knowledge Scope

### 8-5. Message Broker
Message Broker의 사용과 Task/Event 설계는 **Coordination 계층의 책임**이다. Message Broker의 실제 구현은 **Infrastructure 계층의 책임**이다.

Agentic Controller가 어느 Team에 무엇을 보낼지 결정한다. Broker는 판단하지 않고 전달만 한다.
Controller는 `redis.xadd(...)`를 직접 호출하지 않는다. `message_bus.publish(task)`를 호출한다.
구현은 `InMemoryMessageBus` / `RedisMessageBus` / `RabbitMQMessageBus` 중 하나를 Adapter로 꽂는다.

| 계층 | 책임 |
|---|---|
| Application/Coordination | Agentic Controller, Top-Level LangGraph, Routing, Replan, WAIT/RESUME, Task/Event Contract, MessageBus Port |
| Infrastructure | Redis / Redis Streams / RabbitMQ Adapter |

Message Broker는 Agent Team 전용 부속이 아니라 Coordination이 사용하는 컴포넌트다.

### 8-6. Shared State
여러 Team이 같은 Customer Case를 이어서 처리하기 위한 **공식 단일 상태**이다.
- evidence
- decisions
- open_tasks
- owner
- status
- version
- approval state

Team별 Episodic Memory와 다르다.  
Shared State는 “현재 Case의 공식 상태”, Memory는 “과거 경험/지식”이다.

### 8-7. Tool / Action Layer
Agent가 DB나 외부 시스템을 직접 수정하지 않고 **Business Capability API**를 통해 작업하도록 통제한다.
- Tool 권한/Scope
- Idempotency
- Human Approval 여부
- Audit Log
- 실제 외부 side effect 실행

### 8-8. Agentic Controller / Orchestration
- Capability 기반 Team routing
- WAIT / RESUME
- Replan / Retry
- Human Approval
- 다른 Team handoff
- 완료/종료 판단

Top-Level LangGraph는 이 계층에 위치하며, 각 Agent Team은 별도의 Subgraph를 가질 수 있다.

---

## 8-A. Message Broker와 Context Broker 분리

### Message Broker
Coordination 계층이 정의한 Task와 Event를 내부 Worker에게 전달한다.

- Controller: `message_bus.publish(task)` 호출
- MessageBus Port: 전달 계약 제공
- Adapter: InMemoryMessageBus / RedisMessageBus / RabbitMQMessageBus 구현
- Broker: Queue, Retry, Event 전달을 수행하며 Team 선택이나 실행 순서를 판단하지 않음

MVP에서는 In-Process Queue로 시작할 수 있다. 이후 Redis Streams 또는 RabbitMQ Adapter로 교체한다.

### Context Broker
Agent가 판단할 때 필요한 **정보를 선택·조합·압축하여 Context Pack으로 제공**한다.

주요 책임:
- RAG 검색
- DB 상태 조회
- 현재 Case 상태
- 과거 유사 처리 Memory
- Agent별 Knowledge Scope 적용
- Context 최소화

즉:
- Message Broker = **업무/이벤트를 운반**
- Context Broker = **판단에 필요한 정보를 구성**

둘을 하나의 컴포넌트로 합치지 않는다.

### 8-A-1. 계층 경계

```text
Application / Coordination
  Agentic Controller · Top-Level LangGraph · Routing · Replan · WAIT/RESUME
  Task/Event Contract · MessageBus Port
              │
              ▼
Infrastructure
  InMemoryMessageBus · Redis/Redis Streams Adapter · RabbitMQ Adapter
```

Controller는 `redis.xadd(...)` 같은 구현 세부사항을 알지 않는다.

---

## 8-B. Agent Team 플러그인/모듈화 계획

모든 Agent Team은 시스템에 하드코딩되는 고정 팀이 아니라 **등록형 Team Module**로 구성한다.

Core는 각 Agent Team의 내부 구현에 의존하지 않고 다음 공통 Contract만 사용한다.

```text
AgentTeam
├ team_id
├ capabilities[]
├ accepted_case_types[]
├ required_context[]
├ allowed_tools[]
├ knowledge_scope[]
├ input_schema
├ output_schema
└ execute(case_context) -> TeamResult
```

### Agent Team Registry
- 등록된 Team Module 목록 관리
- Capability 기반 Team 탐색
- Team Version 관리
- 활성/비활성 관리
- Agentic Controller가 Case에 맞는 Team을 동적으로 선택

### Team 내부 자유도
각 Team은 다음을 독립적으로 결정할 수 있다.
- Single-Agent / Multi-Agent
- 자체 LangGraph/Subgraph
- 자체 Prompt
- Tool 조합
- Knowledge Scope
- Retrieval / Rerank 전략
- Episodic Memory 정책
- Rule/ML/LLM 혼합

### Platform과 Team의 경계
Platform은 Team별 업무 로직을 대신 만들지 않는다.

**Platform 공통 제공**
- Team Contract / Registry
- Case / Shared State
- Tool 권한 경계
- Vector/Search/Memory Store Port
- 기본 Adapter
- Auth / Audit / Observability

**각 Agent Team 소유**
- 어떤 문서를 검색할지
- 검색/Rerank 전략
- 무엇을 Memory에 저장할지
- 내부 Agent/Graph 구성
- Tool 호출 정책
- TeamResult 생성 규칙

즉, Team을 완전히 독립 서비스처럼 방치하는 것이 아니라  
공통 보안·상태·관측·저장 기반의 중복 구현은 제거하면서 업무 로직의 독립성은 유지한다.

### 권장 구조
```text
app/
├ core/
│  ├ contracts/
│  ├ registry/
│  ├ state/
│  ├ orchestration/
│  ├ context/
│  ├ messaging/
│  └ tools/
└ modules/
   └ customer_ops/
      └ team_modules/
         ├ team_a/
         │  ├ graph/
         │  ├ agents/
         │  ├ tools/
         │  ├ retrieval/
         │  ├ memory/
         │  └ prompts/
         └ team_b/
```

---

## 8-C. Agent/Team 경합과 동시성 처리 책임

Coordination은 Agent/Team 간 실행 경합을 조정하고, Shared State와 Tool Layer는 그 조정이 실패하거나 동시에 요청이 들어와도 상태와 실제 Action의 일관성이 깨지지 않도록 보장한다.

| 경합 종류 | 담당 |
|---|---|
| Team A vs Team B 실행 충돌 | Coordination |
| 동일 Case의 ownership / scheduling | Coordination |
| Message 중복 / retry / delivery | Coordination 정책 + Message Broker |
| Team 내부 Agent A vs Agent B | 각 Agent Team 내부 |
| 같은 Shared State 동시 수정 | State Repository / DB (version, CAS) |
| 같은 Action 중복 실행 | Tool / Action Layer (idempotency key) |
| DB 레코드 동시 변경 | Transaction / CAS / Lock |
| 여러 Team 결과 병합 | Coordination |

Team 내부 Agent 간 경합은 Top-Level Controller가 관리하지 않는다. Team을 하나의 실행 단위로 본다.

Shared State 변경 계약은 다음과 같다.

```text
요청: SharedStateUpdate { case_id, expected_version, state_patch }
결과: UpdateResult = SUCCESS | CONFLICT | NOT_FOUND
```

Coordination은 `CONFLICT`를 받으면 최신 State를 재로드한다. 결과가 아직 유효하면 Retry하고, 그렇지 않으면 Replan한다.

---

## 9. 외부 소비자 AI 연동 구조

### 핵심 개념
사용자는 반드시 우리 웹 UI를 통해서만 문의를 처리하지 않아도 된다.  
자신이 사용하는 **ChatGPT / Claude / Gemini** 같은 개인 AI가  
우리 서비스의 **API/MCP**에 연결되어 고객을 대신해 문의·조회·작업 요청을 할 수 있다.

### 예시
사용자:
> "지난달 구독 해지했는데 이번 달에도 결제됐어. 확인해서 처리해줘."

개인 AI:
1. get_my_subscription()
2. get_payment_history()
3. open_support_case()
4. request_refund() (승인 필요 시 사용자 확인)

우리 플랫폼:
- 인증 확인
- Case 생성
- Billing Agent Team 처리
- 결과 반환

### 보안 원칙
- DB 직접 노출 금지
- SQL 실행형 도구 금지
- 사용자 Scope 기반 권한 제어
- 읽기/쓰기 도구 분리
- 환불/해지 등 쓰기 작업은 승인 단계 고려

---

## 9-C. MCP / A2A / Message Broker 역할 분리

A2A는 2025년 Linux Foundation으로 이관된 뒤 스펙 1.0으로 안정화됐다. 150개 이상 조직이 참여하고 있으며 Azure AI Foundry, AWS Bedrock AgentCore, Google Vertex AI에도 통합됐다.
2025년 12월 신설된 **AAIF(Agentic AI Foundation)** 는 MCP와 A2A를 함께 거버넌스한다.

MCP는 Agent가 Tool과 데이터로 내려가는 수직 통합이다. A2A는 Agent와 Agent가 협업하고 위임하는 수평 통합이다.
도입 순서는 **MCP first, A2A gradually**를 따른다. 내부 Tool과 지식을 먼저 MCP로 연결하고, 독립 Agent 간 위임이 실제로 필요할 때 A2A를 적용한다.

| 기술 | 연결 대상 | 역할 |
|---|---|---|
| MCP | Personal AI → 우리 서비스 | Tool 호출 및 Resource 접근 |
| A2A | 독립 Agent System ↔ Agent System | Capability 발견, Task 위임, 결과/Artifact 교환 |
| Message Broker | 우리 Runtime 내부 Controller ↔ Local Worker | Queue, Retry, Event, 비동기 전달 |

### Agent Team Registry 확장

```text
team_id
capabilities[]
execution_type: LOCAL | A2A
version
entrypoint
agent_card_url
a2a_endpoint
auth_scheme
allowed_tools[]
knowledge_scope[]
status
```

- LOCAL: Message Broker를 통해 내부 Agent Team Slot 실행
- A2A: A2A Adapter를 통해 Remote Agent System 호출
- 두 실행 결과는 TeamResult로 정규화하여 Shared State에 반영

---

## 9-D. Graph DB / GraphRAG 활용 계획

GraphRAG는 비용이 Vector RAG보다 3~5배 높다. 단일 사실 조회에는 이득이 거의 없다.
값을 하는 곳은 교차 문서 multi-hop 질의다.
2026년 분석 기준 엔터프라이즈 RAG의 72~80%가 프로덕션에 도달하지 못했다. graph 구축 오버헤드가 반복 원인으로 꼽혔다.
LLM 기반 추출은 엔티티와 관계를 환각할 수 있다.

따라서 다음 채택 게이트를 둔다.

1. Vector RAG 베이스라인을 먼저 만든다.
2. Graph가 이겨야 하는 질의 유형을 미리 문서로 정의한다. 예시는 반복 VOC 탐지와 유사 Case 근거 확장이다.
3. 해당 질의에서 Graph가 베이스라인을 이기지 못하면 채택하지 않는다.

우리 설계는 LLM으로 그래프를 추출하지 않는다. PostgreSQL의 FK 관계에서 결정적으로 Projection한다.
Case–Issue–Policy–Action 관계가 이미 관계형으로 존재하므로 환각 위험이 없고 추출 비용도 없다.
이는 일반적인 GraphRAG 실패 원인을 구조적으로 줄이는 설계다.

### 역할
- Vector Search: 의미적으로 비슷한 문서/Entity 탐색
- Graph Search: 해당 Entity와 연결된 Case·Issue·Policy·Product·Team·Action 탐색
- Context Broker: Vector + Graph + DB + Memory를 Context Pack으로 조합

### Graph 모델 예시

```text
Customer -REPORTED-> Case
Case -HAS_ISSUE-> Issue
Issue -AFFECTS-> Product
Product -GOVERNED_BY-> Policy
Case -HANDLED_BY-> AgentTeam
Case -TRIGGERED-> Action
Case -USED_EVIDENCE-> KnowledgeDocument
```

### 저장 원칙
- PostgreSQL: Customer Case, Shared State, Action, Approval, Transaction의 Source of Truth
- Graph Store: 관계 탐색을 위한 파생 Projection
- Graph 기술은 `GraphStorePort` 뒤에 Adapter로 연결
- 후보: PostgreSQL 기반 Graph 기능/확장, SQL/PGQ 계열, 전용 Graph DB

### 적용 단계
1. 필수: PostgreSQL + pgvector Vector RAG
2. PoC: Remote A2A Team 1개
3. 선택: 채택 게이트를 통과한 반복 VOC 또는 유사 Case 탐색용 GraphRAG 1개

---

## 10. 핵심 사용자 시나리오

### 시나리오 A: 구독 해지 후 추가 결제
1. 고객이 문의하거나 개인 AI를 통해 요청
2. 감성/의도/이슈 분류
3. Billing Case 생성
4. Billing Agent Team이 결제 이력/구독 상태/정책 조회
5. 환불 가능 여부 판단
6. 결과를 고객에게 응답
7. 필요 시 Human Approval 후 환불 요청 처리

### 시나리오 B: Free/Pro 권한 동기화 오류
1. 고객이 "Free로 바꿨는데 Pro 기능이 남아 있어요" 문의
2. Technical Case 생성
3. Technical Agent Team이 entitlement state, account state, incident history 확인
4. 원인 후보(동기화 실패, 캐시 문제, 구독 상태 불일치) 분석
5. 해결책 제시 또는 내부 조치 요청
6. 결과 공유 및 종료

### 시나리오 C: 반복 불만 탐지
1. VOC Agent Team이 일정 기간 고객 문의/리뷰 분석
2. 비슷한 이슈가 반복되는지 cluster / trend 분석
3. 관리용 리포트 생성
4. 특정 이슈 급증 시 Technical Team에 알림

---

## 11. 데이터 구조 초안

### 주요 테이블
- users
- external_ai_clients
- api_tokens / oauth_connections
- customer_feedback
- customer_cases
- case_events
- agent_teams
- agent_runs
- knowledge_documents
- memory_items
- action_requests
- action_approvals
- voc_reports

### 핵심 관계
- user 1:N customer_cases
- customer_cases 1:N case_events
- customer_cases 1:N agent_runs
- knowledge_documents N:1 domain/module
- action_requests 1:1 or N:1 approval records

---

## 12. 기술 스택(권장)

### Backend
- Python
- FastAPI
- Pydantic
- SQLAlchemy
- PostgreSQL

### Agent / Orchestration
- LangGraph 1.0 (2025년 10월 릴리스, 상위 workflow 및 상태 흐름)
- 체크포인터: `AsyncPostgresSaver`
- `InMemorySaver`는 사용하지 않는다. 재시작 시 진행 상태가 사라질 수 있다.
- `thread_id = case_id`로 매핑한다.
- LangChain 또는 자체 경량 RAG 모듈
- OpenAI / Anthropic / Google 모델 API (선택)

### Retrieval / Memory
- pgvector 또는 Chroma
- BM25 + Vector Hybrid Retrieval
- RAG document pipeline

### Frontend
- React
- TypeScript
- Tailwind CSS (선택)
- 상태 시각화 대시보드

### Dev / Infra
- Docker
- GitHub Actions
- pytest
- ERD / Mermaid 또는 SVG 기반 시각화

### External Agent Integration
- REST API / OpenAPI
- MCP Server
- A2A Adapter / Agent Card / Remote Task
- OAuth 2.0
- Graph Store Adapter / GraphRAG PoC

---

## 13. 클린 아키텍처 기반 폴더 구조(권장)

```text
project/
├ app/
│  ├ presentation/
│  │  ├ api/
│  │  ├ web/
│  │  └ schemas/
│  ├ application/
│  │  ├ usecases/
│  │  ├ services/
│  │  ├ workflows/
│  │  └ orchestrators/
│  ├ domain/
│  │  ├ entities/
│  │  ├ value_objects/
│  │  ├ repositories/
│  │  └ policies/
│  ├ infrastructure/
│  │  ├ db/
│  │  ├ vectorstore/
│  │  ├ llm/
│  │  ├ adapters/
│  │  └ integrations/
│  └ modules/
│     └ customer_ops/
│        ├ agents/
│        ├ tools/
│        ├ prompts/
│        ├ knowledge/
│        └ workflows/
├ tests/
├ docs/
├ scripts/
└ docker/
```

---

## 14. 구현 단계 계획(8~10주)

### 1단계: 기획 / 데이터 설계
- 프로젝트 범위 확정
- 도메인(SaaS Customer Ops) 확정
- Case 시나리오 정의
- ERD 및 상태 전이 설계

### 2단계: Core Basement MVP
- Agent Registry
- Tool Registry
- Shared State
- Context Broker
- 기본 Workflow

### 3단계: Customer Ops Module 구현
- Billing Agent Team
- Technical Support Agent Team
- VOC Agent Team
- FAQ / 정책 RAG

### 4단계: 외부 AI Agent API
- 사용자 인증
- OpenAPI 문서
- 주요 business capability API
- 가능 시 MCP 시범 구현

### 5단계: 운영자 웹 대시보드
- Case 목록
- 상태 전이
- Agent Run 결과
- VOC 리포트
- 승인 UI

### 6단계: 평가 / 고도화
- Baseline 비교
- 응답 정확도/유효성
- 재처리 성공률
- Human intervention 감소 여부
- 발표용 시연 시나리오 정리

---

## 15. 평가 계획

### Baseline A
- 단일 LLM + 단순 RAG

### Baseline B
- 고정형 멀티에이전트 파이프라인
  - 분석 → 검색 → 생성 → 검수

### Proposed
- Shared State + Context Broker + 전문 Agent Team + External AI API

### 평가 지표
- 문의 처리 성공률
- 응답 품질
- 정책 일관성
- Case 재처리 성공률
- 평균 처리 단계 수
- Human intervention 빈도
- VOC 이상징후 탐지 품질
- 외부 AI 연동 성공률

---

## 16. 팀 역할 제안 — 6명 기준

### 전체 배분
- **Core 1 · Case Runtime & Coordination — 1명**
- **Core 2 · Access & Action Platform — 1명**
- **Agent Team Module 개발 — 3명**
- **UX / Observability / Evaluation — 1명**

코드의 책임 경계와 사람의 담당 경계를 똑같이 만들 필요는 없다.

### Core 1 · Case Runtime & Coordination — 1명
- Customer Case, Lifecycle, Shared State, State Repository
- version, CAS/Optimistic Concurrency
- Agentic Controller, Top-Level LangGraph, Routing, Ownership
- Retry/Replan/Cancel, WAIT/RESUME
- Agent Team Registry, Team Contract
- Message Broker(Task/Event, Queue, Retry)

### Core 2 · Access & Action Platform — 1명
- Agent Gateway
- OAuth/Token/Scope/Client Identity
- REST/MCP, A2A Adapter
- Tool/Action Gateway, Business API
- Action Permission, Human Approval
- Idempotency, Audit, 외부 시스템 연동

### Agent Team Module 개발 — 3명
최종 Agent Team 종류와 개수는 요구사항 분석 후 결정한다.
- Team 내부 Agent/Subgraph
- Prompt/Tool 조합
- Knowledge Scope
- Retrieval / Rerank
- Episodic Memory 정책
- Team 단위 테스트/재처리 시나리오

배치 예:
- Team 3개 → 각 1명
- Team 2개 → 2명 + 1명
- 복잡한 Team 하나에 2명 배치 가능

### UX / Observability / Evaluation — 1명
- 사용자/운영자 Web UI
- Case 상태 / Agent Trace / Approval 화면
- Baseline vs Agentic 평가 Harness
- 성공률 / Tool 호출 / 재처리 / latency / cost 지표
- 통합 데모 / 평가 리포트

### DB 소유

| 담당 | 소유 데이터 |
|---|---|
| Core 1 | `customer_cases`, `case_events`, `shared_state`, `agent_runs` |
| Core 2 | `external_ai_clients`, `oauth_connections`, `action_requests`, `action_approvals`, `audit_logs` |
| 공통 합의 | SQLAlchemy 설정, Alembic, DB Connection, Base Repository |

백엔드 담당자 1명이 모든 DB 코드를 맡는 역할은 두지 않는다.

CAS와 Idempotency는 대상이 다르다. Core 1은 같은 Case 상태를 두 작업이 동시에 수정하는 상황을 version/CAS로 다룬다.
Core 2는 같은 환불을 두 번 실행하려는 상황을 idempotency key로 막는다.
따라서 두 책임은 겹치지 않는다.

### 책임 경계
- 어느 Team을 언제 호출하는가? → Core 1
- 외부 AI가 어떤 권한으로 어떻게 들어오는가? → Core 2
- 선택된 Team 안에서 문제를 어떻게 푸는가? → Agent Team 개발자 3명
- 사용자가 무엇을 보고 시스템 품질을 어떻게 측정하는가? → UX/Evaluation 1명

---

## 17. 사용자 본인 역할 어필 문장 예시

> 저는 개별 Agent 하나의 기능 구현보다는, 각 Agent Team이 공유 상태와 기업 지식을 기반으로 협업할 수 있도록 전체 Agentic AI 실행 구조를 설계하고 구현하는 역할을 맡고 싶습니다. 구체적으로는 Shared State, Context Broker, Agent Registry, Tool/API Gateway, External AI Agent 연동, 상위 Workflow와 평가 구조를 담당하겠습니다.

---

## 18. 예상 리스크와 대응

### 리스크 1. 범위 과대
- 대응: 도메인 1개(SaaS), Agent Team 3개로 제한

### 리스크 2. 멀티에이전트 복잡성 과다
- 대응: Team 내부는 단순화, 상위 Controller 중심 설계

### 리스크 3. 외부 AI 연동 범위 과대
- 대응: REST/OpenAPI 우선, MCP는 시범 수준

### 리스크 4. RAG 품질 저하
- 대응: FAQ/정책 문서 중심의 소규모 고품질 corpus 구축

---

## 18-A. 결정사항의 주의점

| 결정사항 | 주의할 점 |
|---|---|
| Message Broker를 Coordination이 소유 | Controller가 Broker의 전달 보장에 의존하기 쉽다. In-process와 Redis 교체를 유지하려면 모든 consumer를 at-least-once 전제로 idempotent하게 설계한다. |
| MVP에서 in-process queue 사용 | Broker가 사실상 함수 호출이 될 수 있다. 중복 전달과 재시도를 강제로 발생시키는 테스트를 둔다. |
| Top-Level Graph와 Message Broker 병행 | Graph는 Case 내부 흐름을 결정하고, Broker는 Team 실행을 배달한다. 두 컴포넌트의 결정 범위를 고정한다. |
| Core 1의 넓은 범위 | Case, State, CAS, Controller, Graph, Registry, Broker가 병목이 되면 Team 개발 3명이 모두 막힌다. 1~2주차에 Contract를 확정하고 stub Core를 내놓는다. |
| Core 간 왕복 계약 | Team의 Tool 호출은 Core 2 Action Layer를 거쳐 Core 1 Shared State로 돌아온다. 이 계약을 1주차에 고정한다. |
| DB 소유 분리 | Alembic revision이 두 갈래로 갈라질 수 있다. 마이그레이션은 단일 브랜치와 순서 합의 규칙으로 관리한다. |
| A2A Task 도입 | A2A Task와 Case 상태가 이중 상태 머신이 된다. 매핑 규칙을 정하고, 우리 더미 Remote Agent 1개로 PoC하는 선까지로 범위를 둔다. |
| GraphRAG 채택 | 채택 게이트를 통과하지 못하면 버린다. 버리는 것도 평가 결과로 보고한다. |

---

## 19. 엑셀 입력용 요약(이미지 구조 대응)

| 번호 | 팀 이름 | 팀원 | 프로젝트 주제 | 프로젝트 주제 설명 | 활용 기술 스택 |
|---|---|---|---|---|---|
| 6 | A-COP Lab *(예시)* | [팀원명 입력] | 다중 에이전트 서빙 기반 고객 피드백 분석 및 맞춤형 응대 자동화 시스템 | 고객 리뷰·문의·상담 로그를 분석하여 감성·의도·이슈를 분류하고, 요구사항에 따라 구성되는 업무별 전문 Agent Team Module이 Shared State와 기업 지식(RAG)을 기반으로 협업하여 맞춤형 응대를 수행하는 Agentic Customer Operations Platform을 구축한다. 또한 사용자가 ChatGPT·Claude·Gemini 같은 개인 AI를 통해 우리 서비스의 Agent API/MCP에 접속하여 문의·조회·작업 요청을 수행할 수 있도록 외부 AI 연동 인터페이스를 제공한다. | Python, FastAPI, PostgreSQL, pgvector, React, LangGraph, RAG, OpenAPI, OAuth2, Docker |

### 엑셀 셀에 더 짧게 넣는 버전
- **프로젝트 주제(짧은 별칭)**: A-COP: AI 연동형 모듈형 에이전틱 고객운영 플랫폼
- **프로젝트 주제 설명(짧은 버전)**: 고객 피드백 분석과 맞춤형 응대를 위해 업무별 Agent Team Module이 Shared State·RAG·Memory를 기반으로 협업하는 모듈형 Agentic Customer Operations Platform. 개인 AI(ChatGPT/Claude/Gemini) 연동 API 제공.
- **활용 기술 스택(짧은 버전)**: FastAPI, React, PostgreSQL, pgvector, LangGraph, RAG/GraphRAG, MCP, A2A, OpenAPI, OAuth2, Redis/RabbitMQ, Docker

---

## 20. 최종 정리

이 프로젝트의 차별점은 다음과 같다.

1. **부트캠프 주제를 유지한다.**
2. **단순 LLM 파이프라인이 아니라 실제 업무 단위 Agent Team을 둔다.**
3. **고객 응답뿐 아니라 상태 기반 운영(Case)을 다룬다.**
4. **RAG를 답변용 검색이 아니라 Agent Context 제공 계층으로 사용한다.**
5. **개인 AI가 고객을 대신해 우리 서비스에 접속하는 구조까지 고려한다.**
6. **향후 다른 도메인에도 확장 가능한 모듈형 Basement 구조를 설계한다.**

---
