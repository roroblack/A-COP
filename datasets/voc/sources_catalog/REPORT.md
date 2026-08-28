# VOC 데이터·모델 소스 카탈로그 (조사, 2026-08-20)

이 폴더는 다른 `datasets/<도메인>/<이름>/`과 다르다 — **아직 받지 않은 후보
소스들의 조사 결과**다. `raw/`·`processed/`가 없는 이유: 여기 나열된 것 중
실제로 다운로드까지 끝낸 건 `datasets/voc/naver_shopping_sentiment/` 하나뿐이고,
나머지는 신청 절차가 필요하거나(로그인 필요, 내가 대신 못 함) 참고용으로만
쓰기로 방침이 정해진 것들이다. 실제로 받으면 그때 자기 폴더로 독립시킨다.

## 데이터셋

| 소스 | 내용 | 접근 상태 | 비고 |
|---|---|---|---|
| **AI Hub 71603** | 속성기반 감성분석, 상품 리뷰 약 25만건. BIO 태깅(스팬 단위 — 암묵적 속성어 케이스 포함) | **다운로드 완료**(2026-08-20) | → [`datasets/voc/aihub_71603_aspect_sentiment/`](../aihub_71603_aspect_sentiment/) |
| **AI Hub 30716** | 민원(콜센터) 질의응답 — 110만 QA쌍 + 440시간 음성, 텍스트 전사 약 2.2만건. 2020년 구축, 2023-12 최종 업데이트. 도메인 구성: K쇼핑 55만·질병관리본부 25만·금융보험 20만·다산콜센터 10만(합계 110만) | **다운로드 완료**(2026-08-20, 라벨링데이터만 — 음성 원천 제외) | → [`datasets/voc/aihub_30716_callcenter_qa/`](../aihub_30716_callcenter_qa/) |
| **AI Hub 71844** | 민간 민원상담 LLM 사전학습·Instruction Tuning용, 원천데이터 12,303건 + 라벨링 132,401건(500자+/3턴+). 수집처: 하나카드 58.01%·LG유플러스 33.17%·액티벤처 8.82% | **다운로드 완료**(2026-08-20) | → [`datasets/voc/aihub_71844_llm_instruction_tuning/`](../aihub_71844_llm_instruction_tuning/) |
| **모두의말뭉치 개체명분석** | 이름·전화번호·주소 패턴 | **다운로드 완료**(2026-08-23, 사용자 직접) | → [`datasets/voc/nikl_ne_2022/`](../nikl_ne_2022/). REV(응답 검증)의 PII 필터 개선용 — [`법령원문`](../../../program/research/_법령원문_2026-08-20.md)의 개인정보보호법 제2조 가목(성명·주민등록번호 등)과 직결 |
| **bab2min/corpus naver_shopping** | 네이버쇼핑 리뷰 199,908건(전처리 완료) | **다운로드·전처리 완료** | → [`datasets/voc/naver_shopping_sentiment/`](../naver_shopping_sentiment/) 실제 폴더 참고 |
| **AI Hub 102** (소상공인 고객 주문 질의-응답 텍스트) | 500만 건(콜센터 400만+녹취기반 100만). 백화점·홈쇼핑·e-commerce 콜센터 포함. 감성(긍/중/부정)+인텐트+개체명 라벨 동시 보유 | **다운로드 완료**(2026-08-20, 사용자 직접) | → [`datasets/voc/aihub_102_smb_order_qa/`](../aihub_102_smb_order_qa/) |
| **공정위·한국소비자원 7종** (15098340 온라인상거래·15098320 위해위험·15098349 지역별·15098336 전문상담·3040720 피해구제정보·15145204 FAQ·15090382 품목별사례) | 합계 약 440만 행. 자유서술 사건내용+답변 원문은 15098320 하나뿐 | **다운로드 완료**(2026-08-20) | → [`datasets/voc/data_go_kr_consumer_complaints/`](../data_go_kr_consumer_complaints/) — EUC-KR 인코딩 주의 |
| **KOTE (Korean Online Comments Emotions)** | 50,000개 댓글 → 250,000건 라벨(43감정+무감정), SNU 구축, LREC 2024 발표. `searle-j/kote`(HuggingFace) | 승인 불필요, `datasets` 라이브러리로 즉시 로드 가능 | 조사 중 발견한 감정 파인튜닝 모델 다수(GGARA02, tojoHere 등)가 이 데이터 기반 — 원본 자체가 더 유용할 수 있음 |

### Kaggle (참고용 방침 — 학습 데이터 본체로 안 씀, 스키마·분류체계 참고 또는 번역 재료용)

