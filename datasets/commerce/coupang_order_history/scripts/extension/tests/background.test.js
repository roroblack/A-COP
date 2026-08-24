'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const { createController } = require('../background.js');

function runningJob(overrides = {}) {
  return {
    jobId: 'job-1',
    engineVersion: 'document-navigation-v2',
    status: 'running',
    tabId: 7,
    config: { collectionScope: 'tracking', minDelayMs: 300, maxDelayMs: 300, longDelayMs: 300 },
    state: { phase: 'LIST', scope: 'tracking', orders: [], warnings: [], queue: [], years: [], cursor: 0 },
    progress: {},
    result: null,
    ...overrides
  };
}

const doneStep = (state) => ({
  state: { ...state, phase: 'DONE', done: true, result: { orderData: { orders: [] }, trackingData: [] } },
  action: { type: 'done' },
  progress: { stage: 'DONE', count: 0, message: '완료' }
});

function mockChrome({ job = runningJob(), runStep = doneStep, injected = true, tab = { id: 7, status: 'complete', discarded: false }, hangCalls = false } = {}) {
  const data = { coupangJob: structuredClone(job) };
  const calls = { runStep: 0, injections: 0, updates: [], reloads: [], removes: [], alarmClears: 0 };
  let hasCollector = injected;
  const api = {
    storage: { local: {
      get(key, callback) { callback({ [key]: data[key] }); },
      set(value, callback) { Object.assign(data, structuredClone(value)); callback?.(); }
    } },
    scripting: { executeScript(details) {
      if (details.files) {
        calls.injections += 1;
        hasCollector = true;
        return Promise.resolve([{ result: true }]);
      }
      if (hangCalls) return new Promise(() => {});
      if (!hasCollector) return Promise.resolve([{ result: undefined }]);
      const [method, value] = details.args;
      if (method === 'runStep') {
        calls.runStep += 1;
        return Promise.resolve([{ result: runStep(value, calls.runStep) }]);
      }
      return Promise.resolve([{ result: undefined }]);
    } },
    tabs: {
      async update(tabId, update) { calls.updates.push({ tabId, update }); return { id: tabId, ...update }; },
      get(_tabId, callback) { callback(tab); },
      async reload(tabId) { calls.reloads.push(tabId); },
      async remove(tabId) { calls.removes.push(tabId); }
    },
    alarms: { clear() { calls.alarmClears += 1; }, create() {} },
    runtime: { lastError: null, sendMessage(_message, callback) { callback?.(); } }
  };
  return { api, data, calls };
}

function controllerFor(api, options = {}) {
  return createController(api, {
    sleep: async () => {},
    pollMs: 0,
    callTimeoutMs: 10,
    random: () => 0,
    ...options
  });
}

test('수집기가 없는 문서는 content.js를 한 번 주입하고 이어간다', async () => {
  const { api, data, calls } = mockChrome({ injected: false });
  await controllerFor(api).resume(2);

  assert.equal(calls.injections, 1);
  assert.equal(calls.runStep, 1);
  assert.equal(data.coupangJob.status, 'completed');
});

test('서비스 워커가 재시작해도 storage 체크포인트에서 재개한다', async () => {
  let receivedPhase = null;
  const { api, data } = mockChrome({
    runStep(state) { receivedPhase = state.phase; return doneStep(state); }
  });

  await controllerFor(api).resume(2);

  assert.equal(receivedPhase, 'LIST');
  assert.equal(data.coupangJob.status, 'completed');
});

test('5.3 helper/fetch 상태는 현재 문서 이동 엔진으로 초기화한다', async () => {
  let receivedState;
  const legacy = runningJob({
    engineVersion: 'fetch-helper-v1',
    startedAt: '2026-08-21T00:00:00.000Z',
    helperTabId: 99,
    state: { phase: 'DETAIL', orders: [{ OrderId: 'old' }], warnings: ['old'] }
  });
  const { api, data, calls } = mockChrome({
    job: legacy,
    runStep(state) { receivedState = structuredClone(state); return doneStep(state); }
  });

  await controllerFor(api).resume(3);

  assert.equal(receivedState.phase, 'INIT');
  assert.deepEqual(receivedState.orders, []);
  assert.deepEqual(calls.removes, [99]);
  assert.equal(data.coupangJob.engineVersion, 'document-navigation-v2');
});

test('navigate 액션은 같은 수집 탭을 정상 문서 주소로 이동시킨다', async () => {
  const target = 'https://mc.coupang.com/ssr/desktop/order/16102412157785';
  const { api, data, calls } = mockChrome({
    runStep: (state) => ({
      state: { ...state, phase: 'DETAIL', queue: [{ orderId: '16102412157785', returning: 'detail' }] },
      action: { type: 'navigate', target: 'detail', url: target, expectedUrl: target, expectedOrderId: '16102412157785' },
      progress: { stage: 'DETAIL', message: '상세 이동' }
    })
  });

  await controllerFor(api).resume(1);

  assert.deepEqual(calls.updates, [{ tabId: 7, update: { url: target, active: true } }]);
  assert.equal(data.coupangJob.pendingNavigation.url, target);
  assert.equal(data.coupangJob.pendingNavigation.expectedOrderId, '16102412157785');
  assert.equal(data.coupangJob.helperTabId, undefined);
});

test('executeScript가 응답하지 않아도 호출 제한시간 뒤 제어권을 되찾는다', async () => {
  const { api } = mockChrome({ hangCalls: true });
  const controller = controllerFor(api, { callTimeoutMs: 5 });

  await controller.resume(1);

  assert.ok(controller.health().timeoutCount >= 2);
  assert.equal(controller.health().looping, false);
});

test('실제로 discarded 된 탭만 다시 불러온다', async () => {
  const { api, calls } = mockChrome({ injected: false, tab: { id: 7, status: 'unloaded', discarded: true } });
  // 주입 뒤에도 결과가 없게 해 recoverTab 경로로 보낸다.
  api.scripting.executeScript = async (details) => details.files ? [{ result: true }] : [{ result: undefined }];

  await controllerFor(api).resume(1);

  assert.deepEqual(calls.reloads, [7]);
});

test('수집 탭이 닫히면 임의의 다른 쿠팡 탭을 잡지 않고 중단한다', async () => {
  const { api, data } = mockChrome({ injected: false, tab: null });
  api.scripting.executeScript = async (details) => details.files ? [{ result: true }] : [{ result: undefined }];

  await controllerFor(api).resume(2);

  assert.equal(data.coupangJob.status, 'stopped');
  assert.match(data.coupangJob.state.warnings.at(-1), /수집 탭이 닫혀/);
});

test('정상 탭의 일시적 호출 실패만으로 새로고침하지 않는다', async () => {
  const { api, calls } = mockChrome({ injected: false, tab: { id: 7, status: 'complete', discarded: false } });
  api.scripting.executeScript = async (details) => details.files ? [{ result: true }] : [{ result: undefined }];

  await controllerFor(api).resume(1);

  assert.deepEqual(calls.reloads, []);
});

test('서비스 워커는 영구 keepalive 대신 이벤트 체크포인트를 사용한다', () => {
  const { api } = mockChrome();
  const health = controllerFor(api).health();

  assert.equal(health.eventDriven, true);
  assert.equal(health.looping, false);
  assert.equal('keepAlive' in health, false);
});
