'use strict';

process.env.TZ = 'Asia/Seoul';

const assert = require('node:assert/strict');
const test = require('node:test');
const { parseFragment, TestElement } = require('./test-dom.js');
const {
  SELECTORS,
  buildExportPayloads,
  collectDetailsOnCurrentPage,
  extractYearTabs,
  findNextButton,
  findOrderTrackingAction,
  isOrderListPage,
  isPaginationButtonDisabled,
  mergeDetail,
  nearbyActionElement,
  parseDocument,
  parseDetailPage,
  parseProduct,
  parseTrackingPage,
  sanitizeValue
} = require('../content.js');

const ORDER_LIST_PAGE_HTML = `
<main>
  <nav><button>2026</button><button>2025</button></nav>
  <section><div>2026. 8. 20 주문</div><button>주문 상세보기</button></section>
  <footer><button>이전</button><button>다음</button></footer>
</main>`;

const ORDER_DETAIL_PAGE_HTML = `
<main>
  <h2>받는사람 정보</h2>
  <h2>결제 정보</h2>
  <button></button>
  <button>장바구니 담기</button>
  <button>취소 상세 보기</button>
  <button>카드영수증</button>
  <button>거래명세서</button>
  <button>주문목록 돌아가기</button>
  <button>주문 내역 삭제</button>
  <button></button>
</main>`;

test('목록 HTML만 주문 목록 페이지로 판정한다', () => {
  assert.equal(isOrderListPage(parseFragment(ORDER_LIST_PAGE_HTML)), true);
  assert.equal(isOrderListPage(parseFragment(ORDER_DETAIL_PAGE_HTML)), false);
});

test('상세 페이지의 버튼 목록에서 다음 버튼을 찾지 않는다', () => {
  assert.equal(findNextButton(parseFragment(ORDER_DETAIL_PAGE_HTML)), null);
});

const CARD_HTML = `
<td class="sc-5a139ee-5 dPHhOe">
  <span font-weight="bold" color="#111111" style="font-size:1.25rem" class="status">상품준비중</span>
  <span font-weight="normal" color="#008C00" class="notice">내일(금) 새벽 도착 보장</span>
  <a href="/ssr/sdp/link?vendorItemId=76676260659&amp;imagePath=x&amp;sourceType=MyCoupang_my_orders_list_product_image" target="_blank" class="image-link">
    <img loading="lazy" width="64" height="64" src="https://thumbnail.coupangcdn.com/product.jpg" alt="해태 허니버터칩, 120g, 1개">
  </a>
  <a href="/ssr/sdp/link?vendorItemId=76676260659&amp;sourceType=MyCoupang_my_orders_list_product_title" target="_blank" class="title-link">
    <img class="badge" height="16" src="badge.png" alt="RDS_LOGO_WOW_DAWN_MD">
    <span color="#111111" class="product-text">해태 허니버터칩, 120g, 1개</span>
  </a>
  <span translate="yes" class="price">2,420 원</span>
  <span class="quantity">1개</span>
  <button class="cart">장바구니 담기</button>
</td>`;

const PAGINATION_HTML = `
<div>
  <button class="sc-19a0c88a-0 boBywg sc-7a9dfa59-1 gULjxs" disabled="">
    <svg width="14" height="14" style="fill: rgb(170, 181, 192); transform: rotate(180deg);">
      <path d="M1 1"></path>
    </svg> 이전
  </button>
  <button class="sc-19a0c88a-0 boBywg sc-7a9dfa59-1 gULjxs">
    다음 <svg width="14" height="14" style="fill: rgb(170, 181, 192);"><path d="M1 1"></path></svg>
  </button>
</div>`;

test('공백과 SVG가 포함된 다음 버튼을 찾는다', () => {
  const root = parseFragment(PAGINATION_HTML);

  assert.equal(findNextButton(root), root.querySelectorAll('button')[1]);
});

test('이전 버튼을 다음 버튼으로 오인하지 않는다', () => {
  const root = parseFragment(PAGINATION_HTML.replace(/<button class="sc-19a0c88a-0 boBywg sc-7a9dfa59-1 gULjxs">[\s\S]*?<\/button>/, ''));

  assert.equal(findNextButton(root), null);
});

