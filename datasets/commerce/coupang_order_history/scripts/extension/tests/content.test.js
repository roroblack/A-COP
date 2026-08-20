'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const { SELECTORS, parseProduct } = require('../content.js');

const CARD_HTML = `
<td class="sc-5a139ee-5 dPHhOe">
  <span font-weight="bold" color="#111111" style="font-size:1.25rem" class="status">상품준비중</span>
  <span font-weight="normal" color="#008C00" class="notice">내일(금) 새벽 도착 보장</span>
  <a href="/ssr/sdp/link?vendorItemId=76676260659&amp;imagePath=x&amp;sourceType=MyCoupang_my_orders_list_product_image" target="_blank" class="image-link">
    <img loading="lazy" width="64" height="64" src="https://thumbnail.coupangcdn.com/product.jpg" alt="해태 허니버터칩, 120g, 1개">
  </a>
  <a href="/ssr/sdp/link?vendorItemId=76676260659&amp;sourceType=MyCoupang_my_orders_list_product_title" target="_blank" class="title-link">
    <img class="badge" height="16" src="badge.png" alt="RDS_LOGO_WOW_DAWN_MD">
    <span color="#111111" class="product-text">해태 허니버터칩, 120g, 1개</span>
  </a>
  <span translate="yes" class="price">2,420 원</span>
  <span class="quantity">1개</span>
  <button class="cart">장바구니 담기</button>
</td>`;

class TestElement {
  constructor(tagName, attributes = {}) {
    this.tagName = tagName.toUpperCase();
    this.attributes = attributes;
    this.children = [];
    this.parentElement = null;
    this.ownText = '';
  }

  appendChild(child) {
    child.parentElement = this;
    this.children.push(child);
  }

  get textContent() {
    return this.ownText + this.children.map((child) => child.textContent).join('');
  }

  getAttribute(name) {
    return this.attributes[name] ?? null;
  }

  matches(selector) {
    const match = selector.match(/^([a-z]+)?(?:\[([\w-]+)(?:([*]?=)"([^"]*)")?\])?$/i);
    if (!match) {
      return false;
    }

    const [, tag, attribute, operator, expected] = match;
    if (tag && this.tagName !== tag.toUpperCase()) {
      return false;
    }
    if (!attribute) {
      return true;
    }

    const actual = this.getAttribute(attribute);
    if (actual === null) {
      return false;
    }
    if (!operator) {
      return true;
    }
    return operator === '*=' ? actual.includes(expected) : actual === expected;
  }

  closest(selector) {
    let element = this;
    while (element) {
      if (element.matches(selector)) {
        return element;
      }
      element = element.parentElement;
    }
    return null;
  }

  querySelector(selector) {
    return this.querySelectorAll(selector)[0] || null;
  }

  querySelectorAll(selector) {
    const parts = selector.trim().split(/\s+/);
    const descendants = [];
    const visit = (element) => {
      for (const child of element.children) {
        descendants.push(child);
        visit(child);
      }
    };
    visit(this);

    return descendants.filter((element) => {
      if (!element.matches(parts.at(-1))) {
        return false;
      }
      let ancestor = element.parentElement;
      for (let index = parts.length - 2; index >= 0; index -= 1) {
        while (ancestor && !ancestor.matches(parts[index])) {
          ancestor = ancestor.parentElement;
        }
        if (!ancestor) {
          return false;
        }
        ancestor = ancestor.parentElement;
      }
      return true;
    });
  }
}

function decodeHtml(value) {
  return value.replaceAll('&amp;', '&').replaceAll('&quot;', '"');
}

function parseFragment(html) {
  const root = new TestElement('root');
  const stack = [root];
  const tokens = html.match(/<[^>]+>|[^<]+/g) || [];
  const voidTags = new Set(['IMG', 'BR', 'HR', 'INPUT', 'META', 'LINK']);

  for (const token of tokens) {
    if (token.startsWith('</')) {
      stack.pop();
      continue;
    }
    if (!token.startsWith('<')) {
      stack.at(-1).ownText += decodeHtml(token);
      continue;
    }

    const tagMatch = token.match(/^<([a-z][\w-]*)/i);
    if (!tagMatch) {
      continue;
    }
    const attributes = {};
    for (const match of token.matchAll(/([\w-]+)="([^"]*)"/g)) {
      attributes[match[1]] = decodeHtml(match[2]);
    }
    const element = new TestElement(tagMatch[1], attributes);
    stack.at(-1).appendChild(element);
    if (!voidTags.has(element.tagName) && !token.endsWith('/>')) {
      stack.push(element);
    }
  }

  return root.children[0];
}

test('실제 주문 카드에서 상품 정보를 파싱한다', () => {
  const card = parseFragment(CARD_HTML);
  const titleLink = card.querySelector(SELECTORS.productTitleLink);
  const result = parseProduct(titleLink);

  assert.equal(result.ProductName, '해태 허니버터칩, 120g, 1개');
  assert.equal(result.ProductPrice, 2420);
  assert.equal(result.Quantity, 1);
  assert.equal(result.OrderStatus, '상품준비중');
  assert.equal(result.DeliveryStatus, '내일(금) 새벽 도착 보장');
  assert.equal(result.VendorItemId, '76676260659');
  assert.equal(result.ProductUrl.startsWith('https://www.coupang.com/'), true);
  assert.equal(result._idSource, 'derived');
});

test('상품명 span이 없으면 상품 이미지 alt를 사용한다', () => {
  const card = parseFragment(CARD_HTML);
  const titleLink = card.querySelector(SELECTORS.productTitleLink);
  titleLink.querySelector('span').ownText = '';

  const result = parseProduct(titleLink);

  assert.equal(result.ProductName, '해태 허니버터칩, 120g, 1개');
  assert.notEqual(result.ProductName, 'RDS_LOGO_WOW_DAWN_MD');
});
