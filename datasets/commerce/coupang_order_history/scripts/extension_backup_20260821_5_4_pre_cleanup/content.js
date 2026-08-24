'use strict';

(() => {
  const BUILD = '2026-08-21a';
  const SELECTORS = Object.freeze({
    productTitleLink: 'a[href*="MyCoupang_my_orders_list_product_title"]',
    productDetailTitleLink: 'a[href*="MyCoupang_order_detail_product_title"]',
    productImageLink: 'a[href*="MyCoupang_my_orders_list_product_image"]',
    price: 'span[translate="yes"]', orderStatus: 'span[style*="font-size:1.25rem"]',
    deliveryNotice: 'span[color="#008C00"]'
  });
  const ORDER_LIST_URL = 'https://mc.coupang.com/ssr/desktop/order/list';
  // 숫자 사이에 끼어 있는 것은 전화번호가 아니다. 주문번호가 잘려 나가던 사고가 있었다.
  const PHONE_PATTERN = /(?<!\d)01[016-9](?:[-\s]?\d{3,4}[-\s]?\d{4}|\*{4}\d{4})(?!\d)/g;
  const BADGE_ALT_PATTERN = /^[A-Z0-9_]+$/;
  const ALLOWED_HOSTS = new Set(['mc.coupang.com', 'www.coupang.com']);
  const PRIVATE_KEYS = new Set(['Recipient', 'RecipientName', 'Phone', 'PhoneNumber', 'Address', 'FullAddress', 'PostalCode']);

  const text = (element) => textSource(element)?.textContent?.replace(/[\s\u200B-\u200D\uFEFF]+/g, ' ').trim() || null;
  // document 를 그대로 넘기면 textContent 가 null 이다. body 로 내려가서 읽는다.
  const textSource = (node) => (node && node.nodeType === 9 ? node.body : node) || node;
  const compact = (element) => (textSource(element)?.textContent || '').replace(/[\s\u200B-\u200D\uFEFF]+/g, '');
  const numberOf = (value) => { const digits = String(value || '').replace(/[^0-9]/g, ''); return digits ? Number(digits) : null; };
  function shortHash(value) { let hash = 2166136261; for (const character of String(value || '')) { hash ^= character.codePointAt(0); hash = Math.imul(hash, 16777619); } return (hash >>> 0).toString(16).padStart(8, '0'); }
  function sanitizeValue(value) {
    if (typeof value === 'string') return value.replace(PHONE_PATTERN, '[제거됨]');
    if (Array.isArray(value)) return value.map(sanitizeValue);
    if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).filter(([key]) => !PRIVATE_KEYS.has(key)).map(([key, item]) => [key, sanitizeValue(item)]));
    return value;
  }
  function safeUrl(element) { const href = element?.getAttribute?.('href'); if (!href) return null; try { const url = new URL(href, 'https://www.coupang.com'); return url.protocol === 'https:' && ALLOWED_HOSTS.has(url.hostname) ? url.href : null; } catch { return null; } }
  const vendorId = (href) => String(href || '').match(/[?&]vendorItemId=(\d+)(?:&|$)/)?.[1] || null;
  function ancestors(element) { const all = []; for (let current = element; current; current = current.parentElement) all.push(current); return all; }
  // body.textContent 에는 script 안의 JSON 문자열까지 들어온다. 쿠팡 SSR 페이지가 그렇다.
  // 그래서 페이지 통짜 텍스트로 표지를 찾으면 목록에서도 상세 라벨이 다 잡힌다.
  const NON_TEXT_TAGS = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE']);
  const visibleElements = (root) => [...(textSource(root)?.querySelectorAll?.('*') || [])].filter((element) => !NON_TEXT_TAGS.has(element.tagName));
  // 라벨과 값이 한 요소에 붙어 있기도 한다. 그럴 땐 리프 안에서 찾는다.
  const hasLeafMatching = (root, pattern) => visibleElements(root).some((element) => !(element.children?.length) && pattern.test(compact(element)));
  const hasElementWithText = (root, wanted) => visibleElements(root).some((element) => compact(element) === wanted);
  const DETAIL_ACTION_TEXT = /^주문상세보기$/;
  function detailActionLeaves(node) { return visibleElements(node).filter((element) => !(element.children?.length) && DETAIL_ACTION_TEXT.test(compact(element))); }
  function orderCardOf(element) {
    let fallback = null;
    for (const candidate of ancestors(element)) {
      if (/\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\s*주문/.test(text(candidate) || '') && /주문\s*상세/.test(text(candidate) || '') && detailActionLeaves(candidate).length <= 1) {
        fallback ||= candidate;
        if (candidate.querySelectorAll?.(SELECTORS.price).length) return candidate;
      }
    }
    if (fallback) return fallback;
    return element?.closest?.('td') || element?.closest?.('tr') || element?.parentElement || element;
  }
  function productContainerOf(element, card) {
    let best = element?.closest?.('td') || element?.parentElement || card;
    for (const candidate of ancestors(element)) { if (candidate === card) break; if ((candidate.querySelectorAll?.(SELECTORS.price).length || 0) === 1 && (candidate.querySelectorAll?.('img[alt]').length || 0) >= 1) best = candidate; }
    return best;
  }
  function productNameOf(link, container) {
    const spanName = text([...(link?.querySelectorAll?.('span') || [])].at(-1));
    if (spanName) return spanName;
    return [...(container?.querySelectorAll?.('img[alt]') || [])].map((image) => image.getAttribute('alt')?.trim()).find((alt) => alt && !BADGE_ALT_PATTERN.test(alt)) || null;
  }
  function quantityAfter(price, container) {
    const spans = [...(container?.querySelectorAll?.('span') || [])];
    for (const span of spans.slice(Math.max(0, spans.indexOf(price) + 1))) { const match = text(span)?.match(/^(\d+)\s*개/); if (match) return Number(match[1]); }
    return null;
  }
  function dateOf(element) { const match = text(element)?.match(/(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\s*주문/); return match ? `${match[1]}-${match[2].padStart(2, '0')}-${match[3].padStart(2, '0')}` : null; }
  function baseOrder(container, card, link, cardIndex = 0, productIndex = 0) {
    const name = productNameOf(link, container); const id = vendorId(link?.getAttribute?.('href')); const price = container?.querySelector?.(SELECTORS.price);
    return { OrderId: `${id || 'unknown'}-${shortHash(name || `${cardIndex}:${productIndex}`)}`, _idSource: 'derived', OrderedAt: dateOf(card), SellerName: null, ProductName: name, Quantity: quantityAfter(price, container), ProductPrice: numberOf(text(price)), ShippingFee: null, TotalAmount: null, OrderStatus: text(container?.querySelector?.(SELECTORS.orderStatus)) || text(card?.querySelector?.(SELECTORS.orderStatus)), DeliveryStatus: text(container?.querySelector?.(SELECTORS.deliveryNotice)) || text(card?.querySelector?.(SELECTORS.deliveryNotice)), DeliveryCompleteDate: null, CourierCompany: null, TrackingNumber: null, ProductUrl: safeUrl(link), VendorItemId: id, DeliveryRegion: null, Warnings: [], _cardIndex: cardIndex, _productIndex: productIndex };
  }
  function parseProduct(link) { const card = orderCardOf(link); return baseOrder(productContainerOf(link, card), card, link); }
  // 목록이 다시 그려지면 카드 순번이 다른 주문을 가리킨다. 내용으로 찾는다.
  const cardKeyOf = (order) => order ? `${order.OrderedAt || ""}|${order.VendorItemId || order.ProductName || ""}` : null;
  function findCard(root, index, key) {
    const cards = discoverCards(root);
    if (key) {
      const rows = parseDocument(root).orders;
      const match = [...new Set(rows.map((order) => order._cardIndex))]
        .find((cardIndex) => cardKeyOf(rows.find((order) => order._cardIndex === cardIndex)) === key);
      if (match !== undefined && cards[match]) return cards[match];
    }
    return cards[index];
  }
  function discoverCards(root) {
    const cards = [];
    // '주문 상세보기' 리프 요소 하나가 주문 하나다. 조상까지 훑으면 목록 전체가 카드로 잡힌다.
    let anchors = detailActionLeaves(root);
    if (!anchors.length) anchors = [...(root?.querySelectorAll?.('*') || [])].filter((element) => !(element.children?.length) && /주문\s*상(?:세보기)?/.test(compact(element)));
    for (const action of anchors) { const card = orderCardOf(action); if (card && !cards.includes(card)) cards.push(card); }
    // 다른 카드를 통째로 포함하는 컨테이너는 카드가 아니다.
    const bounded = cards.filter((card) => !cards.some((other) => other !== card && card.contains?.(other)));
    const result = bounded.length ? bounded : cards;
    if (!result.length && root) result.push(root);
    return result;
  }
  function productRows(card, cardIndex) {
    const result = [];
    for (const [index, price] of [...(card?.querySelectorAll?.(SELECTORS.price) || [])].entries()) {
      const container = productContainerOf(price, card);
      const link = container.querySelector?.(SELECTORS.productTitleLink) || container.querySelector?.(SELECTORS.productDetailTitleLink) || [...(container.querySelectorAll?.('a') || [])].find((item) => item.querySelector?.('span')) || null;
      const order = baseOrder(container, card, link, cardIndex, index);
      if (!order.ProductName) { order.ProductName = [...(container.querySelectorAll?.('img[alt]') || [])].map((image) => image.getAttribute('alt')?.trim()).find((alt) => alt && !BADGE_ALT_PATTERN.test(alt)) || null; order.OrderId = `${order.VendorItemId || 'unknown'}-${shortHash(order.ProductName || `${cardIndex}:${index}`)}`; }
      result.push(order);
    }
    return result;
  }
  function parseDocument(root) { const cards = discoverCards(root); const groups = cards.map((card, index) => productRows(card, index)); return { orders: groups.flat(), orderCardCount: groups.filter((items) => items.length).length }; }
  function actionLeaf(card, labels) {
    const wanted = labels.map((label) => label.replace(/\s+/g, ''));
    const elements = visibleElements(card);
    const innermost = (list) =>
      list.find((element) => ![...(element.children || [])].some((child) => wanted.some((label) => compact(child).includes(label))))
      || list.at(-1) || null;
    // 정확히 일치하는 것을 먼저 쓴다. 포함만 보면 상세 페이지의 다른 '주문목록' 링크를 누른다.
    // 라벨은 구체적인 것부터 온다.
    for (const label of wanted) {
      const exact = elements.filter((element) => compact(element) === label);
      if (!exact.length) continue;
      const clickable = exact.filter((element) => element.tagName === 'BUTTON' || (element.tagName === 'A' && element.getAttribute?.('href')));
      return innermost(clickable.length ? clickable : exact);
    }
    return innermost(elements.filter((element) => wanted.some((label) => compact(element).includes(label))));
  }
  // 리프가 안 먹힐 때를 대비해 조상을 한 칸씩 올린 후보를 함께 둔다.
  function actionCandidates(card, labels) {
    const leaf = actionLeaf(card, labels);
    if (!leaf) return [];
    const chain = [];
    for (let current = leaf; current && chain.length < 4; current = current.parentElement) { chain.push(current); if (current === card) break; }
    return chain;
  }
  function actionIn(card, labels) { return actionCandidates(card, labels)[0] || null; }
  const nearbyActionElement = (link, labels) => actionIn(orderCardOf(link), labels);
  const findOrderDetailAction = (root, order) => actionIn(discoverCards(root)[Number(order?._cardIndex) || 0], ['주문 상세보기', '주문상세보기', '상세보기']);
  const findOrderTrackingAction = (root, order) => actionIn(discoverCards(root)[Number(order?._cardIndex) || 0], ['배송 조회', '배송조회']);
  function findNextButton(root) { return [...(root?.querySelectorAll?.('button') || [])].find((button) => compact(button).includes('다음') && !compact(button).includes('이전')) || null; }
  const isPaginationButtonDisabled = (button) => !button || Boolean(button.disabled) || button.hasAttribute?.('disabled') || button.getAttribute?.('aria-disabled') === 'true';
  function yearEntries(root) { return [...(root?.querySelectorAll?.('*') || [])].map((element) => ({ element, label: text(element) })).filter(({ element, label }) => /^\d{4}$/.test(label || '') && ![...(element.children || [])].some((child) => /^\d{4}$/.test(text(child) || ''))); }
  const extractYearTabs = (root) => yearEntries(root).map(({ label }) => Number(label));
  const hasOrderListData = (root) => { const element = nextDataElement(root); return Boolean(element && (element.textContent || '').includes('"orderList"')); };
  // 서버가 주문 목록 JSON 을 심어줬으면 그것만으로 목록 페이지다.
  // 주소가 가장 확실한 근거다. 배송조회와 주문상세 페이지에도 주문 JSON 이 들어 있어
  // 내용만 보면 목록으로 오인한다.
  const pathOf = (root) => {
    // 전달받은 별도 Document에는 현재 탭의 location을 섞지 않는다.
    // 브라우저의 실제 document는 자체 location을 갖고 있다.
    const href = root?.location?.href || (!root ? globalThis.location?.href : '') || '';
    try { return new URL(href).pathname; } catch { return ''; }
  };
  const isOrderListPage = (root) => {
    const path = pathOf(root);
    if (/\/order\/list(?:\/|$)/.test(path)) return true;
    if (/\/shiptrack(?:\/|$)/.test(path) || /\/order\/\d+(?:\/|$)/.test(path)) return false;
    return (hasOrderListData(root) || detailActionLeaves(root).length > 0)
      && !hasElementWithText(root, '주문목록돌아가기')
      && !hasElementWithText(root, '받는사람정보');
  };
  const rows = (root) => [...(root?.querySelectorAll?.('tr') || [])];
  function rowValue(root, label) {
    const wanted = label.replace(/\s+/g, '');
    const row = rows(root).find((item) => compact(item).startsWith(wanted));
    const directCells = [...(row?.children || [])].filter((cell) => cell.tagName === 'TH' || cell.tagName === 'TD');
    const values = (directCells.length ? directCells : [...(row?.querySelectorAll?.('td') || [])]).map(text);
    const labelIndex = values.findIndex((value) => String(value || '').replace(/\s+/g, '') === wanted);
    if (labelIndex >= 0) return values.slice(labelIndex + 1).find(Boolean) || null;
    for (let index = 0; index < values.length; index += 1) {
      const value = values[index];
      const flattened = String(value || '').replace(/\s+/g, '');
      if (!flattened.startsWith(wanted)) continue;
      const inline = String(value || '').replace(new RegExp(`^\\s*${label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*`), '').trim();
      return inline || values.slice(index + 1).find(Boolean) || null;
    }
    return null;
  }
  function amountAfter(root, label) {
    const source = (textSource(root)?.textContent || '').replace(/[\s\u200B-\u200D\uFEFF]+/g, ' ');
    const escaped = label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const match = source.match(new RegExp(`${escaped}\\s*([+-]?[\\d,]+)\\s*원`));
    return numberOf(match?.[1]);
  }
  function detailProducts(root) {
    const links = [...(root?.querySelectorAll?.(SELECTORS.productDetailTitleLink) || [])];
    return links.map((link, index) => {
      const container = productContainerOf(link, root);
      return baseOrder(container, root, link, 0, index);
    });
  }
  function paymentBreakdownOf(root) {
    const summary = rows(root).map(text).find((value) => /총\s*결제금액/.test(value || '')) || '';
    const methods = [];
    const pattern = /(.+?)([\d,]+)\s*원/g;
    for (const match of summary.matchAll(pattern)) {
      const method = match[1].replace(/^[\s,]+|[\s,]+$/g, '');
      if (!method || /총\s*결제금액/.test(method)) continue;
      methods.push({ method, amount: numberOf(match[2]) });
    }
    return methods;
  }
  function paymentMethodOf(root, methods = paymentBreakdownOf(root)) {
    if (methods.length) return methods.map((item) => item.method).join(' + ');
    const direct = rowValue(root, '결제수단');
    if (direct) return direct;
    const all = rows(root);
    const header = all.findIndex((row) => compact(row).startsWith('결제수단총상품가격'));
    if (header < 0) return null;
    return text(all[header + 1]);
  }
  function parseDetailPage(root, pageUrl = '') {
    const orderId = (text(root) || '').match(/주문번호\s*(\d{8,})/)?.[1] || String(pageUrl).match(/(\d{8,})/)?.[1] || null;
    const address = rowValue(root, '받는주소')?.replace(/^\(\d{5}\)\s*/, ''); const parts = address?.split(/\s+/) || [];
    const link = [...(root.querySelectorAll?.('a') || [])].find((item) => String(item.getAttribute?.('href') || '').includes('/delivery/tracking/'));
    const status = visibleElements(root).filter((element) => !(element.children?.length)).map(text)
      .find((value) => /^(?:결제완료|상품준비중|배송시작|배송중|배송완료|취소완료)$/.test(value || '')) || null;
    const paymentMethods = paymentBreakdownOf(root);
    return sanitizeValue({ OrderId: orderId, _idSource: orderId ? 'orderNumber' : 'derived', OrderedAt: dateOf(root), OrderStatus: status || text(root.querySelector?.(SELECTORS.orderStatus)), products: detailProducts(root), TotalProductAmount: amountAfter(root, '총 상품가격'), DiscountAmount: amountAfter(root, '할인금액'), ShippingFee: amountAfter(root, '배송비'), PaymentMethod: paymentMethodOf(root, paymentMethods), PaymentMethods: paymentMethods, TotalAmount: amountAfter(root, '총 결제금액'), DeliveryRegion: parts.length >= 2 ? `${parts[0]} ${parts[1]}` : null, DeliveryRequest: rowValue(root, '배송요청사항'), _TrackingUrl: link ? new URL(link.getAttribute('href'), 'https://mc.coupang.com').href : null });
  }
  function mergeDetail(order, detail) { const product = { ...(detail.products?.find((item) => item.VendorItemId && item.VendorItemId === order.VendorItemId) || detail.products?.find((item) => item.ProductName === order.ProductName) || {}) }; delete product._cardIndex; delete product._productIndex; Object.assign(order, product, Object.fromEntries(Object.entries(detail).filter(([key, value]) => key !== 'products' && value !== null))); return order; }
  function relativeTime(value, at, warnings) { const raw = String(value || '').trim(); const match = raw.match(/^(오늘|어제)\s+(\d{1,2}):(\d{2})$/); if (!match) { if (raw) warnings.push(`배송 시각을 변환하지 못했습니다: ${raw}`); return raw; } const date = new Date(at); if (match[1] === '어제') date.setDate(date.getDate() - 1); date.setHours(Number(match[2]), Number(match[3]), 0, 0); return date.toISOString(); }
  const STEP_NAMES = ['결제완료', '상품준비중', '배송시작', '배송중', '배송완료'];
  // 진행 막대는 다섯 단계를 항상 다 그린다. 도달한 단계와 아닌 단계는 라벨 클래스가 다르다.
  // 첫 단계는 언제나 도달했으므로 그 클래스를 기준으로 앞에서부터 세어 나간다.
  function deliveryStepInfo(root) {
    const nodes = visibleElements(root).filter((element) => !(element.children?.length) && STEP_NAMES.includes(compact(element)));
    if (!nodes.length) return { all: [], done: [], current: null };
    const all = nodes.map((element) => compact(element));
    const reachedClass = nodes[0].getAttribute?.('class') || '';
    const done = [];
    for (const element of nodes) {
      if ((element.getAttribute?.('class') || '') !== reachedClass) break;
      done.push(compact(element));
    }
    return { all, done, current: done[done.length - 1] || null };
  }
  function parseTrackingPage(root, collectedAt = new Date(), orderStatus = '') {
    const warnings = []; const trackingNumber = rowValue(root, '송장번호')?.replace(/\s+/g, '') || null;
    const trackingRow = rows(root).find((row) => compact(row).startsWith('송장번호')); const courier = text(trackingRow?.closest?.('table')?.querySelector?.('tr')?.querySelector?.('td'));
    const eventTable = [...(root.querySelectorAll?.('table') || [])].find((table) => /시간.*현재위치.*배송상태/.test(compact(table))); const rawTimes = [];
    const events = [...(eventTable?.querySelectorAll?.('tbody tr') || [])].map((row) => { const cells = [...row.querySelectorAll('td')]; const raw = text(cells[0]) || ''; rawTimes.push(raw); return { timeString: relativeTime(raw, collectedAt, warnings), where: text(cells[1]), kind: text(cells[2]) }; }).filter((event) => event.kind || event.where);
    if (trackingNumber && !eventTable) warnings.push('배송 이력 표를 찾지 못했습니다.');
    const parts = [...(root.querySelectorAll?.('*') || [])].map(text).filter(Boolean); const promise = parts.filter((value) => /(?:오늘|내일|어제).*(?:도착|보장|완료)/.test(value) && value.length < 60).sort((a, b) => a.length - b.length)[0] || null; const message = parts.filter((value) => /고객님|준비시작|배송중입니다/.test(value) && value.length < 80).sort((a, b) => a.length - b.length)[0] || null; const stepInfo = deliveryStepInfo(root); const steps = stepInfo.done; const pre = !trackingNumber && events.length === 0;
    return sanitizeValue({ CourierCompany: courier, TrackingNumber: trackingNumber, ShipmentStarted: !pre, TrackingStatus: pre ? '아직 배송이 시작되지 않아 이력이 없습니다.' : null, DeliveryPromise: promise, DeliveryMessage: message, DeliverySteps: steps, DeliveryStep: stepInfo.current, DeliveryStepsAll: stepInfo.all, DeliveryStepIndex: steps.indexOf(orderStatus) >= 0 ? steps.indexOf(orderStatus) : (pre ? 1 : null), TrackingEvents: events, TrackingEventRaw: rawTimes, ReceiptMethod: rowValue(root, '상품수령방법'), Warnings: warnings });
  }

  function buildExportPayloads(orders, meta = {}) {
    const exportedAt = meta.exportedAt || new Date().toISOString(); const trackingData = [];
    const seenTracking = new Set();
    const clean = orders.map((source) => { const order = { ...source }; const events = order.TrackingEvents || []; const raw = order.TrackingEventRaw || []; const trackingKey = `${order.OrderId || ''}|${order._shipmentBoxId || ''}`; if (events.length && !seenTracking.has(trackingKey)) { seenTracking.add(trackingKey); trackingData.push({ courier: order.CourierCompany, tracking_number: order.TrackingNumber || null, shipment_box_id: order._shipmentBoxId || null, order_id: order.OrderId, status: order.DeliveryStatus || order.OrderStatus, events: events.map((event, index) => ({ ...event, raw: raw[index] || event.timeString })), queried_at: exportedAt }); } for (const key of ['TrackingEvents', 'TrackingEventRaw', '_TrackingUrl', '_cardIndex', '_productIndex', '_nextDataOrderIndex', '_nextDataGroupIndex', '_nextDataProductIndex', '_vendorItemIds']) delete order[key]; return order; });
    const trackingSummary = { collected: orders.filter((order) => order._TrackingOutcome === 'collected').length, preShipment: orders.filter((order) => order._TrackingOutcome === 'preShipment').length, buttonMissing: orders.filter((order) => order._TrackingOutcome === 'buttonMissing').length };
    return sanitizeValue({ orderData: { exportedAt, source: ORDER_LIST_URL, collectionScope: meta.collectionScope || 'tracking', pageCount: meta.pageCount || 0, orderCount: clean.length, warning: meta.warning || null, orders: clean }, trackingData, trackingSummary });
  }
  function listPositionKey(root = globalThis.document) { return shortHash(parseDocument(root).orders.map((order) => `${order.OrderedAt}|${order.VendorItemId}|${order.ProductName}`).join('||')); }
  function pageSignature(root = globalThis.document, href = globalThis.location?.href || '') { const ids = parseDocument(root).orders.map((order) => `${order.OrderedAt}|${order.VendorItemId}|${order.ProductName}`).join('||'); return `${href}|${shortHash(ids)}`; }
  const progress = (state, message) => ({ stage: state.phase, page: state.page, count: state.orders.length, orderCount: new Set(state.orders.map((order) => order.OrderId).filter(Boolean)).size, queueDone: state.cursor || 0, queueTotal: (state.queue || []).length, trackingCount: (state.tracking || []).length, pageCount: state.pageCount || 0, year: state.years[state.yearIndex]?.label || null, remaining: Math.max(0, state.queue.length - state.cursor), message });
  function initialState(config = {}) { return { phase: 'INIT', scope: config.collectionScope || config.scope || 'tracking', years: [], yearIndex: 0, page: 1, orders: [], tracking: [], queue: [], cursor: 0, warnings: [], done: false, yearScope: config.yearScope || 'current', pageCount: 0, listSignature: null, listUrl: null, listKey: null, restore: null, seenKeys: [], orderKeys: [], expectedListUrl: null, pagination: null, listingDone: false, skipCurrent: false, pageRetries: 0 }; }
  function finish(state) { state.phase = 'DONE'; state.done = true; state.result = buildExportPayloads(state.orders, { collectionScope: state.scope, pageCount: state.pageCount, warning: state.warnings.length ? state.warnings.join(' ') : null }); state.tracking = state.result.trackingData; return { state, action: { type: 'done' }, progress: progress(state, '수집이 완료되었습니다.') }; }
  function runStep(input = {}) {
    const out = runStepInner(input);
    // 정체 횟수를 클릭 후보 단계로 쓴다. 0이면 리프, 1이면 부모, ...
    if (out?.action?.type === 'click') {
      const expects = { detail: 'leftList', tracking: 'tracking', nextPage: 'listChanged', yearTab: 'listChanged', backToList: 'backOnList' };
      const current = (out.state.queue || [])[out.state.cursor || 0];
      if (current?.cardKey && (out.action.target === 'detail' || out.action.target === 'tracking')) out.action.cardKey = current.cardKey;
      out.action.expect = expects[out.action.target] || null;
    }
    // 실행 중에는 state.orders가 체크포인트다. 결과를 매 걸음 복제하면 storage 사용량이 두 배가 된다.
    // 중단 시 팝업이 이 누적 상태에서 부분 결과를 만들고, 완료 시에만 finish()가 최종 결과를 저장한다.
    return out;
  }
  function documentUrl(root = globalThis.document) {
    return root?.location?.href || globalThis.location?.href || '';
  }
  function sameListCoordinate(left, right) {
    try {
      const a = new URL(left, ORDER_LIST_URL);
      const b = new URL(right, ORDER_LIST_URL);
      return a.pathname === b.pathname
        && (a.searchParams.get('pageIndex') || '0') === (b.searchParams.get('pageIndex') || '0')
        && (a.searchParams.get('requestYear') || '') === (b.searchParams.get('requestYear') || '');
    } catch { return false; }
  }
  function detailUrlFor(orderId) {
    return orderId ? `https://mc.coupang.com/ssr/desktop/order/${encodeURIComponent(orderId)}` : null;
  }
  function matchesDetailDocument(root, orderId) {
    try {
      const url = new URL(documentUrl(root));
      return url.pathname === `/ssr/desktop/order/${orderId}`;
    } catch { return false; }
  }
  function matchesTrackingDocument(root, orderId, shipmentBoxId) {
    try {
      const url = new URL(documentUrl(root));
      return url.pathname === '/ssr/desktop/shiptrack'
        && url.searchParams.get('orderId') === String(orderId || '')
        && url.searchParams.get('shipmentBoxId') === String(shipmentBoxId || '');
    } catch { return false; }
  }
  const isDocumentComplete = (root) => !root?.readyState || root.readyState === 'complete';
  const isDetailReady = (root) => isDocumentComplete(root)
    && /주문번호/.test(compact(root))
    && (/결제정보|받는사람정보/.test(compact(root)) || Boolean(root?.querySelector?.(SELECTORS.productDetailTitleLink)));
  const isTrackingReady = (root) => isDocumentComplete(root) && /송장번호|상품수령방법|결제완료|상품준비중|배송시작|배송중|배송완료/.test(compact(root));
  function pageBlockedReason(root) {
    const body = compact(root);
    if (/로그인|signin/i.test(body) && !/주문번호|송장번호/.test(body)) return '로그인 화면이 열렸습니다.';
    if (/접근이거부|요청을처리할수없|AccessDenied/i.test(body)) return '쿠팡이 문서 접근을 거부했습니다.';
    return null;
  }
  function nextDataOrderKey(order) {
    return [order.OrderId, order._shipmentBoxId, order.VendorItemId, order._nextDataGroupIndex, order._nextDataProductIndex].map((value) => value ?? '').join('|');
  }
  function nextDataPageKey(root, orders, paging) {
    let coordinate = '';
    try {
      const url = new URL(documentUrl(root), ORDER_LIST_URL);
      coordinate = `${url.searchParams.get('requestYear') || ''}:${url.searchParams.get('pageIndex') || paging?.currentPageIndex || 0}`;
    } catch { coordinate = `${paging?.currentPageIndex ?? 0}`; }
    return `${coordinate}:${shortHash(orders.map(nextDataOrderKey).join('||'))}`;
  }
  function appendNextDataOrders(state, orders) {
    const known = new Set(state.orderKeys || []);
    state.orderKeys ||= [];
    for (const order of orders) {
      const key = nextDataOrderKey(order);
      if (known.has(key)) continue;
      known.add(key);
      state.orderKeys.push(key);
      state.orders.push(order);
    }
  }
  function enrichmentQueue(state) {
    const groups = new Map();
    state.orders.forEach((order, index) => {
      const key = `${order.OrderId || ''}|${order._shipmentBoxId || ''}`;
      let item = groups.get(key);
      if (!item) {
        item = { key, orderId: order.OrderId || null, shipmentBoxId: order._shipmentBoxId || null, orderIndexes: [], vendorItemIds: [], detailDone: state.scope === 'list', trackingDone: state.scope !== 'tracking' || !order._shipmentBoxId, returning: null, detailAttempts: 0, trackingAttempts: 0, loadingSince: 0 };
        groups.set(key, item);
      }
      item.orderIndexes.push(index);
      if (order.VendorItemId && !item.vendorItemIds.includes(order.VendorItemId)) item.vendorItemIds.push(order.VendorItemId);
    });
    return [...groups.values()];
  }
  function beginEnrichment(state) {
    state.listingDone = true;
    state.queue = enrichmentQueue(state);
    state.cursor = 0;
    if (state.scope === 'list') return finish(state);
    state.phase = 'DETAIL';
    return { state, action: { type: 'none' }, progress: progress(state, `목록 ${state.pageCount}페이지를 모두 읽었습니다. 상세·배송 수집을 시작합니다.`) };
  }
  function warnItem(state, item, reason) {
    state.warnings.push(reason);
    for (const index of item.orderIndexes || []) {
      const order = state.orders[index];
      if (order) order.Warnings = [...(order.Warnings || []), reason];
    }
  }
  function trackingUrlForItem(state, item) {
    const first = state.orders[item.orderIndexes?.[0]];
    return trackingUrlFor(first ? { ...first, _vendorItemIds: item.vendorItemIds || [] } : null);
  }
  function runNextDataStep(state, root) {
    state.mode = 'nextData';
    if (state.done || state.phase === 'DONE') return finish(state);
    if (state.phase === 'INIT') {
      if (!isOrderListPage(root)) return { state, action: { type: 'navigate', target: 'list', url: ORDER_LIST_URL, expectedUrl: ORDER_LIST_URL }, progress: progress(state, '주문 목록으로 이동합니다.') };
      const entries = yearEntries(root);
      const yearLabels = [...new Set(entries.map(({ label }) => label))];
      state.years = state.yearScope === 'all' ? yearLabels.map((label) => ({ label, done: false })) : [{ label: null, done: false }];
      if (!state.years.length) state.years = [{ label: null, done: false }];
      state.startListUrl = state.yearScope === 'current' ? ORDER_LIST_URL : (documentUrl(root) || ORDER_LIST_URL);
      state.phase = 'LIST';
      if (state.yearScope === 'all' && state.years[0]?.label) {
        const url = listUrlForPage(0, state.years[0].label);
        state.expectedListUrl = url;
        if (!sameListCoordinate(documentUrl(root), url)) {
          return { state, action: { type: 'navigate', target: 'list', url, expectedUrl: url }, progress: progress(state, `${state.years[0].label}년 목록부터 수집합니다.`) };
        }
      }
      if (state.yearScope === 'current' && !sameListCoordinate(documentUrl(root), ORDER_LIST_URL)) {
        state.expectedListUrl = ORDER_LIST_URL;
        return { state, action: { type: 'navigate', target: 'list', url: ORDER_LIST_URL, expectedUrl: ORDER_LIST_URL }, progress: progress(state, '연도 필터 없는 첫 목록부터 수집합니다.') };
      }
      return { state, action: { type: 'none' }, progress: progress(state, '목록 JSON을 확인했습니다.') };
    }
    if (state.phase === 'LIST') {
      if (!isOrderListPage(root)) {
        const url = state.expectedListUrl || state.listUrl || state.startListUrl || ORDER_LIST_URL;
        return { state, action: { type: 'navigate', target: 'list', url, expectedUrl: url }, progress: progress(state, '수집할 목록 페이지로 이동합니다.') };
      }
      if (state.expectedListUrl && !sameListCoordinate(documentUrl(root), state.expectedListUrl)) {
        return { state, action: { type: 'navigate', target: 'list', url: state.expectedListUrl, expectedUrl: state.expectedListUrl }, progress: progress(state, '정확한 다음 목록 페이지를 기다립니다.') };
      }
      const pageOrders = ordersFromNextData(root);
      const paging = paginationFromNextData(root);
      if (!pageOrders || !paging) return { state, action: { type: 'none' }, progress: progress(state, '목록 JSON 렌더링을 기다립니다.') };
      const key = nextDataPageKey(root, pageOrders, paging);
      state.seenKeys ||= [];
      if (!state.seenKeys.includes(key)) {
        appendNextDataOrders(state, pageOrders);
        state.seenKeys.push(key);
        state.pageCount += 1;
        state.pageRetries = 0;
      }
      state.listKey = key;
      state.listSignature = key;
      state.listUrl = documentUrl(root) || state.expectedListUrl || ORDER_LIST_URL;
      state.expectedListUrl = null;
      state.pagination = paging;
      state.phase = 'NEXT_PAGE';
      return { state, action: { type: 'none' }, progress: progress(state, `목록 ${state.pageCount}페이지를 읽었습니다.`) };
    }
    if (state.phase === 'NEXT_PAGE') {
      const paging = state.pagination;
      if (paging?.hasNext && paging.nextPageIndex !== null) {
        const year = state.yearScope === 'all' ? state.years[state.yearIndex]?.label : null;
        const url = listUrlForPage(paging.nextPageIndex, year);
        state.page += 1;
        state.phase = 'LIST';
        state.expectedListUrl = url;
        return { state, action: { type: 'navigate', target: 'list', url, expectedUrl: url }, progress: progress(state, `${state.page}페이지로 이동합니다.`) };
      }
      if (paging?.hasNext && paging.nextPageIndex === null) {
        state.pageRetries = (state.pageRetries || 0) + 1;
        if (state.pageRetries <= 3) {
          state.phase = 'LIST';
          return { state, action: { type: 'none' }, progress: progress(state, `다음 페이지 좌표를 다시 확인합니다(${state.pageRetries}/3).`) };
        }
        state.warnings.push('서버가 다음 페이지가 있다고 했지만 다음 페이지 좌표를 주지 않아 목록 수집을 중단했습니다.');
      }
      if (state.yearScope === 'all') {
        if (state.years[state.yearIndex]) state.years[state.yearIndex].done = true;
        state.phase = 'NEXT_YEAR';
        return { state, action: { type: 'none' }, progress: progress(state, '현재 연도의 마지막 페이지입니다.') };
      }
      return beginEnrichment(state);
    }
    if (state.phase === 'NEXT_YEAR') {
      const nextIndex = state.yearIndex + 1;
      if (nextIndex >= state.years.length) return beginEnrichment(state);
      state.yearIndex = nextIndex;
      state.page = 1;
      state.pagination = null;
      state.phase = 'LIST';
      const url = listUrlForPage(0, state.years[nextIndex].label);
      state.expectedListUrl = url;
      return { state, action: { type: 'navigate', target: 'list', url, expectedUrl: url }, progress: progress(state, `${state.years[nextIndex].label}년 목록으로 이동합니다.`) };
    }
    if (state.phase === 'DETAIL') {
      const item = state.queue[state.cursor];
      if (!item) return finish(state);
      if (state.skipCurrent) {
        state.skipCurrent = false;
        const isTracking = item.returning === 'tracking' || item.detailDone;
        const reason = `${isTracking ? '배송조회' : '주문상세'} 문서를 열지 못해 이 항목을 건너뜁니다.`;
        warnItem(state, item, reason);
        if (isTracking) { item.trackingDone = true; state.cursor += 1; }
        else item.detailDone = true;
        item.returning = null;
        item.loadingSince = 0;
        return { state, action: { type: 'none' }, progress: progress(state, reason) };
      }
      const order = state.orders[item.orderIndexes?.[0]];
      if (!item.detailDone) {
        const url = detailUrlFor(item.orderId || order?.OrderId);
        if (!url) {
          const reason = '실제 주문번호가 없어 주문상세를 건너뜁니다.';
          warnItem(state, item, reason); item.detailDone = true; item.returning = null;
          return { state, action: { type: 'none' }, progress: progress(state, reason) };
        }
        if (item.returning === 'detail') {
          const blocked = pageBlockedReason(root);
          const atTarget = matchesDetailDocument(root, item.orderId);
          if (!blocked && atTarget && isDetailReady(root)) {
            const detail = parseDetailPage(root, documentUrl(root));
            if (String(detail.OrderId || '') === String(item.orderId || '')) {
              const sameOrderIndexes = state.orders.map((candidate, index) => candidate?.OrderId === item.orderId ? index : -1).filter((index) => index >= 0);
              for (const index of sameOrderIndexes) mergeDetail(state.orders[index], detail);
              for (const queued of state.queue) if (queued.orderId === item.orderId) queued.detailDone = true;
              item.returning = null; item.loadingSince = 0;
              return { state, action: { type: 'none' }, progress: progress(state, `주문 ${item.orderId} 상세를 읽었습니다.`) };
            }
          }
          if (!blocked && Date.now() - (item.loadingSince || Date.now()) < 10000) return { state, action: { type: 'none' }, progress: progress(state, atTarget ? '주문상세 문서가 완성되기를 기다립니다.' : '정확한 주문상세 주소가 열리기를 기다립니다.') };
          item.returning = null;
          if ((item.detailAttempts || 0) >= 3) {
            const reason = `주문 ${item.orderId} 상세 파싱 실패: ${blocked || (atTarget ? '필수 표지가 없습니다.' : '다른 주소로 이동했습니다.')}`;
            warnItem(state, item, reason); item.detailDone = true;
            return { state, action: { type: 'none' }, progress: progress(state, reason) };
          }
        }
        item.detailAttempts = (item.detailAttempts || 0) + 1;
        item.returning = 'detail'; item.loadingSince = Date.now();
        return { state, action: { type: 'navigate', target: 'detail', url, expectedUrl: url, expectedOrderId: item.orderId }, progress: progress(state, `주문 ${item.orderId} 상세를 엽니다(${item.detailAttempts}/3).`) };
      }
      if (!item.trackingDone) {
        const url = trackingUrlForItem(state, item);
        if (!url) {
          const reason = `주문 ${item.orderId}의 배송박스 식별자가 없어 배송조회를 건너뜁니다.`;
          warnItem(state, item, reason);
          for (const index of item.orderIndexes) state.orders[index]._TrackingOutcome = 'buttonMissing';
          item.trackingDone = true; state.cursor += 1;
          return { state, action: { type: 'none' }, progress: progress(state, reason) };
        }
        if (item.returning === 'tracking') {
          const blocked = pageBlockedReason(root);
          const atTarget = matchesTrackingDocument(root, item.orderId, item.shipmentBoxId);
          if (!blocked && atTarget && isTrackingReady(root)) {
            const tracking = parseTrackingPage(root, new Date(), order?.OrderStatus);
            for (const index of item.orderIndexes) {
              Object.assign(state.orders[index], tracking);
              state.orders[index]._TrackingOutcome = tracking.ShipmentStarted ? 'collected' : 'preShipment';
            }
            item.trackingDone = true; item.returning = null; item.loadingSince = 0; state.cursor += 1;
            state.tracking = buildExportPayloads(state.orders).trackingData;
            return { state, action: { type: 'none' }, progress: progress(state, `주문 ${item.orderId} 배송조회 ${item.shipmentBoxId}를 읽었습니다.`) };
          }
          if (!blocked && Date.now() - (item.loadingSince || Date.now()) < 10000) return { state, action: { type: 'none' }, progress: progress(state, atTarget ? '배송조회 문서가 완성되기를 기다립니다.' : '정확한 배송조회 주소가 열리기를 기다립니다.') };
          item.returning = null;
          if ((item.trackingAttempts || 0) >= 3) {
            const reason = `주문 ${item.orderId} 배송조회 파싱 실패: ${blocked || (atTarget ? '필수 표지가 없습니다.' : '다른 주소로 이동했습니다.')}`;
            warnItem(state, item, reason); item.trackingDone = true; state.cursor += 1;
            return { state, action: { type: 'none' }, progress: progress(state, reason) };
          }
        }
        item.trackingAttempts = (item.trackingAttempts || 0) + 1;
        item.returning = 'tracking'; item.loadingSince = Date.now();
        return { state, action: { type: 'navigate', target: 'tracking', url, expectedUrl: url, expectedOrderId: item.orderId, expectedShipmentBoxId: item.shipmentBoxId }, progress: progress(state, `주문 ${item.orderId} 배송조회를 엽니다(${item.trackingAttempts}/3).`) };
      }
      state.cursor += 1;
      return { state, action: { type: 'none' }, progress: progress(state, '다음 주문을 확인합니다.') };
    }
    return finish(state);
  }
  function runStepInner(input = {}) {
    const state = Object.assign(initialState(input), input);
    const root = globalThis.document;
    const useNextData = state.mode === 'nextData' || (state.phase === 'INIT' && root && isOrderListPage(root) && Boolean(nextDataElement(root)));
    return useNextData ? runNextDataStep(state, root) : runLegacyStepInner(input);
  }
  function runLegacyStepInner(input = {}) {
    const state = Object.assign(initialState(input), input); const root = globalThis.document;
    if (!root) return { state, action: { type: 'none' }, progress: progress(state, '문서를 기다리고 있습니다.') };
    if (state.done || state.phase === 'DONE') return finish(state);
    if (state.phase === 'INIT') { if (!isOrderListPage(root)) return { state, action: { type: 'navigate', url: ORDER_LIST_URL }, progress: progress(state, '주문 목록으로 이동합니다.') }; const entries = yearEntries(root); state.years = (state.yearScope === 'current' ? entries.slice(0, 1) : entries).map(({ label }) => ({ label, done: false })); if (!state.years.length) state.years = [{ label: null, done: false }]; state.phase = 'LIST'; return { state, action: { type: 'none' }, progress: progress(state, '주문 목록을 확인했습니다.') }; }
    if (state.phase === 'LIST') { if (!isOrderListPage(root)) return { state, action: { type: 'navigate', url: state.listUrl || ORDER_LIST_URL }, progress: progress(state, '주문 목록으로 돌아갑니다.') }; const signature = pageSignature(root); const key = listPositionKey(root); state.seenKeys = state.seenKeys || []; if (key === state.listKey || state.seenKeys.includes(key)) { const next = findNextButton(root); if (next && !isPaginationButtonDisabled(next) && (state.pageRetries || 0) < 2) { state.pageRetries = (state.pageRetries || 0) + 1; state.page = Math.max(1, state.page - 1); state.phase = 'NEXT_PAGE'; return { state, action: { type: 'none' }, progress: progress(state, `페이지가 넘어가지 않아 다시 시도합니다(${state.pageRetries}).`) }; } state.warnings.push(next && !isPaginationButtonDisabled(next) ? '다음 버튼이 있지만 페이지가 넘어가지 않아 멈춥니다.' : '마지막 페이지에 도달했습니다.'); state.queue = []; state.cursor = 0; state.phase = 'NEXT_YEAR'; return { state, action: { type: 'none' }, progress: progress(state, '마지막 페이지입니다.') }; } if (signature !== state.listSignature) { const fromJson = ordersFromNextData(root); const parsed = fromJson && fromJson.length ? { orders: fromJson.map((order) => ({ ...order, _cardIndex: fromJson.findIndex((candidate) => candidate.OrderId === order.OrderId && candidate._shipmentBoxId === order._shipmentBoxId) })), orderCardCount: fromJson.length } : parseDocument(root); const base = state.orders.length; state.orders.push(...parsed.orders); state.queue = [...new Set(parsed.orders.map((order) => order._cardIndex))].map((cardIndex) => ({ cardIndex, cardKey: cardKeyOf(parsed.orders.find((order) => order._cardIndex === cardIndex)), orderIndexes: parsed.orders.map((order, index) => order._cardIndex === cardIndex ? base + index : -1).filter((index) => index >= 0), detailDone: state.scope === 'list', trackingDone: state.scope !== 'tracking' || Boolean(fromJson && fromJson.length && !parsed.orders.some((order) => order._cardIndex === cardIndex && order._shipmentBoxId)), returning: null })); state.cursor = 0; state.pageRetries = 0; state.pageCount += 1; state.listSignature = signature; state.listKey = key; state.seenKeys = [...state.seenKeys.slice(-40), key]; state.listUrl = globalThis.location?.href || ORDER_LIST_URL; } state.phase = state.scope === 'list' ? 'NEXT_PAGE' : 'DETAIL'; return { state, action: { type: 'none' }, progress: progress(state, '현재 페이지의 주문을 읽었습니다.') }; }
    if (state.phase === 'DETAIL') {
      const item = state.queue[state.cursor]; if (item && state.skipCurrent) { state.skipCurrent = false; const failed = item.detailDone ? '배송 조회' : '주문 상세'; const reason = `페이지가 반응하지 않아 ${failed}를 건너뜁니다.`; for (const index of item.orderIndexes) { const order = state.orders[index]; if (order) order.Warnings = [...(order.Warnings || []), reason]; } if (item.detailDone) item.trackingDone = true; else item.detailDone = true; item.returning = null; if (item.detailDone && item.trackingDone) state.cursor += 1; return { state, action: { type: 'none' }, progress: progress(state, reason) }; } if (!item) { state.phase = 'NEXT_PAGE'; return { state, action: { type: 'none' }, progress: progress(state, '현재 페이지의 상세 수집을 마쳤습니다.') }; }
      if (!isOrderListPage(root)) { if (item.returning === 'detail') { const detail = parseDetailPage(root, globalThis.location?.href || ''); for (const index of item.orderIndexes) mergeDetail(state.orders[index], detail); item.detailDone = true; item.returning = 'fromDetail'; } else if (item.returning === 'tracking') { const tracking = parseTrackingPage(root, new Date(), state.orders[item.orderIndexes[0]]?.OrderStatus); for (const index of item.orderIndexes) { Object.assign(state.orders[index], tracking); state.orders[index]._TrackingOutcome = tracking.ShipmentStarted ? 'collected' : 'preShipment'; } const added = buildExportPayloads(item.orderIndexes.map((index) => state.orders[index])).trackingData; const known = new Set(state.tracking.map((entry) => `${entry.order_id}|${entry.tracking_number}`)); state.tracking.push(...added.filter((entry) => !known.has(`${entry.order_id}|${entry.tracking_number}`))); item.trackingDone = true; item.returning = 'fromTracking'; } return { state, action: { type: 'click', target: 'backToList', index: item.cardIndex }, progress: progress(state, '주문 목록으로 돌아갑니다.') }; }
      if (state.listKey && listPositionKey(root) !== state.listKey) { state.restore = { yearDone: false, attempts: 0 }; state.phase = 'RESTORE'; return { state, action: { type: 'none' }, progress: progress(state, '목록 위치가 달라져 복원합니다.') }; }
    if (item.returning === 'fromDetail') item.returning = null; if (item.returning === 'fromTracking') { item.returning = null; state.cursor += 1; return { state, action: { type: 'none' }, progress: progress(state, '다음 주문을 확인합니다.') }; }
      if (!item.detailDone) { item.returning = 'detail'; return { state, action: { type: 'click', target: 'detail', index: item.cardIndex }, progress: progress(state, '주문 상세를 엽니다.') }; }
      if (!item.trackingDone) { const order = state.orders[item.orderIndexes[0]]; const trackUrl = trackingUrlFor(order); if (trackUrl) { item.returning = 'tracking'; return { state, action: { type: 'navigate', url: trackUrl, expect: 'tracking' }, progress: progress(state, '배송조회 주소로 이동합니다.') }; } if (!findOrderTrackingAction(root, order)) { for (const index of item.orderIndexes) { state.orders[index].Warnings = [...(state.orders[index].Warnings || []), '배송 조회 버튼이 없는 주문입니다(취소/환불 등).']; state.orders[index]._TrackingOutcome = 'buttonMissing'; } item.trackingDone = true; state.cursor += 1; return { state, action: { type: 'none' }, progress: progress(state, '배송 조회가 없는 주문을 건너뜁니다.') }; } item.returning = 'tracking'; return { state, action: { type: 'click', target: 'tracking', index: item.cardIndex }, progress: progress(state, '배송 조회를 엽니다.') }; }
      state.cursor += 1; return { state, action: { type: 'none' }, progress: progress(state, '다음 주문을 확인합니다.') };
    }
    if (state.phase === 'RESTORE') {
      if (!isOrderListPage(root)) return { state, action: { type: 'navigate', url: state.listUrl || ORDER_LIST_URL }, progress: progress(state, '주문 목록으로 돌아갑니다.') };
      if (listPositionKey(root) === state.listKey) { state.restore = null; state.phase = 'DETAIL'; return { state, action: { type: 'none' }, progress: progress(state, '목록 위치를 복원했습니다.') }; }
      const restore = state.restore || (state.restore = { yearDone: false, attempts: 0 });
      const giveUp = (reason) => { state.warnings.push(reason); for (const index of (state.queue[state.cursor]?.orderIndexes || [])) { const order = state.orders[index]; if (order) order.Warnings = [...(order.Warnings || []), reason]; } state.restore = null; state.phase = 'NEXT_PAGE'; return { state, action: { type: 'none' }, progress: progress(state, reason) }; };
      if (restore.attempts > state.page + 3) return giveUp('목록 위치를 복원하지 못해 이 페이지의 남은 주문을 건너뜁니다.');
      restore.attempts += 1;
      const label = state.years[state.yearIndex]?.label;
      if (!restore.yearDone && label && state.yearScope !== 'current') { restore.yearDone = true; const tabIndex = yearEntries(root).findIndex((entry) => entry.label === label); if (tabIndex >= 0) return { state, action: { type: 'click', target: 'yearTab', index: tabIndex }, progress: progress(state, `${label} 연도로 돌아갑니다.`) }; }
      const next = findNextButton(root);
      if (!next || isPaginationButtonDisabled(next)) return giveUp('목록 위치 복원 중 다음 페이지 버튼을 찾지 못했습니다.');
      return { state, action: { type: 'click', target: 'nextPage', index: 0 }, progress: progress(state, `목록 위치를 복원하는 중입니다(${restore.attempts}회).`) };
    }
    if (state.phase === 'NEXT_PAGE') { const paging = paginationFromNextData(root); if (paging) { if (!paging.hasNext) { if (state.years[state.yearIndex]) state.years[state.yearIndex].done = true; state.phase = 'NEXT_YEAR'; return { state, action: { type: 'none' }, progress: progress(state, '마지막 페이지입니다.') }; } state.page += 1; state.phase = 'LIST'; const url = listUrlForPage(paging.nextPageIndex, state.years[state.yearIndex]?.label); state.listUrl = url; return { state, action: { type: 'navigate', url }, progress: progress(state, `${paging.nextPageIndex + 1}번째 페이지로 이동합니다.`) }; } const next = findNextButton(root); if (next && !isPaginationButtonDisabled(next)) { state.page += 1; state.phase = 'LIST'; return { state, action: { type: 'click', target: 'nextPage', index: 0 }, progress: progress(state, '다음 페이지로 이동합니다.') }; } if (state.years[state.yearIndex]) state.years[state.yearIndex].done = true; state.phase = 'NEXT_YEAR'; return { state, action: { type: 'none' }, progress: progress(state, '현재 연도의 마지막 페이지입니다.') }; }
    if (state.phase === 'NEXT_YEAR') { const nextIndex = state.yearIndex + 1; if (nextIndex >= state.years.length) return finish(state); const label = state.years[nextIndex].label; const tabIndex = yearEntries(root).findIndex((entry) => entry.label === label); if (tabIndex < 0) { state.warnings.push(`${label} 연도 탭을 찾지 못했습니다.`); state.yearIndex = nextIndex; return { state, action: { type: 'none' }, progress: progress(state, '다음 연도 탭을 찾습니다.') }; } state.yearIndex = nextIndex; state.page = 1; state.phase = 'LIST'; return { state, action: { type: 'click', target: 'yearTab', index: tabIndex }, progress: progress(state, `${label} 연도로 이동합니다.`) }; }
    return finish(state);
  }
  // 클릭이 안 먹히는 페이지가 있다. 대상과 방법을 함께 올려가며 시도한다.
  // 0: 리프+이벤트, 1: 리프+native, 2: 부모+이벤트, 3: 부모+native
  function clickElement(element, native = false) {
    if (!element) return false;
    if (native) {
      if (typeof element.click !== 'function') return false;
      element.click();
      return true;
    }
    const view = globalThis.window;
    if (view && typeof view.MouseEvent === 'function') {
      for (const type of ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']) {
        try { element.dispatchEvent(new view.MouseEvent(type, { bubbles: true, cancelable: true, view })); } catch { /* 지원 안 하는 이벤트는 건너뛴다 */ }
      }
      return true;
    }
    if (typeof element.click === 'function') { element.click(); return true; }
    return false;
  }
  function performAction(action) {
    const root = globalThis.document;
    if (!action || ['none', 'done'].includes(action.type)) return { ok: true };
    if (action.type !== 'click') return { ok: false, reason: '클릭 액션이 아닙니다.' };
    const attempt = Math.max(0, action.attempt || 0);
    let candidates = [];
    if (action.target === 'nextPage') candidates = [findNextButton(root)].filter(Boolean);
    if (action.target === 'yearTab') candidates = [yearEntries(root)[action.index]?.element].filter(Boolean);
    if (action.target === 'detail') candidates = actionCandidates(findCard(root, action.index, action.cardKey), ['주문 상세보기', '주문상세보기']);
    if (action.target === 'tracking') candidates = actionCandidates(findCard(root, action.index, action.cardKey), ['배송 조회', '배송조회']);
    if (action.target === 'backToList') candidates = actionCandidates(root, ['주문목록 돌아가기', '주문 목록 돌아가기', '주문목록']);
    if (!candidates.length) return { ok: false, reason: `${action.target} 요소를 찾지 못했습니다.` };
    // 재시도할수록 바깥쪽 조상을 누른다. 후보가 모자라면 마지막 것을 쓴다.
    const depth = Math.min(attempt >> 1, candidates.length - 1);
    const native = (attempt % 2) === 1;
    const target = candidates[depth];
    if (action.target === 'nextPage' && isPaginationButtonDisabled(target)) return { ok: false, reason: '다음 버튼이 비활성 상태입니다.' };
    if (!clickElement(target, native)) return { ok: false, reason: '클릭할 수 없는 요소입니다.' };
    return { ok: true, attempt, depth, native, tag: target.tagName || null };
  }
  // 지금 페이지에서 무엇을 누를지 그대로 보여준다. 클릭은 하지 않는다.
  function describeTarget(target, index = 0, attempt = 0) {
    const root = globalThis.document;
    const labels = target === 'tracking'
      ? ['배송 조회', '배송조회']
      : ['주문 상세보기', '주문상세보기'];
    const cards = discoverCards(root);
    const card = cards[index];
    const candidates = card ? actionCandidates(card, labels) : [];
    const pick = candidates[Math.min(attempt, Math.max(0, candidates.length - 1))];
    return {
      build: BUILD,
      url: globalThis.location?.href || null,
      isList: isOrderListPage(root),
      cardCount: cards.length,
      candidateCount: candidates.length,
      chain: candidates.map((element) => `${element.tagName}.${(element.getAttribute?.('class') || '').split(' ')[0]}`),
      pickTag: pick?.tagName || null,
      pickText: pick ? (pick.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 30) : null,
      signature: pageSignature(root)
    };
  }
  // 지금 이 문서가 무엇으로 보이는지 그대로 보고한다.
  // 지금 문서의 사실만 모아 준다. 판단은 호출한 쪽에서 한다.
  // 쿠팡 주문목록은 Next.js SSR 페이지다. 서버가 __NEXT_DATA__ 에 주문 데이터를 통째로
  // 심어준다. 화면 DOM 을 긁는 것보다 정확하고, 상세 페이지에 들어갈 이유도 없앤다.
  // 주문번호, 판매자, 단가, 배송비, 택배사, 송장번호가 여기에 다 있다.
  const STATUS_LABELS = Object.freeze({ FINAL_DELIVERY: '배송완료' });

  function nextDataElement(root) {
    const target = (root && root.nodeType === 9 && root.body) ? root.body : root;
    return root?.getElementById?.('__NEXT_DATA__')
      || target?.querySelector?.('script[id="__NEXT_DATA__"]')
      || target?.querySelector?.('#__NEXT_DATA__')
      || null;
  }

  // 폴링은 0.4초마다 돈다. 그때마다 JSON 전체를 다시 파싱하면 그 자체가 느려진다.
  // 같은 문서에서는 한 번만 파싱하고 결과를 들고 있는다.
  function readNextData(root = globalThis.document) {
    const element = nextDataElement(root);
    if (!element) return null;
    const cache = root?.__coupangNextData;
    if (cache && cache.element === element) return cache.value;
    const text = element.textContent || '';
    // shipmentBoxId 같은 값은 자릿수가 커서 JSON.parse 가 정밀도를 잃는다.
    // 1093824089505681408 이 1093824089505681400 이 되어 틀린 주소를 만든다.
    // 파싱 전에 긴 정수를 문자열로 바꿔 원본 자릿수를 지킨다.
    const safe = text.replace(/:\s*(\d{16,})(?=\s*[,}\]])/g, ':"$1"');
    let value = null;
    try { value = JSON.parse(safe); }
    catch { try { value = JSON.parse(text); } catch { value = null; } }
    if (root) { try { root.__coupangNextData = { element, value }; } catch { /* 저장 못해도 동작한다 */ } }
    return value;
  }

  function orderDomainFromNextData(root = globalThis.document) {
    const pageProps = readNextData(root)?.props?.pageProps;
    if (!pageProps) return null;
    const candidates = [
      pageProps.domains?.desktopOrder,
      pageProps.desktopOrder,
      pageProps.orderResponse,
      pageProps.domains?.orderResponse
    ];
    return candidates.find((candidate) => Array.isArray(candidate?.orderList)) || null;
  }

  const kstTime = (ms) => (typeof ms === 'number' && Number.isFinite(ms))
    ? new Date(ms).toLocaleString('sv-SE', { timeZone: 'Asia/Seoul' }) : null;
  const numberOrNull = (value) => (typeof value === 'number' && Number.isFinite(value)) ? value : null;

  function productUrlOf(productId, vendorItemId) {
    if (!productId) return null;
    const base = `https://www.coupang.com/vp/products/${productId}`;
    return vendorItemId ? `${base}?vendorItemId=${vendorItemId}` : base;
  }

  // __NEXT_DATA__ 의 주문 목록을 우리 결과 형식으로 옮긴다.
  function ordersFromNextData(root = globalThis.document) {
    const orderList = orderDomainFromNextData(root)?.orderList;
    if (!Array.isArray(orderList)) return null;

    const rows = [];
    for (const [orderIndex, order] of orderList.entries()) {
      const orderId = order?.orderId != null ? String(order.orderId) : null;
      const orderedAt = kstTime(order?.orderedAt);
      const shippingFee = numberOrNull(order?.baseDeliveryPrice);
      const orderTotal = numberOrNull(order?.totalProductPrice);

      for (const [groupIndex, group] of (order?.deliveryGroupList ?? []).entries()) {
        const statusCode = group?.groupStatus?.status ?? group?.invoiceStatus ?? null;
        // 배송조회 주소를 직접 만들면 버튼을 찾아 누를 필요가 없다.
        const boxId = group?.shipmentBoxId ?? group?.shipmentBoxIds?.[0] ?? Object.entries(group || {}).find(([key]) => /shipmentbox/i.test(key))?.[1] ?? null;
        const freshFirstOrderId = group?.freshFirstOrderId ?? order?.freshFirstOrderId ?? null;
        const products = group?.productList ?? [];
        for (const [productIndex, product] of (products.length ? products : [null]).entries()) {
          rows.push(sanitizeValue({
            OrderId: orderId,
            OrderedAt: orderedAt ? orderedAt.slice(0, 10) : null,
            OrderedAtTime: orderedAt,
            SellerName: group?.vendor?.vendorName ?? null,
            ProductName: product?.vendorItemName ?? product?.productName ?? order?.title ?? null,
            Quantity: numberOrNull(product?.quantity),
            UnitPrice: numberOrNull(product?.unitPrice),
            ProductPrice: numberOrNull(product?.discountedUnitPrice ?? product?.combinedUnitPrice ?? product?.unitPrice),
            ShippingFee: shippingFee,
            OrderTotalProductPrice: orderTotal,
            TotalAmount: orderTotal,
            OrderStatus: statusCode ? (STATUS_LABELS[statusCode] || statusCode) : null,
            DeliveryStatus: group?.pddMessage?.message ?? null,
            DeliveryCompleteDate: kstTime(group?.deliveredDate),
            CourierCompany: group?.deliveryCompany?.companyName ?? null,
            TrackingNumber: group?.invoiceNumber ?? null,
            ProductUrl: productUrlOf(product?.productId, product?.vendorItemId),
            VendorItemId: product?.vendorItemId != null ? String(product.vendorItemId) : null,
            _shipmentBoxId: boxId != null ? String(boxId) : null,
            _freshFirstOrderId: freshFirstOrderId != null ? String(freshFirstOrderId) : null,
            _nextDataOrderIndex: orderIndex,
            _nextDataGroupIndex: groupIndex,
            _nextDataProductIndex: productIndex,
            DeliveryRegion: null,
            TrackingEvents: [],
            Warnings: [],
            _idSource: orderId ? 'orderNumber' : 'derived',
            _source: 'nextData'
          }));
        }
      }
    }
    return rows;
  }

  // 다음 페이지가 있는지, 몇 번인지는 JSON 이 알려준다. 짐작하지 않아도 된다.
  function paginationFromNextData(root = globalThis.document) {
    const domain = orderDomainFromNextData(root);
    const page = domain?.orderPagination ?? domain?.pagination ?? null;
    if (!page) return null;
    const current = numberOrNull(page.pageIndex ?? page.currentPageIndex);
    return {
      hasNext: Boolean(page.hasNext),
      hasPrev: Boolean(page.hasPrev),
      currentPageIndex: current,
      nextPageIndex: numberOrNull(page.nextPageIndex),
      nextYear: page.nextYear != null ? String(page.nextYear) : null,
      prevYear: page.prevYear != null ? String(page.prevYear) : null
    };
  }

  const TRACK_URL = 'https://mc.coupang.com/ssr/desktop/shiptrack';
  // 송장번호가 아직 없어도 주문번호와 배송박스 번호만 있으면 배송조회 화면이 열린다.
  function trackingUrlFor(order) {
    if (!order?.OrderId || !order?._shipmentBoxId) return null;
    const url = new URL(TRACK_URL);
    url.searchParams.set('orderId', order.OrderId);
    url.searchParams.set('shipmentBoxId', order._shipmentBoxId);
    url.searchParams.set('invoiceNumber', order.TrackingNumber || '');
    const vendorIds = Array.isArray(order._vendorItemIds) ? order._vendorItemIds : [order.VendorItemId];
    url.searchParams.set('vendorItemIds', vendorIds.filter(Boolean).join(','));
    url.searchParams.set('freshFirstOrderId', order._freshFirstOrderId || '');
    return url.href;
  }
  function listUrlForPage(pageIndex, year) {
    const url = new URL(ORDER_LIST_URL);
    if (pageIndex !== null && pageIndex !== undefined) url.searchParams.set('pageIndex', String(pageIndex));
    if (year) url.searchParams.set('requestYear', String(year));
    return url.href;
  }

  function pageFacts() {
    const root = globalThis.document;
    const compacted = compact(root) || '';
    return {
      isList: isOrderListPage(root),
      listKey: listPositionKey(root),
      cards: discoverCards(root).length,
      hasTrackingTable: hasLeafMatching(root, /송장번호/),
      hasOrderNumber: hasLeafMatching(root, /주문번호/),
      url: globalThis.location?.href || ''
    };
  }
  function describePage() {
    const root = globalThis.document;
    const compacted = compact(root) || '';
    return {
      build: BUILD,
      url: globalThis.location?.href || null,
      title: globalThis.document?.title || null,
      isList: isOrderListPage(root),
      detailLeaves: detailActionLeaves(root).length,
      cards: discoverCards(root).length,
      hasBackToList: hasElementWithText(root, '주문목록돌아가기'),
      hasRecipientBlock: hasElementWithText(root, '받는사람정보'),
      hasOrderNumberLabel: hasLeafMatching(root, /주문번호/),
      hasPaymentBlock: hasLeafMatching(root, /^결제정보/),
      hasTrackingButton: hasLeafMatching(root, /^배송조회$/),
      nextButton: Boolean(findNextButton(globalThis.document)),
      nextCandidates: [...(root?.querySelectorAll?.('button') || [])]
        .filter((button) => compact(button).includes('다음'))
        .map((button, index) => `${index}:"${compact(button).slice(0, 12)}" cls=${(button.getAttribute('class') || '').split(' ')[0]} disabled=${Boolean(button.disabled) || button.hasAttribute('disabled')}`),

      signature: pageSignature(root)
    };
  }
  function diagnoseStructure(root = globalThis.document) { const parsed = parseDocument(root); const cards = discoverCards(root); const count = (selector) => cards.reduce((sum, card) => sum + card.querySelectorAll(selector).length, 0); return { productTitleLinks: root.querySelectorAll(SELECTORS.productTitleLink).length, orderCards: parsed.orderCardCount, productImageLinks: count(SELECTORS.productImageLink), prices: count(SELECTORS.price), quantities: parsed.orders.filter((order) => order.Quantity !== null).length, orderStatuses: count(SELECTORS.orderStatus), deliveryNotices: count(SELECTORS.deliveryNotice), yearTabs: extractYearTabs(root).length, nextButton: Boolean(findNextButton(root)) }; }
  async function collectDetailsOnCurrentPage(orders, scope, collectedAt, page, visited, start, end, deps = {}) { for (const order of orders) { order.Warnings ||= []; order.TrackingEvents ||= []; order.TrackingEventRaw ||= []; const root = deps.getDocument?.() || globalThis.document; const detail = deps.findOrderDetailAction?.(root, order) ?? findOrderDetailAction(root, order); if (detail && deps.clickAndWait && !await deps.clickAndWait(detail)) order.Warnings.push('주문 상세 수집 실패: 페이지가 전환되지 않았습니다.'); if (scope === 'tracking') { const tracking = deps.findOrderTrackingAction?.(deps.getDocument?.() || root, order) ?? findOrderTrackingAction(deps.getDocument?.() || root, order); if (!tracking) { order.Warnings.push('배송 조회 버튼이 없는 주문입니다(취소/환불 등).'); order._TrackingOutcome = 'buttonMissing'; } else if (deps.clickAndWait && await deps.clickAndWait(tracking)) { const priorWarnings = order.Warnings; const parsed = (deps.parseTrackingPage || parseTrackingPage)(deps.getDocument?.() || globalThis.document, collectedAt, order.OrderStatus); Object.assign(order, parsed); order.Warnings = [...priorWarnings, ...(parsed.Warnings || [])]; } } await deps.returnToOrderList?.(); await deps.randomDelay?.(); } return orders; }
  async function collectOrders(config = {}) { let state = initialState(config); const runtime = config.runtime || {}; for (let count = 0; count < (runtime.maxTransitions || 1000); count += 1) { const result = runStep(state); state = result.state; runtime.reportProgress?.(result.progress); if (result.action.type === 'done') return state.result; if (result.action.type === 'navigate') { if (globalThis.location) globalThis.location.href = result.action.url; } else if (result.action.type === 'click') { const performed = performAction(result.action); if (!performed.ok) throw new Error(performed.reason); } await runtime.randomDelay?.(); } throw new Error('상태 기계 반복 상한을 초과했습니다.'); }

  const api = { BUILD, SELECTORS, pageFacts, readNextData, trackingUrlFor, ordersFromNextData, paginationFromNextData, listUrlForPage, describePage, describeTarget, buildExportPayloads, collectDetailsOnCurrentPage, collectOrders, diagnoseStructure, extractYearTabs, findNextButton, findOrderTrackingAction, isOrderListPage, isPaginationButtonDisabled, mergeDetail, nearbyActionElement, pageSignature, parseDocument, parseDetailPage, parseProduct, parseTrackingPage, performAction, runStep, sanitizeValue };
  globalThis.__coupangOrderCollector = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})();
