# 쿠팡 주문 카드 구조 (실측)

사용자가 제공한 주문 카드 outerHTML 1건에서 확인.

## 확인된 사실

- 클래스명이 styled-components 해시(`sc-5a139ee-5 dPHhOe`)라 **빌드마다 변한다.**
  클래스 기반 선택자는 쓰면 안 된다.
- 대신 안정적인 앵커가 있다:
  - 상품 링크: `a[href*="/ssr/sdp/link"]` + `sourceType=MyCoupang_my_orders_list_product_title`
  - 상품 이미지 링크: `sourceType=MyCoupang_my_orders_list_product_image`
  - `vendorItemId=` 쿼리 파라미터
  - 상품명: 그 링크 안의 `<span>` 텍스트, 그리고 `<img alt="해태 허니버터칩, 120g, 1개">`
  - 카드 루트: `<td>`

## 실측 값

| 항목 | 값 | 위치 |
|---|---|---|
| 주문상태 | 상품준비중 | 카드 상단 `<span style="font-size:1.25rem">` |
| 배송예정 | 내일(금) 새벽 도착 보장 | `color="#008C00"` span |
| 상품명 | 해태 허니버터칩, 120g, 1개 | 링크 내 span, img alt에도 동일 |
| 금액 | 2,420 원 | `translate="yes"` span |
| 수량 | 1개 | 금액 뒤 span |
| vendorItemId | 76676260659 | 링크 href 쿼리 |

## 이 카드에 없는 것

주문번호, 주문일시, 판매자명, 배송비, 총액, 택배사, 송장번호, 배송지.
목록 카드에는 없고 주문 상세로 들어가야 할 가능성이 높다.

## 선택자 전략

해시 클래스 대신 다음을 쓴다.
- 카드: `td` 중 `a[href*="MyCoupang_my_orders_list_product_title"]`를 포함하는 것
- 상품명: `img[alt]`의 alt (가장 안정적) 또는 링크 내 span 텍스트
- 금액: `span[translate="yes"]` 텍스트에서 숫자 추출
- 수량: 금액 span의 다음 형제 span 중 `N개` 패턴
- 상태: 카드 내 `span[style*="font-size:1.25rem"]`
- vendorItemId: href에서 정규식 추출
