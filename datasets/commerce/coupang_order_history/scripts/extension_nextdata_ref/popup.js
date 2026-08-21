'use strict';

const ORDER_LIST_URL = 'https://mc.coupang.com/ssr/desktop/order/list';
const STORAGE_KEY = 'coupangAccumulated';

// 자동 수집 설정
const AUTO_MIN_DELAY = 3000; // ms
const AUTO_MAX_DELAY = 7000; // ms
const MAX_AUTO_PAGES = 500; // 안전 상한
const PAGE_LOAD_TIMEOUT = 20000; // ms

const RECENT_6M = ''; // 기간 select에서 "최근 6개월" 값

const periodSelect = document.querySelector('#periodSelect');
const openPeriodButton = document.querySelector('#openPeriodButton');
const autoButton = document.querySelector('#autoButton');
const startButton = document.querySelector('#startButton');
const nextPageButton = document.querySelector('#nextPageButton');
const downloadButton = document.querySelector('#downloadButton');
const resetButton = document.querySelector('#resetButton');
const statusElement = document.querySelector('#status');

let autoRunning = false;
let stopRequested = false;

function setStatus(message) {
  statusElement.textContent = message;
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

// 선택한 기간의 1페이지(서버렌더) URL. 최근 6개월은 파라미터 없는 기본 URL.
// 연도 필터의 실제 쿼리 파라미터는 requestYear 다(쿠팡 페이지 URL/XHR과 동일).
function startUrlForPeriod(period) {
  if (period === RECENT_6M) {
    return ORDER_LIST_URL;
  }
  const url = new URL(ORDER_LIST_URL);
  url.searchParams.set('pageIndex', '0');
  url.searchParams.set('requestYear', String(period));
  return url.href;
}

// 다음 페이지 URL. 연도 선택 시 requestYear를 그 연도로 고정한다(카테고리 이탈 방지).
// 최근 6개월은 파라미터 없이 pageIndex만 증가시킨다.
function nextUrlForPeriod(period, pagination) {
  if (!pagination || !pagination.hasNext) {
    return null;
  }
  const url = new URL(ORDER_LIST_URL);
  url.searchParams.set('pageIndex', String(pagination.nextPageIndex));
  if (period !== RECENT_6M) {
    url.searchParams.set('requestYear', String(period));
  }
  return url.href;
}

function periodLabel(period) {
  return period === RECENT_6M ? '최근 6개월' : `${period}년`;
}

function randomDelay(min, max) {
  const ms = min + Math.random() * (max - min);
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// 상태는 chrome.storage.local에 둔다(팝업이 닫히거나 페이지가 바뀌어도 유지).
async function getStore() {
  const data = await chrome.storage.local.get(STORAGE_KEY);
  return data[STORAGE_KEY] || { orders: [], pages: 0, lastPagination: null };
}

async function setStore(store) {
  await chrome.storage.local.set({ [STORAGE_KEY]: store });
}

// 누적 전체와 비교해 새 행만 추가한다(직전 페이지가 아니라 전역 비교 → wrap 재수집 차단).
function dedupAppend(store, rows) {
  const seen = new Set(store.orders.map((r) => JSON.stringify(r)));
  let added = 0;
  for (const row of rows) {
    const key = JSON.stringify(row);
    if (!seen.has(key)) {
      seen.add(key);
      store.orders.push(row);
      added += 1;
    }
  }
  return added;
}

async function getOrderListTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id || !isOrderListUrl(tab.url)) {
    throw new Error(`쿠팡 주문목록 페이지에서 실행하세요.\n${ORDER_LIST_URL}`);
  }
  return tab;
}

async function injectAndCollect(tabId) {
  await chrome.scripting.executeScript({ target: { tabId }, files: ['content.js'] });
  const results = await chrome.scripting.executeScript({
    target: { tabId },
    func: () => {
      if (!globalThis.__coupangOrderCollector) {
        throw new Error('수집 스크립트를 불러오지 못했습니다.');
      }
      return globalThis.__coupangOrderCollector.collectCurrentPage();
    }
  });
  const page = results[0]?.result;
  if (!page) {
    throw new Error('수집 결과를 받지 못했습니다.');
  }
  return page;
}

