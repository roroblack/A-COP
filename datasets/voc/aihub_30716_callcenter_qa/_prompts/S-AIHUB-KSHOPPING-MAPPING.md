# S-AIHUB-KSHOPPING-MAPPING — K쇼핑 subset 추출 + A-COP 도메인 매핑

## 0. 배경 — 이미 확인된 사실 (Claude가 이번에 직접 확인함)

`raw/01.데이터/1.Training/라벨링데이터_231222_add/`와
`raw/01.데이터/2.Validation/`(같은 배치명으로 있는지 확인해라) 안에
K쇼핑 도메인 zip 7개가 **이미 카테고리별로 분리돼 있다** — 별도
필터링 작업 없이 파일명만으로 K쇼핑 subset을 골라낼 수 있다:

```
민원(콜센터) 질의응답_K쇼핑_AS_Training.zip       (644K)
민원(콜센터) 질의응답_K쇼핑_결제_Training.zip     (8.0M)
민원(콜센터) 질의응답_K쇼핑_교환_Training.zip     (4.3M)
민원(콜센터) 질의응답_K쇼핑_반품_Training.zip     (2.6M)
민원(콜센터) 질의응답_K쇼핑_배송_Training.zip     (4.0M)
민원(콜센터) 질의응답_K쇼핑_업무처리_Training.zip (7.8M)
민원(콜센터) 질의응답_K쇼핑_주문_Training.zip     (7.1M)
```

★같은 배치(`_231222_add`)에 질병관리본부 도메인 zip도 섞여 있다 —
파일명에 `K쇼핑`이 없는 건 전부 무시해라. 다른 배치
(`_220121_add`, `_220125_add`)엔 K쇼핑이 없거나(전자) 파일이 없고
readme만 있다(후자, `쇼핑/` 폴더 확인해봐라) — 실제 K쇼핑 데이터는
`_231222_add`에만 있다.

각 zip 안에는 JSON 파일 1개가 있고, 최상위가 리스트다. 각 원소는
이런 필드를 가진다(주문 zip 첫 행 실측, 필드명은 한글이니 그대로
써라 — 영문으로 바꾸지 마라):

```json
{
  "도메인": "K쇼핑", "카테고리": "주문", "통화아이디전화번호": "S23241",
  "화자": "상담사", "회차번호": "1", "고객질문": "", "고객요청": "",
  "QA": "A", "고객질문(요청)": "", "고객의도": "",
  "상담사답변": "", "상담사답변": "행복한 하루 되는 하루입니다. ",
  "대체어": "행복, 되세요, 하시고요", "상담사의도": "",
  "화행베이스": "인사표현/일반인사, 응답표현/응답"
}
```

★필드명은 zip마다·행마다 조금씩 다를 수 있다(예: 고객 turn엔
`고객의도`가 채워지고 상담사 turn엔 `상담사의도`가 채워지는 식) —
**실제 데이터를 열어서 진짜 필드 구조를 스크립트 짜기 전에 먼저
파악해라.** 위 예시를 맹신하지 마라, 이건 딱 1개 행만 본 것이다.

각 파일은 개별 QA턴 단위로 보인다(181,081행이 "주문" 카테고리
하나에 있음, `통화아이디전화번호`+`회차번호`로 같은 대화를 묶을 수
있을 걸로 보인다 — 확인해라).

## 1. 목표 매핑 (A-COP 실제 taxonomy, `app/modules/customer_ops/feedback.py`
   — final_project_cs 저장소에 있다, 경로 확인해라)

```python
INTENTS = {"order", "shipping", "return", "exchange", "other"}
ISSUE_CODES = {
    "order_payment_failed", "order_duplicate_charge", "order_change_or_cancel", "order_other",
    "shipping_delayed", "shipping_delivered_not_received", "shipping_other",
    "return_quantity_exceeded", "return_fee_or_period", "return_other",
    "exchange_stock_or_period", "exchange_other",
    "other",
}
```

## 2. 할 일

### 2.1 카테고리 → intent 결정론적 매핑

```
주문     → order
배송     → shipping
반품     → return
교환     → exchange
결제     → order        (결제 실패·중복결제 등은 order.payment_* issue_code로 세분화)
AS       → 매핑하지 않는다(아래 참고)
업무처리 → 매핑하지 않는다(아래 참고)
```

`AS`/`업무처리`는 A-COP의 5개 intent 어디에도 깔끔히 안 들어간다.
**억지로 `other`에 다 몰아넣지 마라** — 두 카테고리를 최종
processed 산출물에서 **제외**해라(수량은 REPORT.md에 남겨서 나중에
필요하면 다시 꺼낼 수 있게 해라). 이건 이미 사전 조사에서 내려진
권고다: "AS/업무처리 물량(10만+14만 쌍)이 깔끔히 안 매핑되면 억지로
`other`에 넣는 대신 빼는 게 낫다."

### 2.2 issue_code 매핑 — 샘플링 + 군집화