test('disabled 속성이 있는 페이지네이션 버튼을 비활성으로 판정한다', () => {
  const previousButton = parseFragment(PAGINATION_HTML).querySelectorAll('button')[0];

  assert.equal(isPaginationButtonDisabled(previousButton), true);
});

test('disabled 다음 버튼을 클릭 대상으로 사용하지 않도록 판정한다', () => {
  const root = parseFragment(PAGINATION_HTML.replace(
    '<button class="sc-19a0c88a-0 boBywg sc-7a9dfa59-1 gULjxs">',
    '<button class="sc-19a0c88a-0 boBywg sc-7a9dfa59-1 gULjxs" disabled="">'
  ));
  const nextButton = findNextButton(root);

  assert.equal(isPaginationButtonDisabled(nextButton), true);
});

test('뒤 공백이 있는 다음 버튼을 찾는다', () => {
  const root = parseFragment('<div><button>다음 </button></div>');

  assert.equal(findNextButton(root), root.querySelector('button'));
});

test('nbsp가 있는 다음 버튼을 찾는다', () => {
  const root = parseFragment('<div><button>다음\u00a0</button></div>');

  assert.equal(findNextButton(root), root.querySelector('button'));
});

test('href 없는 주문 상세보기 div에서 클릭 대상을 찾는다', () => {
  const card = parseFragment(`${CARD_HTML.replace('</td>', '')}<div class="detail-action"><span>주문 상세보기</span><svg></svg></div></td>`);
  const titleLink = card.querySelector(SELECTORS.productTitleLink);
  const target = nearbyActionElement(titleLink, ['주문상세보기', '주문상세', '상세보기']);

  // 클릭은 위로만 전파된다. 핸들러가 어느 조상에 붙었든 닿게 하려면 가장 안쪽을 눌러야 한다.
  assert.equal(target.tagName, 'SPAN');
  assert.equal(target.parentElement.getAttribute('class'), 'detail-action');
});

test('실제 주문 카드에서 상품 정보를 파싱한다', () => {
  const card = parseFragment(CARD_HTML);
  const titleLink = card.querySelector(SELECTORS.productTitleLink);
  const result = parseProduct(titleLink);

  assert.equal(result.ProductName, '해태 허니버터칩, 120g, 1개');
  assert.equal(result.ProductPrice, 2420);
  assert.equal(result.Quantity, 1);
  assert.equal(result.OrderStatus, '상품준비중');
  assert.equal(result.DeliveryStatus, '내일(금) 새벽 도착 보장');
  assert.equal(result.VendorItemId, '76676260659');
  assert.equal(result.ProductUrl.startsWith('https://www.coupang.com/'), true);
  assert.equal(result._idSource, 'derived');
});

test('상품명 span이 없으면 상품 이미지 alt를 사용한다', () => {
  const card = parseFragment(CARD_HTML);
  const titleLink = card.querySelector(SELECTORS.productTitleLink);
  titleLink.querySelector('span').ownText = '';

  const result = parseProduct(titleLink);

  assert.equal(result.ProductName, '해태 허니버터칩, 120g, 1개');
  assert.notEqual(result.ProductName, 'RDS_LOGO_WOW_DAWN_MD');
});

const CANCELLED_ORDER_HTML = `
<div>
  <div>
    <div>2021. 8. 27 주문</div>
    <div><span>주문 상세보기</span><svg></svg></div>
  </div>
  <div>
    <table><tbody><tr><td>
      <span style="font-size:1.25rem">취소완료</span>
      <a><img alt="헤이맨 아이패드 프로 M1 5세대 12.9인치 투명 케이스"></a>
      <a><span>헤이맨 아이패드 프로 M1 5세대 12.9인치 투명 케이스</span></a>
      <span translate="yes">6,900 원</span>
      <span>1개</span>
    </td></tr></tbody></table>
  </div>
</div>`;

test('href 없는 취소완료 주문 카드에서 상품 정보를 파싱한다', () => {
  const result = parseDocument(parseFragment(CANCELLED_ORDER_HTML)).orders[0];

  assert.match(result.ProductName, /^헤이맨 아이패드 프로 M1/);
  assert.equal(result.ProductPrice, 6900);
  assert.equal(result.Quantity, 1);
  assert.equal(result.OrderStatus, '취소완료');
});