| 데이터셋 | URL | 규모 | 라이선스 | 상태 |
|---|---|---|---|---|
| ~~Customer Support Tickets Dataset (200K+)~~ | `mirzayasirabdullah07/customer-support-tickets-dataset-200k-records` | — | — | **죽은 링크**(2026-08-20 확인, "We can't find that page") — 대체 못 찾음 |
| Customer Support Tickets - CRM dataset | `ajverse/customer-support-tickets-crm-dataset` | 20,000건 합성, 12컬럼 | MIT | **다운로드 완료** |
| E-commerce Customer Reviews 100K reviews | `sergionefedov/e-commerce-customer-reviews-100k-reviews` | 100,000건, 제품 5,000개 | Apache 2.0 | **다운로드 완료** — sentiment+quality/shipping/value/service 속성+가짜리뷰 플래그까지 있어 스키마 참고로 최상급 |
| Customer Sentiment Dataset | `kundanbedmutha/customer-sentiment-dataset` | 25,000건 합성 | CC BY 4.0 | **다운로드 완료** |
| IT Support Tickets (synthetic) | `ahsanneural/synthetic-it-support-tickets` | 100,000건 합성 | CC BY 4.0 | **다운로드 완료** |
| KR3: Korean Restaurant Reviews with Ratings | `ninetyninenewton/kr3-korean-restaurant-reviews-with-ratings` | 460K+180K | **CC BY-NC-SA 4.0**(비영리, 실제 받아보고 확인) | **다운로드 완료** — 한국어 원문(음식점, 쇼핑몰 아님), 번역 없이 바로 쓸 수 있는 유일한 항목이나 라이선스가 비영리 제한 |

★2026-08-20, `kaggle` CLI + 사용자 발급 API 토큰으로 5개 실제 다운로드 완료 →
[`datasets/voc/kaggle_customer_support/`](../kaggle_customer_support/). 1개는
죽은 링크로 확인돼 못 받았다.

## 파인튜닝된 모델 (HuggingFace, 즉시 사용 가능 — 다운로드 승인 불필요)

| 모델 | 베이스 | 용도 |
|---|---|---|
| `alsgyu/sentiment-analysis-fine-tuned-model` | beomi/kcbert-base | 감성분석(긍정/부정/중립) |
| `rkdaldus/ko-sent5-classification` | KcBERT 계열 | 5종 감정분류(분노/두려움/기쁨/평온/슬픔) |
| `Jinuuuu/KoELECTRA_fine_tunning_emotion` | KoELECTRA | 6종 감정분류(분노/행복/불안/당황/슬픔/상처) |
| KoBERT 기반 감정분류(여러 공개 변형 존재) | KoBERT | 5종 감정분류(분노/두려움/기쁨/평온/슬픔) |

★**적용**: GEN(응답 생성)의 톤 프로파일 설계나 REV(응답 검증)의 "톤 적절성
사전 필터"에 바로 갖다 쓸 수 있는 수준 — 별도 파인튜닝 없이 참고/비교
기준선(baseline)으로 쓸 수 있다.

## 리뷰 신뢰도 체크 (가짜 리뷰/스팸 탐지) — 참고 자료만, 즉시 쓸 도구 없음

- 학술: KAIST·서울대의 국내 쇼핑사이트 대상 리뷰 스팸 탐지 논문(네이버쇼핑
  대상 성능평가 포함) — 방법론 참고용.
- 오픈소스: TF-IDF+로지스틱회귀 등 GitHub 프로젝트 다수 — 전부 영어 아마존
  리뷰 기준이라 구조만 참고 가능, 한국어 즉시 적용은 안 됨.
- 실사례 참고: 배달의민족은 리뷰 등록 즉시 AI로 허위 여부 실시간 판별한다는
  게 알려져 있다(국내 실서비스 사례로만 인용, 기술 상세는 비공개).

## 검증 방법 및 날짜

2026-08-20, WebSearch로 각 AI Hub 데이터셋 ID·구축연도·최신 업데이트일을
AI Hub 공식 페이지에서 직접 대조, bab2min/corpus는 GitHub README를 WebFetch로
직접 열어 라이선스 문구("Public Domain")를 원문 확인. 이후 "2026년 기준
더 나은 대안이 있는가"를 별도로 재검색했으나 이 카탈로그를 대체할 신규
항목은 없었다(단, 이커머스 상담용이 아닌 범용 오픈 LLM은 이 시기 다수
출시됨 — GEN 생성 베이스 모델 후보로는 별도 검토 대상, VOC 감성분류
용도와는 층위가 다르므로 이 카탈로그에는 넣지 않았다).

## 다음 단계 (미실행)

1. ~~AI Hub 71603/30716/71844 신청~~ — **완료.** 2026-08-20 다운로드까지
   끝났고 각자 독립 폴더로 옮겨졌다(위 표 링크 참고). 셋 다 아직 압축
   해제·전처리 전이다.
2. 모두의말뭉치 — 팀이 직접 로그인해 신청("개체명 분석 말뭉치" 2022,
   "개체 연결" 아닌 쪽으로 — `PLAN.md` 참고).
3. HuggingFace 파인튜닝 모델들은 다운로드 승인 불필요 — 실제로 GEN/REV
   파이프라인에 붙여볼지는 팀 판단 필요(현재는 후보 목록일 뿐, 통합 안 함).
