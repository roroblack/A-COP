'use strict';

process.env.TZ = 'Asia/Seoul';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const { parseFragment } = require('./test-dom.js');
const { diagnoseStructure, parseDocument, performAction, runStep } = require('../content.js');

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


