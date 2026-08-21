'use strict';

process.env.TZ = 'Asia/Seoul';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const { parseFragment } = require('./test-dom.js');
const { diagnoseStructure, isOrderListPage, pageFacts, parseDocument, performAction, runStep } = require('../content.js');

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
