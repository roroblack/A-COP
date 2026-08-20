# Kaggle — 고객지원/이커머스 리뷰 5종 (스키마·번역 재료용, 학습 본체 아님)

## 방침

화요일 브리핑의 데이터 소싱 방침: 해외 Kaggle 데이터는 **스키마·분류체계
설계 참고용, 또는 번역해서 재료로 쓸 수 있는 후보**로만 다룬다. 학습
데이터 본체로 그대로 넣지 않는다(합성·영어 데이터가 대부분이라 도메인
불일치가 큼).

다운로드일: 2026-08-20. `kaggle` CLI(pip, v2.2.4) + 사용자가 발급한 API
토큰(`~/.kaggle/access_token`)으로 받았다.

## 원래 6개 중 1개는 죽은 링크였다

`mirzayasirabdullah07/customer-support-tickets-dataset-200k-records`
(Customer Support Tickets Dataset 200K+) — 브라우저로 직접 열어도
"We can't find that page." 삭제되었거나 비공개 전환된 것으로 보인다.
대체 데이터셋을 찾지 못했다 — 나머지 5개로 대신한다.

## 받은 5종

| 폴더 | Kaggle slug | 라이선스 | 용량 | 파일 |
|---|---|---|---|---|
| `customer-support-tickets-crm/` | `ajverse/customer-support-tickets-crm-dataset` | MIT | 4.5MB×2 | `customer_support_tickets.csv`, `enhanced_customer_support_data.csv` — 두 파일 크기가 동일해 내용도 같을 가능성 있음(미확인) |
| `ecommerce-customer-reviews-100k/` | `sergionefedov/e-commerce-customer-reviews-100k-reviews` | Apache 2.0 | 13.7MB | `reviews.csv`(주 파일, 13MB) + `products.csv`, `sellers.csv`, `sentiment_labels.csv`, `monthly_trends.csv` — 관계형 스키마로 나뉘어 있음 |
| `customer-sentiment-dataset/` | `kundanbedmutha/customer-sentiment-dataset` | CC BY 4.0 | 2.6MB | `Customer_Sentiment.csv` |
| `synthetic-it-support-tickets/` | `ahsanneural/synthetic-it-support-tickets` | CC BY 4.0 | 34.5MB | `synthetic_it_support_tickets.csv` |
| `kr3-korean-restaurant-reviews/` | `ninetyninenewton/kr3-korean-restaurant-reviews-with-ratings` | **CC BY-NC-SA 4.0** | 396MB(원본+raw 두 버전) | `kr3.tsv`(정제본), `kr3_raw.tsv`(원본) |

각 폴더 안에 `raw/`만 있고 `processed/`·`scripts/`는 없다 — 받기만 하고
아직 아무 전처리도 안 했다.

## ★KR3 라이선스 주의 — 이전 카탈로그 기재("확인 안 됨")보다 제약이 크다

`sources_catalog/REPORT.md`에는 KR3 라이선스를 "확인 안 됨"이라고 적어뒀는데,
실제로 받아보니 Kaggle 페이지에 **CC BY-NC-SA 4.0**(비영리·동일조건변경허락)
이 명시돼 있었다. A-COP이 실제로 상업 서비스라면 이 라이선스로는 학습
데이터에 그대로 못 쓸 수 있다 — 비영리 R&D/실험 단계에서만 쓰고, 실제
제품 파인튜닝에 넣기 전에 라이선스 재검토가 필요하다. 나머지 4개는
MIT/Apache 2.0/CC BY 4.0으로 전부 상업 이용에 제약이 적다.

## 한국어 여부

KR3만 한국어 원문(음식점 리뷰, 쇼핑몰 아님)이고 나머지 4개는 전부 영어
합성 데이터다. "번역해서 쓸 수도 있다"는 방향이면 이 4개가 번역 대상
후보이고, KR3는 번역 없이 바로 한국어 감성분류 사전학습 재료로 쓸 수
있다(라이선스 제약 하에).

## 아직 안 한 것

- 5종 전부 압축은 이미 풀려있지만(`--unzip`으로 받음) 스키마 분석·
  실제 컬럼 대조·A-COP 스키마(case_type/issue_code)와의 매핑은 안 함
- `customer-support-tickets-crm`의 두 CSV가 실제로 같은 내용인지 확인 안 함
- 번역 파이프라인 설계·실행 안 함
