'use strict';

(() => {
// 쿠팡 주문목록은 Next.js SSR 페이지다. 불안정한 화면 DOM 대신, 서버가 심어준
// __NEXT_DATA__ JSON을 읽는다. 페이지 이동은 URL의 pageIndex(0부터)/year로 하며
// 매 페이지가 서버렌더되어 이 JSON도 페이지마다 갱신된다.
//
// 구매자 이름/전화/주소(order.deliveryDestination 등)는 매핑하지 않는다(PII 정책).

const PHONE_PATTERN = /01[016-9][-\s]?\d{3,4}[-\s]?\d{4}/g;

// 배송상태 코드 → 한글. 없는 코드는 원문 코드를 그대로 둔다.
const STATUS_LABELS = {
  FINAL_DELIVERY: '배송완료'
};

// 상품명/판매자명 같은 자유 텍스트에만 적용하는 안전장치(혹시 모를 전화번호 제거).
function scrubText(value) {
  return typeof value === 'string' ? value.replace(PHONE_PATTERN, '[제거됨]') : value;
}

function num(value) {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

// epoch(ms) → 한국시간 "YYYY-MM-DD HH:mm:ss"
function toKst(ms) {
  if (typeof ms !== 'number' || !Number.isFinite(ms)) {
    return null;
  }
  return new Date(ms).toLocaleString('sv-SE', { timeZone: 'Asia/Seoul' });
}

function productUrl(productId, vendorItemId) {
  if (!productId) {
    return null;
  }
  try {
    const url = new URL(`https://www.coupang.com/vp/products/${productId}`);
    if (vendorItemId) {
      url.searchParams.set('vendorItemId', String(vendorItemId));
    }
    return url.href;
  } catch {
    return null;
  }
}

function readNextData() {
  const el = document.getElementById('__NEXT_DATA__');
  if (!el) {
    return null;
  }
  try {
    return JSON.parse(el.textContent);
  } catch {
    return null;
  }
}

function mapOrders(orderList) {
  const rows = [];

  for (const order of orderList) {
    const orderId = order?.orderId != null ? String(order.orderId) : null;
    const orderedAt = toKst(order?.orderedAt);
    const shippingFee = num(order?.baseDeliveryPrice);
    const orderTotalProductPrice = num(order?.totalProductPrice);

    for (const group of order?.deliveryGroupList ?? []) {
      const statusCode = group?.groupStatus?.status ?? group?.invoiceStatus ?? null;
      const deliveryStatus = statusCode ? STATUS_LABELS[statusCode] || statusCode : null;
      const sellerName = scrubText(group?.vendor?.vendorName ?? null);
      const deliveryMessage = scrubText(group?.pddMessage?.message ?? null);
      const deliveryCompleteDate = toKst(group?.deliveredDate);
      const courierCompany = group?.deliveryCompany?.companyName ?? null;
      const trackingNumber = group?.invoiceNumber ?? null; // 숫자 문자열, scrub 하지 않는다

      const products = group?.productList ?? [];
      const rowsSource = products.length ? products : [null];

      for (const p of rowsSource) {
        rows.push({
          OrderId: orderId,
          OrderedAt: orderedAt,
          SellerName: sellerName,
          ProductName: scrubText(p?.vendorItemName ?? p?.productName ?? order?.title ?? null),
          Quantity: num(p?.quantity),
          UnitPrice: num(p?.unitPrice), // 정가
          ProductPrice: num(p?.discountedUnitPrice ?? p?.combinedUnitPrice ?? p?.unitPrice), // 결제 단가
          ShippingFee: shippingFee,
          OrderTotalProductPrice: orderTotalProductPrice,
          DeliveryStatus: deliveryStatus,
          DeliveryStatusCode: statusCode,
          DeliveryMessage: deliveryMessage, // 예: "8/13(목) 도착"
          DeliveryCompleteDate: deliveryCompleteDate,
          CourierCompany: courierCompany,
          TrackingNumber: trackingNumber,
          ProductUrl: productUrl(p?.productId, p?.vendorItemId),
          DeliveryRegion: null // PII 정책: 배송지 주소는 수집하지 않는다
        });
      }
    }
  }

  return rows;
}

// 지금 화면(현재 URL의 pageIndex)에 해당하는 페이지 한 장만 파싱한다.
function collectCurrentPage() {
  const data = readNextData();
  const desktopOrder = data?.props?.pageProps?.domains?.desktopOrder;
  const orderList = desktopOrder?.orderList;

  if (!Array.isArray(orderList)) {
    return { orderCardCount: 0, orders: [], pagination: null };
  }

  const p = desktopOrder.orderPagination ?? null;
  const pagination = p
    ? {
        hasPrev: !!p.hasPrev,
        prevYear: p.prevYear ?? null,
        prevPageIndex: p.prevPageIndex ?? null,
        hasNext: !!p.hasNext,
        nextYear: p.nextYear ?? null,
        nextPageIndex: p.nextPageIndex ?? null
      }
    : null;

  return {
    orderCardCount: orderList.length,
    orders: mapOrders(orderList),
    pagination
  };
}

globalThis.__coupangOrderCollector = { collectCurrentPage };
})();
