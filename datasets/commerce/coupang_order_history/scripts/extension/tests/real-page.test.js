'use strict';

process.env.TZ = 'Asia/Seoul';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const { parseFragment } = require('./test-dom.js');
const { diagnoseStructure, isOrderListPage, listUrlForPage, ordersFromNextData, pageFacts, paginationFromNextData, trackingUrlFor, parseDocument, parseTrackingPage, performAction, runStep } = require('../content.js');

// 사용자가 실제 쿠팡 주문목록에서 복사한 HTML이다. raw/find.md에서 뽑았다.
const html = fs.readFileSync(path.join(__dirname, 'fixtures/order_list_real.html'), 'utf8');

function realDocument() {
  const document = parseFragment(html);
  global.document = document;
  return document;
}

test('실측 목록: 주문 카드를 7개로 잡는다', () => {
  const document = realDocument();
  assert.equal(parseDocument(document).orderCardCount, 7);
});

test('실측 목록: 상품 행은 8개다', () => {
  const document = realDocument();
  const orders = parseDocument(document).orders;
  assert.equal(orders.length, 8);
  const perCard = new Map();
  for (const order of orders) perCard.set(order._cardIndex, (perCard.get(order._cardIndex) || 0) + 1);
  assert.equal([...perCard.values()].filter((count) => count === 2).length, 1, '다품목 카드는 하나다');
});

test('실측 목록: 구조 진단 수치가 카드 수와 어긋나지 않는다', () => {
  const document = realDocument();
  const diagnosis = diagnoseStructure(document);
  assert.equal(diagnosis.orderCards, 7);
  // 카드 경계가 무너지면 이 값들이 카드 수의 몇 배로 부풀어 오른다.
  assert.ok(diagnosis.prices <= 12, `가격 span ${diagnosis.prices}개는 과다하다`);
  assert.ok(diagnosis.quantities <= 12, `수량 ${diagnosis.quantities}개는 과다하다`);
  assert.ok(diagnosis.deliveryNotices <= 12);
  assert.equal(diagnosis.nextButton, true);
});

test('실측 목록: 취소완료 주문도 상품명을 얻는다', () => {
  const document = realDocument();
  const cancelled = parseDocument(document).orders.filter((order) => order.OrderStatus === '취소완료');
  assert.ok(cancelled.length >= 2);
  assert.ok(cancelled.every((order) => order.ProductName));
});

test('실측 목록: 주문 상세보기 클릭 대상은 가장 안쪽 span이다', () => {
  const document = realDocument();
  const clicked = [];
  for (let index = 0; index < 7; index += 1) {
    const result = performAction({ type: 'click', target: 'detail', index, attempt: 0 });
    assert.equal(result.ok, true, `카드 ${index}의 상세보기 대상을 못 찾았다`);
    clicked.push(result.tag);
  }
  // 조상을 누르면 그 아래 React 핸들러에 닿지 않는다. 반드시 리프여야 한다.
  assert.deepEqual(clicked, Array(7).fill('SPAN'));
});

test('실측 목록: 재시도하면 대상과 클릭 방법을 함께 올린다', () => {
  const document = realDocument();
  const results = [0, 1, 2, 3].map((attempt) => performAction({ type: 'click', target: 'detail', index: 0, attempt }));
  assert.deepEqual(results.map((result) => result.ok), [true, true, true, true]);
  // 0: 리프+이벤트, 1: 리프+native, 2: 부모+이벤트, 3: 부모+native
  assert.deepEqual(results.map((result) => result.depth), [0, 0, 1, 1]);
  assert.deepEqual(results.map((result) => result.native), [false, true, false, true]);
  assert.equal(results[0].tag, 'SPAN');
  assert.equal(results[2].tag, 'DIV');
});

test('실측 목록: 배송 조회는 button을 직접 누른다', () => {
  const document = realDocument();
  const orders = parseDocument(document).orders;
  const shipped = orders.filter((order) => ['배송중', '배송시작', '배송완료'].includes(order.OrderStatus));
  assert.ok(shipped.length >= 3, `배송 상태 주문이 ${shipped.length}건뿐이다`);
  for (const order of shipped) {
    const result = performAction({ type: 'click', target: 'tracking', index: order._cardIndex, attempt: 0 });
    assert.equal(result.ok, true, `카드 ${order._cardIndex}의 배송 조회 대상을 못 찾았다`);
    assert.equal(result.tag, 'BUTTON');
  }
});

test('실측 목록: 취소완료 주문에는 배송 조회 대상이 없다', () => {
  const document = realDocument();
  const cancelled = parseDocument(document).orders.filter((order) => order.OrderStatus === '취소완료');
  for (const order of cancelled) {
    assert.equal(performAction({ type: 'click', target: 'tracking', index: order._cardIndex, attempt: 0 }).ok, false);
  }
});