test('목록 헤더에서 주문일을 파싱한다', () => {
  const result = parseDocument(parseFragment(CANCELLED_ORDER_HTML)).orders[0];

  assert.equal(result.OrderedAt, '2021-08-27');
});

test('한 주문 카드의 여러 상품 블록을 각각 수집한다', () => {
  const html = CANCELLED_ORDER_HTML.replace('</td></tr>', `
    </td><td>
      <span style="font-size:1.25rem">취소완료</span>
      <img alt="두 번째 상품">
      <span translate="yes">12,000 원</span><span>2개</span>
    </td></tr>`);
  const orders = parseDocument(parseFragment(html)).orders;

  assert.equal(orders.length, 2);
  assert.equal(orders[1].ProductName, '두 번째 상품');
  assert.equal(orders[1].ProductPrice, 12000);
  assert.equal(orders[1].Quantity, 2);
});

test('연도 탭에서 4자리 연도만 순서대로 추출한다', () => {
  const root = parseFragment(`<div>
    <div>최근 6개월</div><div>2026</div><div>2025</div><div>2024</div>
    <div>2023</div><div>2022</div><div>2021</div>
  </div>`);

  assert.deepEqual(extractYearTabs(root), [2026, 2025, 2024, 2023, 2022, 2021]);
});

const DETAIL_HTML = `
<div>
  <strong>2026. 8. 20 주문</strong>
  <div>주문번호 16102412730885</div>
  <span style="font-size:1.25rem">배송완료</span>
  <table>
    <tbody>
      <tr><td>
        <a href="/ssr/sdp/link?vendorItemId=76676260659&amp;sourceType=MyCoupang_order_detail_product_title">
          <span>해태 허니버터칩, 120g, 1개</span>
        </a>
        <span translate="yes">2,420 원</span><span>1개</span>
      </td></tr>
    </tbody>
  </table>
  <table>
    <tbody>
      <tr><td>총 상품가격</td><td><strong translate="yes">2,420 원</strong></td></tr>
      <tr><td>배송비</td><td><span translate="yes">0 원</span></td></tr>
      <tr><td>결제수단</td><td>쿠팡캐시</td></tr>
      <tr><td>총 결제금액</td><td><strong translate="yes">2,420 원</strong></td></tr>
    </tbody>
  </table>
  <table>
    <tbody>
      <tr><td>받는사람</td><td>최*우</td></tr>
      <tr><td>연락처</td><td>010****7059</td></tr>
      <tr><td>받는주소</td><td>(06725) 서울특별시 서초구 남부순환로339길 ** ***호</td></tr>
      <tr><td>배송요청사항</td><td>새벽 : 문 앞 (자유 출입가능)</td></tr>
    </tbody>
  </table>
  <a href="/ssr/desktop/order/delivery/tracking/16102412730885"><button>배송 조회</button></a>
</div>`;

const TRACKING_HTML = `
<div>
  <div>어제(목) 도착 완료</div>
  <table>
    <tbody>
      <tr><td>로켓배송</td></tr>
      <tr><td>송장번호</td><td>10327825750572</td></tr>
    </tbody>
  </table>
  <table>
    <thead><tr><th>시간</th><th>현재위치</th><th>배송상태</th></tr></thead>
    <tbody>
      <tr><td>어제 23:07</td><td>안양1</td><td>배송완료</td></tr>
      <tr><td>어제 21:32</td><td>안양1</td><td>배송출발</td></tr>
      <tr><td>어제 20:50</td><td>안양1</td><td>캠프도착</td></tr>
    </tbody>
  </table>
  <table><tbody>
    <tr><td>받는사람</td><td>최*우</td></tr>
    <tr><td>연락처</td><td>010****7059</td></tr>
    <tr><td>받는주소</td><td>서울특별시 서초구 남부순환로339길</td></tr>
    <tr><td>상품수령방법</td><td>문앞 전달</td></tr>
  </tbody></table>
</div>`;

