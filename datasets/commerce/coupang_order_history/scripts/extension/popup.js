'use strict';

const ORDER_LIST_URL = 'https://mc.coupang.com/ssr/desktop/order/list';
const minDelayInput = document.querySelector('#minDelay');
const maxDelayInput = document.querySelector('#maxDelay');
const startButton = document.querySelector('#startButton');
const diagnoseButton = document.querySelector('#diagnoseButton');
const downloadButton = document.querySelector('#downloadButton');
const statusElement = document.querySelector('#status');

let collectedResult = null;

function setStatus(message) {
  statusElement.textContent = message;
}

function readDelaySettings() {
  const minSeconds = Number(minDelayInput.value);
  const maxSeconds = Number(maxDelayInput.value);

  if (!Number.isFinite(minSeconds) || minSeconds < 0.8) {
    throw new Error('최소 대기 시간은 0.8초 이상이어야 합니다.');
  }

  if (!Number.isFinite(maxSeconds) || maxSeconds < 0.8) {
    throw new Error('최대 대기 시간은 0.8초 이상이어야 합니다.');
  }

  if (maxSeconds < minSeconds) {
    throw new Error('최대 대기 시간은 최소 대기 시간보다 짧을 수 없습니다.');
  }

  return {
    minDelayMs: Math.round(minSeconds * 1000),
    maxDelayMs: Math.round(maxSeconds * 1000)
  };
}

function isOrderListUrl(url) {
  try {
    const parsed = new URL(url);
    return parsed.origin === 'https://mc.coupang.com' &&
      parsed.pathname.startsWith('/ssr/desktop/order/list');
  } catch {
    return false;
  }
}

async function activeOrderListTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id || !isOrderListUrl(tab.url)) {
    throw new Error(`쿠팡 주문목록 페이지에서 실행하세요.\n${ORDER_LIST_URL}`);
  }
  return tab;
}

async function loadCollector(tabId) {
  await chrome.scripting.executeScript({
    target: { tabId },
    files: ['content.js']
  });
}

chrome.runtime.onMessage.addListener((message) => {
  if (message?.type !== 'COUPANG_COLLECTION_PROGRESS') {
    return;
  }

  setStatus(
    `현재 페이지: ${message.page}\n누적 건수: ${message.count}\n${message.message || ''}`
  );
});

startButton.addEventListener('click', async () => {
  startButton.disabled = true;
  downloadButton.disabled = true;
  collectedResult = null;

  try {
    const delaySettings = readDelaySettings();
    const tab = await activeOrderListTab();

    setStatus('수집을 준비하고 있습니다.');

    await loadCollector(tab.id);

    const executionResults = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: async (config) => {
        if (!globalThis.__coupangOrderCollector) {
          throw new Error('수집 스크립트를 불러오지 못했습니다.');
        }

        return globalThis.__coupangOrderCollector.collectOrders(config);
      },
      args: [delaySettings]
    });

    collectedResult = executionResults[0]?.result || null;
    if (!collectedResult) {
      throw new Error('수집 결과 객체가 없습니다. 구조 진단을 실행하세요.');
    }

    const warningText = collectedResult.warning ? `\n알림: ${collectedResult.warning}` : '';
    const zeroGuide = collectedResult.orderCount === 0
      ? '\n수집 결과: 0건\n구조 진단을 실행해 선택자 매칭 수를 확인하세요.'
      : '';
    setStatus(
      `수집 완료\n처리 페이지: ${collectedResult.pageCount}\n누적 건수: ${collectedResult.orderCount}${zeroGuide}${warningText}`
    );
    downloadButton.disabled = collectedResult.orderCount === 0;
  } catch (error) {
    setStatus(`오류: ${error.message || String(error)}`);
  } finally {
    startButton.disabled = false;
  }
});

diagnoseButton.addEventListener('click', async () => {
  diagnoseButton.disabled = true;

  try {
    const tab = await activeOrderListTab();
    setStatus('현재 페이지 구조를 진단하고 있습니다.');
    await loadCollector(tab.id);

    const executionResults = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => globalThis.__coupangOrderCollector?.diagnoseStructure() || null
    });
    const result = executionResults[0]?.result;
    if (!result) {
      throw new Error('진단 결과 객체가 없습니다. 확장을 새로고침한 뒤 다시 시도하세요.');
    }

    setStatus([
      '구조 진단 결과',
      `상품명 링크: ${result.productTitleLinks}개`,
      `주문 카드: ${result.orderCards}개`,
      `상품 이미지 링크: ${result.productImageLinks}개`,
      `금액: ${result.prices}개`,
      `수량: ${result.quantities}개`,
      `주문상태: ${result.orderStatuses}개`,
      `배송예정 안내: ${result.deliveryNotices}개`
    ].join('\n'));
  } catch (error) {
    setStatus(`진단 오류: ${error.message || String(error)}`);
  } finally {
    diagnoseButton.disabled = false;
  }
});

downloadButton.addEventListener('click', async () => {
  if (!collectedResult) {
    setStatus('먼저 수집을 완료하세요.');
    return;
  }

  const json = JSON.stringify(collectedResult, null, 2);
  const objectUrl = URL.createObjectURL(new Blob([json], { type: 'application/json' }));
  const date = new Date().toISOString().slice(0, 10).replaceAll('-', '');

  try {
    await chrome.downloads.download({
      url: objectUrl,
      filename: `coupang_order_history_${date}.json`,
      saveAs: true
    });
    setStatus(`JSON 내려받기를 시작했습니다.\n누적 건수: ${collectedResult.orderCount}`);
  } catch (error) {
    setStatus(`내려받기 오류: ${error.message || String(error)}`);
  } finally {
    setTimeout(() => URL.revokeObjectURL(objectUrl), 10000);
  }
});
