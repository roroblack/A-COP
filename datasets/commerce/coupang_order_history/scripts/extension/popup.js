'use strict';

(() => {
  const ORDER_LIST_URL = 'https://mc.coupang.com/ssr/desktop/order/list';
  const elements = {
    min: document.querySelector('#minDelay'), max: document.querySelector('#maxDelay'),
    start: document.querySelector('#startButton'), stop: document.querySelector('#stopButton'),
    diagnose: document.querySelector('#diagnoseButton'), detailProbe: document.querySelector('#detailProbeButton'), buildLine: document.querySelector('#buildLine'), orderDownload: document.querySelector('#orderDownloadButton'),
    trackingDownload: document.querySelector('#trackingDownloadButton'), trackingReason: document.querySelector('#trackingDownloadReason'),
    status: document.querySelector('#status'), scopeSummary: document.querySelector('#scopeSummary')
  };
  let currentJob = null;

  function setStatus(message) { elements.status.textContent = message; }
  function selected(name) { return document.querySelector(`input[name="${name}"]:checked`)?.value; }
  function isOrderListUrl(value) { try { const url = new URL(value); return url.origin === 'https://mc.coupang.com' && url.pathname.startsWith('/ssr/desktop/order/list'); } catch { return false; } }
  async function activeOrderListTab() { const [tab] = await chrome.tabs.query({ active: true, currentWindow: true }); if (!tab?.id || !isOrderListUrl(tab.url)) throw new Error(`쿠팡 주문목록 페이지에서 실행하세요.\n${ORDER_LIST_URL}`); return tab; }
  function config() {
    const minDelayMs = Math.round(Number(elements.min.value) * 1000); const maxDelayMs = Math.round(Number(elements.max.value) * 1000);
    if (!Number.isFinite(minDelayMs) || minDelayMs < 800) throw new Error('최소 대기 시간은 0.8초 이상이어야 합니다.');
    if (!Number.isFinite(maxDelayMs) || maxDelayMs < minDelayMs) throw new Error('최대 대기 시간은 최소 대기 시간 이상이어야 합니다.');
    return { collectionScope: selected('collectionScope') || 'tracking', yearScope: selected('yearScope') || 'current', minDelayMs, maxDelayMs };
  }
  function message(payload) { return new Promise((resolve, reject) => chrome.runtime.sendMessage(payload, (response) => { if (chrome.runtime.lastError) reject(new Error(chrome.runtime.lastError.message)); else if (!response?.ok) reject(new Error(response?.error || '요청에 실패했습니다.')); else resolve(response); })); }
  function render(job) {
    currentJob = job || null; const running = job?.status === 'running'; const completed = job?.status === 'completed';
    elements.start.disabled = running; elements.stop.disabled = !running;
    // 이전 버전에서 중단된 작업은 result가 없다. 누적 상태에서 되살린다.
    if (job && !job.result?.orderData && (job.state?.orders?.length || 0) > 0) {
      const collector = globalThis.__coupangOrderCollector;
      if (collector) job.result = collector.buildExportPayloads(job.state.orders, { collectionScope: job.state.scope, pageCount: job.state.pageCount, warning: '중단 시점까지의 부분 결과입니다.', partial: true });
    }
    const orderCount = job?.result?.orderData?.orders?.length || 0; const trackingCount = job?.result?.trackingData?.length || 0;
    // 중단해도 그때까지 모은 것은 내려받을 수 있어야 한다.
    elements.orderDownload.disabled = running || orderCount === 0;
    elements.trackingDownload.disabled = running || trackingCount === 0;
    const partialNote = !completed && orderCount > 0 ? ' (중단 시점까지의 부분 결과)' : '';
    elements.trackingReason.textContent = trackingCount > 0 ? `배송 이력 ${trackingCount}건을 내려받을 수 있습니다.${partialNote}` : running ? '수집 중에는 내려받을 수 없습니다.' : '수집된 배송 이력이 없습니다.';
    if (!job) return;
    const progress = job.progress || {};
    setStatus(`${job.status === 'completed' ? '수집 완료' : job.status === 'stopped' ? '수집 중단' : '수집 중'}\n단계: ${progress.stage || '-'} / ${progress.year || '-'}년\n페이지: ${progress.page || 1}\n누적 건수: ${progress.orderCount ?? 0}건 (상품 행 ${progress.count || 0}개)\n${progress.message || ''}${job.lastClick && job.lastClick.ok === false ? `
마지막 클릭 실패: ${job.lastClick.reason}` : ''}`);
  }
  function dateStamp() { const now = new Date(); return `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}`; }
  function downloadJson(value, filename) { const blob = new Blob([JSON.stringify(value, null, 2)], { type: 'application/json;charset=utf-8' }); const url = URL.createObjectURL(blob); chrome.downloads.download({ url, filename, saveAs: true }, () => { URL.revokeObjectURL(url); void chrome.runtime.lastError; }); }
  function updateScopeSummary() { const labels = { list: '목록만', detail: '목록 + 상세', tracking: '목록 + 상세 + 배송조회' }; elements.scopeSummary.textContent = `수집 범위: ${labels[selected('collectionScope')] || labels.tracking}`; }

  elements.start.addEventListener('click', async () => { try { const tab = await activeOrderListTab(); setStatus('수집 작업을 시작합니다.'); const response = await message({ type: 'START', tabId: tab.id, config: config() }); render(response.job); } catch (error) { setStatus(`오류: ${error.message}`); } });
  elements.stop.addEventListener('click', async () => { try { const response = await message({ type: 'STOP' }); render(response.job); } catch (error) { setStatus(`오류: ${error.message}`); } });
  elements.diagnose.addEventListener('click', async () => { elements.diagnose.disabled = true; try { const tab = await activeOrderListTab(); await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ['content.js'] }); const results = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: () => globalThis.__coupangOrderCollector?.diagnoseStructure() }); const diagnosis = results?.[0]?.result; if (!diagnosis) throw new Error('진단 결과를 받지 못했습니다.'); setStatus(Object.entries(diagnosis).map(([key, value]) => `${key}: ${value}`).join('\n')); } catch (error) { setStatus(`오류: ${error.message}`); } finally { elements.diagnose.disabled = false; } });
  async function runInTab(tabId, method, ...args) {
    const results = await chrome.scripting.executeScript({
      target: { tabId },
      func: (name, values) => {
        const collector = globalThis.__coupangOrderCollector;
        if (!collector) return { error: '수집 스크립트가 없습니다.' };
        try { return { value: collector[name](...values) }; } catch (error) { return { error: error.message }; }
      },
      args: [method, args]
    });
    return results?.[0]?.result || { error: '응답이 없습니다.' };
  }

  // 현재 페이지에서 상세 열기를 실제로 한 번 해보고 단계별로 보고한다.
  elements.detailProbe.addEventListener('click', async () => {
    elements.detailProbe.disabled = true;
    const lines = [];
    const show = () => setStatus(lines.join('\n'));
    try {
      const tab = await activeOrderListTab();
      await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ['content.js'] });
      lines.push(`확장 ${chrome.runtime.getManifest().version}`);

      const before = await runInTab(tab.id, 'describeTarget', 'detail', 0, 0);
      if (before.error) throw new Error(before.error);
      const info = before.value;
      lines.push(`content.js 빌드 ${info.build}`);
      lines.push(`목록 페이지 ${info.isList ? 'ok' : '아님'}`);
      lines.push(`카드 ${info.cardCount}개`);
      lines.push(`클릭 후보 ${info.candidateCount}개: ${info.chain.join(' < ') || '없음'}`);
      lines.push(`누를 것 ${info.pickTag || '없음'} "${info.pickText || ''}"`);
      show();
      if (!info.pickTag) throw new Error('클릭할 요소를 찾지 못했습니다.');

      const clicked = await runInTab(tab.id, 'performAction', { type: 'click', target: 'detail', index: 0, attempt: 0 });
      lines.push(`클릭 ${clicked.error ? `예외 ${clicked.error}` : JSON.stringify(clicked.value)}`);
      show();

      await new Promise((resolve) => setTimeout(resolve, 3000));
      const after = await runInTab(tab.id, 'describeTarget', 'detail', 0, 0);
      if (after.error) {
        lines.push('3초 후: 스크립트가 사라짐 (페이지가 이동했다는 뜻)');
      } else {
        const now = after.value;
        lines.push(`3초 후 주소 ${now.url === info.url ? '그대로' : '바뀜'}`);
        lines.push(`3초 후 서명 ${now.signature === info.signature ? '그대로' : '바뀜'}`);
        lines.push(`3초 후 목록페이지 ${now.isList ? 'ok (안 열림)' : '아님 (상세로 보임)'}`);
      }
      show();
    } catch (error) {
      lines.push(`오류: ${error.message}`);
      show();
    } finally {
      elements.detailProbe.disabled = false;
    }
  });

  elements.orderDownload.addEventListener('click', () => { if (currentJob?.result?.orderData) downloadJson(currentJob.result.orderData, `coupang_order_history_${dateStamp()}.json`); });
  elements.trackingDownload.addEventListener('click', () => { if ((currentJob?.result?.trackingData?.length || 0) > 0) downloadJson(currentJob.result.trackingData, `coupang_tracking_${dateStamp()}.json`); });
  for (const radio of document.querySelectorAll('input[name="collectionScope"]')) radio.addEventListener('change', updateScopeSummary);
  chrome.runtime.onMessage.addListener((event) => { if (event?.type === 'COUPANG_JOB_PROGRESS') message({ type: 'GET_JOB' }).then((response) => render(response.job)).catch(() => {}); });
  chrome.storage.onChanged.addListener((changes, area) => { if (area === 'local' && changes.coupangJob) render(changes.coupangJob.newValue); });
  updateScopeSummary();
  elements.buildLine.textContent = `확장 ${chrome.runtime.getManifest().version}`;
  message({ type: 'GET_JOB' }).then((response) => render(response.job)).catch(() => {});
})();
