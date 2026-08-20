# datasets/

외부에서 가져온 실 데이터 산출물을 두는 곳이다. `program/research/`는 **조사
문서**(요약·법령원문·사례)이고, 여기는 **데이터 파일 자체**(원본 + 전처리
결과 + 재현 스크립트)다.

## 구조 규칙

```
datasets/<도메인>/<데이터셋명>/
  raw/          원본 그대로 (가공 금지, 재현/재검증의 기준점)
  processed/    전처리 결과
  scripts/      raw → processed 를 만든 스크립트 (재실행 가능해야 함)
  REPORT.md     출처·라이선스·전처리 통계·검증 로그
  preprocess_stats.json  같은 정보를 스크립트가 읽을 수 있는 형태로도
```

- `raw/`는 절대 손으로 고치지 않는다. 다시 받아야 하면 `REPORT.md`의 출처
  정보로 재현한다.
- 새 데이터셋을 추가할 때마다 이 README에 한 줄씩 등록한다.
- 라이선스가 불명확하거나 재배포 제한이 있는 데이터는 `raw/`를 통째로
  두지 말고 `REPORT.md`에 "어디서 어떻게 받았는지"만 남긴다(재현 경로만
  기록, 데이터 자체는 미보관).

## 등록된 데이터셋

| 경로 | 내용 | 출처 | 라이선스 | 수집일 |
|---|---|---|---|---|
| `commerce/naver_order_history/` | 네이버 주문·배송 이력, Commerce Ops Pack 전처리용 (크롤링 진행 전, 정규화 파이프라인만 구성) | 팀 내부 네이버 주문내역 크롤러 출력 | 개인 데이터, 재배포 금지 | 진행 중 |
| `commerce/courier_tracking/` | 공개 택배 조회 페이지에서 단계별 배송 이력을 수집하는 Playwright 어댑터와 결과 스키마 | CJ대한통운·롯데택배·한진택배·로젠택배·우체국택배 공개 조회 페이지 | 택배사별 이용 조건 확인 필요 | 진행 중 |
| `voc/naver_shopping_sentiment/` | 네이버쇼핑 리뷰 199,908건, 긍정/부정 이분류(별점 3 없음) | [bab2min/corpus](https://github.com/bab2min/corpus) `sentiment/naver_shopping.txt` | Public Domain | 2026-08-20 |
| `mt/olist_reviews_mt_bench/` | Olist 리뷰 300쌍 기준 번역모델 15종 PT→EN/PT→KO 벤치마크 (둘 다 완료) | [Olist Brazilian E-Commerce](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) (원문) + 팀 내 en-translated(출처 미확인) | CC BY-NC-SA 4.0 (원문) | 2026-08-20 |
| `voc/aihub_71603_aspect_sentiment/` | 속성기반 감정분석(상품 리뷰, 원천+라벨링 원본 zip, 미압축해제), 63MB | AI Hub `dataSetSn=71603` | R&D 무료(상업 임베드 별도협의) | 2026-08-20 |
| `voc/aihub_30716_callcenter_qa/` | 민원 콜센터 QA 라벨링데이터만(음성 원천 제외), 83MB | AI Hub `dataSetSn=98`(구 `aidata/30716`) | AI Hub 표준 | 2026-08-20 |
| `voc/aihub_71844_llm_instruction_tuning/` | 민간 민원상담 LLM instruction tuning용, 원천+라벨링 원본 zip, 209MB | AI Hub `dataSetSn=71844` | AI Hub 표준 | 2026-08-20 |
| `voc/data_go_kr_consumer_complaints/` | 공정위·한국소비자원 소비자상담 7종(73만/13만/332만/19만/1.7만/50/678건), EUC-KR 인코딩. 자유서술 사건내용+답변 원문은 15098320 하나뿐 | data.go.kr (공정거래위원회·한국소비자원) | 승인 불필요, 이용허락범위 제한 없음 | 2026-08-20 |
| `voc/aihub_102_smb_order_qa/` | 소상공인 고객 주문 질의응답, 라벨링데이터만(원본 zip, 미압축해제), 189MB. 원 데이터셋 500만건(백화점·홈쇼핑·e-commerce 콜센터, 감성+인텐트+개체명) | AI Hub `dataSetSn=102` | AI Hub 표준 | 2026-08-20 |
| `voc/kaggle_customer_support/` | Kaggle 5종(CRM티켓·이커머스리뷰100K·감성데이터셋·IT티켓·KR3 한국음식점리뷰), 463MB. 스키마·번역 재료용, 학습 본체 아님 | Kaggle (각 슬러그는 REPORT.md 참고) | MIT/Apache 2.0/CC BY 4.0 4종 + KR3만 **CC BY-NC-SA 4.0**(비영리 제한) | 2026-08-20 |

## 등록된 조사 카탈로그 (raw/processed 없음 — 아직 안 받은 후보 소스 목록)

| 경로 | 내용 | 수집일 |
|---|---|---|
| `voc/sources_catalog/` | 모두의말뭉치(신청 필요)·HuggingFace 파인튜닝 감성모델 4종+KOTE·리뷰스팸탐지 설계논의 조사. AI Hub 4종·Kaggle 5종 전부 다운로드 완료돼 위 표로 이동함 | 2026-08-20 |
