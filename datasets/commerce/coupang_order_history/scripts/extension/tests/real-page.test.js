'use strict';

process.env.TZ = 'Asia/Seoul';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const { parseFragment } = require('./test-dom.js');
const { diagnoseStructure, parseDocument } = require('../content.js');

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
