# 구조 파악용 임시 스크립트

네이버페이 결제내역 페이지의 실제 DOM 구조와 조회 파라미터를 알아내려고 만든 일회성
스크립트다. 현재 수집에는 쓰지 않는다.

현행 파이프라인은 상위 폴더의 두 파일이다.

- `save_session.py` — 로그인 창을 열고 세션을 `naver_state.json`으로 저장한다.
- `naver_order_crawler.py` — 저장된 세션으로 주문내역을 수집한다.

## 각 파일이 무엇을 알아냈는가

| 파일 | 알아낸 것 |
|---|---|
| `inspect_page.py` | 결제내역 페이지의 카드 선택자 `li[class*="PaymentItem_item-payment"]` |
| `find_shopping_tab.py` | 쇼핑만 거르는 필터가 `serviceChannel=SHOPPING` 파라미터임 |
| `probe_shopping.py` | 페이지당 카드 약 15개, `page=N`으로 순회 가능 |
| `probe_detail.py` | 상세 페이지에 판매자명·수량·배송비·구매확정일이 있음 |
| `probe_period.py` | `startDate`/`endDate`는 인식되지만 함께 쓰면 `page`가 무시됨 |
| `open_login_window.py`, `keep_window_open.py`, `login_session.py` | 로그인 창을 여는 여러 시도. 브라우저 프로필은 비정상 종료 시 쿠키를 잃어 `storage_state` 파일 방식으로 바뀌었다 |

## 남겨둔 이유

페이지 구조가 바뀌어 크롤러가 깨지면 같은 방식으로 다시 조사해야 한다. 그때 참고한다.
