# 네이버 주문 이력 정규화

## 목적

네이버 주문 크롤러의 JSON 출력을 A-COP 주문 스키마에 맞는 JSONL로 변환한다.

기존 `order_schema.json`의 중첩 구조를 유지한다.

배송비는 `shipping.fee`에 저장한다.

선택한 배송 이력은 `shipping.events`에 저장한다.

## 실행

데이터셋 폴더에서 다음 명령을 실행한다.

```bash
python scripts/normalize.py
python scripts/validate.py
```

기본 실행은 `raw/` 바로 아래의 `*.json`만 읽는다.

`raw/`의 하위 폴더는 읽지 않는다.

바로 아래에 JSON 파일이 없으면 안내 메시지를 출력하고 종료한다.

특정 파일만 처리하려면 `--input`을 사용한다.

```bash
python scripts/normalize.py --input raw/_backup_v2/2026-08-20_68건.json
```

여러 입력에 같은 `OrderId`가 있으면 처음 나온 레코드만 출력한다.

택배 배송 이력을 결합하려면 `--with-tracking`을 사용한다.

```bash
python scripts/normalize.py --input raw/_backup_v2/2026-08-20_68건.json --with-tracking
```

이 옵션은 `../courier_tracking/raw/tracking_*.jsonl`을 읽는다.

`TrackingNumber`와 `tracking_number`를 비교한다.

파일이 없으면 배송 이력 결합을 건너뛴다.

## 필드 매핑

| 정규화 필드 | 크롤러 필드 |
|---|---|
| `payment.amount` | `TotalAmount` |
| `payment.paid_at` | `OrderedAt` |
| `product.unit_price` | `ProductPrice` |
| `product.total_price` | `ProductPrice * Quantity` |
| `product.quantity` | `Quantity` |
| `shipping.region` | `DeliveryRegion` |
| `shipping.carrier` | `CourierCompany` |
| `shipping.tracking_number` | `TrackingNumber` |
| `shipping.fee` | `ShippingFee` |
| `cs.purchase_confirmed_at` | `PurchaseConfirmedAt` |

`Quantity`가 없거나 유효하지 않으면 1을 사용한다.

상품명에서 수량을 추출하지 않는다.

이 경우 `quantity_missing_or_invalid:defaulted_to_1` 경고를 남긴다.

## 날짜 처리

`payment.paid_at`은 연도와 초가 있는 `OrderedAt`을 우선 사용한다.

결과는 KST 오프셋이 있는 ISO 8601 형식으로 저장한다.

`OrderedAt`이 없을 때만 `PaymentDate`를 사용한다.

`PaymentDate`의 연도는 입력 파일 수정 시각의 연도로 추정한다.

이 경우 `year_inferred:PaymentDate` 경고를 남긴다.

`PurchaseConfirmedAt`은 연도가 있는 날짜로 파싱한다.

시각이 없으므로 KST 자정으로 저장한다.

`DeliveryCompleteDate`는 연도가 없다.

같은 레코드의 `OrderedAt` 연도로 먼저 만든다.

시각 없이 전달 방식만 있는 값은 KST 자정으로 저장한다.

만든 배송 완료일이 주문일보다 이르면 다음 해로 보정한다.

연도를 추정한 레코드에는 `year_inferred:DeliveryCompleteDate` 경고를 남긴다.

## 개인정보 처리

수령인 이름, 전화번호, 상세 주소에 해당하는 원본 필드는 출력에 복사하지 않는다.

해당 값은 `_source.pii_hashes`에 SHA-256 해시만 저장한다.

`DeliveryRegion`은 시·군·구 수준의 지역으로 `shipping.region`에 저장한다.

원본 주문 데이터가 있는 `raw/` 파일은 공개 저장소에 커밋하지 않는다.

## 파일

- `order_schema.json`: JSON Schema draft-07 스키마
- `raw/`: 크롤러 원본 입력
- `processed/orders.jsonl`: 정규화 결과
- `scripts/normalize.py`: 정규화 도구
- `scripts/validate.py`: 스키마 검증 도구
