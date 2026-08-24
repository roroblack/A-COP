'use strict';

process.env.TZ = 'Asia/Seoul';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const { parseFragment } = require('./test-dom.js');
const {
  diagnoseStructure,
  isOrderListPage,
  listUrlForPage,
  ordersFromNextData,
  paginationFromNextData,
  parseDetailPage,
  parseTrackingPage,
  runStep,
  trackingUrlFor
} = require('../content.js');

const fixture = (name) => fs.readFileSync(path.join(__dirname, 'fixtures', name), 'utf8');
const detailHtml = fixture('order_detail_real.html');
const nextDataHtml = fixture('order_list_nextdata.html');
const trackingListHtml = fixture('order_list_tracking.html');

function asDocument(source, url, title = '') {
  const body = typeof source === 'string' ? parseFragment(source) : source;
  return {
    nodeType: 9,
    body,
    title,
    readyState: 'complete',
    location: { href: url },
    getElementById: (id) => body.querySelector(`#${id}`),
    querySelector: (selector) => body.querySelector(selector),
    querySelectorAll: (selector) => body.querySelectorAll(selector)
  };
}

function useDocument(source, url) {
  const document = asDocument(source, url);
  global.document = document;
  global.location = document.location;
  return document;
}

function stateAfterLastList(source, scope = 'tracking') {
  useDocument(source, 'https://mc.coupang.com/ssr/desktop/order/list');
  let state = { phase: 'INIT', scope, yearScope: 'current' };
  state = runStep(state).state;
  state = runStep(state).state;
  state = runStep(state).state;
  return state;
}

test('실측 상세 문서는 상품·할인·복합결제·배송정보를 정확히 읽는다', () => {
  const document = asDocument(detailHtml, 'https://mc.coupang.com/ssr/desktop/order/16102427880443');
  const detail = parseDetailPage(document, document.location.href);

  assert.equal(detail.OrderId, '16102427880443');
  assert.equal(detail.products.length, 1, '할인·배송비를 상품으로 오인했다');
  assert.equal(detail.products[0].ProductName, '이클립스 4가지 믹스팩 274g, 1개');
  assert.equal(detail.TotalProductAmount, 18400);
  assert.equal(detail.DiscountAmount, 5520);
  assert.equal(detail.ShippingFee, 0);
  assert.equal(detail.TotalAmount, 12880);
  assert.equal(detail.PaymentMethod, '삼성카드 / 일시불 + 쿠팡캐시');
  assert.deepEqual(detail.PaymentMethods, [
    { method: '삼성카드 / 일시불', amount: 9990 },
    { method: '쿠팡캐시', amount: 2890 }
  ]);
  assert.equal(detail.DeliveryRegion, '서울특별시 서초구');
  assert.equal(detail.DeliveryRequest, '새벽 : 문 앞 (자유 출입가능)');
});

test('실측 배송 진행 막대는 도달한 단계까지만 담는다', () => {
  const source = fixture('tracking_stepper_real.html');
  const document = asDocument(source, 'https://mc.coupang.com/ssr/desktop/shiptrack?orderId=1&shipmentBoxId=2');
  const tracking = parseTrackingPage(document, new Date('2026-08-21T12:00:00+09:00'), '배송중');

  assert.deepEqual(tracking.DeliveryStepsAll, ['결제완료', '상품준비중', '배송시작', '배송중', '배송완료']);
  assert.deepEqual(tracking.DeliverySteps, ['결제완료', '상품준비중', '배송시작']);
  assert.equal(tracking.DeliveryStep, '배송시작');
});

test('__NEXT_DATA__ 정확한 도메인에서 주문번호·송장번호·상품 행을 읽는다', () => {
  const document = asDocument(nextDataHtml, 'https://mc.coupang.com/ssr/desktop/order/list');
  const rows = ordersFromNextData(document);

  assert.equal(isOrderListPage(document), true);
  assert.equal(rows.length, 3);
  const chip = rows.find((row) => row.ProductName.includes('허니버터칩'));
  assert.equal(chip.OrderId, '16102412730885');
  assert.equal(chip.TrackingNumber, '10327825750572');
  assert.equal(chip.CourierCompany, '로켓배송');
  assert.equal(chip.OrderStatus, '배송완료');
  assert.equal(chip.ProductPrice, 2420);
  assert.equal(chip.OrderedAt, '2026-08-20');
  assert.equal(rows.filter((row) => row.OrderId === '16102412664912').length, 2);
});

