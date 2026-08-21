'use strict';

(() => {
  const ORDER_LIST_URL = 'https://mc.coupang.com/ssr/desktop/order/list';
  const elements = {
    min: document.querySelector('#minDelay'), max: document.querySelector('#maxDelay'), long: document.querySelector('#longDelay'),
    start: document.querySelector('#startButton'), stop: document.querySelector('#stopButton'),
    openList: document.querySelector('#openListButton'), probe: document.querySelector('#probe'), diagnose: document.querySelector('#diagnoseButton'), detailProbe: document.querySelector('#detailProbeButton'), stateProbe: document.querySelector('#stateProbeButton'), nextProbe: document.querySelector('#nextProbeButton'), buildLine: document.querySelector('#buildLine'), orderDownload: document.querySelector('#orderDownloadButton'),
    trackingDownload: document.querySelector('#trackingDownloadButton'), trackingReason: document.querySelector('#trackingDownloadReason'),
    status: document.querySelector('#status'), scopeSummary: document.querySelector('#scopeSummary')
  };
  let currentJob = null;

  function setStatus(message) { elements.status.textContent = message; }
  function selected(name) { return document.querySelector(`input[name="${name}"]:checked`)?.value; }
  function isOrderListUrl(value) { try { const url = new URL(value); return url.origin === 'https://mc.coupang.com' && url.pathname.startsWith('/ssr/desktop/order/list'); } catch { return false; } }
  const REQUIRED_ORIGINS = ['https://mc.coupang.com/*', 'https://www.coupang.com/*'];

  // 사이트 액세스가 "클릭할 때"면 확장은 아이콘을 누른 순간에만 접근할 수 있고
  // 페이지를 이동하면 회수된다. 팝업은 되는데 배경 수집은 멈추는 이유가 이것이다.
  // 시작 버튼 클릭은 사용자 제스처이므로 이 자리에서 영구 허용을 요청할 수 있다.
  async function ensureHostPermission() {
    const has = await new Promise((resolve) => {
      try { chrome.permissions.contains({ origins: REQUIRED_ORIGINS }, (result) => resolve(Boolean(result))); }
      catch { resolve(true); }
    });
    if (has) return true;
    setStatus('쿠팡 페이지 접근 권한을 요청합니다. 허용을 눌러주세요.');
    const granted = await new Promise((resolve) => {
      try { chrome.permissions.request({ origins: REQUIRED_ORIGINS }, (result) => resolve(Boolean(result))); }
      catch { resolve(false); }
    });
    if (!granted) {
      throw new Error(
        '쿠팡 페이지 접근이 허용되지 않아 수집할 수 없습니다.\n' +
        '확장 아이콘을 오른쪽 클릭해 사이트 액세스를 "모든 사이트에서"로 바꿔주세요.'
      );
    }
    return true;
  }

  function waitForTabLoad(tabId, timeoutMs = 20000) {
    return new Promise((resolve) => {
      const timer = setTimeout(() => { chrome.tabs.onUpdated.removeListener(listener); resolve(false); }, timeoutMs);
      function listener(changedTabId, info) {
        if (changedTabId !== tabId || info.status !== 'complete') return;
        clearTimeout(timer);
        chrome.tabs.onUpdated.removeListener(listener);
        resolve(true);
      }
      chrome.tabs.onUpdated.addListener(listener);
    });
  }

  // 주문목록이 아니면 알아서 옮겨준다. 매번 주소를 찾아 들어갈 이유가 없다.
  async function ensureOrderListTab() {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id) throw new Error('활성 탭을 찾지 못했습니다.');
    if (isOrderListUrl(tab.url)) return tab;
    setStatus('주문목록 페이지로 이동합니다.');
    await chrome.tabs.update(tab.id, { url: ORDER_LIST_URL });
    await waitForTabLoad(tab.id);
    return tab;
  }

  async function activeOrderListTab(anyCoupangPage = false) { const [tab] = await chrome.tabs.query({ active: true, currentWindow: true }); const ok = tab?.id && (anyCoupangPage ? /^https:\/\/mc\.coupang\.com\//.test(tab.url || '') : isOrderListUrl(tab.url)); if (!ok) throw new Error(`쿠팡 주문목록 페이지에서 실행하세요.
${ORDER_LIST_URL}`); return tab; }
  function config() {
    const minDelayMs = Math.round(Number(elements.min.value) * 1000);
    const maxDelayMs = Math.round(Number(elements.max.value) * 1000);
    const longDelayMs = Math.round(Number(elements.long.value) * 1000);
    if (!Number.isFinite(minDelayMs) || minDelayMs < 300) throw new Error('최소 대기 시간은 0.3초 이상이어야 합니다.');
    if (!Number.isFinite(maxDelayMs) || maxDelayMs < minDelayMs) throw new Error('최대 대기 시간은 최소 대기 시간 이상이어야 합니다.');
    if (!Number.isFinite(longDelayMs) || longDelayMs < maxDelayMs) throw new Error('가끔 쉬는 초는 최대 대기 시간 이상이어야 합니다.');
    return {
      collectionScope: selected('collectionScope') || 'tracking',
      yearScope: selected('yearScope') || 'current',
      minDelayMs, maxDelayMs, longDelayMs
    };
  }
  function message(payload) { return new Promise((resolve, reject) => chrome.runtime.sendMessage(payload, (response) => { if (chrome.runtime.lastError) reject(new Error(chrome.runtime.lastError.message)); else if (!response?.ok) reject(new Error(response?.error || '요청에 실패했습니다.')); else resolve(response); })); }
  // 진단 출력은 진행 표시와 따로 둔다. 같은 자리에 쓰면 곧바로 덮어써진다.
  function setProbe(text) {
    elements.probe.hidden = !text;
    elements.probe.textContent = text || '';
  }

  function bar(done, total, width = 14) {
    if (!total) return '';
    const filled = Math.max(0, Math.min(width, Math.round((done / total) * width)));
    return `${'▓'.repeat(filled)}${'░'.repeat(width - filled)} ${Math.round((done / total) * 100)}%`;
  }

  let countdownTimer = null;
  function renderStatusLines(job) {
    const progress = job.progress || {};
    const head = job.status === 'completed' ? '수집 완료' : job.status === 'stopped' ? '수집 중단' : '수집 중';
    const done = progress.queueDone || 0;
    const total = progress.queueTotal || 0;
    const lines = [
      `${head} · ${progress.year || '-'}년 ${progress.page || 1}페이지 (지금까지 ${progress.pageCount || 0}페이지)`,
      total ? `이 페이지 ${done}/${total}건  ${bar(done, total)}` : '이 페이지 목록을 읽는 중',
      `누적 주문 ${progress.orderCount ?? 0}건 (상품 행 ${progress.count || 0}개) · 배송 ${progress.trackingCount || 0}건`
    ];
    const remain = (progress.waitUntil || 0) - Date.now();
    if (job.status === 'running' && remain > 0) {
      const total = (progress.waitMs || 0) / 1000;
      const kind = progress.longBreak ? '잠깐 쉬는 중' : '대기';
      lines.push(`${kind} ${(remain / 1000).toFixed(1)}초 남음 (추첨 ${total.toFixed(1)}초) ${bar(total - remain / 1000, total, 10)}`);
    }
    lines.push(progress.message || '');
    if (job.lastClick && job.lastClick.ok === false) lines.push(`마지막 클릭 실패: ${job.lastClick.reason}`);
    return lines.filter(Boolean).join('\n');
  }

  function showProgress(job) {
    if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null; }
    setStatus(renderStatusLines(job));
    const remain = (job.progress?.waitUntil || 0) - Date.now();
    // 남은 대기를 0.1초마다 다시 그린다. 멈춘 것인지 기다리는 것인지 구분된다.
    if (job.status === 'running' && remain > 0) {
      countdownTimer = setInterval(() => {
        if (((job.progress?.waitUntil || 0) - Date.now()) <= 0) { clearInterval(countdownTimer); countdownTimer = null; }
        setStatus(renderStatusLines(job));
      }, 100);
    }
  }

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
    showProgress(job);
  }
  // 파일명에는 내려받은 시각이 아니라 수집을 시작한 시각을 쓴다.
  // 같은 결과를 다시 받아도 이름이 같고, 여러 번 돌린 것끼리 섞이지 않는다.
  function runStamp(job) {
    const at = job?.startedAt ? new Date(job.startedAt) : new Date();
    const when = Number.isNaN(at.getTime()) ? new Date() : at;
    const pad = (value) => String(value).padStart(2, '0');
    return `${when.getFullYear()}${pad(when.getMonth() + 1)}${pad(when.getDate())}_${pad(when.getHours())}${pad(when.getMinutes())}${pad(when.getSeconds())}`;
  }
  function downloadJson(value, filename) { const blob = new Blob([JSON.stringify(value, null, 2)], { type: 'application/json;charset=utf-8' }); const url = URL.createObjectURL(blob); chrome.downloads.download({ url, filename, saveAs: true }, () => { URL.revokeObjectURL(url); void chrome.runtime.lastError; }); }
  function updateScopeSummary() { const labels = { list: '목록만', detail: '목록 + 상세', tracking: '목록 + 상세 + 배송조회' }; elements.scopeSummary.textContent = `수집 범위: ${labels[selected('collectionScope')] || labels.tracking}`; }

  // 팝업이 열려 있는 동안은 팝업이 수집을 돌린다.
  // 서비스 워커는 유휴 30초면 종료되지만 팝업은 열려 있는 한 살아 있다.
  // 워커는 팝업의 심장박동이 멎으면 이어받는다.
  const popupController = globalThis.__coupangController?.createController(chrome, { driver: 'popup' }) || null;

  function drivePopupLoop() {
    if (!popupController) return;
    void popupController.resume().catch(() => {});
  }

  // resume 은 이미 돌고 있으면 아무 일도 하지 않는다. 주기적으로 밀어도 안전하다.
  // 팝업 루프가 어떤 이유로 끝났으면 여기서 다시 시작된다.
  setInterval(() => { if (currentJob?.status === 'running') drivePopupLoop(); }, 3000);

  elements.start.addEventListener('click', async () => { try { await ensureHostPermission(); const tab = await ensureOrderListTab(); setStatus('수집 작업을 시작합니다.'); const response = await message({ type: 'START', tabId: tab.id, config: config(), popupDrives: Boolean(popupController) }); render(response.job); drivePopupLoop(); } catch (error) { setStatus(`오류: ${error.message}`); } });
  elements.stop.addEventListener('click', async () => { try { const response = await message({ type: 'STOP' }); render(response.job); } catch (error) { setStatus(`오류: ${error.message}`); } });
  elements.diagnose.addEventListener('click', async () => { elements.diagnose.disabled = true; try { const tab = await activeOrderListTab(); await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ['content.js'] }); const results = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: () => globalThis.__coupangOrderCollector?.diagnoseStructure() }); const diagnosis = results?.[0]?.result; if (!diagnosis) throw new Error('진단 결과를 받지 못했습니다.'); setStatus(Object.entries(diagnosis).map(([key, value]) => `${key}: ${value}`).join('\n')); } catch (error) { setProbe(`오류: ${error.message}`); } finally { elements.diagnose.disabled = false; } });
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

  // 수집이 멈춘 순간 무슨 상태인지 그대로 찍는다. 수집 중에도 눌러도 된다.
  elements.stateProbe.addEventListener('click', async () => {
    elements.stateProbe.disabled = true;
    try {
      const health = await message({ type: 'HEALTH' }).then((r) => r.health).catch(() => null);
      const hasHost = await new Promise((resolve) => {
        try { chrome.permissions.contains({ origins: REQUIRED_ORIGINS }, (r) => resolve(Boolean(r))); } catch { resolve(null); }
      });
      const tab = await activeOrderListTab(true);
      await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ['content.js'] });
      const page = await runInTab(tab.id, 'describePage');
      const job = (await message({ type: 'GET_JOB' })).job;
      const state = job?.state || {};
      const item = (state.queue || [])[state.cursor || 0];
      const lines = [
        `확장 ${chrome.runtime.getManifest().version}`,
        page.error ? `페이지: 오류 ${page.error}` : [
          `빌드 ${page.value.build}`,
          `주소 ${String(page.value.url).replace('https://mc.coupang.com', '')}`,
          `목록판정 ${page.value.isList} (상세보기 ${page.value.detailLeaves}개, 카드 ${page.value.cards}개)`,
          `표지 돌아가기=${page.value.hasBackToList} 받는사람정보=${page.value.hasRecipientBlock} 주문번호=${page.value.hasOrderNumberLabel} 결제정보=${page.value.hasPaymentBlock} 배송조회=${page.value.hasTrackingButton}`,
          `다음버튼 ${page.value.nextButton} 후보 ${(page.value.nextCandidates || []).length}개`,
          ...(page.value.nextCandidates || []).map((line) => `  ${line}`),
        ].join('\n'),
        `작업 ${job?.status} / ${state.phase} / ${state.page}페이지`,
        `마지막결과 ${job?.lastOutcome ? JSON.stringify(job.lastOutcome) : '없음'} 건너뛰기=${Boolean(state.skipCurrent)}`,
        `큐 ${state.cursor || 0}/${(state.queue || []).length} returning=${item?.returning ?? '-'} detailDone=${item?.detailDone ?? '-'}`,
        `마지막클릭 ${job?.lastClick ? JSON.stringify(job.lastClick) : '없음'}`,
        `주문 ${(state.orders || []).length}행, 주문번호확보 ${(state.orders || []).filter((o) => o && o._idSource === 'orderNumber').length}행`,
        `경고 ${(state.warnings || []).slice(-2).join(' | ') || '없음'}`
      ];
      lines.push(`사이트 접근 권한 ${hasHost === null ? '확인 불가' : hasHost ? '있음' : '없음 (배경 수집 불가)'}`);
      if (health) {
        const since = health.lastLoopAt ? Math.round((Date.now() - new Date(health.lastLoopAt).getTime()) / 1000) : null;
        lines.push(`루프 ${health.looping ? '돎' : '멈춤'} · 깨움 ${health.keepAlive ? '켜짐' : '꺼짐'} · 마지막 걸음 ${since === null ? '없음' : `${since}초 전`}`);
        lines.push(`응답없음 ${health.timeoutCount}회 · 루프오류 ${health.loopErrorCount}회 · 호출실패 ${health.callFailCount}회`);
        if (health.lastLoopError) lines.push(`루프오류: ${health.lastLoopError}`);
        if (health.lastCallError) lines.push(`호출오류: ${health.lastCallError}`);
      }
      const mine = popupController?.health?.();
      if (!popupController) lines.push('팝업루프 없음 (컨트롤러를 불러오지 못함)');
      else {
        const since = mine?.lastLoopAt ? Math.round((Date.now() - new Date(mine.lastLoopAt).getTime()) / 1000) : null;
        if (mine?.currentAction) lines.push(`팝업이 기다리는 것: ${mine.currentAction} (${Math.round((mine.currentActionMs || 0) / 1000)}초째)`);
        lines.push(`팝업루프 ${mine?.looping ? '돎' : '멈춤'} · 마지막 걸음 ${since === null ? '없음' : `${since}초 전`} · 호출실패 ${mine?.callFailCount ?? '-'}회`);
        if (mine?.lastCallError) lines.push(`팝업호출오류: ${mine.lastCallError}`);
        if (mine?.lastLoopError) lines.push(`팝업루프오류: ${mine.lastLoopError}`);
        if (health.startupError) lines.push(`시작오류: ${health.startupError}`);
      }
      const text = lines.join('\n');
      setProbe(text);
      console.log(text);
    } catch (error) {
      setProbe(`오류: ${error.message}`);
    } finally {
      elements.stateProbe.disabled = false;
    }
  });

  // 팝업에서 직접 다음 버튼을 눌러본다. 서비스 워커 경로와 비교하기 위한 것이다.
  elements.nextProbe.addEventListener('click', async () => {
    elements.nextProbe.disabled = true;
    const lines = [];
    const show = () => setStatus(lines.join('\n'));
    try {
      const tab = await activeOrderListTab();
      await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ['content.js'] });
      const before = await runInTab(tab.id, 'describePage');
      if (before.error) throw new Error(before.error);
      lines.push(`빌드 ${before.value.build}`);
      lines.push(`누르기 전 카드 ${before.value.cards}개`);
      lines.push(`다음 후보 ${(before.value.nextCandidates || []).join(' / ') || '없음'}`);
      show();

      const clicked = await runInTab(tab.id, 'performAction', { type: 'click', target: 'nextPage', index: 0, attempt: 0 });
      lines.push(`클릭 반환 ${clicked.error ? `예외 ${clicked.error}` : JSON.stringify(clicked.value)}`);
      show();

      for (const seconds of [1, 2, 4]) {
        await new Promise((resolve) => setTimeout(resolve, seconds * 1000));
        const after = await runInTab(tab.id, 'describePage');
        if (after.error) { lines.push(`${seconds}초: 스크립트 사라짐 (페이지 이동)`); show(); continue; }
        lines.push(`${seconds}초: 카드 ${after.value.cards}개, 서명 ${after.value.signature === before.value.signature ? '그대로' : '바뀜'}`);
        show();
      }
    } catch (error) {
      lines.push(`오류: ${error.message}`);
      show();
    } finally {
      elements.nextProbe.disabled = false;
    }
  });

  elements.openList.addEventListener('click', async () => {
    elements.openList.disabled = true;
    try { const tab = await ensureOrderListTab(); setProbe(`주문목록 페이지입니다.
${tab.url || ''}`); }
    catch (error) { setProbe(`오류: ${error.message}`); }
    finally { elements.openList.disabled = false; }
  });

  elements.orderDownload.addEventListener('click', () => { if (currentJob?.result?.orderData) downloadJson(currentJob.result.orderData, `coupang_order_history_${runStamp(currentJob)}.json`); });
  elements.trackingDownload.addEventListener('click', () => { if ((currentJob?.result?.trackingData?.length || 0) > 0) downloadJson(currentJob.result.trackingData, `coupang_tracking_${runStamp(currentJob)}.json`); });
  for (const radio of document.querySelectorAll('input[name="collectionScope"]')) radio.addEventListener('change', updateScopeSummary);
  chrome.runtime.onMessage.addListener((event) => { if (event?.type === 'COUPANG_JOB_PROGRESS') message({ type: 'GET_JOB' }).then((response) => render(response.job)).catch(() => {}); });
  chrome.storage.onChanged.addListener((changes, area) => { if (area === 'local' && changes.coupangJob) render(changes.coupangJob.newValue); });
  updateScopeSummary();
  elements.buildLine.textContent = `확장 ${chrome.runtime.getManifest().version}`;
  setTimeout(() => { if (currentJob?.status === 'running') drivePopupLoop(); }, 300);
  message({ type: 'GET_JOB' }).then((response) => render(response.job)).catch(() => {});
})();
