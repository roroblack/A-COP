# 택배 배송 이력 조회

네이버 택배조회 내부 API를 사용해 택배 배송 이력을 JSONL로 저장한다. 택배사별 HTML 파서는 `legacy/`에 보관한다.

## 동작 방식

Playwright가 설치된 Chrome을 `channel="chrome"`으로 연다. 네이버 검색 페이지 HTML에서 `passportKey`를 얻는다. 같은 페이지에 JSONP 스크립트 태그를 주입해 조회한다. `fetch`는 사용하지 않는다.

택배사 코드는 `courier_codes.json`에서 읽는다. `code`가 `null`인 선택 항목은 제외한다. 택배사명은 공백과 문장부호 및 대소문자 차이를 제거한 뒤 비교한다.

passportKey는 한 번 받아 재사용한다. `timeout`, `script_error`, `key_expired`가 연속 3회 발생하면 다음 조회 전에 키를 다시 얻는다.

## 설치

Python 3.10 이상과 Google Chrome이 필요하다.

```powershell
pip install playwright
```

별도 로그인과 인증 코드는 사용하지 않는다.

## 사용법

단일 송장 조회:

```powershell
cd datasets/commerce/courier_tracking/scripts
python track.py --courier CJ대한통운 --number 540885631633
```

네이버 주문 파일 전체 조회:

```powershell
python track.py --from-orders ../../naver_order_history/raw/<파일>.json
```

중단한 당일 작업 재개:

```powershell
python track.py --from-orders ../../naver_order_history/raw/<파일>.json --resume
```

기본 대기는 조회마다 2.0초에서 5.0초 사이에서 새로 선택한다. 옵션으로 범위를 바꿀 수 있다.

```powershell
python track.py --from-orders ../../naver_order_history/raw/<파일>.json --delay-min 2.5 --delay-max 6.0
```

최소값과 최대값은 모두 1.0초 이상이어야 한다.

## 입력 형식

JSON 배열과 JSONL을 지원한다. 객체 안의 `orders`, `items`, `data`, `results` 배열도 읽는다.

원본 주문의 `CourierCompany`, `TrackingNumber` 필드를 읽는다. 정규화된 `shipping.carrier`, `shipping.tracking_number` 필드도 읽는다.

## 출력

결과는 `raw/tracking_YYYY-MM-DD.jsonl`에 한 줄씩 즉시 추가한다. 진행 로그는 `raw/_track_log.txt`에 UTF-8로 기록한다. `--resume`은 당일 결과 파일에 있는 송장번호를 건너뛴다.

통계는 총 시도, 이력 있음, 이력 없음, 미지원 택배사, 오류를 표시한다. 이력 없음은 보관기간 만료 가능성이 있다.

오류 값은 다음과 같다.

| 값 | 의미 |
|---|---|
| `no_history` | `result`가 `Y`지만 배송 이력이 없음 |
| `not_found` | `result`가 `N`임 |
| `unsupported_courier` | 코드 목록에서 택배사명을 찾지 못함 |
| `timeout` | JSONP 응답이 12초 안에 오지 않음 |
| `script_error` | JSONP 스크립트 로드 또는 응답 파싱 실패 |
| `key_expired` | 응답에서 passportKey 만료 또는 무효 상태를 확인함 |

## 개인정보 제외

응답에서 새 결과 객체를 만들 때 허용한 필드만 복사한다. 배송 이벤트에는 `kind`, `where`, `timeString`, `time`, `level`만 저장한다.

전화번호와 배송기사 이름 및 사진은 저장하지 않는다. 발송인과 수취인 이름 및 주소도 저장하지 않는다. 상품명인 `itemName`은 `item_name`으로 저장한다.

## 테스트

테스트는 네트워크와 Playwright 없이 실행된다.

```powershell
python -m unittest discover -s scripts/tests -p "test_*.py"
```
