'use strict';

process.env.TZ = 'Asia/Seoul';

const assert = require('node:assert/strict');
const test = require('node:test');
const { parseFragment } = require('./test-dom.js');
const {
  buildExportPayloads,
  mergeDetail,
  parseDetailPage,
  parseTrackingPage,
  sanitizeValue,
  trackingUrlFor
} = require('../content.js');

const DETAIL_HTML = `
<main>
  <strong>2026. 8. 20 주문</strong>
  <div>주문번호 16102412730885</div>
  <span style="font-size:1.25rem">배송완료</span>
  <table><tbody><tr><td>
    <a href="/ssr/sdp/link?vendorItemId=76676260659&amp;sourceType=MyCoupang_order_detail_product_title">
      <span>해태 허니버터칩, 120g, 1개</span>
    </a>
    <span translate="yes">2,420 원</span><span>1개</span>
  </td></tr></tbody></table>
  <table><tbody>
    <tr><td>총 상품가격</td><td><strong translate="yes">2,420 원</strong></td></tr>
    <tr><td>배송비</td><td><span translate="yes">0 원</span></td></tr>
    <tr><td>결제수단</td><td>쿠팡캐시</td></tr>
    <tr><td>총 결제금액</td><td><strong translate="yes">2,420 원</strong></td></tr>
  </tbody></table>
  <table><tbody>
    <tr><td>받는사람</td><td>황*길</td></tr>
    <tr><td>연락처</td><td>010****7059</td></tr>
    <tr><td>받는주소</td><td>(00000) 서울특별시 서초구 테스트로 ** ***호</td></tr>
    <tr><td>배송요청사항</td><td>새벽 : 문 앞 (자유 출입가능)</td></tr>
  </tbody></table>
</main>`;

const TRACKING_HTML = `
<main>
  <div>어제(목) 도착 완료</div>
  <table><tbody>
    <tr><td>로켓배송</td></tr>
    <tr><td>송장번호</td><td>10327825750572</td></tr>
  </tbody></table>
  <table>
    <thead><tr><th>시간</th><th>현재위치</th><th>배송상태</th></tr></thead>
    <tbody>
      <tr><td>어제 23:07</td><td>안양1</td><td>배송완료</td></tr>
      <tr><td>어제 21:32</td><td>안양1</td><td>배송출발</td></tr>
    </tbody>
  </table>
  <table><tbody>
    <tr><td>받는사람</td><td>황*길</td></tr>
    <tr><td>연락처</td><td>010****7059</td></tr>
    <tr><td>받는주소</td><td>서울특별시 서초구 남부순환로339길</td></tr>
    <tr><td>상품수령방법</td><td>문앞 전달</td></tr>
  </tbody></table>
</main>`;

const PRE_SHIPMENT_HTML = `
<main>
  <div>내일(토) 새벽 7시 전 도착 보장</div>
  <div>고객님이 주문하신 상품이 준비시작되었습니다.</div>
  <section><div>결제완료</div><div>상품준비중</div><div>배송시작</div><div>배송중</div><div>배송완료</div></section>
  <table><tbody><tr><td>로켓배송</td></tr><tr><td>송장번호</td><td> </td></tr></tbody></table>
</main>`;

test('상세 문서에서 주문번호·상품·결제·배송정보를 읽는다', () => {
  const detail = parseDetailPage(parseFragment(DETAIL_HTML), 'https://mc.coupang.com/ssr/desktop/order/16102412730885');

  assert.equal(detail.OrderId, '16102412730885');
  assert.equal(detail._idSource, 'orderNumber');
  assert.equal(detail.OrderedAt, '2026-08-20');
  assert.equal(detail.OrderStatus, '배송완료');
  assert.equal(detail.products.length, 1);
  assert.equal(detail.products[0].ProductName, '해태 허니버터칩, 120g, 1개');
  assert.equal(detail.products[0].VendorItemId, '76676260659');
  assert.equal(detail.products[0].ProductPrice, 2420);
  assert.equal(detail.TotalProductAmount, 2420);
  assert.equal(detail.ShippingFee, 0);
  assert.equal(detail.TotalAmount, 2420);
  assert.equal(detail.PaymentMethod, '쿠팡캐시');
  assert.equal(detail.DeliveryRegion, '서울특별시 서초구');
  assert.equal(detail.DeliveryRequest, '새벽 : 문 앞 (자유 출입가능)');
});

test('상세 결과를 동일 vendorItem 주문 행에 병합한다', () => {
  const order = { OrderId: '16102412730885', VendorItemId: '76676260659', ProductName: '임시 이름' };
  mergeDetail(order, parseDetailPage(parseFragment(DETAIL_HTML)));

  assert.equal(order.ProductName, '해태 허니버터칩, 120g, 1개');
  assert.equal(order.TotalAmount, 2420);
  assert.equal(order._idSource, 'orderNumber');
});

test('배송 문서에서 송장과 이력을 읽고 상대 시각을 ISO로 바꾼다', () => {
  const tracking = parseTrackingPage(parseFragment(TRACKING_HTML), new Date('2026-08-21T10:00:00+09:00'));

  assert.equal(tracking.CourierCompany, '로켓배송');
  assert.equal(tracking.TrackingNumber, '10327825750572');
  assert.equal(tracking.ShipmentStarted, true);
  assert.equal(tracking.TrackingEvents.length, 2);
  assert.deepEqual(tracking.TrackingEvents[0], {
    timeString: new Date('2026-08-20T23:07:00+09:00').toISOString(),
    where: '안양1',
    kind: '배송완료'
  });
  assert.equal(tracking.ReceiptMethod, '문앞 전달');
  assert.deepEqual(tracking.Warnings, []);
});

