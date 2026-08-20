# 공공데이터포털 — 소비자 민원·피해구제 데이터 7종

## 출처 및 다운로드 방법

전부 `data.go.kr`, 승인·로그인 불필요. 페이지의 "다운로드" 버튼이 JS로
`atchFileId`/`fileDetailSn`을 알아낸 뒤
`https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId={id}&fileDetailSn={n}&insertDataPrcus=N`
로 실제 파일을 받는 구조다. 대부분은 페이지 HTML의 schema.org
`DataDownload.contentUrl`에 이미 노출돼 있어 `curl`로 바로 받았고, 2건
(15098320, 15090382)은 그 값이 없어 브라우저에서 실제 다운로드 버튼의
`fn_fileDataDown()` 호출을 그대로 재현(`/tcs/dss/selectFileDataDownload.do`
POST)해 `atchFileId`를 알아낸 뒤 받았다.

다운로드일: 2026-08-20

## ★인코딩 주의 — EUC-KR(CP949)다, UTF-8 아니다

전부 CSV(1건은 XML)인데 **EUC-KR/CP949로 인코딩**돼 있다. UTF-8로 그냥
열면 헤더부터 깨진다(직접 확인함). 전처리 스크립트를 쓸 때
`encoding='cp949'` 또는 `encoding='euc-kr'`로 읽어야 한다.

## 받은 파일 7종

| 파일 | 원 데이터셋 | 건수(카탈로그 표기) | 실제 용량 | 주요 필드(헤더에서 직접 확인) |
|---|---|---:|---:|---|
| `15098340_online_commerce_complaints.csv` | 공정위 15098340, 온라인 상거래 소비자상담 내역 | 736,806 | 91MB | ACCIDENT_NO, RCPT_YMD, GENDER_CODE, AGE_GROUP_CODE, AREA_CODE, ITEM_CODE, ITEM_NAME, ACCIDENT_TITLE, PRCS_RESULT_CODE, PRCS_RESULT |
| `15098320_risk_hazard_complaints.csv` | 공정위 15098320, 위해위험 소비자상담 내역 | 129,759 | 106MB | ACCIDENT_NO, RCPT_YMD, ITEM_CODE, COUNTRY_PRODUCTION_CODE, CTRT_AMOUNT, SALES_METHOD_CODE, ACCIDENT_TITLE, **ACCIDENT_CONTENT(사건내용 원문)**, **ANS_CONTENT(답변내용 원문)** — 7종 중 유일하게 자유서술 본문+답변이 둘 다 있다 |
| `15098349_regional_complaints.csv` | 공정위 15098349, 지역별 소비자 상담내역 | 3,321,133 | 64MB | ACCIDENT_NO, RCPT_YMD, GENDER_CODE, AGE_GROUP_CODE, AREA_CODE, ITEM_CODE, ITEM_NAME, ACCIDENT_TITLE, PRCS_RESULT_CODE, PRCS_RESULT_NAME |
| `15098336_specialist_complaints.csv` | 공정위 15098336, 전문상담 내역 | 191,408 | 21MB | ACCIDENT_NO, RCPT_YMD, PROFESSIONAL_DSCSN_RESULT, ITEM_CODE, ITEM_NAME, ACCIDENT_TITLE, PRCS_RESULT_CODE, PRCS_RESULT — 의료/금융/자동차 중심, 쇼핑몰과 무관 |
| `3040720_relief_info.csv` | 한국소비자원 3040720, 소비자 피해구제 정보 | 16,802 | 1.5MB | 사건번호, 접수일, 성별, 연령대, 지역, 판매방법, 물품명, 청구이유 — 2026-05-27 최신(분기갱신) |
| `15145204_faq.csv` | 한국소비자원 15145204, 피해구제·분쟁조정 FAQ | 50 | 21KB | 번호, 질문, 답변 |
| `15090382_item_relief_cases.xml` | 한국소비자원 15090382, 품목별 피해구제 사례 | 678 | 1.4MB | Excel XML(mso-application), 품목·출처·제목·질문·답변 |

## ★가장 중요한 발견 — 자유서술 본문+답변이 있는 건 15098320 하나뿐

다운로드 전 카탈로그 조사 때는 15098340(온라인 상거래, 73만건)이 최우선
후보였는데, **실제로 열어보니 15098340엔 ACCIDENT_CONTENT/ANS_CONTENT
필드가 없다** — 제목·품목·처리결과 코드만 있고 자유서술 상담 본문이
없다. 반대로 15098320(위해위험, 13만건)은 온라인 상거래로 좁혀지진
않지만 **사건내용·답변내용 원문이 둘 다 있다.** 즉:

- **분류체계·규모 학습**(성별/연령/지역/품목 분포, 도메인이 온라인
  상거래로 명시)용으로는 15098340·15098349가 낫다.
- **감성분석·응답생성 학습**(실제 문장, GEN/REV용)에 쓸 수 있는 원문
  텍스트는 15098320이 사실상 유일하다. 온라인 상거래 건만 골라내려면
  SALES_METHOD_CODE 필드로 필터링해야 하는데, 코드값 매핑표는 아직
  못 찾았다 — 다음 단계로 남긴다.

## 아직 안 한 것

- 압축 해제 불필요(이미 CSV/XML 원본)이지만 **CP949→UTF-8 재인코딩,
  컬럼 정의서 대조, SALES_METHOD_CODE 코드값 매핑**은 안 함
- 15098320에서 온라인 쇼핑몰 관련 건만 필터링하는 작업 안 함
- `processed/`, `scripts/` 없음 — 전부 `raw/`만 있는 상태
