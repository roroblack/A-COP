'use strict';

(() => {
  const BUILD = '2026-08-23i';
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
  const hasOrderListData = (root) => { const data = readNextData(root); return Boolean(data && deepFind(data, 'orderList')); };
  // 서버가 주문 목록 JSON 을 심어줬으면 그것만으로 목록 페이지다.
  const isOrderListPage = (root) => (hasOrderListData(root) || detailActionLeaves(root).length > 0) && !hasElementWithText(root, '주문목록돌아가기') && !hasElementWithText(root, '받는사람정보');
  const rows = (root) => [...(root?.querySelectorAll?.('tr') || [])];
  function rowValue(root, label) { const row = rows(root).find((item) => compact(item).startsWith(label.replace(/\s+/g, ''))); return text([...(row?.querySelectorAll?.('td') || [])].at(-1)); }
  function parseDetailPage(root, pageUrl = '') {
    const orderId = (text(root) || '').match(/주문번호\s*(\d{8,})/)?.[1] || String(pageUrl).match(/(\d{8,})/)?.[1] || null;
    const address = rowValue(root, '받는주소')?.replace(/^\(\d{5}\)\s*/, ''); const parts = address?.split(/\s+/) || [];
    const link = [...(root.querySelectorAll?.('a') || [])].find((item) => String(item.getAttribute?.('href') || '').includes('/delivery/tracking/'));
    return sanitizeValue({ OrderId: orderId, _idSource: orderId ? 'orderNumber' : 'derived', OrderedAt: dateOf(root), OrderStatus: text(root.querySelector?.(SELECTORS.orderStatus)), products: parseDocument(root).orders, TotalProductAmount: numberOf(rowValue(root, '총상품가격')), ShippingFee: numberOf(rowValue(root, '배송비')), PaymentMethod: rowValue(root, '결제수단'), TotalAmount: numberOf(rowValue(root, '총결제금액')), DeliveryRegion: parts.length >= 2 ? `${parts[0]} ${parts[1]}` : null, DeliveryRequest: rowValue(root, '배송요청사항'), _TrackingUrl: link ? new URL(link.getAttribute('href'), 'https://mc.coupang.com').href : null });
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
    const clean = orders.map((source) => { const order = { ...source }; const events = order.TrackingEvents || []; const raw = order.TrackingEventRaw || []; if (order.TrackingNumber && events.length) trackingData.push({ courier: order.CourierCompany, tracking_number: order.TrackingNumber, order_id: order.OrderId, status: order.DeliveryStatus || order.OrderStatus, events: events.map((event, index) => ({ ...event, raw: raw[index] || event.timeString })), queried_at: exportedAt }); for (const key of ['TrackingEvents', 'TrackingEventRaw', '_TrackingUrl', '_cardIndex', '_productIndex']) delete order[key]; return order; });
    const trackingSummary = { collected: orders.filter((order) => order._TrackingOutcome === 'collected').length, preShipment: orders.filter((order) => order._TrackingOutcome === 'preShipment').length, buttonMissing: orders.filter((order) => order._TrackingOutcome === 'buttonMissing').length };
    return sanitizeValue({ orderData: { exportedAt, source: ORDER_LIST_URL, collectionScope: meta.collectionScope || 'tracking', pageCount: meta.pageCount || 0, orderCount: clean.length, warning: meta.warning || null, orders: clean }, trackingData, trackingSummary });
  }
  function listPositionKey(root = globalThis.document) { return shortHash(parseDocument(root).orders.map((order) => `${order.OrderedAt}|${order.VendorItemId}|${order.ProductName}`).join('||')); }
  function pageSignature(root = globalThis.document, href = globalThis.location?.href || '') { const ids = parseDocument(root).orders.map((order) => `${order.OrderedAt}|${order.VendorItemId}|${order.ProductName}`).join('||'); return `${href}|${shortHash(ids)}`; }
  const progress = (state, message) => ({ stage: state.phase, page: state.page, count: state.orders.length, orderCount: new Set(state.orders.map((order) => order.OrderId).filter(Boolean)).size, queueDone: state.cursor || 0, queueTotal: (state.queue || []).length, trackingCount: (state.tracking || []).length, pageCount: state.pageCount || 0, year: state.years[state.yearIndex]?.label || null, remaining: Math.max(0, state.queue.length - state.cursor), message });
  function initialState(config = {}) { return { phase: 'INIT', scope: config.collectionScope || config.scope || 'tracking', years: [], yearIndex: 0, page: 1, orders: [], tracking: [], queue: [], cursor: 0, warnings: [], done: false, yearScope: config.yearScope || 'current', pageCount: 0, listSignature: null, listUrl: null, listKey: null, restore: null, seenKeys: [], skipCurrent: false, pageRetries: 0 }; }
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
    // 중단되거나 탭이 닫혀도 누적분을 내려받을 수 있게 매 걸음 부분 결과를 갱신한다.
    if (out?.state && !out.state.done) out.state.result = buildExportPayloads(out.state.orders, { collectionScope: out.state.scope, pageCount: out.state.pageCount, warning: out.state.warnings.length ? out.state.warnings.join(' ') : null, partial: true });
    return out;
  }
  function runStepInner(input = {}) {
    const state = Object.assign(initialState(input), input); const root = globalThis.document;
    if (!root) return { state, action: { type: 'none' }, progress: progress(state, '문서를 기다리고 있습니다.') };
    if (state.done || state.phase === 'DONE') return finish(state);
    if (state.phase === 'INIT') { if (!isOrderListPage(root)) return { state, action: { type: 'navigate', url: ORDER_LIST_URL }, progress: progress(state, '주문 목록으로 이동합니다.') }; const entries = yearEntries(root); state.years = (state.yearScope === 'current' ? entries.slice(0, 1) : entries).map(({ label }) => ({ label, done: false })); if (!state.years.length) state.years = [{ label: null, done: false }]; state.phase = 'LIST'; return { state, action: { type: 'none' }, progress: progress(state, '주문 목록을 확인했습니다.') }; }
    if (state.phase === 'LIST') { if (!isOrderListPage(root)) return { state, action: { type: 'navigate', url: state.listUrl || ORDER_LIST_URL }, progress: progress(state, '주문 목록으로 돌아갑니다.') }; const signature = pageSignature(root); const key = listPositionKey(root); state.seenKeys = state.seenKeys || []; if (key === state.listKey || state.seenKeys.includes(key)) { const next = findNextButton(root); if (next && !isPaginationButtonDisabled(next) && (state.pageRetries || 0) < 2) { state.pageRetries = (state.pageRetries || 0) + 1; state.page = Math.max(1, state.page - 1); state.phase = 'NEXT_PAGE'; return { state, action: { type: 'none' }, progress: progress(state, `페이지가 넘어가지 않아 다시 시도합니다(${state.pageRetries}).`) }; } state.warnings.push(next && !isPaginationButtonDisabled(next) ? '다음 버튼이 있지만 페이지가 넘어가지 않아 멈춥니다.' : '마지막 페이지에 도달했습니다.'); state.queue = []; state.cursor = 0; state.phase = 'NEXT_YEAR'; return { state, action: { type: 'none' }, progress: progress(state, '마지막 페이지입니다.') }; } if (signature !== state.listSignature) { const fromJson = ordersFromNextData(root); const parsed = fromJson && fromJson.length ? { orders: fromJson.map((order, index) => ({ ...order, _cardIndex: index })), orderCardCount: fromJson.length } : parseDocument(root); const base = state.orders.length; state.orders.push(...parsed.orders); state.queue = [...new Set(parsed.orders.map((order) => order._cardIndex))].map((cardIndex) => ({ cardIndex, cardKey: cardKeyOf(parsed.orders.find((order) => order._cardIndex === cardIndex)), orderIndexes: parsed.orders.map((order, index) => order._cardIndex === cardIndex ? base + index : -1).filter((index) => index >= 0), detailDone: state.scope === 'list' || Boolean(fromJson && fromJson.length), trackingDone: state.scope !== 'tracking' || Boolean(fromJson && fromJson.length && !parsed.orders.some((order) => order._cardIndex === cardIndex && order.TrackingNumber)), returning: null })); state.cursor = 0; state.pageRetries = 0; state.pageCount += 1; state.listSignature = signature; state.listKey = key; state.seenKeys = [...state.seenKeys.slice(-40), key]; state.listUrl = globalThis.location?.href || ORDER_LIST_URL; } state.phase = state.scope === 'list' ? 'NEXT_PAGE' : 'DETAIL'; return { state, action: { type: 'none' }, progress: progress(state, '현재 페이지의 주문을 읽었습니다.') }; }
    if (state.phase === 'DETAIL') {
      const item = state.queue[state.cursor]; if (item && state.skipCurrent) { state.skipCurrent = false; const failed = item.detailDone ? '배송 조회' : '주문 상세'; const reason = `페이지가 반응하지 않아 ${failed}를 건너뜁니다.`; for (const index of item.orderIndexes) { const order = state.orders[index]; if (order) order.Warnings = [...(order.Warnings || []), reason]; } if (item.detailDone) item.trackingDone = true; else item.detailDone = true; item.returning = null; if (item.detailDone && item.trackingDone) state.cursor += 1; return { state, action: { type: 'none' }, progress: progress(state, reason) }; } if (!item) { state.phase = 'NEXT_PAGE'; return { state, action: { type: 'none' }, progress: progress(state, '현재 페이지의 상세 수집을 마쳤습니다.') }; }
      if (!isOrderListPage(root)) { if (item.returning === 'detail') { const detail = parseDetailPage(root, globalThis.location?.href || ''); for (const index of item.orderIndexes) mergeDetail(state.orders[index], detail); item.detailDone = true; item.returning = 'fromDetail'; } else if (item.returning === 'tracking') { const tracking = parseTrackingPage(root, new Date(), state.orders[item.orderIndexes[0]]?.OrderStatus); for (const index of item.orderIndexes) { Object.assign(state.orders[index], tracking); state.orders[index]._TrackingOutcome = tracking.ShipmentStarted ? 'collected' : 'preShipment'; } const added = buildExportPayloads(item.orderIndexes.map((index) => state.orders[index])).trackingData; const known = new Set(state.tracking.map((entry) => `${entry.order_id}|${entry.tracking_number}`)); state.tracking.push(...added.filter((entry) => !known.has(`${entry.order_id}|${entry.tracking_number}`))); item.trackingDone = true; item.returning = 'fromTracking'; } return { state, action: { type: 'click', target: 'backToList', index: item.cardIndex }, progress: progress(state, '주문 목록으로 돌아갑니다.') }; }
      if (state.listKey && listPositionKey(root) !== state.listKey) { state.restore = { yearDone: false, attempts: 0 }; state.phase = 'RESTORE'; return { state, action: { type: 'none' }, progress: progress(state, '목록 위치가 달라져 복원합니다.') }; }
    if (item.returning === 'fromDetail') item.returning = null; if (item.returning === 'fromTracking') { item.returning = null; state.cursor += 1; return { state, action: { type: 'none' }, progress: progress(state, '다음 주문을 확인합니다.') }; }
      if (!item.detailDone) { item.returning = 'detail'; return { state, action: { type: 'click', target: 'detail', index: item.cardIndex }, progress: progress(state, '주문 상세를 엽니다.') }; }
      if (!item.trackingDone) { const order = state.orders[item.orderIndexes[0]]; if (!findOrderTrackingAction(root, order)) { for (const index of item.orderIndexes) { state.orders[index].Warnings = [...(state.orders[index].Warnings || []), '배송 조회 버튼이 없는 주문입니다(취소/환불 등).']; state.orders[index]._TrackingOutcome = 'buttonMissing'; } item.trackingDone = true; state.cursor += 1; return { state, action: { type: 'none' }, progress: progress(state, '배송 조회가 없는 주문을 건너뜁니다.') }; } item.returning = 'tracking'; return { state, action: { type: 'click', target: 'tracking', index: item.cardIndex }, progress: progress(state, '배송 조회를 엽니다.') }; }
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

  function readNextData(root = globalThis.document) {
    const target = (root && root.nodeType === 9 && root.body) ? root.body : root;
    const element = root?.getElementById?.('__NEXT_DATA__')
      || target?.querySelector?.('script[id="__NEXT_DATA__"]')
      || target?.querySelector?.('#__NEXT_DATA__');
    if (!element) return null;
    try { return JSON.parse(element.textContent || ''); } catch { return null; }
  }

  const deepFind = (node, key, depth = 0) => {
    if (!node || depth > 8) return null;
    if (Array.isArray(node)) {
      for (const item of node) { const found = deepFind(item, key, depth + 1); if (found) return found; }
      return null;
    }
    if (typeof node !== 'object') return null;
    if (Array.isArray(node[key])) return node[key];
    for (const value of Object.values(node)) { const found = deepFind(value, key, depth + 1); if (found) return found; }
    return null;
  };

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
    const data = readNextData(root);
    if (!data) return null;
    const orderList = deepFind(data, 'orderList');
    if (!orderList) return null;

    const rows = [];
    for (const order of orderList) {
      const orderId = order?.orderId != null ? String(order.orderId) : null;
      const orderedAt = kstTime(order?.orderedAt);
      const shippingFee = numberOrNull(order?.baseDeliveryPrice);
      const orderTotal = numberOrNull(order?.totalProductPrice);

      for (const group of order?.deliveryGroupList ?? []) {
        const statusCode = group?.groupStatus?.status ?? group?.invoiceStatus ?? null;
        const products = group?.productList ?? [];
        for (const product of (products.length ? products : [null])) {
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
            TotalAmount: orderTotal,
            OrderStatus: statusCode ? (STATUS_LABELS[statusCode] || statusCode) : null,
            DeliveryStatus: group?.pddMessage?.message ?? null,
            DeliveryCompleteDate: kstTime(group?.deliveredDate),
            CourierCompany: group?.deliveryCompany?.companyName ?? null,
            TrackingNumber: group?.invoiceNumber ?? null,
            ProductUrl: productUrlOf(product?.productId, product?.vendorItemId),
            VendorItemId: product?.vendorItemId != null ? String(product.vendorItemId) : null,
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
    const data = readNextData(root);
    if (!data) return null;
    const found = (node, depth = 0) => {
      if (!node || typeof node !== 'object' || depth > 8) return null;
      if (Array.isArray(node)) { for (const item of node) { const hit = found(item, depth + 1); if (hit) return hit; } return null; }
      if ('hasNext' in node) return node;
      for (const value of Object.values(node)) { const hit = found(value, depth + 1); if (hit) return hit; }
      return null;
    };
    const page = found(data);
    if (!page) return null;
    const current = numberOrNull(page.pageIndex ?? page.currentPageIndex);
    return {
      hasNext: Boolean(page.hasNext),
      currentPageIndex: current,
      nextPageIndex: numberOrNull(page.nextPageIndex) ?? (current === null ? null : current + 1)
    };
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

  const api = { BUILD, SELECTORS, pageFacts, readNextData, ordersFromNextData, paginationFromNextData, listUrlForPage, describePage, describeTarget, buildExportPayloads, collectDetailsOnCurrentPage, collectOrders, diagnoseStructure, extractYearTabs, findNextButton, findOrderTrackingAction, isOrderListPage, isPaginationButtonDisabled, mergeDetail, nearbyActionElement, pageSignature, parseDocument, parseDetailPage, parseProduct, parseTrackingPage, performAction, runStep, sanitizeValue };
  globalThis.__coupangOrderCollector = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})();
