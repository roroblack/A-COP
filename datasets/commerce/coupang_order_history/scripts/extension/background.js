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

    async function rateLimit(config) {
      const min = Math.max(800, Number(config?.minDelayMs) || 1500);
      const max = Math.max(min, Number(config?.maxDelayMs) || 3500);
      await sleep(Math.round(min + random() * (max - min)));
    }

    function sendProgress(progress, status) {
      try {
        chromeApi.runtime.sendMessage({ type: 'COUPANG_JOB_PROGRESS', progress, status }, () => void chromeApi.runtime.lastError);
      } catch {
        // 팝업이 닫혀도 작업은 저장소를 기준으로 계속된다.
      }
    }

    async function readFacts(tabId) {
      const facts = await callCollector(tabId, 'pageFacts');
      if (!facts || typeof facts !== 'object') throw new Error('페이지 정보를 받지 못했습니다.');
      return facts;
    }

    // "무언가 바뀌었나"가 아니라 "원하는 상태가 됐나"를 본다.
    async function awaitCondition(tabId, isSatisfied, timeoutMs = changeTimeoutMs) {
      const startedAt = Date.now();
      do {
        await sleep(pollMs);
        try {
          if (isSatisfied(await readFacts(tabId))) return true;
        } catch {
          // 페이지 이동 중에는 주입 컨텍스트가 잠시 없다. 다음 폴링에서 다시 본다.
        }
      } while (Date.now() - startedAt < timeoutMs);
      return false;
    }

    function conditionFor(action, before) {
      if (action.expect === 'leftList') return (facts) => !facts.isList;
      if (action.expect === 'listChanged') return (facts) => facts.isList && facts.listKey !== before.listKey;
      if (action.expect === 'backOnList') return (facts) => facts.isList;
      if (action.expect === 'tracking') return (facts) => !facts.isList && facts.hasTrackingTable;
      return (facts) => facts.listKey !== before.listKey || facts.isList !== before.isList;
    }

    async function executeAction(job, action) {
      if (action.type === 'none' || action.type === 'done') return { ok: true };
      if (action.type === 'navigate') {
        await chromeApi.tabs.update(job.tabId, { url: action.url });
        const ok = await awaitCondition(job.tabId, (facts) => facts.isList);
        return { ok, reason: ok ? null : '주소 이동 뒤 목록이 나타나지 않았습니다.' };
      }
      if (action.type !== 'click') return { ok: false, reason: `모르는 액션 ${action.type}` };

      const before = await readFacts(job.tabId);
      const satisfied = conditionFor(action, before);
      // 방법을 바꿔가며 네 번까지 눌러본다. 기다리기만 하지 않는다.
      for (let attempt = 0; attempt < 4; attempt += 1) {
        const report = await callCollector(job.tabId, 'performAction', { ...action, attempt });
        job.lastClick = { ...(report || {}), attempt, target: action.target, expect: action.expect || null };
        await saveJob(job);
        if (report?.ok === false) continue;
        if (await awaitCondition(job.tabId, satisfied)) return { ok: true, attempt };
      }
      return { ok: false, reason: `${action.target} 클릭이 네 번 다 통하지 않았습니다.` };
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
          let outcome;
          try {
            outcome = await executeAction(job, step.action);
          } catch (error) {
            outcome = { ok: false, reason: `실행 중 예외: ${error.message}` };
          }
          job.lastOutcome = outcome;
          if (!outcome.ok) {
            // 네 가지 방법이 다 실패했다. 이 걸음은 포기하고 다음으로 넘긴다.
            job.state.skipCurrent = true;
            job.state.warnings ||= [];
            job.state.warnings.push(outcome.reason || '행동이 통하지 않았습니다.');
          }
          await saveJob(job);
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
          yearScope: config.yearScope || 'current', pageCount: 0, listSignature: null, listUrl: null
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

    return { start, stop, resume, getJob, saveJob, awaitCondition, executeAction, callCollector };
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