test('실측 상세 HTML 조각에서 주문번호와 결제정보를 파싱한다', () => {
  const result = parseDetailPage(parseFragment(DETAIL_HTML), 'https://mc.coupang.com/ssr/desktop/order/detail/1');

  assert.equal(result.OrderId, '16102412730885');
  assert.equal(result._idSource, 'orderNumber');
  assert.equal(result.OrderedAt, '2026-08-20');
  assert.equal(result.OrderStatus, '배송완료');
  assert.equal(result.products[0].ProductName, '해태 허니버터칩, 120g, 1개');
  assert.equal(result.products[0].ProductPrice, 2420);
  assert.equal(result.products[0].Quantity, 1);
  assert.equal(result.TotalProductAmount, 2420);
  assert.equal(result.ShippingFee, 0);
  assert.equal(result.TotalAmount, 2420);
  assert.equal(result.PaymentMethod, '쿠팡캐시');
  assert.equal(result.DeliveryRegion, '서울특별시 서초구');
  assert.equal(result.DeliveryRequest, '새벽 : 문 앞 (자유 출입가능)');
  assert.match(result._TrackingUrl, /delivery\/tracking/);
});

test('상세 파싱 결과로 목록의 대체 주문 ID를 실제 주문번호로 교체한다', () => {
  const listCard = parseFragment(CARD_HTML);
  const order = parseProduct(listCard.querySelector(SELECTORS.productTitleLink));
  const detail = parseDetailPage(parseFragment(DETAIL_HTML));

  assert.equal(order._idSource, 'derived');
  mergeDetail(order, detail);
  assert.equal(order.OrderId, '16102412730885');
  assert.equal(order._idSource, 'orderNumber');
});

test('실측 배송조회 HTML 조각에서 송장과 배송 이력 3건을 파싱한다', () => {
  const collectedAt = new Date('2026-08-21T10:00:00+09:00');
  const result = parseTrackingPage(parseFragment(TRACKING_HTML), collectedAt);

  assert.equal(result.CourierCompany, '로켓배송');
  assert.equal(result.TrackingNumber, '10327825750572');
  assert.equal(result.ShipmentStarted, true);
  assert.equal(result.DeliveryPromise, '어제(목) 도착 완료');
  assert.equal(result.TrackingEvents.length, 3);
  assert.deepEqual(result.TrackingEvents[0], {
    timeString: new Date('2026-08-20T23:07:00+09:00').toISOString(),
    where: '안양1',
    kind: '배송완료'
  });
  assert.equal(result.TrackingEventRaw[0], '어제 23:07');
  assert.equal(result.ReceiptMethod, '문앞 전달');
  assert.deepEqual(result.Warnings, []);
});

const PRE_SHIPMENT_TRACKING_HTML = `
<div>
  <div>내일(토) 새벽 7시 전 도착 보장</div>
  <div>고객님이 주문하신 상품이 준비시작되었습니다.</div>
  <section>
    <div>결제완료</div><div>상품준비중</div><div>배송시작</div><div>배송중</div><div>배송완료</div>
  </section>
  <table><tbody>
    <tr><td>로켓배송</td></tr>
    <tr><td>송장번호</td><td>   </td></tr>
  </tbody></table>
</div>`;

test('실측 배송 전 화면을 경고가 아닌 정상 상태로 파싱한다', () => {
  const result = parseTrackingPage(
    parseFragment(PRE_SHIPMENT_TRACKING_HTML),
    new Date('2026-08-21T10:00:00+09:00'),
    '상품준비중'
  );

  assert.equal(result.TrackingNumber, null);
  assert.equal(result.ShipmentStarted, false);
  assert.equal(result.TrackingStatus, '아직 배송이 시작되지 않아 이력이 없습니다.');
  assert.equal(result.DeliveryPromise, '내일(토) 새벽 7시 전 도착 보장');
  assert.equal(result.DeliveryMessage, '고객님이 주문하신 상품이 준비시작되었습니다.');
  assert.deepEqual(result.DeliverySteps, ['결제완료', '상품준비중', '배송시작', '배송중', '배송완료']);
  assert.equal(result.DeliveryStepIndex, 1);
  assert.deepEqual(result.TrackingEvents, []);
  assert.deepEqual(result.Warnings, []);
});

test('송장번호가 있는데 이력 표가 없을 때만 실제 경고를 남긴다', () => {
  const html = PRE_SHIPMENT_TRACKING_HTML.replace('<td>   </td>', '<td>10327825750572</td>');
  const result = parseTrackingPage(parseFragment(html), new Date(), '상품준비중');

  assert.equal(result.ShipmentStarted, true);
  assert.deepEqual(result.Warnings, ['배송 이력 표를 찾지 못했습니다.']);
});

