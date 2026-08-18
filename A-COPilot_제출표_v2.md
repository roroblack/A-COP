# A-COPilot 프로젝트 제출표 v2

## 1. 제출용 표 [I1](https://www.poweredbysearch.com/blog/how-to-design-b2b-saas-product-pages-with-examples/)

엑셀에 붙여넣을 때 셀 안의 줄바꿈은 `Alt+Enter`로 입력한다.

| 번호 | 팀 이름 | 팀원 | 프로젝트 주제 | 프로젝트 주제 설명 | 활용 기술 스택 | 주제 선정 이유 |
|---|---|---|---|---|---|---|
| 6 | A-COPilot | 김지혜 · 서유현 · 송채영 · 정세환 · 최상욱 · 최연우 | 다중 에이전트 서빙 기반 고객 피드백 분석 및 맞춤형 응대 자동화 시스템 | 근거번호 링크는 이 표 바로 아래 목록에서 클릭<br><br>기업이 자사 고객 응대를 Agentic AI로 운영하도록 구축·판매하는 B2B 플랫폼이며, 고객사의 소비자는 자기 AI에서 MCP를 통해 제한된 검증 범위의 문의·조회 기능을 이용한다. 상품·주문·배송·반품을 포함한 전면 Commerce Ops는 확장 범위(vision)다.<br>· 제공 형태 — Team은 Registry 등록형이며 도입 기업이 자사 Team을 추가해도 Core 코드는 불변이다.<br>· 소비자 접점 — MCP Server가 Tool과 Resource를 노출해 자기 에이전트에서 지금은 제한된 검증 범위의 문의·조회 기능을 제공하고, 상품·주문·배송·반품을 포함한 전면 Commerce Ops는 앞으로 열 확장 범위로 둔다. UCP·AP2 정합성을 고려한다.<br>· 처리 구조 — Case 상태를 관리하고 Agent Team과 Agentic Controller가 실행·대기·재계획·승인을 조정한다.<br>· 안전 경계 — Team은 제안만 반환하고 실행은 승인 경로에서 수행하며, 근거 대조로 없는 대상·금액·수량을 차단한다.<br>· 검증 — 판단과 근거를 함께 기록해 재생·감사하고 golden/holdout과 통계 검정으로 평가한다.<br>· 운영 — 운영자는 이상 신호와 고위험 Action만 확인한다.<br>· 배포 — 자체 호스팅을 목표로 설계했으며, 고객사 배포와 데이터 외부 반출 방지는 별도 검증 항목으로 둔다. | 근거번호 링크는 이 표 바로 아래 목록에서 클릭<br><br>· 코어 1 (Case Runtime & Coordination) — Case lifecycle·Shared State·Controller·Top-Level LangGraph에 사용<br>  MVP — Python, LangGraph, PostgreSQL(CAS·트랜잭션), Registry<br>  Phase 2 — Redis/RabbitMQ Adapter, Apache AGE·Neo4j<br><br>· 코어 2 (Access & Action Platform) — Gateway, Tool/Action, approval, idempotency, audit에 사용<br>  MVP — FastAPI, REST/OpenAPI, MCP, A2A Adapter, API Key+Scope<br>  Phase 2 — OAuth2/OIDC, 외부 Message Broker<br><br>· 모델 (Agent Team Module) — Team graph/agent, retrieval/rerank, memory 정책, 모델 선택/라우팅, TeamResult 생성에 사용<br>  MVP — RAG, pgvector, 프롬프트 버전 관리, retrieval/rerank, memory, 모델 라우팅<br>  Phase 2 — GraphRAG 확장<br><br>· 검증 & 프론트 — 평가, 통계 검정, contract/회귀 테스트, 운영 UI, 통합 데모, observability에 사용<br>  MVP — pytest, golden/holdout harness, bootstrap/McNemar, contract test, React 운영 UI<br>  Phase 2 — 고급 observability<br><br>· 배포 (Deployment) — 실제 서비스 배포와 24시간 운영 환경에 사용한다.<br>  Phase 2: AWS, Docker(컨테이너 기반 배포). 현재 로컬 개발 환경에는 Docker가 설치돼 있지 않아 로컬은 PostgreSQL 직접 실행으로 진행하고, 배포 단계에서 컨테이너화한다. | 근거번호 링크는 이 표 바로 아래 목록에서 클릭<br><br>① 고객이 이미 에이전트다 — 자동화 트래픽이 53%로 인간 47%를 넘었다 [A1](https://www.imperva.com/resources/resource-library/reports/2026-bad-bot-report/). 미국 리테일 사이트 AI 유입은 전년 대비 4,700% 증가했고 [B1](https://commercetools.com/blog/agentic-commerce-stats-enterprise-guide), Shopify AI 유입 주문은 약 13배가 됐으며 [B5](https://www.metarouter.io/post/agentic-commerce-trends-statistics), AI 유입 쇼퍼 전환율은 인간보다 42% 높다 [B6](https://commercetools.com/blog/agentic-commerce-stats-enterprise-guide). MCP Server 표면은 1급 기능으로 설계하되, 현재는 제한된 검증 범위의 문의·조회 기능만 열고 주문·CS까지 자기 에이전트로 수행하는 범위는 앞으로 열 확장 대상으로 둔다.<br><br>② 시장은 크고 자란다 — 글로벌 AI 고객서비스 시장은 2030년 478.2억 달러, CAGR 25.8%로 전망된다 [C1](https://www.marketsandmarkets.com/PressReleases/ai-for-customer-service.asp). 국내 AICC 수치는 원출처 미확인인 업계 추정이므로 핵심 근거로 단정하지 않는다 [C3](https://claw-ops.com/blog/korea-aicc-market).<br><br>③ 도입은 됐는데 작동하지 않는다 — 콜센터 AI 사용 88%, 완전 통합 25% [D1](https://www.lorikeetcx.ai/articles/ai-customer-service-statistics), Gartner의 2027년까지 agentic AI 프로젝트 40% 이상 폐기 전망 [D2](https://www.kai-waehner.de/blog/2026/04/06/enterprise-agentic-ai-landscape-2026-trust-flexibility-and-vendor-lock-in/), 데모 자동화율 90% 이상 대비 실제 프로덕션 55~70% [D3](https://builts.ai/blog/ai-customer-service-trends-2026/)이 보여주는 운영화 공백을 겨냥한다.<br><br>④ 1군 제품에 구조적 공백이 있다 — Intercom Fin은 단일 에이전트이며 자체 호스팅 불가 근거가 있다 [G1](https://inkeep.com/blog/inkeep-vs-intercom-fin-ai) [G2](https://myaskai.com/blog/intercom-fin-ai-agent-complete-guide-2026). Sierra·Decagon은 공개 비교 자료에서 end-to-end 품질관리 기능이 확인되지 않고 [G3](https://www.notch.cx/learn/deep-dive-comparison-for-enterprise-ai-customer-support), Decagon의 AOP와 Sierra의 policy는 대화 종결에 최적화된 것으로 분석된다 [G4](https://www.mavenagi.com/blog/decagon-alternatives).<br><br>⑤ 자체 호스팅 수요는 규제가 만든다 — 유럽·중동 기업의 자국 내 워크로드 비중 75% 이상 전망 [F1](https://thoughtminds.ai/blog/sovereign-ai-and-on-premise-llms), sovereign AI에 관한 Deloitte 조사 [F2](https://thoughtminds.ai/blog/sovereign-ai-and-on-premise-llms), AI 인프라 예산 증가 응답 86% [F3](https://thoughtminds.ai/blog/sovereign-ai-and-on-premise-llms)가 이를 뒷받침한다.<br><br>⑥ 목표는 더 똑똑한 AI가 아니라 믿고 맡길 수 있는 AI다 — 승인 경계·근거 대조·감사·통계 측정을 구현하고, 현재 확보된 구독·결제·고객운영 시나리오에서 검증한다. 검증 쇼핑몰은 현재 준비 중이며, 해당 사이트에서 주문·반품 시나리오를 확인할 계획이다. |

### 1-1. 제출용 셀의 읽기용 본문

#### 프로젝트 주제 설명

기업이 자사 고객 응대를 Agentic AI로 운영하도록 구축·판매하는 B2B 플랫폼이며, 고객사의 소비자는 자신이 이미 쓰던 AI 에이전트로 MCP Server를 통해 상품 탐색·주문·배송조회·문의·반품까지 수행한다.

- 제공 형태: Team은 Registry 등록형이다. 도입 기업이 자사 업무 Team을 추가해도 Core 코드는 불변이다.
- 소비자 접점: MCP Server가 Tool과 Resource를 노출해 소비자의 기존 에이전트에서 주문부터 CS까지 연결한다. UCP·AP2 정합성을 고려한다.
- 처리 구조: Case lifecycle, Shared State, Agent Team, Agentic Controller가 실행·대기·재계획·승인을 조정한다.
- 안전 경계: Team은 ActionProposal만 반환하고 side effect는 승인 경로에서 실행한다. 실행 직전 대상·금액·수량·scope를 근거와 대조한다.
- 검증: 판단·근거·실행 기록을 남겨 재생·감사하고, golden/holdout과 통계 검정으로 성능을 확인한다.
- 운영: 운영자는 이상 신호와 고위험 Action만 확인하는 human-on-the-loop 구조다.
- 배포: 고객사 네트워크·스토리지·키 관리 기반의 자체 호스팅 경로를 제공한다.

#### 활용 기술 스택

· 코어 1 (Case Runtime & Coordination) — Case lifecycle·Shared State·Controller·Top-Level LangGraph에 사용한다.

- MVP: Python, LangGraph, PostgreSQL(CAS·트랜잭션), Registry
- Phase 2: Redis/RabbitMQ Adapter, Apache AGE·Neo4j

· 코어 2 (Access & Action Platform) — Gateway, Tool/Action, approval, idempotency, audit에 사용한다.

- MVP: FastAPI, REST/OpenAPI, MCP, A2A Adapter, API Key+Scope
- Phase 2: OAuth2/OIDC, 외부 Message Broker

· 모델 (Agent Team Module) — Team graph/agent, retrieval/rerank, memory 정책, 모델 선택/라우팅, TeamResult 생성에 사용한다.

- MVP: RAG, pgvector, 프롬프트 버전 관리, retrieval/rerank, memory, 모델 라우팅
- Phase 2: GraphRAG 확장

· 검증 & 프론트 — 평가, 통계 검정, contract/회귀 테스트, 운영 UI, 통합 데모, observability에 사용한다.

- MVP: pytest, golden/holdout harness, bootstrap/McNemar, contract test, React 운영 UI
- Phase 2: 고급 observability

#### 주제 선정 이유

① 고객이 이미 에이전트다

자동화 트래픽이 53%로 인간 47%를 넘었다([A1](https://www.imperva.com/resources/resource-library/reports/2026-bad-bot-report/)). 미국 리테일 사이트 AI 유입은 전년 대비 4,700% 증가했고([B1](https://commercetools.com/blog/agentic-commerce-stats-enterprise-guide)), Shopify AI 유입 주문은 약 13배가 됐으며([B5](https://www.metarouter.io/post/agentic-commerce-trends-statistics)), AI 유입 쇼퍼 전환율은 인간보다 42% 높다([B6](https://commercetools.com/blog/agentic-commerce-stats-enterprise-guide)). 따라서 소비자가 자기 에이전트로 주문·CS까지 수행하는 MCP Server 표면을 1급 기능으로 설계했다.

② 시장은 크고 자란다

글로벌 AI 고객서비스 시장은 2030년 478.2억 달러, CAGR 25.8%로 전망된다([C1](https://www.marketsandmarkets.com/PressReleases/ai-for-customer-service.asp)). 국내 AICC 수치는 원출처 미확인인 업계 추정이므로 핵심 근거로 단정하지 않는다([C3](https://claw-ops.com/blog/korea-aicc-market)).

③ 도입은 됐는데 작동하지 않는다

콜센터 AI 사용 88%, 완전 통합 25%([D1](https://www.lorikeetcx.ai/articles/ai-customer-service-statistics)), Gartner의 2027년까지 agentic AI 프로젝트 40% 이상 폐기 전망([D2](https://www.kai-waehner.de/blog/2026/04/06/enterprise-agentic-ai-landscape-2026-trust-flexibility-and-vendor-lock-in/)), 데모 자동화율 90% 이상 대비 실제 프로덕션 55~70%([D3](https://builts.ai/blog/ai-customer-service-trends-2026/))이 보여주는 운영화 공백을 겨냥한다.

④ 1군 제품에 구조적 공백이 있다

Fin은 단일 에이전트라는 공개 비교 근거([G1](https://inkeep.com/blog/inkeep-vs-intercom-fin-ai))와 자체 호스팅 불가 근거([G2](https://myaskai.com/blog/intercom-fin-ai-agent-complete-guide-2026))가 있고, Sierra·Decagon은 end-to-end 품질관리 공개 근거가 없으며([G3](https://www.notch.cx/learn/deep-dive-comparison-for-enterprise-ai-customer-support)) AOP/policy가 대화 종결에 최적화됐다는 분석이 있다([G4](https://www.mavenagi.com/blog/decagon-alternatives)).

⑤ 자체 호스팅 수요는 규제가 만든다

유럽·중동 기업의 자국 내 워크로드 비중 75% 이상 전망([F1](https://thoughtminds.ai/blog/sovereign-ai-and-on-premise-llms)), sovereign AI에 관한 Deloitte 조사([F2](https://thoughtminds.ai/blog/sovereign-ai-and-on-premise-llms)), AI 인프라 예산 증가 응답 86%([F3](https://thoughtminds.ai/blog/sovereign-ai-and-on-premise-llms))가 이를 뒷받침한다.

⑥ 목표는 더 똑똑한 AI가 아니라 믿고 맡길 수 있는 AI다

승인 경계·근거 대조·감사·통계 측정을 구현하고 직접 운영하는 검증 쇼핑몰에서 확인한다.

## 2. 근거 데이터

아래 표는 `research/_출처검증_2026-08-17.md`의 A~H를 주제별로 재구성한 것이다. 모든 수치 행에 근거번호·출처기관·등급·URL을 붙였다. B7은 추정, C3은 원출처 미확인으로 표시한다.

| 주제 | 근거번호 | 사실 또는 수치 | 출처기관 | 등급 | URL |
|---|---|---|---|---|---|
| 에이전트 웹 트래픽 | A1 | 자동화 트래픽 53%, 인간 47%; 전년 51%에서 상승 | Imperva(Thales) | 1차 | [출처](https://www.imperva.com/resources/resource-library/reports/2026-bad-bot-report/) |
| 에이전트 웹 트래픽 | A2 | “Bots in the Agentic Age” 보고서 해설 | Imperva | 1차 | [출처](https://www.imperva.com/blog/bad-bot-report-2026-bots-agentic-age/) |
| 에이전트 웹 트래픽 | A3 | 나쁜 봇 전체 트래픽 40%, 전년 대비 3%p 증가 | Imperva(Thales) | 1차 | [출처](https://www.imperva.com/resources/resource-library/reports/2026-bad-bot-report/) |
| 에이전트 웹 트래픽 | A4 | AI 기반 공격 탐지·차단 12.5배 증가, 일 200만에서 2,500만 건 | Imperva(Thales) | 1차 | [출처](https://www.imperva.com/resources/resource-library/reports/2026-bad-bot-report/) |
| 에이전트 쇼핑 | B1 | 미국 리테일 사이트 AI 유입 4,700% YoY 증가 | Adobe Analytics | 2차 인용 | [출처](https://commercetools.com/blog/agentic-commerce-stats-enterprise-guide) |
| 에이전트 쇼핑 | B2 | Prime Day GenAI 유입 트래픽 3,300% YoY 증가 | Adobe Analytics | 2차 인용 | [출처](https://commercetools.com/blog/agentic-commerce-stats-enterprise-guide) |
| 에이전트 쇼핑 | B3 | Black Friday AI 유입 리테일 트래픽 805% YoY 증가 | Adobe Analytics | 2차 인용 | [출처](https://www.digitalapplied.com/blog/agentic-commerce-statistics-2026-data) |
| 에이전트 쇼핑 | B4 | Shopify 가맹점 AI 유입 약 8배 YoY | Shopify | 2차 인용 | [출처](https://www.metarouter.io/post/agentic-commerce-trends-statistics) |
| 에이전트 쇼핑 | B5 | Shopify AI 유입 주문 약 13배 YoY | Shopify | 2차 인용 | [출처](https://www.metarouter.io/post/agentic-commerce-trends-statistics) |
| 에이전트 쇼핑 | B6 | AI 유입 쇼퍼 전환율이 인간 대비 42% 높음 | Adobe | 2차 인용 | [출처](https://commercetools.com/blog/agentic-commerce-stats-enterprise-guide) |
| 에이전트 쇼핑 | B7 | agentic commerce 시장 2030년 3~5조 달러 전망; 기관 특정이 없는 추정 | 컨설팅펌 종합 | 2차 인용·추정 | [출처](https://www.digitalapplied.com/blog/agentic-commerce-statistics-2026-data) |
| 시장 규모 | C1 | 글로벌 AI 고객서비스 시장 2030년 478.2억 달러, CAGR 25.8% | MarketsandMarkets | 1차(보도자료) | [출처](https://www.marketsandmarkets.com/PressReleases/ai-for-customer-service.asp) |
| 시장 규모 | C2 | 같은 시장 2026년 151.2억 달러 | MarketsandMarkets 추정 | 2차 인용 | [출처](https://www.lorikeetcx.ai/articles/ai-customer-service-statistics) |
| 시장 규모 | C3 | 국내 AICC 2020년 4,214만 달러에서 2030년 3억 5,008만 달러; 원출처 미확인 업계 추정 | 국내 시장 분석 | 2차·원출처 미확인 | [출처](https://claw-ops.com/blog/korea-aicc-market) |
| 도입·운영화 | D1 | 콜센터 AI 사용 88%, 그중 완전 통합 25% | 업계 통계 종합 | 2차 | [출처](https://www.lorikeetcx.ai/articles/ai-customer-service-statistics) |
| 도입·운영화 | D2 | 2027년까지 agentic AI 프로젝트 40% 이상 폐기 전망; 원인은 운영화 실패 | Gartner | 2차 인용 | [출처](https://www.kai-waehner.de/blog/2026/04/06/enterprise-agentic-ai-landscape-2026-trust-flexibility-and-vendor-lock-in/) |
| 도입·운영화 | D3 | 벤더 데모 자동화율 90% 이상 대비 실제 프로덕션 55~70% | 수천 건 구현 데이터 | 2차 | [출처](https://builts.ai/blog/ai-customer-service-trends-2026/) |
| 비용 구조 | E1 | 사람의 Tier 1 티켓 처리 비용 15~25달러 | 지원 비용 통계 | 2차 | [출처](https://www.mavenagi.com/blog/cost-per-ticket-statistics-customer-support) |
| 비용 구조 | E2 | AI 해결 티켓 비용 0.49~2.00달러 | AI 지원 가격 조사 | 2차 | [출처](https://www.dragapp.com/blog/state-of-ai-support-pricing/) |
| 비용 구조 | E3 | Intercom Fin 해결당 0.99달러 | AI 지원 가격 조사 | 2차 | [출처](https://www.dragapp.com/blog/state-of-ai-support-pricing/) |
| 비용 구조 | E4 | Fin 평균 해결률 67%, 고객사 7,000곳 이상 | Intercom 공개 수치 | 2차 인용 | [출처](https://www.dragapp.com/blog/state-of-ai-support-pricing/) |
| 비용 구조 | E5 | 해결당 과금이 잘될수록 비싸져 이탈 사유 1위라는 리뷰 분석 | Fin 리뷰 | 2차 | [출처](https://myaskai.com/blog/intercom-fin-ai-agent-complete-guide-2026) |
| 자체 호스팅 | F1 | 2030년까지 유럽·중동 기업 75% 이상이 워크로드를 자국 내로 이전; 현재 5% 미만 | Gartner | 2차 인용 | [출처](https://thoughtminds.ai/blog/sovereign-ai-and-on-premise-llms) |
| 자체 호스팅 | F2 | sovereign AI가 이사회 안건; 24개국 3,235명 조사 | Deloitte | 2차 인용 | [출처](https://thoughtminds.ai/blog/sovereign-ai-and-on-premise-llms) |
| 자체 호스팅 | F3 | AI 인프라 예산이 3년 내 3배 이상 증가할 것이라는 응답 86% | Deloitte | 2차 인용 | [출처](https://thoughtminds.ai/blog/sovereign-ai-and-on-premise-llms) |
| 자체 호스팅 | F4 | 관련 규제로 GDPR, HIPAA, DORA, NIS2, EU AI Act가 거론됨 | 종합 | 2차 | [출처](https://www.gooddata.ai/blog/data-sovereignty-and-ai-analytics-keep-your-llm-on-premise/) |
| 경쟁 | G1 | Intercom Fin은 단일 에이전트; multi-agent·agent-to-agent·전문 라우팅 증거 없음 | Inkeep | 2차 | [출처](https://inkeep.com/blog/inkeep-vs-intercom-fin-ai) |
| 경쟁 | G2 | Fin은 자체 호스팅·온프레미스·air-gapped 불가 | Fin 리뷰 | 2차 | [출처](https://myaskai.com/blog/intercom-fin-ai-agent-complete-guide-2026) |
| 경쟁 | G3 | Sierra·Decagon 모두 end-to-end 품질관리 기능을 공개하지 않음 | Notch | 2차 | [출처](https://www.notch.cx/learn/deep-dive-comparison-for-enterprise-ai-customer-support) |
| 경쟁 | G4 | Decagon AOP와 Sierra policy는 대화 종결에 최적화되고 프로세스 오케스트레이션용이 아님 | MavenAGI | 2차 | [출처](https://www.mavenagi.com/blog/decagon-alternatives) |
| 경쟁 | G5 | Decagon은 Zendesk·Salesforce·Kustomer 지원, Freshdesk·HubSpot 미지원 | Decagon 비교 | 2차 | [출처](https://www.eesel.ai/blog/decagon-vs-sierra) |
| 경쟁 | G6 | Decagon AOP 작성 전에 API 연결·통합·guardrail 구성 필요 | Decagon 가이드 | 2차 | [출처](https://www.getmacha.com/blog/decagon-ai-complete-guide) |
| 경쟁 | G7 | 컴플레인은 감정·서비스 회복·정책 예외에서 자율 처리에 한계 | 업계 분석 | 2차 | [출처](https://builts.ai/blog/ai-customer-service-trends-2026/) |
| 상호운용 표준 | H1 | A2A 스펙 1.0, Linux Foundation 이관, 150개 이상 조직, 주요 클라우드 통합 | Linux Foundation | 1차 | [출처](https://www.linuxfoundation.org/press/a2a-protocol-surpasses-150-organizations-lands-in-major-cloud-platforms-and-sees-enterprise-production-use-in-first-year) |
| 상호운용 표준 | H2 | AP2는 구매를 서명된 Mandate 3종으로 표현하고 W3C Verifiable Credentials 사용 | Google Cloud | 1차 | [출처](https://cloud.google.com/blog/products/ai-machine-learning/announcing-agents-to-payments-ap2-protocol) |
| 상호운용 표준 | H3 | UCP는 Google·Shopify·Etsy·Wayfair·Target·Walmart 공동 개발이며 A2A·MCP 통합 가능 | Google Developers Blog | 1차 | [출처](https://developers.googleblog.com/under-the-hood-universal-commerce-protocol-ucp/) |
| 상호운용 표준 | H4 | UCP 구축 배경 | Shopify Engineering | 1차 | [출처](https://shopify.engineering/ucp) |
| 상호운용 표준 | H5 | MCP Server는 Tool과 Resource를 노출 | MCP 공식 문서 | 1차 | [출처](https://platform.claude.com/docs/en/docs/mcp) |

## 3. 경쟁 포지셔닝

비교는 공개 자료만 사용했다. 비공개 내부 구현은 판단 근거로 쓰지 않았다. 각 주장 셀에 G 근거번호를 붙였고, 근거가 없는 칸은 확인 필요로 표기했다.

| 비교축 | Fin | Sierra | Decagon | A-COPilot |
|---|---|---|---|---|
| 구조 | 단일 에이전트 [G1](https://inkeep.com/blog/inkeep-vs-intercom-fin-ai) | 확인 필요 [G1](https://inkeep.com/blog/inkeep-vs-intercom-fin-ai), [G2](https://myaskai.com/blog/intercom-fin-ai-agent-complete-guide-2026), [G3](https://www.notch.cx/learn/deep-dive-comparison-for-enterprise-ai-customer-support), [G4](https://www.mavenagi.com/blog/decagon-alternatives), [G5](https://www.eesel.ai/blog/decagon-vs-sierra), [G6](https://www.getmacha.com/blog/decagon-ai-complete-guide), [G7](https://builts.ai/blog/ai-customer-service-trends-2026/) | 확인 필요 [G1](https://inkeep.com/blog/inkeep-vs-intercom-fin-ai), [G2](https://myaskai.com/blog/intercom-fin-ai-agent-complete-guide-2026), [G3](https://www.notch.cx/learn/deep-dive-comparison-for-enterprise-ai-customer-support), [G4](https://www.mavenagi.com/blog/decagon-alternatives), [G5](https://www.eesel.ai/blog/decagon-vs-sierra), [G6](https://www.getmacha.com/blog/decagon-ai-complete-guide), [G7](https://builts.ai/blog/ai-customer-service-trends-2026/) | Registry 등록형 Agent Team과 공통 Runtime [프로젝트 기준선] |
| 대화 종결·업무 처리 | 해결 중심 가격·해결 모델 [E3~E5] | 대화 종결 최적화 [G4](https://www.mavenagi.com/blog/decagon-alternatives) | AOP가 대화 종결 최적화 [G4](https://www.mavenagi.com/blog/decagon-alternatives) | 주문·배송·문의·반품 Case의 실행·대기·재계획·승인 |
| 품질관리 | 확인 필요 [G3](https://www.notch.cx/learn/deep-dive-comparison-for-enterprise-ai-customer-support) | 공개 end-to-end 품질관리 근거 없음 [G3](https://www.notch.cx/learn/deep-dive-comparison-for-enterprise-ai-customer-support) | 공개 end-to-end 품질관리 근거 없음 [G3](https://www.notch.cx/learn/deep-dive-comparison-for-enterprise-ai-customer-support) | 근거 기록·재생·감사·golden/holdout·통계 검정 [프로젝트 기준선] |
| 자체 호스팅 | 불가 [G2](https://myaskai.com/blog/intercom-fin-ai-agent-complete-guide-2026) | 확인 필요 [G2](https://myaskai.com/blog/intercom-fin-ai-agent-complete-guide-2026), [G3](https://www.notch.cx/learn/deep-dive-comparison-for-enterprise-ai-customer-support), [G4](https://www.mavenagi.com/blog/decagon-alternatives), [G5](https://www.eesel.ai/blog/decagon-vs-sierra), [G6](https://www.getmacha.com/blog/decagon-ai-complete-guide), [G7](https://builts.ai/blog/ai-customer-service-trends-2026/) | 확인 필요 [G2](https://myaskai.com/blog/intercom-fin-ai-agent-complete-guide-2026), [G3](https://www.notch.cx/learn/deep-dive-comparison-for-enterprise-ai-customer-support), [G4](https://www.mavenagi.com/blog/decagon-alternatives), [G5](https://www.eesel.ai/blog/decagon-vs-sierra), [G6](https://www.getmacha.com/blog/decagon-ai-complete-guide), [G7](https://builts.ai/blog/ai-customer-service-trends-2026/) | 고객사 자체 호스팅을 제품 경로로 설계 [프로젝트 기준선] |
| 사전 통합 부담 | 확인 필요 [G6](https://www.getmacha.com/blog/decagon-ai-complete-guide) | 확인 필요 [G6](https://www.getmacha.com/blog/decagon-ai-complete-guide) | API 연결·통합·guardrail 선행 필요 [G6](https://www.getmacha.com/blog/decagon-ai-complete-guide) | MCP/API/A2A 경계와 Registry로 고객 Team 확장 |
| 안전 실행 경계 | 확인 필요 [G7](https://builts.ai/blog/ai-customer-service-trends-2026/) | policy 기반이라는 공개 분석 [G4](https://www.mavenagi.com/blog/decagon-alternatives) | AOP 기반이라는 공개 분석 [G4](https://www.mavenagi.com/blog/decagon-alternatives) | Team은 제안만, 승인·idempotency·근거 대조 후 실행 |

## 4. 주장 경계

| 주장하는 것 | 주장하지 않는 것 |
|---|---|
| A-COPilot은 하나의 Runtime 위에 CS/Commerce 도메인 팩을 Registry로 교체·확장하는 B2B Agentic Operations Platform이다. | 자동화율은 아직 측정 전이므로 특정 자동화율을 주장하지 않는다. |
| 소비자는 자기 기존 에이전트로 MCP Server의 Tool·Resource를 사용해 주문부터 CS까지 접근한다. | 현재 실측에서 Commerce MCP는 없음으로 기록됐으므로 이미 완성됐다고 주장하지 않는다. |
| Team은 side effect를 직접 실행하지 않고 제안하며, 실행은 승인·idempotency·audit 경계를 통과한다. | 전면 Commerce Ops 자동화가 구현됐다고 주장하지 않는다. 이는 vision이다. |
| 자체 호스팅 배포 프로파일을 제공하도록 설계한다. | Docker 실기동과 전면 배포가 완료됐다고 주장하지 않는다. 시스템 지도 실측은 골격만이다. |
| golden/holdout, contract test, 근거 기록과 통계 검정으로 신뢰성을 측정한다. | 아직 측정하지 않은 성능·정확도·비용 절감 수치를 확정하지 않는다. |
| 공개 비교 자료에 근거해 구조적 공백을 포지셔닝한다. | 경쟁사의 비공개 내부 구현이나 확인되지 않은 기능을 단정하지 않는다. |

## 5. 출처 목록

확인일: 2026-08-17. 아래 URL은 출처검증 문서에 수록된 전체 URL 목록이며, 중복 URL은 원문 표의 출처 행을 보존해 반복 표기했다.

| 근거번호 | 등급 | URL |
|---|---|---|
| A1, A3, A4 | 1차 | [출처](https://www.imperva.com/resources/resource-library/reports/2026-bad-bot-report/) |
| A2 | 1차 | [출처](https://www.imperva.com/blog/bad-bot-report-2026-bots-agentic-age/) |
| B1, B2, B6 | 2차 인용 | [출처](https://commercetools.com/blog/agentic-commerce-stats-enterprise-guide) |
| B3 | 2차 인용 | [출처](https://www.digitalapplied.com/blog/agentic-commerce-statistics-2026-data) |
| B4, B5 | 2차 인용 | [출처](https://www.metarouter.io/post/agentic-commerce-trends-statistics) |
| B7 | 2차 인용·추정 | [출처](https://www.digitalapplied.com/blog/agentic-commerce-statistics-2026-data) |
| C1 | 1차(보도자료) | [출처](https://www.marketsandmarkets.com/PressReleases/ai-for-customer-service.asp) |
| C2 | 2차 인용 | [출처](https://www.lorikeetcx.ai/articles/ai-customer-service-statistics) |
| C3 | 2차·원출처 미확인 | [출처](https://claw-ops.com/blog/korea-aicc-market) |
| D1 | 2차 | [출처](https://www.lorikeetcx.ai/articles/ai-customer-service-statistics) |
| D2 | 2차 인용 | [출처](https://www.kai-waehner.de/blog/2026/04/06/enterprise-agentic-ai-landscape-2026-trust-flexibility-and-vendor-lock-in/) |
| D3, G7 | 2차 | [출처](https://builts.ai/blog/ai-customer-service-trends-2026/) |
| E1 | 2차 | [출처](https://www.mavenagi.com/blog/cost-per-ticket-statistics-customer-support) |
| E2, E3, E4 | 2차·2차 인용 | [출처](https://www.dragapp.com/blog/state-of-ai-support-pricing/) |
| E5, G2 | 2차 | [출처](https://myaskai.com/blog/intercom-fin-ai-agent-complete-guide-2026) |
| F1, F2, F3 | 2차 인용 | [출처](https://thoughtminds.ai/blog/sovereign-ai-and-on-premise-llms) |
| F4 | 2차 | [출처](https://www.gooddata.ai/blog/data-sovereignty-and-ai-analytics-keep-your-llm-on-premise/) |
| G1 | 2차 | [출처](https://inkeep.com/blog/inkeep-vs-intercom-fin-ai) |
| G3 | 2차 | [출처](https://www.notch.cx/learn/deep-dive-comparison-for-enterprise-ai-customer-support) |
| G4 | 2차 | [출처](https://www.mavenagi.com/blog/decagon-alternatives) |
| G5 | 2차 | [출처](https://www.eesel.ai/blog/decagon-vs-sierra) |
| G6 | 2차 | [출처](https://www.getmacha.com/blog/decagon-ai-complete-guide) |
| H1 | 1차 | [출처](https://www.linuxfoundation.org/press/a2a-protocol-surpasses-150-organizations-lands-in-major-cloud-platforms-and-sees-enterprise-production-use-in-first-year) |
| H2 | 1차 | [출처](https://cloud.google.com/blog/products/ai-machine-learning/announcing-agents-to-payments-ap2-protocol) |
| H3 | 1차 | [출처](https://developers.googleblog.com/under-the-hood-universal-commerce-protocol-ucp/) |
| H4 | 1차 | [출처](https://shopify.engineering/ucp) |
| H5 | 1차 | [출처](https://platform.claude.com/docs/en/docs/mcp) |
| I1 | 미분류 | [출처](https://www.poweredbysearch.com/blog/how-to-design-b2b-saas-product-pages-with-examples/) |
| I2 | 미분류 | [출처](https://www.kalungi.com/blog/how-to-write-your-product-marketing-one-pager-template) |
| I3 | 미분류 | [출처](https://www.saashero.net/content/b2b-saas-marketing-collateral-templates/) |