// 진짜 Document는 textContent가 null이다. 요소만으로 테스트하면 이 차이를 놓친다.
function asDocument(element) {
  return {
    nodeType: 9,
    textContent: null,
    body: element,
    title: '주문상세',
    querySelector: (selector) => element.querySelector(selector),
    querySelectorAll: (selector) => element.querySelectorAll(selector)
  };
}

const detailHtml = fs.readFileSync(path.join(__dirname, 'fixtures/order_detail_real.html'), 'utf8');

test('실측 상세: document로 넘겨도 목록으로 오인하지 않는다', () => {
  const document = asDocument(parseFragment(detailHtml));
  global.document = document;
  assert.equal(isOrderListPage(document), false);
});

test('실측 상세: 주문목록 돌아가기 버튼을 찾는다', () => {
  const document = asDocument(parseFragment(detailHtml));
  global.document = document;
  const result = performAction({ type: 'click', target: 'backToList', index: 0, attempt: 0 });
  assert.equal(result.ok, true, result.reason);
  assert.equal(result.tag, 'BUTTON');
});

test('실측 상세: pageFacts가 상세 표지를 제대로 읽는다', () => {
  const document = asDocument(parseFragment(detailHtml));
  global.document = document;
  global.location = { href: 'https://mc.coupang.com/ssr/desktop/order/16102427993090' };
  const facts = pageFacts();
  assert.equal(facts.isList, false);
  assert.equal(facts.hasOrderNumber, true, '주문번호 표지를 못 읽었다');
});

test('실측 목록: document로 넘겨도 목록으로 본다', () => {
  const document = asDocument(parseFragment(html));
  global.document = document;
  assert.equal(isOrderListPage(document), true);
});

test('실측 목록: script 안의 JSON에 상세 라벨이 있어도 목록으로 본다', () => {
  // 쿠팡 SSR 페이지는 script에 JSON을 심는다. body.textContent에는 그 문자열도 들어온다.
  // 통짜 텍스트로 표지를 찾으면 목록에서도 상세 라벨이 전부 잡힌다.
  const withScript = html.replace(
    '<main>',
    '<main><script>window.__DATA__={"labels":["주문목록 돌아가기","받는사람 정보","결제 정보","주문번호","송장번호","배송 조회"]}</script>'
  );
  const document = asDocument(parseFragment(withScript));
  global.document = document;

  assert.equal(isOrderListPage(document), true, 'script 텍스트에 속아 목록이 아니라고 했다');
  const facts = pageFacts();
  assert.equal(facts.isList, true);
  assert.equal(facts.hasTrackingTable, false, 'script 안의 송장번호를 실제 표로 착각했다');
});

test('실측 상세: script가 있어도 상세로 본다', () => {
  const withScript = detailHtml.replace('<div', '<script>var x="주문 상세보기"</script><div');
  const document = asDocument(parseFragment(withScript));
  global.document = document;
  assert.equal(isOrderListPage(document), false, 'script 안의 주문 상세보기를 버튼으로 착각했다');
});

test('연도 탭을 쓰지 않는 설정이면 위치 복원에서도 누르지 않는다', () => {
  // 연도 탭을 누르면 주소에 requestYear가 붙어 자리가 더 어긋난다.
  const document = asDocument(parseFragment(html));
  global.document = document;
  const state = {
    phase: 'RESTORE', scope: 'tracking', yearScope: 'current',
    years: [{ label: '2026', done: false }], yearIndex: 0, page: 2,
    orders: [], tracking: [], queue: [{ cardIndex: 0, orderIndexes: [], detailDone: false, trackingDone: false, returning: null }],
    cursor: 0, warnings: [], listKey: '다른키', restore: { yearDone: false, attempts: 0 }
  };
  const step = runStep(state);
  assert.equal(step.action.type, 'click');
  assert.equal(step.action.target, 'nextPage', `연도 탭을 눌렀다: ${step.action.target}`);
});

test('상세가 실패해도 배송 조회는 시도한다', () => {
  // 목록 카드에 배송 조회 버튼이 있으므로 상세를 못 읽어도 배송은 받을 수 있다.
  const document = asDocument(parseFragment(html));
  global.document = document;
  const item = { cardIndex: 0, orderIndexes: [0], detailDone: false, trackingDone: false, returning: 'detail' };
  const state = {
    phase: 'DETAIL', scope: 'tracking', yearScope: 'current',
    years: [{ label: '2026', done: false }], yearIndex: 0, page: 1,
    orders: [{ OrderId: 'x', OrderStatus: '배송중', Warnings: [] }], tracking: [],
    queue: [item], cursor: 0, warnings: [], skipCurrent: true, listKey: null
  };

  const step = runStep(state);

  assert.equal(step.state.queue[0].detailDone, true, '상세는 포기해야 한다');
  assert.equal(step.state.queue[0].trackingDone, false, '배송 조회까지 같이 포기했다');
  assert.equal(step.state.cursor, 0, '아직 다음 주문으로 넘어가면 안 된다');
});