test('알 수 없는 상대 시각은 원문을 남기고 경고한다', () => {
  const html = TRACKING_HTML.replaceAll('어제 23:07', '2일 전 23:07');
  const result = parseTrackingPage(parseFragment(html), new Date('2026-08-21T10:00:00+09:00'));

  assert.equal(result.TrackingEvents[0].timeString, '2일 전 23:07');
  assert.equal(result.TrackingEventRaw[0], '2일 전 23:07');
  assert.match(result.Warnings[0], /변환하지 못했습니다/);
});

test('PII 필드는 선택하지 않고 일반·마스킹 휴대폰번호도 제거한다', () => {
  const detail = parseDetailPage(parseFragment(DETAIL_HTML));
  const tracking = parseTrackingPage(parseFragment(TRACKING_HTML), new Date('2026-08-21T10:00:00+09:00'));
  const protectedResult = sanitizeValue({ detail, tracking, defense: ['010-1234-5678', '010****7059'] });
  const json = JSON.stringify(protectedResult);

  assert.equal(json.includes('최*우'), false);
  assert.equal(json.includes('010****7059'), false);
  assert.equal(json.includes('남부순환로339길'), false);
  assert.deepEqual(protectedResult.defense, ['[제거됨]', '[제거됨]']);
});

test('주문 JSON과 배송 JSON을 분리한다', () => {
  const exports = buildExportPayloads([{
    OrderId: '16102412730885', CourierCompany: '로켓배송', TrackingNumber: '10327825750572',
    DeliveryStatus: '배송완료', TrackingEvents: [{ kind: '배송완료', where: '안양1', timeString: '2026-08-20T14:07:00.000Z' }],
    TrackingEventRaw: ['어제 23:07'], Warnings: []
  }], {
    exportedAt: '2026-08-21T01:00:00.000Z', collectionScope: 'tracking', pageCount: 1, warning: null
  });

  assert.equal(exports.orderData.orders[0].TrackingEvents, undefined);
  assert.equal(exports.orderData.orders[0].TrackingEventRaw, undefined);
  assert.equal(exports.orderData.orders[0].TrackingNumber, '10327825750572');
  assert.deepEqual(exports.trackingData, [{
    courier: '로켓배송', tracking_number: '10327825750572', order_id: '16102412730885', status: '배송완료',
    events: [{ kind: '배송완료', where: '안양1', timeString: '2026-08-20T14:07:00.000Z', raw: '어제 23:07' }],
    queried_at: '2026-08-21T01:00:00.000Z'
  }]);
});

test('발송 전 주문은 배송 JSON에서 제외하고 배송 완료 주문만 포함한다', () => {
  const beforeShipment = {
    OrderId: 'before', OrderStatus: '상품준비중',
    ...parseTrackingPage(parseFragment(PRE_SHIPMENT_TRACKING_HTML), new Date(), '상품준비중'),
    _TrackingOutcome: 'preShipment'
  };
  const completed = {
    OrderId: 'completed', OrderStatus: '배송완료',
    ...parseTrackingPage(parseFragment(TRACKING_HTML), new Date('2026-08-21T10:00:00+09:00'), '배송완료'),
    _TrackingOutcome: 'collected'
  };
  const exports = buildExportPayloads([beforeShipment, completed], {
    exportedAt: '2026-08-21T01:00:00.000Z', collectionScope: 'tracking', pageCount: 1, warning: null
  });

  assert.equal(exports.trackingData.length, 1);
  assert.equal(exports.trackingData[0].order_id, 'completed');
  assert.equal(exports.orderData.orders[0].ShipmentStarted, false);
  assert.equal(exports.orderData.orders[0].DeliveryStepIndex, 1);
  assert.equal(exports.trackingSummary.preShipment, 1);
});

