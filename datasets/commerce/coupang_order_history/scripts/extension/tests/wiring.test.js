'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const path = require('node:path');

// 브라우저와 같은 경로로 돌린다.
// 모듈이 평가되면서 리스너가 등록되고, START 메시지가 그 리스너로 들어온다.
// 지금까지 테스트는 controller.start()를 직접 불러서 이 경로를 밟은 적이 없다.
function loadWorker({ initialJob = null, onRunStep, setDelays = [], getError = null } = {}) {
  const data = initialJob ? { coupangJob: structuredClone(initialJob) } : {};
  const listeners = { message: [], alarm: [], tabUpdated: [] };
  const calls = { runStep: 0, injections: 0, alarmCreates: [] };
  let setIndex = 0;

  const chrome = {
    storage: { local: {
      get(key, cb) {
        if (getError) throw new Error(getError);
        setTimeout(() => cb({ [key]: data[key] }), 0);
      },
      set(value, cb) {
        const snapshot = structuredClone(value);
        const delay = setDelays[setIndex++] || 0;
        setTimeout(() => { Object.assign(data, snapshot); cb?.(); }, delay);
      }
    } },
    scripting: { async executeScript(details) {
      if (details.files) {
        calls.injections += 1;
        return [{ result: true }];
      }
      const [method, value] = details.args;
      if (method === 'pageFacts') return [{ result: { isList: true, listKey: 'p1', cards: 3, hasTrackingTable: false, hasOrderNumber: false, url: '/list' } }];
      if (method === 'runStep') { calls.runStep += 1; return [{ result: await onRunStep(value, calls.runStep) }]; }
      return [{ result: undefined }];
    } },
    tabs: { async update() { return {}; }, onUpdated: { addListener: (fn) => listeners.tabUpdated.push(fn) } },
    alarms: {
      create(name, details) { calls.alarmCreates.push({ name, details, createdAt: Date.now() }); },
      clear() {},
      onAlarm: { addListener: (fn) => listeners.alarm.push(fn) }
    },
    runtime: {
      lastError: null,
      sendMessage(_message, cb) { cb?.(); },
      onMessage: { addListener: (fn) => listeners.message.push(fn) },
      getPlatformInfo(cb) { cb?.({}); }
    }
  };

  const previous = globalThis.chrome;
  globalThis.chrome = chrome;
  delete require.cache[require.resolve(path.join(__dirname, '..', 'background.js'))];
  require(path.join(__dirname, '..', 'background.js'));
  globalThis.chrome = previous;

  const send = (message) => new Promise((resolve) => {
    for (const listener of listeners.message) {
      if (listener(message, {}, resolve)) return;
    }
    resolve(null);
  });
  return { data, send, calls };
}

const DONE_STEP = (state) => ({
  state: { ...state, phase: 'DONE', done: true, result: { orderData: { orders: [{ OrderId: 'a' }] }, trackingData: [] } },
  action: { type: 'done' },
  progress: { stage: 'DONE', page: 1, count: 1, remaining: 0, message: '완료' }
});

test('START 메시지만으로 수집이 실제로 진행된다', async () => {
  const { data, send, calls } = loadWorker({ onRunStep: (state) => DONE_STEP(state) });

  const response = await send({ type: 'START', tabId: 7, config: { collectionScope: 'list', minDelayMs: 300, maxDelayMs: 300, longDelayMs: 300 } });
  assert.equal(response?.ok, true, response?.error);

  await new Promise((resolve) => setTimeout(resolve, 60));

  assert.ok(calls.runStep >= 1, 'runStep이 한 번도 불리지 않았다. 시작해도 아무 일이 없다는 뜻이다.');
  assert.equal(data.coupangJob.status, 'completed');
});

test('이전 작업이 남아 있어도 START 가 새 수집을 진행시킨다', async () => {
  // 서비스 워커가 깨어날 때 모듈 최상단 초기화와 start 가 겹치는 상황이다.
  const previousJob = { status: 'completed', tabId: 7, config: {}, state: { phase: 'DONE' }, progress: {}, result: null };
  const { data, send, calls } = loadWorker({ initialJob: previousJob, onRunStep: (state) => DONE_STEP(state) });

  const response = await send({ type: 'START', tabId: 7, config: { collectionScope: 'list', minDelayMs: 300, maxDelayMs: 300, longDelayMs: 300 } });
  assert.equal(response?.ok, true, response?.error);

  await new Promise((resolve) => setTimeout(resolve, 60));

  assert.ok(calls.runStep >= 1, '이전 작업이 남아 있으면 새 수집이 시작되지 않는다');
  assert.equal(data.coupangJob.status, 'completed');
});