test('실측 진행막대: 도달한 단계만 담고 현재 단계를 가려낸다', () => {
  // 진행 막대는 다섯 단계를 항상 다 그린다. 있다고 다 담으면 배송중인데 배송완료까지 나온다.
  const stepper = fs.readFileSync(path.join(__dirname, 'fixtures/tracking_stepper_real.html'), 'utf8');
  const document = asDocument(parseFragment(stepper));
  global.document = document;
  const tracking = parseTrackingPage(document, new Date('2026-08-21T12:00:00+09:00'), '배송중');

  assert.deepEqual(tracking.DeliveryStepsAll, ['결제완료', '상품준비중', '배송시작', '배송중', '배송완료']);
  assert.deepEqual(tracking.DeliverySteps, ['결제완료', '상품준비중', '배송시작'], '도달하지 않은 단계까지 담았다');
  assert.equal(tracking.DeliveryStep, '배송시작');
});

test('다음이 한 번 안 통했다고 마지막 페이지로 보지 않는다', () => {
  // 클릭 한 번이 흘러가면 뒤 페이지를 통째로 잃는다. 실제로 2021년 주문이 빠졌다.
  const document = asDocument(parseFragment(html));
  global.document = document;
  const state = {
    phase: 'LIST', scope: 'list', yearScope: 'current',
    years: [{ label: '2026', done: false }], yearIndex: 0, page: 2,
    orders: [], tracking: [], queue: [], cursor: 0, warnings: [],
    listKey: null, seenKeys: [], pageRetries: 0
  };
  // 먼저 한 번 읽어 listKey 를 채운다
  const first = runStep(state);
  const seen = first.state;
  // 같은 페이지가 다시 나온 상황
  const retry = runStep({ ...seen, phase: 'LIST' });
  assert.equal(retry.state.phase, 'NEXT_PAGE', `바로 끝냈다: ${retry.state.phase}`);
  assert.equal(retry.state.pageRetries, 1);

  const retry2 = runStep({ ...retry.state, phase: 'LIST' });
  assert.equal(retry2.state.pageRetries, 2);

  // 세 번째에는 포기하고 사유를 남긴다
  const giveUp = runStep({ ...retry2.state, phase: 'LIST' });
  assert.equal(giveUp.state.phase, 'NEXT_YEAR');
  assert.match(giveUp.state.warnings.at(-1), /넘어가지 않아|마지막 페이지/);
});

test('목록 순서가 바뀌어도 같은 주문을 누른다', () => {
  // 목록이 다시 그려지면 카드 순번이 다른 주문을 가리킨다.
  // 실제로 배송조회에서 나온 뒤 엉뚱한 주문의 상세로 들어갔다.
  const document = asDocument(parseFragment(html));
  global.document = document;
  const orders = parseDocument(document).orders;
  const target = orders.find((order) => order._cardIndex === 2);
  const key = `${target.OrderedAt || ''}|${target.VendorItemId || target.ProductName || ''}`;

  // 순번은 일부러 틀리게 주고 키로만 찾게 한다
  const byKey = performAction({ type: 'click', target: 'detail', index: 0, attempt: 0, cardKey: key });
  const byIndex = performAction({ type: 'click', target: 'detail', index: 2, attempt: 0 });

  assert.equal(byKey.ok, true, byKey.reason);
  assert.equal(byIndex.ok, true, byIndex.reason);
  assert.equal(byKey.tag, byIndex.tag);
  assert.equal(byKey.tag, 'SPAN');
});

const nextDataHtml = fs.readFileSync(path.join(__dirname, 'fixtures/order_list_nextdata.html'), 'utf8');

