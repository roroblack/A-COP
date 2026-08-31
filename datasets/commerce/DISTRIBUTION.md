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

## `_dist/` 에 무엇이 있나

목적이 다른 세 종류가 있다. 섞어 쓰면 안 된다.

| 파일 | 무엇 | 만드는 명령 |
|---|---|---|
| `commerce_datasets_*.zip` | 재현 코드·스키마·문서 + 쿠팡 산출물 배포본 | `python build_distribution.py` |
| `team_submissions_*.zip` | **팀원 제출본 원본.** 바이트 그대로, 이름도 그대로 | `python build_team_submissions.py` |
| `team_naver_orders_*.jsonl`<br>`team_coupang_orders_*.jsonl`<br>`team_naver_tracking_*.jsonl`<br>`team_coupang_tracking_*.jsonl` | **제출본을 합친 파생본.** 쇼핑몰별 · 주문/배송별로 넷이다 | `python build_team_merged.py` |

합본 세 파일은 레코드마다 `_submitter`, `_platform`, `_source_file` 을 박아 둔다.
합치고 나면 어느 파일에서 온 줄인지 알 방법이 없어지기 때문이다.

2026-08-31 기준 건수는 이렇다.

| 파일 | 줄 수 |
|---|---:|
| 네이버 주문 | 270 |
| 쿠팡 주문 | 3,483 |
| 네이버 택배 배송 | 238 |
| 쿠팡 택배 배송 | 1,782 |
| 합계 | 5,773 |

★택배 배송을 쇼핑몰별로 나눈 이유는 **레코드 모양이 다르기 때문**이다.
네이버는 택배 조회 API 응답이라 `courier_code`·`level`·`estimate`·`error` 가 있고,
쿠팡은 자사 배송 데이터라 `shipment_box_id`·`order_id` 가 있다. 한 파일에 섞어 두면
읽는 쪽이 매번 `_platform` 으로 갈라야 하고, 없는 필드를 있는 줄 알고 쓴다.

### ★합본에서 가리는 것

쿠팡 `DeliveryRequest` 의 `기타사항 (…)` 안 자유입력을 가린다.

공동현관 비밀번호는 쿠팡이 `#****` 로 가려서 내보내는데 **이 자유입력은 안 가려진다.**
실측으로 `집앞우편함에열쇠로대문안에` 같은 **집 열쇠 위치가 51건** 들어 있었다.
같은 레코드에 `DeliveryRegion`(구 단위 배송지)이 있어서 그대로 쓸 수 있는 정보다.
팀 안에서 도는 파일이라도 넘기지 않는다.

가린 것은 `_masked` 필드에 이름으로 남긴다. 조용히 지우지 않는다.
원본이 필요하면 `build_team_merged.py --no-mask` 를 쓰거나 제출본 zip 을 본다.
**제출본 zip 은 가리지 않은 원본이다.**

### 저장소 밖으로 내보낼 때

`_dist/` 는 `.gitignore` 의 `datasets/**/*.zip` 과 `datasets/**/*.jsonl` 로 막혀 있어
커밋되지 않는다. 다만 손으로 내보낼 때는 아래 둘을 지우고 내보낸다.

- `DeliveryRegion` — 구 단위 배송지
- `DeliveryRequest` — 가려도 `문 앞`, `새벽 배송` 같은 생활 패턴이 남는다