test('__NEXT_DATA__ 페이지네이션 좌표를 추측하지 않고 그대로 읽는다', () => {
  const document = asDocument(nextDataHtml, 'https://mc.coupang.com/ssr/desktop/order/list');

  assert.deepEqual(paginationFromNextData(document), {
    hasNext: true,
    hasPrev: false,
    currentPageIndex: 0,
    nextPageIndex: 1,
    nextYear: null,
    prevYear: null
  });
  assert.equal(new URL(listUrlForPage(1)).searchParams.has('requestYear'), false);
  assert.equal(new URL(listUrlForPage(1, '2026')).searchParams.get('requestYear'), '2026');
});

test('구조 진단은 DOM 카드가 아니라 NextData와 페이지 좌표를 보고한다', () => {
  const document = asDocument(nextDataHtml, 'https://mc.coupang.com/ssr/desktop/order/list');
  const diagnosis = diagnoseStructure(document);

  assert.equal(diagnosis.isList, true);
  assert.equal(diagnosis.documentReady, true);
  assert.equal(diagnosis.nextDataFound, true);
  assert.equal(diagnosis.orderDomainFound, true);
  assert.equal(diagnosis.orderRows, 3);
  assert.equal(diagnosis.orderIds, 2);
  assert.equal(diagnosis.currentPageIndex, 0);
  assert.equal(diagnosis.nextPageIndex, 1);
  assert.equal(diagnosis.hasNext, true);
});

test('다음만 모드는 목록을 먼저 저장하고 requestYear 없이 다음 좌표로 간다', () => {
  useDocument(nextDataHtml, 'https://mc.coupang.com/ssr/desktop/order/list');
  let state = { phase: 'INIT', scope: 'tracking', yearScope: 'current' };
  state = runStep(state).state;
  state = runStep(state).state;
  const next = runStep(state);

  assert.equal(next.action.type, 'navigate');
  assert.equal(next.action.target, 'list');
  assert.equal(new URL(next.action.url).searchParams.get('pageIndex'), '1');
  assert.equal(new URL(next.action.url).searchParams.has('requestYear'), false);
  assert.equal(next.state.orders.length, 3);
  assert.equal(next.state.queue.length, 0, '목록 완료 전에 상세 큐를 만들었다');
});

test('다음만 모드는 nextYear를 필터로 바꾸지 않고 이미 읽은 pageIndex 좌표에서 목록을 끝낸다', () => {
  useDocument(nextDataHtml, 'https://mc.coupang.com/ssr/desktop/order/list?pageIndex=1');
  const step = runStep({
    phase: 'NEXT_PAGE', scope: 'tracking', yearScope: 'current',
    page: 2, pageCount: 2, orders: [], warnings: [], queue: [],
    listUrl: 'https://mc.coupang.com/ssr/desktop/order/list?pageIndex=1',
    listCoordinates: [':0', ':1'],
    pagination: { hasNext: true, currentPageIndex: null, nextPageIndex: 0, nextYear: '2021' }
  });

  assert.equal(step.action.type, 'none');
  assert.equal(step.state.phase, 'DETAIL');
  assert.equal(step.state.expectedListUrl, null);
});

test('서버가 이미 읽은 목록 좌표를 다시 주면 무한 페이지 증가 대신 상세 단계로 넘어간다', () => {
  useDocument(nextDataHtml, 'https://mc.coupang.com/ssr/desktop/order/list?pageIndex=1');
  const step = runStep({
    phase: 'NEXT_PAGE', scope: 'tracking', yearScope: 'current',
    page: 2, pageCount: 2, orders: [], warnings: [], queue: [],
    listUrl: 'https://mc.coupang.com/ssr/desktop/order/list?pageIndex=1',
    listCoordinates: [':0', ':1'],
    pagination: { hasNext: true, currentPageIndex: null, nextPageIndex: 0, nextYear: '2021' }
  });

  assert.equal(step.action.type, 'none');
  assert.equal(step.state.phase, 'DETAIL');
  assert.match(step.state.warnings.at(-1), /이미 읽은 목록 좌표/);
});

test('다음만 모드를 필터 URL에서 시작하면 필터 없는 첫 목록으로 정규화한다', () => {
  useDocument(nextDataHtml, 'https://mc.coupang.com/ssr/desktop/order/list?pageIndex=1&requestYear=2026');
  const step = runStep({ phase: 'INIT', scope: 'list', yearScope: 'current' });

  assert.equal(step.action.type, 'navigate');
  assert.equal(step.action.url, 'https://mc.coupang.com/ssr/desktop/order/list');
  assert.equal(step.state.orders.length, 0);
});