test('__NEXT_DATA__: 상세 페이지 없이 주문번호와 송장번호를 얻는다', () => {
  // 서버가 심어준 JSON 에 주문번호, 판매자, 단가, 배송비, 택배사, 송장번호가 다 있다.
  // 이걸 읽으면 상세 페이지와 배송조회 화면에 들어갈 이유가 대부분 사라진다.
  const document = asDocument(parseFragment(nextDataHtml));
  global.document = document;
  const rows = ordersFromNextData(document);

  assert.equal(rows.length, 3, '상품 행 수가 다르다');
  const chip = rows.find((row) => row.ProductName.includes('허니버터칩'));
  assert.equal(chip.OrderId, '16102412730885');
  assert.equal(chip._idSource, 'orderNumber');
  assert.equal(chip.TrackingNumber, '10327825750572');
  assert.equal(chip.CourierCompany, '로켓배송');
  assert.equal(chip.OrderStatus, '배송완료');
  assert.equal(chip.ProductPrice, 2420);
  assert.equal(chip.OrderedAt, '2026-08-20');

  // 한 주문에 상품이 둘이면 두 행이 같은 주문번호를 갖는다
  const cancelled = rows.filter((row) => row.OrderId === '16102412664912');
  assert.equal(cancelled.length, 2);
  assert.equal(cancelled[0].TrackingNumber, null);
});

test('__NEXT_DATA__: 다음 페이지 여부를 짐작하지 않는다', () => {
  const document = asDocument(parseFragment(nextDataHtml));
  global.document = document;
  const paging = paginationFromNextData(document);

  assert.deepEqual(paging, { hasNext: true, currentPageIndex: 0, nextPageIndex: 1 });
  assert.match(listUrlForPage(1, '2026'), /pageIndex=1/);
  assert.match(listUrlForPage(1, '2026'), /requestYear=2026/);
});

test('__NEXT_DATA__: 송장이 없는 주문은 배송조회를 열지 않는다', () => {
  // 송장번호가 없으면 배송조회 화면에도 볼 것이 없다. 여는 것 자체가 낭비다.
  const document = asDocument(parseFragment(nextDataHtml));
  global.document = document;
  global.location = { href: 'https://mc.coupang.com/ssr/desktop/order/list' };

  let state = { phase: 'INIT', scope: 'tracking', yearScope: 'current' };
  state = runStep(state).state;   // INIT -> LIST
  state = runStep(state).state;   // LIST -> 큐 생성

  assert.equal(state.orders.length, 3);
  // JSON 에서 왔으므로 상세는 전부 끝난 것으로 본다
  assert.ok(state.queue.every((item) => item.detailDone), '상세를 다시 방문하려 한다');

  const withTracking = state.queue.filter((item) => !item.trackingDone);
  assert.equal(withTracking.length, 1, '송장 있는 주문만 배송조회 대상이어야 한다');
});

const trackingListHtml = fs.readFileSync(path.join(__dirname, 'fixtures/order_list_tracking.html'), 'utf8');

test('__NEXT_DATA__: 배송조회 주소를 만들어 클릭 없이 이동한다', () => {
  // 버튼을 찾아 누르는 대신 주소를 만든다. 화면 구조와 무관해진다.
  const document = asDocument(parseFragment(trackingListHtml));
  global.document = document;
  global.location = { href: 'https://mc.coupang.com/ssr/desktop/order/list' };

  const rows = ordersFromNextData(document);
  const url = trackingUrlFor(rows[0]);

  assert.match(url, /shiptrack/);
  assert.match(url, /orderId=16102412157785/);
  assert.match(url, /shipmentBoxId=1093824089505681408/);
  assert.match(url, /invoiceNumber=10327823250323/);
  assert.match(url, /vendorItemIds=86704060029/);

  let state = { phase: 'INIT', scope: 'tracking', yearScope: 'current' };
  state = runStep(state).state;
  state = runStep(state).state;
  const step = runStep(state);

  assert.equal(step.action.type, 'navigate', `클릭을 하려 한다: ${step.action.type}`);
  assert.equal(step.action.expect, 'tracking');
  assert.match(step.action.url, /shiptrack/);
});

test('__NEXT_DATA__: 배송박스 번호가 없으면 주소를 만들지 않는다', () => {
  // 못 만들면 기존 방식대로 버튼을 찾는다. 조용히 틀린 주소로 가지 않는다.
  assert.equal(trackingUrlFor({ OrderId: '1', TrackingNumber: '2' }), null);
  assert.equal(trackingUrlFor({ OrderId: '1', _shipmentBoxId: '3' }), null);
});

test('__NEXT_DATA__: 자릿수가 큰 값이 잘리지 않는다', () => {
  // shipmentBoxId 는 JavaScript 안전 정수 범위를 넘는다.
  // JSON.parse 를 그냥 쓰면 1093824089505681408 이 1093824089505681400 이 된다.
  // 그 상태로 주소를 만들면 다른 배송건을 조회한다.
  const document = asDocument(parseFragment(trackingListHtml));
  global.document = document;
  const rows = ordersFromNextData(document);

  assert.equal(rows[0]._shipmentBoxId, '1093824089505681408');
  assert.match(trackingUrlFor(rows[0]), /shipmentBoxId=1093824089505681408/);
});