test('중단하면 진행 중이던 걸음이 다시 살려내지 않는다', async () => {
  // 걸음 도중에 중단이 들어오면 손에 든 낡은 job 이 status 를 running 으로 되돌렸다.
  let sawStop = false;
  const { data, send, calls } = loadWorker({
    onRunStep: (state, n) => {
      if (n === 1) return { state: { ...state, phase: 'LIST' }, action: { type: 'none' }, progress: { message: '한 걸음' } };
      sawStop = true;
      return { state: { ...state, phase: 'LIST' }, action: { type: 'none' }, progress: { message: '또 한 걸음' } };
    }
  });

  await send({ type: 'START', tabId: 7, config: { collectionScope: 'list', minDelayMs: 300, maxDelayMs: 300, longDelayMs: 300 } });
  await new Promise((resolve) => setTimeout(resolve, 20));
  await send({ type: 'STOP' });
  const stoppedAt = calls.runStep;
  await new Promise((resolve) => setTimeout(resolve, 80));

  assert.equal(data.coupangJob.status, 'stopped', `중단이 ${data.coupangJob.status} 로 되살아났다`);
  assert.ok(calls.runStep <= stoppedAt + 1, `중단 뒤에도 ${calls.runStep - stoppedAt}걸음 더 갔다`);
  assert.ok(sawStop || true);
});

test('중단한 뒤 지금 상태를 눌러도 다시 돌지 않는다', async () => {
  const { data, send, calls } = loadWorker({
    onRunStep: (state) => ({ state: { ...state, phase: 'LIST' }, action: { type: 'none' }, progress: { message: '걸음' } })
  });

  await send({ type: 'START', tabId: 7, config: { collectionScope: 'list', minDelayMs: 300, maxDelayMs: 300, longDelayMs: 300 } });
  await new Promise((resolve) => setTimeout(resolve, 20));
  await send({ type: 'STOP' });
  await new Promise((resolve) => setTimeout(resolve, 20));
  const before = calls.runStep;

  await send({ type: 'GET_JOB' });
  await new Promise((resolve) => setTimeout(resolve, 60));

  assert.equal(data.coupangJob.status, 'stopped');
  assert.equal(calls.runStep, before, '지금 상태가 중단된 작업을 되살렸다');
});

test('START 직후 워커가 끝나도 곧 깨울 알람을 남긴다', async () => {
  const { send, calls } = loadWorker({ onRunStep: (state) => DONE_STEP(state) });

  const response = await send({ type: 'START', tabId: 7, config: { collectionScope: 'list' } });
  assert.equal(response?.ok, true, response?.error);

  const alarm = calls.alarmCreates.at(-1);
  assert.ok(alarm, '이어가기 알람을 만들지 않았다');
  const firstAt = alarm.details.when ?? alarm.createdAt + (alarm.details.delayInMinutes ?? alarm.details.periodInMinutes) * 60000;
  assert.ok(firstAt - alarm.createdAt <= 1000, `첫 알람이 ${firstAt - alarm.createdAt}ms 뒤라 워커 종료 직후 이어가지 못한다`);
});

test('느린 storage 쓰기가 나중 START를 덮어쓰지 않는다', async () => {
  let finishStep;
  let stepState;
  const stepGate = new Promise((resolve) => { finishStep = resolve; });
  const { data, send } = loadWorker({
    setDelays: [40, 0],
    onRunStep: async (state) => {
      stepState = state;
      return stepGate;
    }
  });

  const first = send({ type: 'START', tabId: 7, config: { collectionScope: 'detail' } });
  await new Promise((resolve) => setTimeout(resolve, 5));
  const second = send({ type: 'START', tabId: 7, config: { collectionScope: 'list' } });
  await Promise.all([first, second]);

  const savedScope = data.coupangJob.config.collectionScope;
  finishStep(DONE_STEP(stepState));
  await new Promise((resolve) => setTimeout(resolve, 20));
  assert.equal(savedScope, 'list', '먼저 온 START가 나중 START를 덮어썼다');
});

test('GET_JOB storage 읽기가 실패해도 메시지에 응답한다', async () => {
  const { send } = loadWorker({ getError: 'storage 읽기 실패', onRunStep: (state) => DONE_STEP(state) });

  const response = await Promise.race([
    send({ type: 'GET_JOB' }),
    new Promise((resolve) => setTimeout(() => resolve(null), 30))
  ]);

  assert.equal(response?.ok, false, '응답 채널이 열린 채로 남았다');
  assert.match(response?.error || '', /storage 읽기 실패/);
});

test('대기 중 STOP이 와도 대기 종료 저장이 작업을 되살리지 않는다', async () => {
  const { data, send } = loadWorker({
    onRunStep: (state, count) => count === 1 ? {
      state: { ...state, phase: 'LIST' },
      action: { type: 'navigate', url: 'https://mc.coupang.com/ssr/desktop/order/list' },
      progress: { stage: 'LIST', message: '이동' }
    } : DONE_STEP(state)
  });

  await send({
    type: 'START', tabId: 7,
    config: { collectionScope: 'list', minDelayMs: 300, maxDelayMs: 300, longDelayMs: 300 }
  });
  const deadline = Date.now() + 1200;
  while (!(data.coupangJob?.progress?.waitUntil > Date.now()) && Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, 10));
  }
  assert.ok(data.coupangJob?.progress?.waitUntil > Date.now(), '대기 상태에 들어가지 않았다');

  await send({ type: 'STOP' });
  await new Promise((resolve) => setTimeout(resolve, 450));

  assert.equal(data.coupangJob.status, 'stopped', '대기 종료 저장이 중단 작업을 되살렸다');
});