test('연도 탭 모드는 첫 연도의 첫 페이지 주소부터 시작한다', () => {
  const source = nextDataHtml.replace('<main>', '<main><nav><div>2026</div><div>2025</div></nav>');
  useDocument(source, 'https://mc.coupang.com/ssr/desktop/order/list');
  const step = runStep({ phase: 'INIT', scope: 'list', yearScope: 'all' });

  assert.equal(step.action.type, 'navigate');
  assert.equal(new URL(step.action.url).searchParams.get('pageIndex'), '0');
  assert.equal(new URL(step.action.url).searchParams.get('requestYear'), '2026');
  assert.deepEqual(step.state.years.map((year) => year.label), ['2026', '2025']);
});

test('목록 완료 뒤 상세→배송 문서를 같은 탭에서 주소로 연속 수집한다', () => {
  let state = stateAfterLastList(trackingListHtml, 'tracking');
  assert.equal(state.phase, 'DETAIL');
  assert.equal(state.queue.length, 1);

  const detailNavigation = runStep(state);
  assert.equal(detailNavigation.action.target, 'detail');
  assert.match(detailNavigation.action.url, /\/ssr\/desktop\/order\/16102412157785$/);

  const detailSource = detailHtml.replace(/16102427880443/g, '16102412157785');
  useDocument(detailSource, detailNavigation.action.url);
  const parsedDetail = runStep(detailNavigation.state);
  assert.equal(parsedDetail.state.queue[0].detailDone, true);

  const trackingNavigation = runStep(parsedDetail.state);
  assert.equal(trackingNavigation.action.type, 'navigate');
  assert.equal(trackingNavigation.action.target, 'tracking');
  assert.equal(new URL(trackingNavigation.action.url).searchParams.get('shipmentBoxId'), '1093824089505681408');

  useDocument(`
    <main><div>오늘 도착 완료</div>
      <table><tbody><tr><td>로켓배송</td></tr><tr><td>송장번호</td><td>10327823250323</td></tr></tbody></table>
      <table><thead><tr><th>시간</th><th>현재위치</th><th>배송상태</th></tr></thead>
      <tbody><tr><td>오늘 09:00</td><td>서울</td><td>배송완료</td></tr></tbody></table>
    </main>`, trackingNavigation.action.url);
  const parsedTracking = runStep(trackingNavigation.state);

  assert.equal(parsedTracking.state.queue[0].trackingDone, true);
  assert.equal(parsedTracking.state.cursor, 1);
  assert.equal(parsedTracking.state.orders[0].TrackingEvents.length, 1);
  const done = runStep(parsedTracking.state);
  assert.equal(done.action.type, 'done');
});

test('이전 주문의 상세 DOM을 현재 주문 결과로 합치지 않는다', () => {
  const state = stateAfterLastList(trackingListHtml, 'detail');
  const navigation = runStep(state);
  useDocument(detailHtml, 'https://mc.coupang.com/ssr/desktop/order/99999999999999');

  const stale = runStep(navigation.state);

  assert.equal(stale.action.type, 'none');
  assert.equal(stale.state.queue[0].detailDone, false);
  assert.equal(stale.state.orders[0].PaymentMethod, undefined);
  assert.match(stale.progress.message, /정확한 주문상세 주소/);
});

test('송장번호가 없으면 배송박스가 있어도 배송조회 대상에서 제외한다', () => {
  const withoutInvoice = trackingListHtml.replace('"invoiceNumber": "10327823250323"', '"invoiceNumber": null');
  const state = stateAfterLastList(withoutInvoice, 'tracking');

  assert.equal(state.queue[0].trackingDone, true);
  assert.match(trackingUrlFor(state.orders[0]), /invoiceNumber=&/);
});

test('같은 배송박스의 모든 vendorItemId를 배송조회 주소에 넣는다', () => {
  const twoProducts = trackingListHtml.replace(
    '"unitPrice": 16690}',
    '"unitPrice": 16690}, {"productId": 10, "vendorItemId": 99900011122, "vendorItemName": "두 번째 상품", "quantity": 1, "unitPrice": 1000}'
  );
  const state = stateAfterLastList(twoProducts, 'tracking');
  state.queue[0].detailDone = true;
  const step = runStep(state);

  assert.deepEqual(state.queue[0].vendorItemIds, ['86704060029', '99900011122']);
  assert.equal(new URL(step.action.url).searchParams.get('vendorItemIds'), '86704060029,99900011122');
});

test('16자리 이상 배송박스 번호를 정밀도 손실 없이 URL에 넣는다', () => {
  const document = asDocument(trackingListHtml, 'https://mc.coupang.com/ssr/desktop/order/list');
  const row = ordersFromNextData(document)[0];

  assert.equal(row._shipmentBoxId, '1093824089505681408');
  assert.match(trackingUrlFor(row), /shipmentBoxId=1093824089505681408/);
});