function waitForTabLoad(tabId, timeoutMs = PAGE_LOAD_TIMEOUT) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      chrome.tabs.onUpdated.removeListener(onUpdated);
      reject(new Error('페이지 로딩 시간 초과'));
    }, timeoutMs);

    function onUpdated(id, info) {
      if (id === tabId && info.status === 'complete') {
        clearTimeout(timer);
        chrome.tabs.onUpdated.removeListener(onUpdated);
        resolve();
      }
    }
    chrome.tabs.onUpdated.addListener(onUpdated);
  });
}

async function navigateTab(tabId, url) {
  const loaded = waitForTabLoad(tabId);
  await chrome.tabs.update(tabId, { url });
  await loaded;
}

function syncButtons(store) {
  downloadButton.disabled = store.orders.length === 0;
  nextPageButton.disabled = !nextUrlForPeriod(periodSelect.value, store.lastPagination);
}

function setRunningUI(running) {
  autoRunning = running;
  autoButton.textContent = running ? '중지' : '자동 수집 (끝까지)';
  startButton.disabled = running;
  nextPageButton.disabled = running;
  resetButton.disabled = running;
  openPeriodButton.disabled = running;
  periodSelect.disabled = running;
}

// 한 페이지 수집 후 누적. 주문 0건이면 저장하지 않는다. { added, store, page } 반환.
async function collectInto(tabId) {
  const page = await injectAndCollect(tabId);
  const store = await getStore();
  let added = 0;
  if (page.orderCardCount > 0) {
    added = dedupAppend(store, page.orders);
    if (added > 0) {
      store.pages += 1;
    }
    store.lastPagination = page.pagination;
    await setStore(store);
  }
  return { added, store, page };
}

// --- 기간 열기 (수동 모드용: 선택 기간의 1페이지를 서버렌더로 연다) ---
openPeriodButton.addEventListener('click', async () => {
  try {
    const tab = await getOrderListTab();
    const period = periodSelect.value;
    setStatus(`${periodLabel(period)} 페이지를 여는 중입니다.`);
    await navigateTab(tab.id, startUrlForPeriod(period));
    setStatus(`${periodLabel(period)} 페이지를 열었습니다.\n'이 페이지만 수집' 또는 '자동 수집'을 누르세요.`);
  } catch (error) {
    setStatus(`오류: ${error.message || String(error)}`);
  }
});

// --- 수동: 이 페이지만 수집 ---
startButton.addEventListener('click', async () => {
  startButton.disabled = true;
  try {
    const tab = await getOrderListTab();
    setStatus('현재 페이지를 수집하고 있습니다.');
    const { added, store, page } = await collectInto(tab.id);
    if (page.orderCardCount === 0) {
      setStatus('주문을 찾지 못했습니다.\n주문목록 페이지인지, 로그인 상태인지 확인하세요.');
      return;
    }
    const tail = nextUrlForPeriod(periodSelect.value, page.pagination)
      ? "'다음 페이지로 이동' 후 다시 수집."
      : '마지막 페이지입니다. \'JSON 내려받기\'.';
    setStatus(
      (added > 0
        ? `이번 페이지 +${added}건(신규)\n`
        : `새 주문이 없습니다(이미 수집했거나 마지막).\n`) +
      `누적 건수: ${store.orders.length}\n${tail}`
    );
    syncButtons(store);
  } catch (error) {
    setStatus(`오류: ${error.message || String(error)}`);
  } finally {
    startButton.disabled = false;
  }
});

