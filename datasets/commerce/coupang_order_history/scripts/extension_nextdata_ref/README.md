# 쿠팡 주문내역 추출 확장 프로그램

이미 로그인된 Chrome의 쿠팡 주문목록을 읽어 로컬 JSON 파일로 저장한다.

화면 DOM(자동생성 클래스)에 의존하지 않고, 서버가 페이지에 심어주는 `__NEXT_DATA__`
JSON을 읽는다. 2026-08 실제 주문목록 페이지 구조를 기준으로 작성했다.

로그인 정보는 다루지 않는다. 외부 서버로 수집 결과를 전송하지 않는다.

## 왜 확장 방식인가

쿠팡은 Playwright 같은 자동화 브라우저를 차단한다. 전용 프로필, 로그인 페이지 직접
접근, 기존 Chrome 프로필 재사용을 모두 시도했으나 로그인 단계에서 막혔다. 확장은
사용자의 실제 Chrome 안에서 확장 API로 동작하므로 그 차단과 무관하다.

## 동작 방식

- 주문목록은 Next.js 서버렌더(SSR) 페이지다. 서버가 페이지 HTML 안에
  `<script id="__NEXT_DATA__">` 로 주문 데이터를 통째로 심어준다. `content.js`가
  `props.pageProps.domains.desktopOrder.orderList`를 읽어 주문·상품 정보를 뽑는다.
- 페이지 이동은 URL 쿼리 `pageIndex`(0부터)와 `year`로 한다.
  예: `https://mc.coupang.com/ssr/desktop/order/list?pageIndex=1&year=2026`.
  각 URL이 서버렌더되어 `__NEXT_DATA__`도 그 페이지 내용으로 갱신된다.
- 확장은 `orderPagination`(`hasNext`/`nextPageIndex`/`nextYear`)을 읽어 다음 페이지
  URL을 만든다. **자동 수집**은 페이지마다 3~7초 랜덤 대기하며 끝까지 넘기고, **수동**은
  버튼으로 한 페이지씩 넘긴다. 자동이라도 실제 Chrome의 일반 SSR 페이지 로드이며,
  헤드리스 브라우저나 자동화 프레임워크가 아니다.
- 수집한 주문은 누적 전체와 비교해 **중복을 자동 제거**한다. 쿠팡 목록은 마지막 페이지
  다음에 1페이지로 되돌아오는(wrap) 경우가 있는데, 신규 0건이면 자동으로 멈춘다.
- 기간(최근 6개월/연도)은 확장의 **기간** 드롭다운으로 고른다. 자동 수집은 그 기간의
  서버렌더 URL(연도는 `?requestYear=YYYY`, 최근 6개월은 파라미터 없음)로 먼저 이동한 뒤,
  연도 선택 시 `requestYear`를 그 연도로 고정해 페이지를 넘긴다. 화면의 연도 탭 클릭은
  URL만 바꾸고 초기 SSR(`__NEXT_DATA__`)은 그대로라, 확장은 URL을 직접 로드해서 쓴다.

## 설치 방법

1. Chrome 주소창에 `chrome://extensions`를 입력한다.
2. 오른쪽 위의 **개발자 모드**를 켠다.
3. 왼쪽 위의 **압축해제된 확장 프로그램을 로드**를 누른다.
4. 파일 선택 창에서 이 `scripts/extension/` 폴더를 선택한다.
5. 확장 프로그램 목록에 **쿠팡 주문내역 추출**이 표시되는지 확인한다.
6. Chrome 도구 모음의 퍼즐 아이콘을 누르고 **쿠팡 주문내역 추출**을 고정한다.

파일을 수정한 뒤에는 `chrome://extensions`에서 확장의 새로고침 버튼을 눌러야 한다.

## 팀원 배포

이 `extension/` 폴더를 그대로 공유한다(zip 등). 각자 위 **설치 방법**대로 압축해제 로드하고,
본인 쿠팡 계정으로 로그인해 자기 주문내역만 수집한다.

- 확장은 외부 서버로 아무것도 전송하지 않는다. 수집 결과는 각자 로컬 JSON으로만 저장된다.
- 자동 수집도 페이지마다 3~7초 랜덤 대기하며 실제 Chrome으로 페이지를 로드한다(헤드리스/자동화 프레임워크 아님).
- 서로의 계정·데이터에 접근하지 않는다. 각자 내려받은 JSON을 모아서 합친다.

## 사용 방법

### 자동 수집 (권장)

1. 평소 사용하는 Chrome에서 쿠팡에 로그인한다.
2. `https://mc.coupang.com/ssr/desktop/order/list`로 이동한다.
3. 확장 아이콘을 누르고, **기간** 드롭다운에서 "최근 6개월" 또는 연도를 고른다.
4. **자동 수집 (끝까지)**를 누른다. 선택한 기간의 1페이지부터 3~7초 랜덤 대기하며 끝까지
   모은다. 진행 중 **팝업을 닫지 않는다**(닫으면 멈춘다). 중간에 세우려면 **중지**.
5. "…에 주문이 없습니다" / "끝까지 수집했습니다" / "마지막 페이지"가 나오면 끝이다.
6. **JSON 내려받기** → 파일을 `datasets/commerce/coupang_order_history/raw/`에 넣는다.

다른 기간도 모으려면 **기간**을 바꾸고 다시 **자동 수집**을 누른다. 이미 모은 주문과 겹쳐도
중복 없이 새 것만 추가된다.