test('송장과 이력이 없는 배송 전 문서는 정상 상태로 처리한다', () => {
  const tracking = parseTrackingPage(parseFragment(PRE_SHIPMENT_HTML), new Date(), '상품준비중');

  assert.equal(tracking.TrackingNumber, null);
  assert.equal(tracking.ShipmentStarted, false);
  assert.equal(tracking.TrackingStatus, '아직 배송이 시작되지 않아 이력이 없습니다.');
  assert.deepEqual(tracking.TrackingEvents, []);
  assert.deepEqual(tracking.Warnings, []);
});

test('송장은 있는데 이력 표가 없을 때만 경고한다', () => {
  const html = PRE_SHIPMENT_HTML.replace('<td> </td>', '<td>10327825750572</td>');
  const tracking = parseTrackingPage(parseFragment(html), new Date(), '상품준비중');

  assert.equal(tracking.ShipmentStarted, true);
  assert.deepEqual(tracking.Warnings, ['배송 이력 표를 찾지 못했습니다.']);
});

test('PII 필드와 휴대폰번호를 결과에서 제거한다', () => {
  const value = sanitizeValue({
    Recipient: '황*길',
    Address: '서울특별시 서초구',
    note: '010-1234-5678 / 010****7059',
    orderId: '16001612345678'
  });

  assert.equal(value.Recipient, undefined);
  assert.equal(value.Address, undefined);
  assert.equal(value.note, '[제거됨] / [제거됨]');
  assert.equal(value.orderId, '16001612345678');
});

test('주문 JSON과 배송 JSON을 분리하고 내부 좌표는 내보내지 않는다', () => {
  const exported = buildExportPayloads([{
    OrderId: '16102412730885', _shipmentBoxId: 'box-a', _nextDataOrderIndex: 0,
    CourierCompany: '로켓배송', TrackingNumber: '10327825750572', DeliveryStatus: '배송완료',
    TrackingEvents: [{ kind: '배송완료', where: '안양1', timeString: '2026-08-20T14:07:00.000Z' }],
    TrackingEventRaw: ['어제 23:07'], Warnings: [], _TrackingOutcome: 'collected'
  }], { exportedAt: '2026-08-21T01:00:00.000Z', pageCount: 1 });

  assert.equal(exported.orderData.orders[0].TrackingEvents, undefined);
  assert.equal(exported.orderData.orders[0]._nextDataOrderIndex, undefined);
  assert.equal(exported.trackingData.length, 1);
  assert.equal(exported.trackingData[0].shipment_box_id, 'box-a');
  assert.equal(exported.trackingSummary.collected, 1);
});

test('이벤트가 있어도 송장번호가 없으면 배송 JSON에서 제외한다', () => {
  const event = { kind: '상품준비중', where: '물류센터', timeString: '2026-08-21T01:00:00.000Z' };
  const exported = buildExportPayloads([
    { OrderId: 'same', _shipmentBoxId: 'box-a', TrackingNumber: null, TrackingEvents: [event], TrackingEventRaw: ['A'] },
    { OrderId: 'same', _shipmentBoxId: 'box-b', TrackingNumber: null, TrackingEvents: [event], TrackingEventRaw: ['B'] }
  ]);

  assert.equal(exported.trackingData.length, 0);
});

test('송장번호가 있는 건은 이벤트가 비어 있어도 배송 JSON에 포함한다', () => {
  const exported = buildExportPayloads([
    { OrderId: 'active', _shipmentBoxId: 'box-active', OrderStatus: '결제완료', TrackingStatus: '아직 배송이 시작되지 않아 이력이 없습니다.', _TrackingOutcome: 'preShipment', TrackingEvents: [] },
    { OrderId: 'invoiced', _shipmentBoxId: 'box-invoiced', TrackingNumber: 'invoice-1', OrderStatus: '배송준비', _TrackingOutcome: 'collected', TrackingEvents: [] }
  ]);

  assert.equal(exported.trackingData.length, 1);
  assert.equal(exported.trackingData[0].order_id, 'invoiced');
  assert.equal(exported.trackingData[0].events.length, 0);
});

test('한 배송박스에 상품 행이 둘이어도 배송조회와 요약은 한 건으로 센다', () => {
  const row = { OrderId: 'same', _shipmentBoxId: 'box-a', TrackingNumber: 'invoice-1', OrderStatus: '배송중', _TrackingOutcome: 'collected', TrackingEvents: [] };
  const exported = buildExportPayloads([{ ...row, VendorItemId: '1' }, { ...row, VendorItemId: '2' }]);

  assert.equal(exported.trackingData.length, 1);
  assert.equal(exported.trackingSummary.collected, 1);
  assert.equal(exported.orderData.orders.length, 2);
});

test('배송박스가 없으면 임의의 배송조회 URL을 만들지 않는다', () => {
  assert.equal(trackingUrlFor({ OrderId: '1', TrackingNumber: '2' }), null);
});