// ── 사용자 실측 HTML: 한 주문에 상품 2개가 같은 td 안 형제 블록으로 들어있는 경우 ──
const REAL_TWO_ITEM_HTML = `
<div>
  <div>
    <div>2026. 8. 20 주문</div>
    <div><span>주문 상세보기</span></div>
  </div>
  <table><tbody><tr>
    <td>
      <div><div><span style="font-size:1.25rem">취소완료</span></div></div>
      <div>
        <div class="gvWLHD">
          <a><img width="64" height="64" src="a.jpg" alt="누아트 에어팟프로2 / 프로 이어팁 호환 실리콘 이어팁 4개입, 1개, NATET-M"></a>
          <a><img height="16" src="fresh.png" alt="ROCKET_FRESH"><span>누아트 에어팟프로2 / 프로 이어팁 호환 실리콘 이어팁 4개입, 1개, NATET-M</span></a>
          <a><div><span translate="yes">5,080 원</span><span>1개</span></div></a>
        </div>
        <div class="gvWLHD">
          <a><img width="64" height="64" src="b.jpg" alt="모아바이오팜 당도선별 샤인머스캣, 1개, 1.5kg"></a>
          <a><img height="16" src="fresh.png" alt="ROCKET_FRESH"><span>모아바이오팜 당도선별 샤인머스캣, 1개, 1.5kg</span></a>
          <a><div><span translate="yes">14,440 원</span><span>1개</span></div></a>
        </div>
      </div>
    </td>
    <td><div><button>취소 상세 보기</button></div></td>
  </tr></tbody></table>
</div>`;

test('실측: 한 td 안 형제 블록의 상품 2개를 각각 분리한다', () => {
  const orders = parseDocument(parseFragment(REAL_TWO_ITEM_HTML)).orders;

  assert.equal(orders.length, 2);
  assert.ok(orders[0].ProductName.includes('누아트 에어팟프로2'), `첫 상품: ${orders[0].ProductName}`);
  assert.ok(orders[1].ProductName.includes('샤인머스캣'), `둘째 상품: ${orders[1].ProductName}`);
  assert.equal(orders[0].ProductPrice, 5080);
  assert.equal(orders[1].ProductPrice, 14440);
  assert.equal(orders[0].Quantity, 1);
  assert.equal(orders[1].Quantity, 1);
  for (const order of orders) {
    assert.equal(order.OrderStatus, '취소완료');
    assert.equal(order.OrderedAt, '2026-08-20');
  }
});

const TWO_TRACKING_CARDS_HTML = `
<div>
  <div>
    <div>2026. 8. 20 주문</div><div><span>주문 상세보기</span></div>
    <img alt="첫 상품"><span translate="yes">1,000 원</span>
    <button>배송 조회</button><button>첫 카드 전용</button>
  </div>
  <div>
    <div>2026. 8. 19 주문</div><div><span>주문 상세보기</span></div>
    <img alt="둘째 상품"><span translate="yes">2,000 원</span>
    <button>배송조회</button><button>둘째 카드 전용</button>
  </div>
</div>`;

test('목록의 해당 주문 카드 안에서만 배송 조회 버튼을 찾는다', () => {
  const root = parseFragment(TWO_TRACKING_CARDS_HTML);
  const orders = parseDocument(root).orders;
  const first = findOrderTrackingAction(root, orders[0]);
  const second = findOrderTrackingAction(root, orders[1]);

  assert.equal(first.textContent.trim(), '배송 조회');
  assert.equal(second.textContent.trim(), '배송조회');
  assert.notEqual(first, second);
});

test('배송 조회가 없는 취소완료 카드는 null과 구분된 사유를 남긴다', async () => {
  const root = parseFragment(CANCELLED_ORDER_HTML);
  const order = parseDocument(root).orders[0];

  assert.equal(findOrderTrackingAction(root, order), null);
  await collectDetailsOnCurrentPage([order], 'tracking', new Date(), 1, new Set(), 0, 0, {
    getDocument: () => root,
    findOrderDetailAction: () => null,
    returnToOrderList: async () => true,
    randomDelay: async () => {},
    reportProgress: () => {}
  });
  assert.ok(order.Warnings.includes('배송 조회 버튼이 없는 주문입니다(취소/환불 등).'));
});

