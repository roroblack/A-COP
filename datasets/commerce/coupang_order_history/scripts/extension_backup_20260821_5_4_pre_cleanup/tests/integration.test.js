'use strict';

process.env.TZ = 'Asia/Seoul';

const assert = require('node:assert/strict');
const test = require('node:test');
const {
  collectOrders,
  findNextButton,
  findOrderTrackingAction,
  isOrderListPage,
  parseDocument
} = require('../content.js');
const { parseFragment } = require('./test-dom.js');

const YEARS = [2026, 2025];
const PAGES_PER_YEAR = 2;
const CARDS_PER_PAGE = 3;
const MAX_TRANSITIONS = 250;

const STATUS_PLAN = {
  '2026-1': ['배송완료', '취소완료', '배송중'],
  '2026-2': ['상품준비중', '배송완료', '배송중'],
  '2025-1': ['취소완료', '배송완료', '상품준비중'],
  '2025-2': ['배송중', '취소완료', '배송완료']
};

const MULTI_PRODUCT_CARDS = new Set(['2026-1-1', '2026-2-1', '2025-1-2', '2025-2-0']);

function orderNumber(year, page, cardIndex) {
  return `${year}${page}${cardIndex}00000001`;
}

function productBlock(order, productIndex) {
  const vendorId = `${order.year}${order.page}${order.cardIndex}${productIndex}001`;
  const name = `테스트 상품 ${order.year}-${order.page}-${order.cardIndex}-${productIndex}`;
  const productLink = order.status === '취소완료'
    ? `<a><span>${name}</span></a>`
    : `<a href="/ssr/sdp/link?vendorItemId=${vendorId}&amp;sourceType=MyCoupang_my_orders_list_product_title"><span>${name}</span></a>`;
  return `<div class="product">
    <span style="font-size:1.25rem">${order.status}</span>
    <img alt="${name}">
    ${productLink}
    <span translate="yes">${1000 + productIndex * 100} 원</span><span>1개</span>
  </div>`;
}

function listHtml(year, page) {
  const cards = STATUS_PLAN[`${year}-${page}`].map((status, cardIndex) => {
    const key = `${year}-${page}-${cardIndex}`;
    const order = { year, page, cardIndex, status };
    const productCount = MULTI_PRODUCT_CARDS.has(key) ? 2 : 1;
    return `<section class="order-card" data-key="${key}">
      <div>${year}. ${page}. ${cardIndex + 1} 주문</div>
      <button data-action="detail">주문 상세보기</button>
      ${Array.from({ length: productCount }, (_, index) => productBlock(order, index)).join('')}
      ${status === '취소완료' ? '' : '<button data-action="tracking">배송 조회</button>'}
    </section>`;
  }).join('');
  return `<main>
    <nav>${YEARS.map((value) => `<button data-year="${value}" aria-selected="${value === year}">${value}</button>`).join('')}</nav>
    ${cards}
    <footer><button ${page === 1 ? 'disabled=""' : ''}>이전</button><button ${page === PAGES_PER_YEAR ? 'disabled=""' : ''}>다음</button></footer>
  </main>`;
}

function detailHtml(order) {
  const key = `${order.year}-${order.page}-${order.cardIndex}`;
  const productCount = MULTI_PRODUCT_CARDS.has(key) ? 2 : 1;
  return `<main>
    <div>${order.year}. ${order.page}. ${order.cardIndex + 1} 주문</div>
    <div>주문번호 ${orderNumber(order.year, order.page, order.cardIndex)}</div>
    <h2>받는사람 정보</h2><div>연락처 010-1234-5678</div>
    <span style="font-size:1.25rem">${order.status}</span>
    ${Array.from({ length: productCount }, (_, index) => productBlock(order, index)).join('')}
    <table><tbody>
      <tr><td>총 상품가격</td><td><strong translate="yes">1000 원</strong></td></tr>
      <tr><td>배송비</td><td><span translate="yes">0 원</span></td></tr>
      <tr><td>결제수단</td><td>쿠팡캐시</td></tr>
      <tr><td>총 결제금액</td><td><strong translate="yes">1000 원</strong></td></tr>
      <tr><td>받는주소</td><td>서울특별시 서초구 비공개</td></tr>
    </tbody></table>
    <button data-action="list">주문목록 돌아가기</button>
  </main>`;
}

