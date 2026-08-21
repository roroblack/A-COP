'use strict';

(() => {
  const JOB_KEY = 'coupangJob';
  const ALARM_NAME = 'coupangCollectorKeepAlive';
  const DEFAULT_POLL_MS = 400;
  const DEFAULT_CHANGE_TIMEOUT_MS = 15000;

  function createController(chromeApi, options = {}) {
    const sleep = options.sleep || ((ms) => new Promise((resolve) => setTimeout(resolve, ms)));
    const random = options.random || Math.random;
    const pollMs = options.pollMs ?? DEFAULT_POLL_MS;
    const changeTimeoutMs = options.changeTimeoutMs ?? DEFAULT_CHANGE_TIMEOUT_MS;
    let loopPromise = null;

    const storageGet = (key) => new Promise((resolve) => chromeApi.storage.local.get(key, resolve));
    const storageSet = (value) => new Promise((resolve) => chromeApi.storage.local.set(value, resolve));

    async function getJob() {
      return (await storageGet(JOB_KEY))[JOB_KEY] || null;
    }

    async function saveJob(job) {
      job.updatedAt = new Date().toISOString();
      await storageSet({ [JOB_KEY]: job });
      return job;
    }

    async function inject(tabId) {
      await chromeApi.scripting.executeScript({ target: { tabId }, files: ['content.js'] });
    }

    async function callCollector(tabId, method, argument) {
      await inject(tabId);
      const results = await chromeApi.scripting.executeScript({
        target: { tabId },
        func: (name, value) => {
          const collector = globalThis.__coupangOrderCollector;
          if (!collector || typeof collector[name] !== 'function') return undefined;
          return collector[name](value);
        },
        args: [method, argument]
      });
      return results?.[0]?.result;
    }

    async function readSignature(tabId) {
      const signature = await callCollector(tabId, 'pageSignature');
      if (typeof signature !== 'string') throw new Error('페이지 서명을 받지 못했습니다.');
      return signature;
    }

    async function waitForPageChange(tabId, before) {
      const startedAt = Date.now();
      do {
        await sleep(pollMs);
        try {
          const current = await readSignature(tabId);
          if (current !== before) return true;
        } catch {
          // 전체 문서 이동 중에는 주입 컨텍스트가 잠시 없을 수 있다.
        }
      } while (Date.now() - startedAt < changeTimeoutMs);
      return false;
    }

    async function rateLimit(config) {
      const min = Math.max(800, Number(config?.minDelayMs) || 1500);
      const max = Math.max(min, Number(config?.maxDelayMs) || 3500);
      await sleep(Math.round(min + random() * (max - min)));
    }

    function sendProgress(progress, status) {
      try {
        chromeApi.runtime.sendMessage({ type: 'COUPANG_JOB_PROGRESS', progress, status }, () => void chromeApi.runtime.lastError);
      } catch {
        // 팝업이 닫힌 경우에도 작업은 저장소를 기준으로 계속된다.
      }
    }

    async function executeAction(job, action) {
      if (action.type === 'none' || action.type === 'done') return true;
      if (action.type === 'navigate') {
        let before = '';
        try { before = await readSignature(job.tabId); } catch { /* 현재 문서가 없는 경우 */ }
        await chromeApi.tabs.update(job.tabId, { url: action.url });
        return waitForPageChange(job.tabId, before);
      }
      if (action.type === 'click') {
        const before = await readSignature(job.tabId);
        await callCollector(job.tabId, 'performAction', action);
        return waitForPageChange(job.tabId, before);
      }
      return false;
    }

    async function loop(maxIterations = Infinity) {
      let iterations = 0;
      while (iterations < maxIterations) {
        iterations += 1;
        const job = await getJob();
        if (!job || job.status !== 'running') return job;

        let step;
        try {
          step = await callCollector(job.tabId, 'runStep', job.state);
        } catch {
          await sleep(pollMs);
          continue;
        }
        if (!step?.state || !step?.action) {
          await sleep(pollMs);
          continue;
        }

        job.state = step.state;
        job.progress = step.progress;
        if (step.state.result) job.result = step.state.result;
        await saveJob(job);
        sendProgress(step.progress, job.status);

        if (step.action.type === 'done') {
          job.status = 'completed';
          job.completedAt = new Date().toISOString();
          job.result = step.state.result || job.result;
          await saveJob(job);
          sendProgress(step.progress, job.status);
          chromeApi.alarms.clear(ALARM_NAME);
          return job;
        }

        if (step.action.type !== 'none') {
          try {
            const changed = await executeAction(job, step.action);
            if (changed) job.state.stalls = 0;
            if (!changed) {
              // 같은 액션이 계속 먹히지 않으면 그 주문을 건너뛰고 진행한다.
              job.state.stalls = (job.state.stalls || 0) + 1;
              if (job.state.stalls >= 3) { job.state.forceSkip = true; job.state.stalls = 0; }
              job.state.warnings ||= [];
              job.state.warnings.push('페이지 변화 확인 시간이 초과되었습니다. 같은 단계를 다시 확인합니다.');
              await saveJob(job);
            }
          } catch {
            // 이동 중 컨텍스트 소실은 다음 반복에서 재주입하여 복구한다.
          }
          await rateLimit(job.config);
        }
      }
      return getJob();
    }

    function resume(maxIterations = Infinity) {
      if (!loopPromise) loopPromise = loop(maxIterations).finally(() => { loopPromise = null; });
      return loopPromise;
    }

    async function start(tabId, config = {}) {
      const job = {
        status: 'running', tabId, config,
        state: {
          phase: 'INIT', scope: config.collectionScope || 'tracking', years: [], yearIndex: 0,
          page: 1, orders: [], tracking: [], queue: [], cursor: 0, warnings: [], done: false,
          yearScope: config.yearScope || 'all', pageCount: 0, listSignature: null, listUrl: null
        },
        progress: { stage: 'INIT', page: 1, count: 0, remaining: 0, message: '수집을 시작합니다.' },
        result: null, startedAt: new Date().toISOString()
      };
      await saveJob(job);
      chromeApi.alarms.create(ALARM_NAME, { periodInMinutes: 0.5 });
      if (options.autoRun !== false) void resume();
      return job;
    }

    async function stop() {
      const job = await getJob();
      if (!job) return null;
      job.status = 'stopped';
      job.stoppedAt = new Date().toISOString();
      await saveJob(job);
      chromeApi.alarms.clear(ALARM_NAME);
      sendProgress(job.progress, job.status);
      return job;
    }

    return { start, stop, resume, getJob, saveJob, waitForPageChange, callCollector };
  }

  if (typeof chrome !== 'undefined' && chrome.runtime?.onMessage) {
    const controller = createController(chrome);
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
      if (message?.type === 'START') {
        const tabId = message.tabId || sender.tab?.id;
        controller.start(tabId, message.config).then((job) => sendResponse({ ok: true, job })).catch((error) => sendResponse({ ok: false, error: error.message }));
        return true;
      }
      if (message?.type === 'STOP') {
        controller.stop().then((job) => sendResponse({ ok: true, job })).catch((error) => sendResponse({ ok: false, error: error.message }));
        return true;
      }
      if (message?.type === 'GET_JOB') {
        controller.getJob().then((job) => sendResponse({ ok: true, job }));
        return true;
      }
      return false;
    });
    chrome.alarms.onAlarm.addListener((alarm) => {
      if (alarm.name === ALARM_NAME) void controller.resume();
    });
    void controller.resume();
  }

  if (typeof module !== 'undefined' && module.exports) module.exports = { createController, JOB_KEY, ALARM_NAME };
})();