> 페이지에 있는 연도 **탭을 직접 클릭해도 기간이 바뀌지 않는다.** 그 클릭은 화면만 바꾸고
> 서버 데이터(`__NEXT_DATA__`)는 그대로라, 반드시 확장의 **기간** 드롭다운을 써야 한다.

### 수동 수집

**기간**을 고르고 **기간 열기**로 해당 기간을 연 뒤, **이 페이지만 수집** →
**다음 페이지로 이동**을 반복한다.

누적 데이터는 브라우저에 저장되어 팝업을 닫거나 페이지를 넘겨도 유지된다. 처음부터
다시 하려면 **초기화 (처음부터)**를 누른다. 같은 내용은 다시 눌러도 중복 저장되지 않는다.

## 수집 항목

주문·배송그룹·상품을 펼쳐 상품 한 줄을 한 레코드로 저장한다. 주요 키:

- `OrderId`, `OrderedAt`(한국시간)
- `SellerName`, `ProductName`, `Quantity`
- `UnitPrice`(정가), `ProductPrice`(결제 단가), `ShippingFee`, `OrderTotalProductPrice`
- `DeliveryStatus`(한글), `DeliveryStatusCode`(원문 코드), `DeliveryMessage`(예: "8/13(목) 도착")
- `DeliveryCompleteDate`(실제 배송완료 시각), `CourierCompany`, `TrackingNumber`
- `ProductUrl`
- `DeliveryRegion`: 항상 `null` (아래 PII 정책 참고)

### 출력 예시

`JSON 내려받기`로 저장되는 파일 형태:

```json
{
  "exportedAt": "2026-08-21T07:22:03.123Z",
  "source": "https://mc.coupang.com/ssr/desktop/order/list",
  "pageCount": 12,
  "orderCount": 85,
  "orders": [
    {
      "OrderId": "14102237452389",
      "OrderedAt": "2026-08-12 14:07:32",
      "SellerName": "쿠팡(주)",
      "ProductName": "동원샘물 무라벨, 500ml, 60개",
      "Quantity": 1,
      "UnitPrice": 12940,
      "ProductPrice": 12680,
      "ShippingFee": 0,
      "OrderTotalProductPrice": 12940,
      "DeliveryStatus": "배송완료",
      "DeliveryStatusCode": "FINAL_DELIVERY",
      "DeliveryMessage": "8/13(목) 도착",
      "DeliveryCompleteDate": "2026-08-13 10:59:06",
      "CourierCompany": "로켓배송",
      "TrackingNumber": "10327104342063",
      "ProductUrl": "https://www.coupang.com/vp/products/7869554357?vendorItemId=86493937835",
      "DeliveryRegion": null
    }
  ]
}
```

분리배송으로 한 주문이 여러 박스로 나뉘면, 같은 `OrderId`에 `TrackingNumber`만 다른
레코드가 여러 줄 생긴다. 값을 못 찾은 필드는 `null`이 된다.

## PII 정책 (수집하지 않는 항목)

다음 항목은 `__NEXT_DATA__`에 들어있어도 **읽지 않는다**. `content.js`의 매핑은
아래 필드를 아예 참조하지 않는다.

- 수취인 이름·전화·상세주소·동/호수·우편번호 (`order.deliveryDestination`)
  - 참고: 목록 페이지 JSON엔 이 값들이 애초에 비어 있다(전부 `null`). 실제 주소는
    상세페이지에만 있으나, 상세페이지는 조회하지 않는다.
- 판매자 담당자 이름·주소·전화 (`vendor.repPersonName`, `vendor.repAddr*`, `vendor.repPhoneNum`)
- 사업자등록번호 (`vendor.businessNumber`)
- 택배사 전화번호·배송조회 URL (`deliveryCompany.phoneNumber`, `deliveryCompany.trackingUrl`)
- 상품 썸네일·배지 이미지 URL (`imagePath`, `badgeImageUrl`)

`DeliveryRegion`은 항상 `null`이다. 주소에서 지역을 잘라내는 처리도 하지 않는다.

상품명·판매자명 같은 자유 텍스트에는 휴대폰번호 정규식을 적용해, 발견되면 `[제거됨]`으로
바꾼다. 운송장번호는 숫자라 이 치환을 적용하지 않는다.

수집 결과는 각자 브라우저에만 저장되고 외부로 전송되지 않는다.

## 주의

자동 수집은 페이지마다 3~7초 랜덤 대기하며 실제 Chrome으로 일반 페이지를 로드한다.
대기 시간(`AUTO_MIN_DELAY`/`AUTO_MAX_DELAY`)을 임의로 크게 줄이지 않는다. 한 번에 과도하게
많은 페이지를 조회하지 않는다.

쿠팡 목록은 "최근 6개월"·연도 필터에 따라 페이지가 나뉘고, 마지막 페이지 뒤 1페이지로
되돌아오는(wrap) 경우가 있다. 확장은 누적 전체와 비교해 중복을 제거하고, 신규 0건이면
자동으로 멈춘다(안전 상한 `MAX_AUTO_PAGES`).

쿠팡 페이지 구조나 `__NEXT_DATA__` 스키마가 바뀌면 `content.js`의 매핑을 다시 확인한다.

이 확장은 로그인·인증을 수행하지 않고, 브라우저 식별 정보를 변경하지 않는다.