function trackingHtml(order) {
  const preShipment = order.status === '상품준비중';
  const eventCount = order.status === '배송완료' ? 3 : 2;
  const events = preShipment ? '' : Array.from({ length: eventCount }, (_, index) =>
    `<tr><td>오늘 ${String(10 - index).padStart(2, '0')}:00</td><td>물류센터 ${index + 1}</td><td>${index === 0 ? order.status : '배송중'}</td></tr>`
  ).join('');
  return `<main>
    <div>${preShipment ? '내일 도착 보장' : '오늘 도착 완료'}</div>
    ${preShipment ? '<div>상품이 준비되고 있습니다.</div>' : ''}
    <div>배송상태</div>
    <section><div>결제완료</div><div>상품준비중</div><div>배송시작</div><div>배송중</div><div>배송완료</div></section>
    <table><tbody><tr><td>로켓배송</td></tr><tr><td>송장번호</td><td>${preShipment ? ' ' : `TR${orderNumber(order.year, order.page, order.cardIndex)}`}</td></tr></tbody></table>
    ${preShipment ? '' : `<table><thead><tr><th>시간</th><th>현재위치</th><th>배송상태</th></tr></thead><tbody>${events}</tbody></table>`}
    <button data-action="list">주문목록 돌아가기</button>
  </main>`;
}

class FakeSite {
  constructor() {
    this.year = YEARS[0];
    this.page = 1;
    this.kind = 'list';
    this.transitions = [];
    this.yearVisits = [];
    this.pageVisits = [];
    this.currentOrder = null;
    this.forceWrongReturnOnce = true;
    this.location = {};
    Object.defineProperty(this.location, 'href', {
      get: () => `https://mc.coupang.com/fake/${this.kind}/${this.year}/${this.page}`,
      set: () => this.showList(this.year, 1, 'forced-url-return')
    });
    this.showList(this.year, this.page, 'initial');
  }

  transition(label) {
    this.transitions.push(label);
    assert.ok(this.transitions.length <= MAX_TRANSITIONS,
      `전체 반복 상한 ${MAX_TRANSITIONS}회 초과: ${this.transitions.slice(-12).join(' -> ')}`);
  }

  showList(year, page, reason) {
    this.transition(`list:${year}:${page}:${reason}`);
    this.year = year;
    this.page = page;
    this.kind = 'list';
    this.document = parseFragment(listHtml(year, page));
    global.document = this.document;
    if (reason === 'year') this.yearVisits.push(year);
    if (reason === 'next') this.pageVisits.push(`${year}:${page}`);
    this.attachListActions();
  }

  attachListActions() {
    for (const tab of this.document.querySelectorAll('button[data-year]')) {
      tab.onclick = () => this.showList(Number(tab.getAttribute('data-year')), 1, 'year');
    }
    const cards = this.document.querySelectorAll('section[data-key]');
    cards.forEach((card, cardIndex) => {
      const order = { year: this.year, page: this.page, cardIndex, status: STATUS_PLAN[`${this.year}-${this.page}`][cardIndex] };
      card.querySelector('button[data-action="detail"]').onclick = () => this.showDetail(order);
      const tracking = card.querySelector('button[data-action="tracking"]');
      if (tracking) tracking.onclick = () => this.showTracking(order);
    });
    const next = findNextButton(this.document);
    if (next && !next.disabled) next.onclick = () => this.showList(this.year, this.page + 1, 'next');
  }

  showDetail(order) {
    this.transition(`detail:${order.year}:${order.page}:${order.cardIndex}`);
    this.kind = 'detail';
    this.currentOrder = order;
    this.document = parseFragment(detailHtml(order));
    global.document = this.document;
    this.document.querySelector('button[data-action="list"]').onclick = () => this.returnToList('detail-return');
  }

