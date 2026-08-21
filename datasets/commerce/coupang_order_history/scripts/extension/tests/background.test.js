'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const { createController, JOB_KEY } = require('../background.js');

// content.js 대신 이 함수가 응답한다. method 이름으로 갈라 쓴다.
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

const LIST = { isList: true, listKey: 'p1', cards: 3, hasTrackingTable: false, hasOrderNumber: false, url: '/list' };

function runningJob(state, extra = {}) {
  return { status: 'running', tabId: 7, config: { minDelayMs: 800, maxDelayMs: 800 }, state, progress: null, result: null, ...extra };
}

function controllerFor(api) {
  return createController(api, { sleep: async () => {}, pollMs: 0, changeTimeoutMs: 20, random: () => 0 });
}

test('주입 컨텍스트가 사라져도 재주입 후 작업을 이어간다', async () => {
  let runCalls = 0;
  const { api, data } = fakeChrome(async (method, value) => {
    if (method === 'pageFacts') return [{ result: LIST }];
    if (method === 'runStep') {
      runCalls += 1;
      if (runCalls === 1) return undefined;                     // 결과 없음
      if (runCalls === 2) throw new Error('주입 컨텍스트 소실'); // 예외
      return [{ result: {
        state: { ...value, phase: 'DONE', done: true, result: { orderData: { orders: [1, 2, 3] }, trackingData: [] } },
        action: { type: 'done' },
        progress: { stage: 'DONE', page: 1, count: 3, remaining: 0, message: '완료' }
      } }];
    }
    return undefined;
  }, runningJob({ phase: 'INIT', orders: [], warnings: [] }));

  await controllerFor(api).resume(10);

  assert.equal(data[JOB_KEY].status, 'completed');
  assert.equal(data[JOB_KEY].result.orderData.orders.length, 3);
  assert.ok(runCalls >= 3, '결과 없음과 예외 뒤에 다시 호출해야 한다');
});

test('서비스 워커 재시작 뒤 storage 상태에서 재개한다', async () => {
  const seen = [];
  const { api, data } = fakeChrome(async (method, value) => {
    if (method === 'pageFacts') return [{ result: LIST }];
    if (method === 'runStep') {
      seen.push(value.page);
      return [{ result: {
        state: { ...value, phase: 'DONE', done: true, result: { orderData: { orders: [] }, trackingData: [] } },
        action: { type: 'done' },
        progress: { stage: 'DONE', page: value.page, count: 0, remaining: 0, message: '완료' }
      } }];
    }
    return undefined;
  }, runningJob({ phase: 'LIST', page: 5, orders: [], warnings: [] }));

  // 새 서비스 워커 인스턴스가 메모리 없이 시작한 상황이다.
  await controllerFor(api).resume(5);

  assert.deepEqual(seen, [5], '저장된 페이지에서 이어가야 한다');
  assert.equal(data[JOB_KEY].status, 'completed');
});

test('중단 요청을 storage에 반영하고 루프가 더 진행하지 않는다', async () => {
  let runCalls = 0;
  const { api, data } = fakeChrome(async (method, value) => {
    if (method === 'pageFacts') return [{ result: LIST }];
    if (method === 'runStep') {
      runCalls += 1;
      return [{ result: { state: { ...value }, action: { type: 'none' }, progress: { stage: 'LIST', page: 1, count: 0, remaining: 0, message: '진행' } } }];
    }
    return undefined;
  }, runningJob({ phase: 'LIST', orders: [], warnings: [] }));
  const controller = controllerFor(api);

  await controller.stop();
  await controller.resume(5);

  assert.equal(data[JOB_KEY].status, 'stopped');
  assert.equal(runCalls, 0, '중단 뒤에는 한 걸음도 더 가면 안 된다');
});

test('클릭 0단계가 안 통하면 방법을 올려 다시 누른다', async () => {
  const attempts = [];
  let facts = { ...LIST };
  const { api } = fakeChrome(async (method, value) => {
    if (method === 'pageFacts') return [{ result: facts }];
    if (method === 'performAction') {
      attempts.push(value.attempt);
      // 0단계는 아무 일도 일어나지 않고 1단계에서야 페이지가 넘어간다.
      if (value.attempt >= 1) facts = { ...LIST, listKey: 'p2' };
      return [{ result: { ok: true, attempt: value.attempt } }];
    }
    return undefined;
  }, runningJob({ phase: 'LIST', orders: [], warnings: [] }));

  const outcome = await controllerFor(api).executeAction(
    runningJob({ phase: 'LIST', orders: [], warnings: [] }),
    { type: 'click', target: 'nextPage', index: 0, expect: 'listChanged' }
  );

  assert.deepEqual(attempts, [0, 1]);
  assert.deepEqual({ ok: outcome.ok, attempt: outcome.attempt }, { ok: true, attempt: 1 });
});

test('네 단계가 다 실패하면 이 걸음을 포기하고 사유를 남긴다', async () => {
  const attempts = [];
  const { api, data } = fakeChrome(async (method, value) => {
    if (method === 'pageFacts') return [{ result: LIST }];       // 끝까지 그대로
    if (method === 'performAction') { attempts.push(value.attempt); return [{ result: { ok: true } }]; }
    if (method === 'runStep') {
      return [{ result: {
        state: { ...value },
        action: { type: 'click', target: 'detail', index: 0, expect: 'leftList' },
        progress: { stage: 'DETAIL', page: 1, count: 0, remaining: 1, message: '상세' }
      } }];
    }
    return undefined;
  }, runningJob({ phase: 'DETAIL', orders: [], warnings: [] }));

  await controllerFor(api).resume(1);

  assert.deepEqual(attempts, [0, 1, 2, 3], '네 가지 방법을 모두 써야 한다');
  assert.equal(data[JOB_KEY].state.skipCurrent, true);
  assert.equal(data[JOB_KEY].lastOutcome.ok, false);
  assert.match(data[JOB_KEY].state.warnings.at(-1), /네 번 다 통하지 않았습니다/);
});

test('조건이 늦게 참이 되면 기다렸다가 성공으로 본다', async () => {
  let polls = 0;
  const { api } = fakeChrome(async (method) => {
    if (method === 'pageFacts') {
      polls += 1;
      // 세 번째 확인에서야 상세 페이지가 된다.
      return [{ result: polls >= 4 ? { ...LIST, isList: false } : LIST }];
    }
    if (method === 'performAction') return [{ result: { ok: true } }];
    return undefined;
  }, runningJob({ phase: 'DETAIL', orders: [], warnings: [] }));

  const outcome = await controllerFor(api).executeAction(
    runningJob({ phase: 'DETAIL', orders: [], warnings: [] }),
    { type: 'click', target: 'detail', index: 0, expect: 'leftList' }
  );

  assert.equal(outcome.ok, true);
  assert.equal(outcome.attempt, 0, '한 번에 됐으면 방법을 올리지 않아야 한다');
});