test('상세 진입이 실패해도 목록의 배송 조회를 시도한다', async () => {
  const order = { OrderId: 'test-order', Warnings: [], TrackingEvents: [], TrackingEventRaw: [] };
  const detailTarget = { kind: 'detail' };
  const trackingTarget = { kind: 'tracking' };
  const clicked = [];

  await collectDetailsOnCurrentPage([order], 'tracking', new Date('2026-08-21T10:00:00+09:00'), 1, new Set(), 0, 0, {
    getDocument: () => ({}),
    getLocationHref: () => 'https://mc.coupang.com/ssr/desktop/order/list',
    findOrderDetailAction: () => detailTarget,
    findOrderTrackingAction: () => trackingTarget,
    clickAndWait: async (target) => {
      clicked.push(target.kind);
      return target.kind === 'tracking';
    },
    parseTrackingPage: () => ({
      CourierCompany: '로켓배송', TrackingNumber: '123', TrackingEvents: [], TrackingEventRaw: [], Warnings: []
    }),
    returnToOrderList: async () => true,
    randomDelay: async () => {},
    reportProgress: () => {}
  });

  assert.deepEqual(clicked, ['detail', 'tracking']);
  assert.equal(order.TrackingNumber, '123');
  assert.match(order.Warnings[0], /주문 상세 수집 실패/);
});

test('실측: 미래 연도(2027)가 추가돼도 자동으로 포함된다', () => {
  // 사용자가 제공한 실제 연도 탭 구조 + 2027 추가 가정
  const root = parseFragment(`<div class="sc-6441a31c-0 uPEsB">
    <div width="72px" class="sc-6441a31c-1 bFUExT">최근 6개월</div>
    <div class="sc-6441a31c-1 erAJoq">2027</div>
    <div class="sc-6441a31c-1 erAJoq">2026</div>
    <div class="sc-6441a31c-1 gUoxrz">2025</div>
    <div class="sc-6441a31c-1 gUoxrz">2024</div>
    <div class="sc-6441a31c-1 gUoxrz">2023</div>
    <div class="sc-6441a31c-1 gUoxrz">2022</div>
    <div class="sc-6441a31c-1 gUoxrz">2021</div>
  </div>`);

  const years = extractYearTabs(root);
  assert.deepEqual(years, [2027, 2026, 2025, 2024, 2023, 2022, 2021]);
  assert.ok(!years.includes(NaN), '최근 6개월은 제외돼야 한다');
  assert.equal(years.length, 7);
});

// ── 실측 형태 C: 배송중 (송장 있음 + 이력 있음 + 미완료) ──
const REAL_IN_TRANSIT_HTML = `
<div class="my-area-contents">
  <div>배송 조회</div>
  <div><div>오늘 도착 보장</div><div>고객님의 상품을 배송중입니다.</div></div>
  <div>
    <div><div></div><div>결제완료</div><div></div></div>
    <div><div></div><div>상품준비중</div><div></div></div>
    <div><div></div><div>배송시작</div><div></div></div>
    <div><div></div><div>배송중</div><div></div></div>
    <div><div></div><div>배송완료</div><div></div></div>
  </div>
  <table><tbody><tr><td><table><tbody>
    <tr><td>로켓배송</td></tr>
    <tr><td>송장번호</td><td>10327825290451</td></tr>
  </tbody></table></td>
  <td><table><tbody>
    <tr><td>받는사람</td><td>최*우</td></tr>
    <tr><td>배송요청사항</td><td>문 앞</td></tr>
  </tbody></table></td></tr></tbody></table>
  <div><table>
    <thead><tr><th>시간</th><th>현재위치</th><th>배송상태</th></tr></thead>
    <tbody>
      <tr><td>오늘 09:11</td><td>안양1</td><td>배송출발</td></tr>
      <tr><td>오늘 08:36</td><td>안양1</td><td>캠프도착</td></tr>
    </tbody>
  </table></div>
</div>`;

test('실측 형태 C: 배송중은 발송됨이되 완료가 아니다', () => {
  const t = parseTrackingPage(parseFragment(REAL_IN_TRANSIT_HTML), '2026-08-21T10:00:00+09:00');

  assert.equal(t.TrackingNumber, '10327825290451', '송장번호');
  assert.equal(t.CourierCompany, '로켓배송');
  assert.equal(t.ShipmentStarted, true, '송장이 있으므로 발송됨');
  assert.equal(t.TrackingEvents.length, 2, '이력 2건');
  assert.equal(t.TrackingEvents[0].kind, '배송출발');
  assert.equal(t.TrackingEvents[0].where, '안양1');
  assert.equal(t.DeliveryPromise, '오늘 도착 보장');

  const kinds = t.TrackingEvents.map((e) => e.kind);
  assert.ok(!kinds.includes('배송완료'), '아직 완료 이벤트가 없어야 한다');

  const json = JSON.stringify(t);
  assert.equal(json.includes('최*우'), false, 'PII 미포함');
});