  showTracking(order) {
    this.transition(`tracking:${order.year}:${order.page}:${order.cardIndex}`);
    this.kind = 'tracking';
    this.currentOrder = order;
    this.document = parseFragment(trackingHtml(order));
    global.document = this.document;
    this.document.querySelector('button[data-action="list"]').onclick = () => this.returnToList('tracking-return');
  }

  returnToList(reason) {
    if (this.forceWrongReturnOnce && this.currentOrder.year === 2026 && this.currentOrder.page === 2) {
      this.forceWrongReturnOnce = false;
      this.showList(2026, 1, 'wrong-position-return');
      return;
    }
    this.showList(this.currentOrder.year, this.currentOrder.page, reason);
  }
}

test('가짜 DOM에서 전체 연도·페이지·상세·배송 수집 흐름을 끝까지 실행한다', async (t) => {
  const previousGlobals = { document: global.document, location: global.location, history: global.history, chrome: global.chrome };
  const site = new FakeSite();
  global.location = site.location;
  global.history = { back: () => site.returnToList('history-back') };
  global.chrome = { runtime: { lastError: null, sendMessage: (_message, callback) => callback?.() } };
  t.after(() => Object.assign(global, previousGlobals));

  const result = await collectOrders({
    collectionScope: 'tracking',
    yearScope: 'all',
    runtime: {
      randomDelay: async () => {},
      reportProgress: () => {},
      maxPages: 5,
      maxYears: 5,
      maxOrders: 100,
      maxOrdersPerPage: 20
    }
  });

  const orders = result.orderData.orders;
  const uniqueOrderNumbers = new Set(orders.map((order) => order.OrderId));
  const uniqueProductRows = new Set(orders.map((order) => `${order.OrderId}|${order.VendorItemId || order.ProductName}`));
  assert.equal(orders.length, YEARS.length * PAGES_PER_YEAR * CARDS_PER_PAGE + MULTI_PRODUCT_CARDS.size);
  assert.equal(uniqueProductRows.size, orders.length, '같은 주문의 동일 상품 행이 중복 수집됨');
  assert.equal(uniqueOrderNumbers.size, YEARS.length * PAGES_PER_YEAR * CARDS_PER_PAGE);
  assert.ok(orders.every((order) => order.OrderId && order._idSource !== 'derived'));

  for (const order of orders.filter((item) => ['배송완료', '배송중'].includes(item.OrderStatus))) {
    assert.ok(order.TrackingNumber, `${order.OrderId} 송장번호 누락`);
    const tracking = result.trackingData.find((item) => item.order_id === order.OrderId);
    assert.ok(tracking?.events.length >= 2, `${order.OrderId} 배송 이력 누락`);
  }
  for (const order of orders.filter((item) => item.OrderStatus === '상품준비중')) {
    assert.equal(order.ShipmentStarted, false);
    assert.equal(order._TrackingOutcome, 'preShipment');
    assert.deepEqual(order.Warnings, []);
  }
  const cancelled = orders.filter((item) => item.OrderStatus === '취소완료');
  assert.ok(cancelled.length > 0);
  assert.ok(cancelled.every((order) => order._TrackingOutcome === 'buttonMissing'));
  assert.ok(orders.some((order) => order.OrderId === orderNumber(2026, 1, 2)), '취소 주문 뒤의 주문을 처리하지 못함');

  assert.deepEqual(site.yearVisits.filter((year, index, values) => index === 0 || year !== values[index - 1]), [2026, 2025], '복원 시 연도 탭을 다시 눌러야 한다');
  assert.ok(site.pageVisits.includes('2026:2') && site.pageVisits.includes('2025:2'));
  assert.equal(result.orderData.pageCount, 4);
  assert.equal(site.kind, 'list');
  assert.equal(`${site.year}:${site.page}`, '2025:2');
  assert.equal(isOrderListPage(site.document), true);
  assert.ok(site.transitions.length < MAX_TRANSITIONS);
  assert.notEqual(findOrderTrackingAction(site.document, parseDocument(site.document).orders[0]), null);

  const serialized = JSON.stringify(result);
  assert.doesNotMatch(serialized, /010[-\s]?\d{3,4}[-\s]?\d{4}/);
  assert.doesNotMatch(serialized, /받는사람|비공개/);
});
