'use strict';

(() => {
const SELECTORS = Object.freeze({
  productTitleLink: 'a[href*="MyCoupang_my_orders_list_product_title"]',
  productImageLink: 'a[href*="MyCoupang_my_orders_list_product_image"]',
  price: 'span[translate="yes"]',
  orderStatus: 'span[style*="font-size:1.25rem"]',
  deliveryNotice: 'span[color="#008C00"]',
  nextPage: 'a[rel="next"], a[aria-label="다음"]'
});

const PHONE_PATTERN = /01[016-9][-\s]?\d{3,4}[-\s]?\d{4}/g;
const BADGE_ALT_PATTERN = /^[A-Z0-9_]+$/;
const ALLOWED_HOSTS = new Set(['mc.coupang.com', 'www.coupang.com']);
const PRODUCT_BASE_URL = 'https://www.coupang.com';
const MAX_PAGES = 200;

function normalizedText(element) {
  const text = element?.textContent?.replace(/\s+/g, ' ').trim();
  return text || null;
}

function numberOf(text) {
  if (!text) {
    return null;
  }

  const digits = text.replace(/[^0-9]/g, '');
  const number = Number(digits);
  return digits && Number.isFinite(number) ? number : null;
}

function productNameOf(titleLink, card) {
  const spans = [...titleLink.querySelectorAll('span')];
  const spanName = normalizedText(spans.at(-1));
  if (spanName) {
    return spanName;
  }

  const image = card.querySelector(`${SELECTORS.productImageLink} img[alt]`);
  const alt = image?.getAttribute('alt')?.trim() || null;
  return alt && !BADGE_ALT_PATTERN.test(alt) ? alt : null;
}

function safeProductUrl(titleLink) {
  const href = titleLink.getAttribute('href');
  if (!href) {
    return null;
  }

  try {
    const url = new URL(href, PRODUCT_BASE_URL);
    return url.protocol === 'https:' && ALLOWED_HOSTS.has(url.hostname) ? url.href : null;
  } catch {
    return null;
  }
}

function vendorItemIdOf(href) {
  return href?.match(/[?&]vendorItemId=(\d+)(?:&|$)/)?.[1] || null;
}

function quantityAfter(priceElement, card) {
  if (!priceElement) {
    return null;
  }

  const spans = [...card.querySelectorAll('span')];
  const priceIndex = spans.indexOf(priceElement);
  for (const span of spans.slice(priceIndex + 1)) {
    const match = normalizedText(span)?.match(/^(\d+)\s*개$/);
    if (match) {
      return Number(match[1]);
    }
  }

  return null;
}

function shortHash(text) {
  let hash = 2166136261;
  for (const character of text || '') {
    hash ^= character.codePointAt(0);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(16).padStart(8, '0');
}

function derivedOrderId(vendorItemId, productName) {
  return `${vendorItemId || 'unknown'}-${shortHash(productName || '')}`;
}

function isBlockElement(element) {
  const blockTags = new Set([
    'ARTICLE', 'ASIDE', 'BLOCKQUOTE', 'DIV', 'DL', 'FIELDSET', 'FIGURE', 'FOOTER',
    'FORM', 'HEADER', 'LI', 'MAIN', 'NAV', 'OL', 'P', 'SECTION', 'TABLE', 'TBODY', 'UL'
  ]);
  return blockTags.has(element?.tagName);
}

function cardOf(titleLink) {
  const tableCell = titleLink.closest('td');
  if (tableCell) {
    return tableCell;
  }

  const tableRow = titleLink.closest('tr');
  if (tableRow) {
    return tableRow;
  }

  let ancestor = titleLink.parentElement;
  while (ancestor && !isBlockElement(ancestor)) {
    ancestor = ancestor.parentElement;
  }
  return ancestor || titleLink.parentElement || titleLink;
}

function parseProduct(titleLink) {
  const card = cardOf(titleLink);
  const productName = productNameOf(titleLink, card);
  const href = titleLink.getAttribute('href') || '';
  const vendorItemId = vendorItemIdOf(href);
  const priceElement = card.querySelector(SELECTORS.price);

  return {
    OrderId: derivedOrderId(vendorItemId, productName),
    _idSource: 'derived',
    OrderedAt: null,
    SellerName: null,
    ProductName: productName,
    Quantity: quantityAfter(priceElement, card),
    ProductPrice: numberOf(normalizedText(priceElement)),
    ShippingFee: null,
    TotalAmount: null,
    OrderStatus: normalizedText(card.querySelector(SELECTORS.orderStatus)),
    DeliveryStatus: normalizedText(card.querySelector(SELECTORS.deliveryNotice)),
    DeliveryCompleteDate: null,
    CourierCompany: null,
    TrackingNumber: null,
    ProductUrl: safeProductUrl(titleLink),
    VendorItemId: vendorItemId,
    DeliveryRegion: null
  };
}

function sanitizeValue(value) {
  if (typeof value === 'string') {
    return value.replace(PHONE_PATTERN, '[제거됨]');
  }

  if (Array.isArray(value)) {
    return value.map(sanitizeValue);
  }

  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [key, sanitizeValue(item)])
    );
  }

  return value;
}