각 zip(AS/업무처리 제외 5개)에서 **고객 turn만**(화자가 고객인 행,
`고객의도` 또는 `고객질문(요청)`이 채워진 행) 300건씩 무작위
샘플링해라(seed 고정, 재현 가능하게). 샘플의 `고객의도`(또는 동등
필드) 자유텍스트를 읽고, 위 §1의 issue_code 중 하나로 군집화해라.

- 명확히 매칭되면 그 issue_code를 붙여라.
- 애매하면 억지로 끼워맞추지 말고 `issue_code: null` + 원본
  `고객의도` 문자열을 그대로 남겨라(이 프로젝트가 이미 여러 번 쓴
  탈출구 패턴이다 — golden.jsonl 재라벨링 작업들도 같은 원칙을
  따랐다).
- 카테고리(결제/교환 등)와 issue_code 접두어(order_*/exchange_* 등)가
  안 맞는 조합은 만들지 마라(예: "배송" 카테고리 행에
  `return_other`를 붙이지 마라).

### 2.3 산출물

`datasets/voc/aihub_30716_callcenter_qa/processed/` 아래:

- `kshopping_sample.jsonl` — 위 5개 카테고리 × 300건(고객 turn) 샘플,
  스키마: `{"source_category": "...", "customer_turn_text": "...",
  "mapped_intent": "...", "mapped_issue_code": "..." 또는 null,
  "raw_intent_field": "..." (원본 고객의도/질문 원문 그대로)}`.
  PII는 이 데이터에 원래 없어 보이지만(전화번호 필드가 있다면 마스킹
  없이 원문인지 확인해라 — 있으면 `datasets/README.md`의 PII 원칙대로
  마스킹하거나 제거해라).
- `category_mapping.json` — §2.1의 결정론적 매핑 + §2.2 군집화에서
  실제로 어떤 고객의도 패턴이 어떤 issue_code로 갔는지 요약(예:
  `{"issue_code": "shipping_delayed", "matched_patterns": ["배송이 늦어요", "출고가 안 됐어요", ...]}`).
- `stats.json` — 카테고리별 원본 전체 행 수, 고객 turn 수, 샘플링
  수, issue_code별 매핑 성공/실패(null) 개수, AS/업무처리 제외 수.
- `scripts/extract_and_map.py` — 이 전체 처리를 재현 가능한
  스크립트로 만들어라(zip 압축 해제 → 필드 파싱 → 매핑 → 샘플링 →
  출력). 다른 이 프로젝트 seed/처리 스크립트 스타일을 참고해라
  (`datasets/commerce/coupang_order_history/` 등 기존 데이터셋의
  `scripts/`가 있으면 그 스타일을 따라라).
- `REPORT.md` — 이 폴더 기존 `REPORT.md`를 갱신해라(덮어쓰지 말고
  "아직 안 한 것" 섹션을 "완료" 섹션으로 바꾸고 이번 작업 내용을
  추가해라). 카테고리별 전체 건수, AS/업무처리 제외 이유, issue_code
  매핑 성공률(샘플 기준), 한계(전수 매핑이 아니라 샘플 기반이라는 것)를
  정직하게 적어라.

## 3. 검증

- `python -c "import json; [json.loads(l) for l in open('datasets/voc/aihub_30716_callcenter_qa/processed/kshopping_sample.jsonl', encoding='utf-8')]"`
  같은 방식으로 산출물이 유효한 JSONL인지 확인해라.
- `mapped_intent`가 전부 `{order,shipping,return,exchange}` 중
  하나인지 확인해라(AS/업무처리 제외했으니 `other`도 없어야 정상 —
  있으면 왜 있는지 설명해라).
- `mapped_issue_code`가 null이 아닐 때 전부 §1의 `ISSUE_CODES`
  집합 안에 있는지 확인해라.
- `stats.json`의 숫자가 실제 zip 파일 행 수와 맞는지(최소
  order/shipping/return/exchange 4개 카테고리는) 다시 세어 확인해라.

## 4. 하지 말 것

- `final_project_cs/eval/datasets/golden.jsonl`이나
  `holdout.jsonl`을 이 데이터로 **자동으로 채우거나 병합하지 마라**
  — 이건 별도의, 더 신중한 결정이 필요한 작업이다. 이번 계약은
  `datasets/voc/aihub_30716_callcenter_qa/processed/`까지만 만든다.
- `final_project_cs/` 안의 어떤 파일도 건드리지 마라 — 이 계약은
  `datasets/voc/aihub_30716_callcenter_qa/` 안에서만 작업한다(단,
  `app/modules/customer_ops/feedback.py`는 taxonomy를 확인하려고
  **읽기만** 해라).
- AS/업무처리를 강제로 `other`에 매핑하지 마라(§2.1).
- 원본 zip(`raw/`)을 수정·삭제하지 마라 — 읽기만 한다.
- 전체 55만 건을 다 처리하려 하지 마라(시간 낭비다) — §2.2가 명시한
  카테고리당 300건 샘플로 충분하다.
