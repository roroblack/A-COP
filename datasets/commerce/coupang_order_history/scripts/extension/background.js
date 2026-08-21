'use strict';

(() => {
  const JOB_KEY = 'coupangJob';
  const ALARM_NAME = 'coupangCollectorKeepAlive';
  const DEFAULT_POLL_MS = 400;
  const DEFAULT_CHANGE_TIMEOUT_MS = 15000;
  const NAVIGATION_TIMEOUT_MS = 30000;
  const CALL_TIMEOUT_MS = 5000;

  function createController(chromeApi, options = {}) {
    const sleep = options.sleep || ((ms) => new Promise((resolve) => setTimeout(resolve, ms)));
    const random = options.random || Math.random;
    const pollMs = options.pollMs ?? DEFAULT_POLL_MS;
    const changeTimeoutMs = options.changeTimeoutMs ?? DEFAULT_CHANGE_TIMEOUT_MS;
    // 페이지 이동은 더 오래 기다린다. 테스트가 짧게 잡았으면 그걸 따른다.
    const navigationTimeoutMs = options.navigationTimeoutMs ?? options.changeTimeoutMs ?? NAVIGATION_TIMEOUT_MS;
    const callTimeoutMs = options.callTimeoutMs ?? CALL_TIMEOUT_MS;
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

    // executeScript 가 끝내 응답하지 않으면 루프가 통째로 멈춘다. 탭이 숨겨지거나
    // 버려졌을 때 그런 일이 생긴다. 어떤 호출도 무한정 기다리지 않게 한다.
    let timeoutCount = 0;
    let lastTimeoutAt = null;
    let lastLoopAt = null;
    let loopErrorCount = 0;
    let lastLoopError = null;
    let callFailCount = 0;
    let lastCallError = null;
    function withTimeout(promise, ms, label) {
      let timer = null;
      const guard = new Promise((_, reject) => { timer = setTimeout(() => { timeoutCount += 1; lastTimeoutAt = new Date().toISOString(); reject(new Error(`${label} 응답이 없습니다.`)); }, ms); });
      return Promise.race([promise, guard]).finally(() => clearTimeout(timer));
    }

    async function inject(tabId) {
      await withTimeout(chromeApi.scripting.executeScript({ target: { tabId }, files: ['content.js'] }), callTimeoutMs, '수집 스크립트 주입');
    }

    // 중첩된 undefined도 직렬화를 깨뜨린다. 한 번 걸러서 보낸다.
    function serializable(value) {
      if (value === undefined) return null;
      try { return JSON.parse(JSON.stringify(value)); } catch { return null; }
    }

    async function callCollector(tabId, method, argument) {
      const payload = serializable(argument);
      const run = async () => {
        const results = await withTimeout(chromeApi.scripting.executeScript({
          target: { tabId },
          // args에 undefined가 들어가면 Chrome이 직렬화하지 못하고 예외를 던진다.
          // 인자 없는 함수를 부를 때가 그렇다. null로 바꿔 보내고 저쪽에서 되살린다.
          func: (name, value) => {
            const collector = globalThis.__coupangOrderCollector;
            if (!collector || typeof collector[name] !== 'function') return undefined;
            return value === null ? collector[name]() : collector[name](value);
          },
          args: [method, payload]
        }), callTimeoutMs, method);
        return results?.[0]?.result;
      };

      // 이미 주입돼 있으면 그대로 쓴다. 폴링마다 37KB를 다시 넣으면 느리다.
      try {
        const result = await run();
        if (result !== undefined) return result;
      } catch (error) {
        lastCallError = `${method}: ${error.message}`;
      }
      try {
        await inject(tabId);
        const result = await run();
        if (result === undefined) { callFailCount += 1; lastCallError = `${method}: 결과 없음`; }
        return result;
      } catch (error) {
        callFailCount += 1;
        lastCallError = `${method}: ${error.message}`;
        return undefined;
      }
    }

    // 대개 최소~최대 사이로 쉰다. 여섯 번에 한 번쯤 더 길게 쉰다.
    // 간격이 일정하면 사람으로 보이지 않는다.
    function drawWait(config) {
      const min = Math.max(300, Number(config?.minDelayMs) || 300);
      const max = Math.max(min, Number(config?.maxDelayMs) || 1100);
      const long = Math.max(max, Number(config?.longDelayMs) || 2000);
      const takeLongBreak = random() < 1 / 6;
      const low = takeLongBreak ? max : min;
      const high = takeLongBreak ? long : max;
      return { waitMs: Math.round(low + random() * (high - low)), longBreak: takeLongBreak };
    }

    async function rateLimit(config, job) {
      const { waitMs, longBreak } = drawWait(config);
      if (job) {
        job.progress = { ...(job.progress || {}), waitMs, longBreak, waitUntil: Date.now() + waitMs };
        await saveJob(job);
        sendProgress(job.progress, job.status);
      }
      await sleep(waitMs);
      if (job) {
        job.progress = { ...(job.progress || {}), waitMs: 0, longBreak: false, waitUntil: 0 };
        await saveJob(job);
      }
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

    async function isSatisfiedNow(tabId, satisfied) {
      try { return satisfied(await readFacts(tabId)); } catch { return false; }
    }

    async function executeAction(job, action) {
      if (action.type === 'none' || action.type === 'done') return { ok: true };
      if (action.type === 'navigate') {
        await chromeApi.tabs.update(job.tabId, { url: action.url });
        const ok = await awaitCondition(job.tabId, (facts) => facts.isList, navigationTimeoutMs);
        return { ok, reason: ok ? null : '주소 이동 뒤 목록이 나타나지 않았습니다.' };
      }
      if (action.type !== 'click') return { ok: false, reason: `모르는 액션 ${action.type}` };

      const before = await readFacts(job.tabId);
      const satisfied = conditionFor(action, before);
      // 페이지 이동을 기대하는 행동은 더 오래 기다린다.
      const timeout = action.expect === 'leftList' || action.expect === 'tracking' || action.expect === 'backOnList'
        ? navigationTimeoutMs : changeTimeoutMs;

      for (let attempt = 0; attempt < 4; attempt += 1) {
        // 재시도도 사람 속도로 한다. 연달아 네 번 누르면 봇으로 보인다.
        if (attempt > 0) await rateLimit(job.config, job);
        // 이미 원하는 상태면 또 누르지 않는다. 늦게 반영된 이동을 다시 누르면 망가진다.
        if (await isSatisfiedNow(job.tabId, satisfied)) return { ok: true, attempt, note: attempt ? '이미 이동해 있었습니다.' : null };

        const report = await callCollector(job.tabId, 'performAction', { ...action, attempt });
        job.lastClick = { ...(report || {}), attempt, target: action.target, expect: action.expect || null };
        await saveJob(job);

        if (report?.ok === false) {
          // 요소가 사라진 것은 이미 넘어갔다는 뜻일 수 있다.
          if (await isSatisfiedNow(job.tabId, satisfied)) return { ok: true, attempt, note: '요소는 없었지만 이미 이동해 있었습니다.' };
          continue;
        }
        if (await awaitCondition(job.tabId, satisfied, timeout)) return { ok: true, attempt };
      }
      return { ok: false, reason: `${action.target} 클릭이 네 번 다 통하지 않았습니다.` };
    }

    // MV3 서비스 워커는 유휴 30초면 종료된다. 알람이 깨울 때까지 작업이 멈춰 보인다.
    // 다른 창을 보고 있어도 계속 돌게 20초마다 확장 API를 한 번 부른다.
    let keepAliveTimer = null;
    function startKeepAlive() {
      if (keepAliveTimer) return;
      keepAliveTimer = setInterval(() => {
        try { chromeApi.runtime.getPlatformInfo?.(() => void chromeApi.runtime.lastError); } catch { /* 무시 */ }
      }, 20000);
    }
    function stopKeepAlive() {
      if (!keepAliveTimer) return;
      clearInterval(keepAliveTimer);
      keepAliveTimer = null;
    }

    // 오래 걸리는 걸음 도중에 중단이 들어올 수 있다. 그때 손에 든 낡은 job 을 그대로
    // 저장하면 status 가 running 으로 되살아난다. 저장 전에 실제 상태를 확인한다.
    async function saveIfRunning(job) {
      const current = await getJob();
      if (current?.status !== 'running') return false;
      await saveJob(job);
      return true;
    }

    let stepFailures = 0;
    async function noteStepFailure(job, reason) {
      stepFailures += 1;
      job.progress = { ...(job.progress || {}), message: `걸음이 진행되지 않습니다(${stepFailures}회): ${reason}` };
      try { await saveJob(job); sendProgress(job.progress, job.status); } catch { /* 저장 실패는 다음 걸음에서 다시 시도한다 */ }
    }

    async function loop(maxIterations = Infinity) {
      let iterations = 0;
      while (iterations < maxIterations) {
        iterations += 1;
        lastLoopAt = new Date().toISOString();
        try {
        const job = await getJob();
        if (!job || job.status !== 'running') return job;

        let step;
        try {
          step = await callCollector(job.tabId, 'runStep', job.state);
        } catch (error) {
          await noteStepFailure(job, error.message);
          await sleep(pollMs);
          continue;
        }
        if (!step?.state || !step?.action) {
          // 조용히 넘어가면 화면이 시작값에서 멈춘 채로 남는다. 사유를 남긴다.
          await noteStepFailure(job, lastCallError || '수집기가 결과를 주지 않았습니다.');
          await sleep(pollMs);
          continue;
        }

        job.state = step.state;
        job.progress = step.progress;
        if (step.state.result) job.result = step.state.result;
        if (!await saveIfRunning(job)) return getJob();
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
          if (!await saveIfRunning(job)) return getJob();
          await rateLimit(job.config, job);
        }
        } catch (error) {
          // 루프는 어떤 이유로도 죽지 않는다. 죽으면 다음 이벤트가 올 때까지 아무 일도 안 일어난다.
          loopErrorCount += 1;
          lastLoopError = `${error.message} (${new Date().toISOString()})`;
          await sleep(pollMs);
        }
      }
      return getJob();
    }

    // 루프가 끝나는 중에 들어온 resume 요청을 흘리면 아무도 돌지 않는 상태가 된다.
    // 서비스 워커가 START 메시지로 깨어날 때 모듈 최상단 resume 과 start 의 resume 이 겹친다.
    let resumeRequested = false;
    function resume(maxIterations = Infinity) {
      if (loopPromise) { resumeRequested = true; return loopPromise; }
      startKeepAlive();
      loopPromise = loop(maxIterations).finally(() => {
        loopPromise = null;
        stopKeepAlive();
        if (resumeRequested) { resumeRequested = false; void resume(maxIterations); }
      });
      return loopPromise;
    }

    // 서비스 워커가 페이지에 접근할 수 있는지 먼저 확인한다.
    // 사이트 액세스가 "클릭할 때"면 팝업은 되는데(아이콘 클릭으로 activeTab 획득)
    // 배경에서 도는 수집은 아무것도 못 한다. 증상은 "시작하자마자 멈춤"이다.
    async function ensureAccess(tabId) {
      try {
        await inject(tabId);
      } catch (error) {
        throw new Error(
          '페이지에 접근할 수 없어 수집을 시작하지 못했습니다.\n' +
          '확장 아이콘을 오른쪽 클릭해 사이트 액세스를 "mc.coupang.com에서" 또는 "모든 사이트에서"로 바꿔주세요.\n' +
          `(${error.message})`
        );
      }
    }

    async function start(tabId, config = {}, startOptions = {}) {
      await ensureAccess(tabId);
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
      chromeApi.alarms.create(ALARM_NAME, { periodInMinutes: 0.5, delayInMinutes: 0.5 });
      if (startOptions.autoRun !== false && options.autoRun !== false) void resume();
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

    return { start, stop, resume, getJob, saveJob, awaitCondition, executeAction, callCollector, rateLimit, health: () => ({ timeoutCount, lastTimeoutAt, lastLoopAt, loopErrorCount, lastLoopError, callFailCount, lastCallError, looping: Boolean(loopPromise), keepAlive: Boolean(keepAliveTimer) }) };
  }

  let startupError = null;
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
      if (message?.type === 'HEALTH') { sendResponse({ ok: true, health: { ...controller.health(), startupError } }); return true; }
      if (message?.type === 'GET_JOB') {
        // 서비스 워커가 잠들었다면 이 메시지가 깨운다. 깨어난 김에 작업도 이어간다.
        controller.getJob().then((job) => { if (job?.status === 'running') void controller.resume(); sendResponse({ ok: true, job }); });
        return true;
      }
      return false;
    });
    // 등록 하나가 실패하면 그 뒤의 등록이 전부 건너뛰어진다. 따로 감싼다.
    // 우리 작업은 페이지를 계속 이동시킨다. 그 로드를 서비스 워커를 깨우는 신호로 쓴다.
    try {
      chrome.tabs.onUpdated.addListener((tabId, info) => {
        if (info.status !== 'complete') return;
        controller.getJob().then((job) => { if (job?.status === 'running' && job.tabId === tabId) void controller.resume(); }).catch(() => {});
      });
    } catch (error) {
      startupError = `탭 이벤트 등록 실패: ${error.message}`;
    }
    try {
      chrome.alarms.onAlarm.addListener((alarm) => {
        if (alarm.name === ALARM_NAME) void controller.resume();
      });
    } catch (error) {
      startupError = `알람 등록 실패: ${error.message}`;
    }
    // 도는 작업이 있을 때만 시작한다. 헛도는 루프가 start 의 resume 과 겹친다.
    controller.getJob().then((job) => { if (job?.status === 'running') void controller.resume(); }).catch(() => {});
  }

  if (typeof module !== 'undefined' && module.exports) module.exports = { createController, JOB_KEY, ALARM_NAME };
})();
