# Commerce datasets 배포본

배포 ZIP은 재현 코드, 스키마, 문서와 쿠팡 `raw`/`processed` 산출물을 포함한다.

쿠팡 확장 출력은 수취인·전화번호·상세주소·우편번호를 수집 결과에서 이미 제거한다.
`build_distribution.py`는 최신 주문/배송 JSON 쌍과 `processed/*.jsonl`을 추가 마스킹 없이
원본 바이트 그대로 넣고, 압축 후 각 항목이 원본과 동일한지 검증한다.

다음 항목은 인증 정보 또는 불필요한 실측 자료를 포함할 수 있어 제외한다.

- 쿠팡의 MHTML/HTML 캡처, 실측 fixture, 과거 확장 백업
- 브라우저 프로필, 세션, 쿠키, `.env` 파일

쿠팡 로컬 전처리는 `python coupang_order_history/scripts/normalize.py`, 데이터 포함 배포 ZIP은
`python build_distribution.py`로 재생성한다.
