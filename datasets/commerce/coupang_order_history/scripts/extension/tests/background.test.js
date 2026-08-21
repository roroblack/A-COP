'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const { createController, JOB_KEY } = require('../background.js');

function fakeChrome(handler, initialJob = null) {
  const data = initialJob ? { [JOB_KEY]: structuredClone(initialJob) } : {};
  const api = {
    storage: { local: {
      get(key, callback) { callback({ [key]: data[key] }); },
      set(value, callback) { Object.assign(data, structuredClone(value)); callback?.(); }
    } },
    scripting: { async executeScript(details) {
      if (details.files) return [{ result: true }];
      return handler(details.args[0], details.args[1]);
    } },
    tabs: { async update() { return {}; } },
    alarms: { create() {}, clear() {}, onAlarm: { addListener() {} } },
    runtime: { lastError: null, sendMessage(_message, callback) { callback?.(); }, onMessage: { addListener() {} } }
  };
  return { api, data };
}

function runningJob(state) {
  return {
    status: 'running', tabId: 7,
    config: { minDelayMs: 800, maxDelayMs: 800 },
    state, progress: null, result: null
  };
}

test('주입 컨텍스트가 사라져도 재주입 후 작업을 이어간다', async () => {
  let runCalls = 0;
  let signature = '목록-1';
  let signatureCalls = 0;
  const { api, data } = fakeChrome(async (method, value) => {
    if (method === 'runStep') {
      runCalls += 1;
      if (runCalls === 1) return undefined;
      if (runCalls === 2) throw new Error('주입 컨텍스트 소실');
      if (value.phase === 'INIT') return [{ result: { state: { ...value, phase: 'AFTER_CLICK' }, action: { type: 'click', target: 'nextPage', index: 0 }, progress: { stage: 'LIST', page: 1, count: 3, remaining: 0, message: '다음 페이지' } } }];
      return [{ result: { state: { ...value, phase: 'DONE', done: true, result: { orderData: { orders: [1, 2, 3] }, trackingData: [] } }, action: { type: 'done' }, progress: { stage: 'DONE', page: 2, count: 3, remaining: 0, message: '완료' } } }];
    }
    if (method === 'pageSignature') {
      signatureCalls += 1;
      if (signatureCalls === 2) throw new Error('페이지 이동 중');
      return [{ result: signature }];
    }
    if (method === 'performAction') { signature = '목록-2'; return undefined; }
    return undefined;
  }, runningJob({ phase: 'INIT', scope: 'list', years: [], yearIndex: 0, page: 1, orders: [], tracking: [], queue: [], cursor: 0, warnings: [], done: false }));
  const controller = createController(api, { sleep: async () => {}, pollMs: 0, changeTimeoutMs: 100, random: () => 0 });

  await controller.resume(10);

  assert.equal(data[JOB_KEY].status, 'completed');
  assert.equal(data[JOB_KEY].result.orderData.orders.length, 3);
  assert.ok(runCalls >= 4, 'undefined와 예외 뒤에 runStep을 다시 호출해야 한다');
});

test('서비스 워커 재시작 뒤 storage 상태에서 재개한다', async () => {
  const storedState = { phase: 'RESUME', scope: 'list', years: [{ label: '2026', done: false }], yearIndex: 0, page: 2, orders: [{ OrderId: '저장됨' }], tracking: [], queue: [], cursor: 0, warnings: [], done: false };
  const { api, data } = fakeChrome(async (method, value) => {
    if (method === 'runStep') return [{ result: { state: { ...value, phase: 'DONE', done: true, result: { orderData: { orders: value.orders }, trackingData: [] } }, action: { type: 'done' }, progress: { stage: 'DONE', page: 2, count: 1, remaining: 0, message: '재개 완료' } } }];
    return [{ result: '서명' }];
  }, runningJob(storedState));

  const restartedController = createController(api, { sleep: async () => {} });
  await restartedController.resume(3);

  assert.equal(data[JOB_KEY].status, 'completed');
  assert.equal(data[JOB_KEY].result.orderData.orders[0].OrderId, '저장됨');
});

test('중단 요청을 storage에 반영하고 루프가 더 진행하지 않는다', async () => {
  let runCalls = 0;
  const { api, data } = fakeChrome(async () => { runCalls += 1; return undefined; }, runningJob({ phase: 'INIT', orders: [], tracking: [], queue: [], cursor: 0, warnings: [], done: false }));
  const controller = createController(api, { sleep: async () => {} });

  await controller.stop();
  await controller.resume(3);

  assert.equal(data[JOB_KEY].status, 'stopped');
  assert.equal(runCalls, 0);
});

test('클릭이 계속 먹히지 않으면 forceSkip을 세워 주문을 건너뛴다', async () => {
  // performAction이 아무 변화도 만들지 못하는 상황을 흉내 낸다.
  let stepCalls = 0;
  const { api, data } = fakeChrome(async (method, value) => {
    if (method === 'runStep') {
      stepCalls += 1;
      if (value.forceSkip) {
        return [{ result: { state: { ...value, phase: 'DONE', done: true, forceSkip: false, result: { orderData: { orders: [] }, trackingData: [] } }, action: { type: 'done' }, progress: { stage: 'DONE', page: 1, count: 0, remaining: 0, message: '건너뜀' } } }];
      }
      return [{ result: { state: { ...value, phase: 'DETAIL' }, action: { type: 'click', target: 'detail', index: 0 }, progress: { stage: 'DETAIL', page: 1, count: 1, remaining: 1, message: '주문 상세를 엽니다.' } } }];
    }
    if (method === 'pageSignature') return [{ result: '고정-서명' }];   // 변화 없음
    if (method === 'performAction') return [{ result: { ok: false, reason: '버튼 없음' } }];
    return undefined;
  }, runningJob({ phase: 'DETAIL', scope: 'tracking', years: [], yearIndex: 0, page: 1, orders: [], tracking: [], queue: [], cursor: 0, warnings: [], done: false }));
  const controller = createController(api, { sleep: async () => {}, pollMs: 0, changeTimeoutMs: 5, random: () => 0 });

  await controller.resume(12);

  assert.equal(data[JOB_KEY].status, 'completed', '정체 상태에서 빠져나오지 못했다');
  assert.ok(stepCalls <= 6, `건너뛰기까지 ${stepCalls}번은 너무 많다`);
});