// --- 자동: 선택 기간을 끝까지 수집 ('중지'로도 동작) ---
autoButton.addEventListener('click', async () => {
  if (autoRunning) {
    stopRequested = true;
    setStatus('중지 요청됨. 현재 페이지까지 마치고 멈춥니다.');
    return;
  }

  stopRequested = false;
  setRunningUI(true);
  const period = periodSelect.value;

  try {
    const tab = await getOrderListTab();

    // 선택 기간의 1페이지(서버렌더)로 먼저 이동해 __NEXT_DATA__가 그 기간을 반영하게 한다.
    setStatus(`${periodLabel(period)} 1페이지로 이동 중입니다.`);
    await navigateTab(tab.id, startUrlForPeriod(period));
    await randomDelay(AUTO_MIN_DELAY, AUTO_MAX_DELAY);

    let stopReason = `안전 상한(${MAX_AUTO_PAGES}페이지)에 도달해 멈췄습니다.`;

    for (let i = 0; i < MAX_AUTO_PAGES; i += 1) {
      if (stopRequested) {
        stopReason = '사용자 요청으로 중지했습니다.';
        break;
      }

      const { added, store, page } = await collectInto(tab.id);

      if (page.orderCardCount === 0) {
        stopReason = i === 0
          ? `${periodLabel(period)}에 주문이 없습니다.`
          : `끝까지 수집했습니다.\n누적 ${store.orders.length}건`;
        break;
      }

      setStatus(
        `자동 수집 중… ${periodLabel(period)} (${i + 1}페이지)\n` +
        `이번 +${added}건 / 누적 ${store.orders.length}건`
      );

      if (added === 0) {
        stopReason = `새 주문이 없어 종료합니다(끝 또는 중복).\n누적 ${store.orders.length}건`;
        break;
      }

      const url = nextUrlForPeriod(period, page.pagination);
      if (!url) {
        stopReason = `마지막 페이지입니다.\n누적 ${store.orders.length}건`;
        break;
      }

      await navigateTab(tab.id, url);
      await randomDelay(AUTO_MIN_DELAY, AUTO_MAX_DELAY);
    }

    setStatus(`자동 수집 종료.\n${stopReason}`);
  } catch (error) {
    setStatus(`자동 수집 오류: ${error.message || String(error)}`);
  } finally {
    setRunningUI(false);
    syncButtons(await getStore());
  }
});

// --- 수동: 다음 페이지로 이동 (선택 기간 유지) ---
nextPageButton.addEventListener('click', async () => {
  const store = await getStore();
  const url = nextUrlForPeriod(periodSelect.value, store.lastPagination);
  if (!url) {
    setStatus('다음 페이지가 없습니다.');
    return;
  }
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) {
    setStatus('활성 탭을 찾지 못했습니다.');
    return;
  }
  await chrome.tabs.update(tab.id, { url });
  setStatus(`다음 페이지로 이동 중입니다.\n페이지가 뜨면 '이 페이지만 수집'을 누르세요.`);
});

// --- JSON 내려받기 ---
downloadButton.addEventListener('click', async () => {
  const store = await getStore();
  if (store.orders.length === 0) {
    setStatus('먼저 수집을 하세요.');
    return;
  }

  const result = {
    exportedAt: new Date().toISOString(),
    source: ORDER_LIST_URL,
    pageCount: store.pages,
    orderCount: store.orders.length,
    orders: store.orders
  };

  const json = JSON.stringify(result, null, 2);
  const objectUrl = URL.createObjectURL(new Blob([json], { type: 'application/json' }));
  const date = new Date().toISOString().slice(0, 10).replaceAll('-', '');

  try {
    await chrome.downloads.download({
      url: objectUrl,
      filename: `coupang_order_history_${date}.json`,
      saveAs: true
    });
    setStatus(`JSON 내려받기를 시작했습니다.\n누적 건수: ${store.orders.length}`);
  } catch (error) {
    setStatus(`내려받기 오류: ${error.message || String(error)}`);
  } finally {
    setTimeout(() => URL.revokeObjectURL(objectUrl), 10000);
  }
});

// --- 초기화 ---
resetButton.addEventListener('click', async () => {
  await chrome.storage.local.remove(STORAGE_KEY);
  downloadButton.disabled = true;
  nextPageButton.disabled = true;
  setStatus('누적 데이터를 초기화했습니다.\n기간을 고르고 다시 시작하세요.');
});

// 기간 드롭다운 채우기: 최근 6개월 + 올해부터 과거 연도.
(function fillPeriods() {
  const thisYear = new Date().getFullYear();
  const options = [[RECENT_6M, '최근 6개월']];
  for (let year = thisYear; year >= thisYear - 7; year -= 1) {
    options.push([String(year), `${year}년`]);
  }
  periodSelect.innerHTML = options
    .map(([value, label]) => `<option value="${value}">${label}</option>`)
    .join('');
})();

// 팝업을 다시 열었을 때 상태 복원
(async () => {
  const store = await getStore();
  if (store.orders.length > 0) {
    setStatus(
      `누적 건수: ${store.orders.length}\n수집한 페이지: ${store.pages}\n` +
      `이어서 수집하거나 'JSON 내려받기'를 누르세요.`
    );
  } else {
    setStatus("기간을 고르고 '자동 수집'을 누르세요.");
  }
  syncButtons(store);
})();
