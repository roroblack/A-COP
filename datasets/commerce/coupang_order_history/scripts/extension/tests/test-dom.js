'use strict';

class TestElement {
  constructor(tagName, attributes = {}) {
    this.tagName = tagName.toUpperCase();
    this.attributes = attributes;
    this.children = [];
    this.parentElement = null;
    this.ownText = '';
    this.onclick = null;
  }

  appendChild(child) {
    child.parentElement = this;
    this.children.push(child);
  }

  get textContent() {
    return this.ownText + this.children.map((child) => child.textContent).join('');
  }

  get disabled() {
    return this.hasAttribute('disabled');
  }

  get nextElementSibling() {
    const siblings = this.parentElement?.children || [];
    return siblings[siblings.indexOf(this) + 1] || null;
  }

  get previousElementSibling() {
    const siblings = this.parentElement?.children || [];
    return siblings[siblings.indexOf(this) - 1] || null;
  }

  getAttribute(name) {
    return this.attributes[name] ?? null;
  }

  setAttribute(name, value) {
    this.attributes[name] = String(value);
  }

  hasAttribute(name) {
    return Object.hasOwn(this.attributes, name);
  }

  click() {
    if (!this.disabled && typeof this.onclick === 'function') this.onclick();
  }

  matches(selector) {
    // 진짜 브라우저는 #id 를 지원한다. 테스트도 같아야 한다.
    if (selector.startsWith('#')) return this.getAttribute('id') === selector.slice(1);
    if (selector === '*') return true;
    const match = selector.match(/^([a-z]+)?(?:\[([\w-]+)(?:([*]?=)"([^"]*)")?\])?$/i);
    if (!match) return false;

    const [, tag, attribute, operator, expected] = match;
    if (tag && this.tagName !== tag.toUpperCase()) return false;
    if (!attribute) return true;
    const actual = this.getAttribute(attribute);
    if (actual === null) return false;
    if (!operator) return true;
    return operator === '*=' ? actual.includes(expected) : actual === expected;
  }

  closest(selector) {
    let element = this;
    while (element) {
      if (element.matches(selector)) return element;
      element = element.parentElement;
    }
    return null;
  }

  querySelector(selector) {
    return this.querySelectorAll(selector)[0] || null;
  }

  contains(other) {
    for (let node = other; node; node = node.parentElement) if (node === this) return true;
    return false;
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
      if (!element.matches(parts.at(-1))) return false;
      let ancestor = element.parentElement;
      for (let index = parts.length - 2; index >= 0; index -= 1) {
        while (ancestor && !ancestor.matches(parts[index])) ancestor = ancestor.parentElement;
        if (!ancestor) return false;
        ancestor = ancestor.parentElement;
      }
      return true;
    });
  }
}

function decodeHtml(value) {
  return value.replaceAll('&amp;', '&').replaceAll('&quot;', '"').replaceAll('&nbsp;', '\u00a0');
}

function parseFragment(html) {
  const root = new TestElement('root');
  const stack = [root];
  const tokens = html.match(/<[^>]+>|[^<]+/g) || [];
  const voidTags = new Set(['AREA', 'BASE', 'BR', 'COL', 'EMBED', 'HR', 'IMG', 'INPUT', 'LINK', 'META', 'PARAM', 'SOURCE', 'TRACK', 'WBR']);

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
    if (!tagMatch) continue;
    const attributes = {};
    for (const match of token.matchAll(/([\w-]+)="([^"]*)"/g)) attributes[match[1]] = decodeHtml(match[2]);
    const element = new TestElement(tagMatch[1], attributes);
    stack.at(-1).appendChild(element);
    if (!voidTags.has(element.tagName) && !token.endsWith('/>')) stack.push(element);
  }

  return root.children[0];
}

module.exports = { parseFragment, TestElement };