function parseDocument(documentRoot) {
  const titleLinks = [...documentRoot.querySelectorAll(SELECTORS.productTitleLink)];
  return {
    orders: titleLinks.map(parseProduct),
    orderCardCount: new Set(titleLinks.map(cardOf)).size
  };
}

function diagnoseStructure(documentRoot = document) {
  const titleLinks = [...documentRoot.querySelectorAll(SELECTORS.productTitleLink)];
  const cards = [...new Set(titleLinks.map(cardOf))];
  const countInCards = (selector) => cards.reduce(
    (count, card) => count + card.querySelectorAll(selector).length,
    0
  );
  const quantityCount = cards.reduce((count, card) => {
    const price = card.querySelector(SELECTORS.price);
    return count + (quantityAfter(price, card) === null ? 0 : 1);
  }, 0);

  return {
    productTitleLinks: titleLinks.length,
    orderCards: cards.length,
    productImageLinks: countInCards(SELECTORS.productImageLink),
    prices: countInCards(SELECTORS.price),
    quantities: quantityCount,
    orderStatuses: countInCards(SELECTORS.orderStatus),
    deliveryNotices: countInCards(SELECTORS.deliveryNotice)
  };
}

function nextPageUrl(documentRoot, pageUrl) {
  const nextElement = documentRoot.querySelector(SELECTORS.nextPage);
  if (!nextElement) {
    return null;
  }

  const disabled = nextElement.matches('[disabled], [aria-disabled="true"]');
  const href = nextElement.getAttribute('href');
  if (disabled || !href || href === '#') {
    return null;
  }

  try {
    const url = new URL(href, pageUrl);
    return url.protocol === 'https:' && ALLOWED_HOSTS.has(url.hostname) ? url.href : null;
  } catch {
    return null;
  }
}

function randomDelay(minDelayMs, maxDelayMs) {
  const duration = minDelayMs + Math.random() * (maxDelayMs - minDelayMs);
  return new Promise((resolve) => setTimeout(resolve, duration));
}

function reportProgress(page, count, message) {
  chrome.runtime.sendMessage(
    { type: 'COUPANG_COLLECTION_PROGRESS', page, count, message },
    () => {
      // 팝업이 닫힌 경우의 오류를 읽어서 콘솔에 남기지 않는다.
      void chrome.runtime.lastError;
    }
  );
}

async function collectOrders(config) {
  const minDelayMs = Math.max(800, Number(config.minDelayMs) || 1500);
  const maxDelayMs = Math.max(minDelayMs, Number(config.maxDelayMs) || 3500);
  const visitedUrls = new Set();
  const allOrders = [];
  let currentDocument = document;
  let currentUrl = location.href;
  let page = 1;
  let warning = null;

  while (page <= MAX_PAGES) {
    if (visitedUrls.has(currentUrl)) {
      warning = '같은 페이지가 반복되어 수집을 중단했습니다.';
      break;
    }

    visitedUrls.add(currentUrl);
    const parsed = parseDocument(currentDocument);
    if (parsed.orderCardCount === 0) {
      warning = page === 1
        ? '수집 결과가 0건입니다. 구조 진단을 실행해 선택자 매칭 수를 확인하세요.'
        : warning;
      break;
    }

    allOrders.push(...parsed.orders);
    reportProgress(page, allOrders.length, '현재 페이지를 수집했습니다.');

    const nextUrl = nextPageUrl(currentDocument, currentUrl);
    if (!nextUrl) {
      break;
    }

    reportProgress(page, allOrders.length, '다음 페이지를 기다리고 있습니다.');
    await randomDelay(minDelayMs, maxDelayMs);

    const response = await fetch(nextUrl, {
      credentials: 'include',
      redirect: 'error',
      headers: { Accept: 'text/html' }
    });

    if (!response.ok) {
      throw new Error(`다음 페이지 요청에 실패했습니다. HTTP ${response.status}`);
    }

    currentUrl = nextUrl;
    currentDocument = new DOMParser().parseFromString(await response.text(), 'text/html');
    page += 1;
  }

  if (page > MAX_PAGES) {
    warning = `안전을 위해 ${MAX_PAGES}페이지에서 수집을 중단했습니다.`;
  }

  return sanitizeValue({
    exportedAt: new Date().toISOString(),
    source: 'https://mc.coupang.com/ssr/desktop/order/list',
    pageCount: visitedUrls.size,
    orderCount: allOrders.length,
    warning,
    orders: allOrders
  });
}

globalThis.__coupangOrderCollector = { collectOrders, diagnoseStructure };

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    SELECTORS,
    cardOf,
    parseProduct,
    productNameOf,
    quantityAfter,
    vendorItemIdOf
  };
}
})();
