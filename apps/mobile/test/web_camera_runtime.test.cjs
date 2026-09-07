const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const web = path.join(__dirname, '../web');

async function camera(mode) {
  let now = 1000;
  let worker;
  let strokes = 0;
  const shadowValues = [];
  const paint = new Proxy({}, {
    get: (_, key) => key === 'stroke' ? () => strokes++ : () => {},
    set: (_, key, value) => {
      if (key === 'shadowBlur') shadowValues.push(value);
      return true;
    },
  });
  const canvas = { clientWidth: 360, clientHeight: 640,
    getContext: () => paint };
  const video = { videoWidth: 640, videoHeight: 480, style: {},
    addEventListener() {}, play: async () => {},
    requestVideoFrameCallback: () => 1, cancelVideoFrameCallback() {} };
  const window = { addEventListener() {} };
  const context = vm.createContext({ window, URL, console,
    performance: { now: () => now, timeOrigin: 100000 },
    createImageBitmap: async () => ({ close() {} }),
    document: { baseURI: 'https://example.test/',
      body: { contains: () => true },
      getElementById: id => id === 'mediapipe-video-source' ? video : canvas },
    navigator: { mediaDevices: { getUserMedia: async () => ({
      getTracks: () => [{ stop() {} }],
    }) } },
    Worker: class {
      constructor() { worker = this; }
      postMessage(message) {
        if (message.type === 'init') {
          this.onmessage({ data: { type: 'ready', delegate: 'CPU' } });
        }
      }
      terminate() {}
    },
  });
  const html = fs.readFileSync(path.join(web, 'index.html'), 'utf8');
  vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1], context);
  const bridge = window.sinalizaAiMediaPipe;
  bridge.init();
  bridge.setCaptureMode(mode);
  await bridge.start();
  const hands = [Array.from({ length: 21 }, (_, i) => ({
    x: 0.3 + i * 0.01, y: 0.4, z: 0,
  }))];
  async function result(latency) {
    now += latency;
    await worker.onmessage({ data: {
      type: 'result', sessionId: 1, timestampMs: now - latency,
      inferenceLatencyMs: latency, landmarks: hands,
      handedness: [[{ label: 'Right', score: 1 }]],
      faceDetected: true, poseDetected: true,
      poseLandmarks: Array.from({ length: 13 }, () => ({ x: 0.5, y: 0.5, z: 0 })),
      expression: { mouth_open: 0.1, mouth_width: 0.3, left_brow: 0, right_brow: 0 },
    } });
  }
  return { bridge, result, hands, shadowValues, strokes: () => strokes };
}

test('holistic uses its own pressure threshold and still backs off under load', async () => {
  const c = await camera('holistic');
  for (let i = 0; i < 5; i++) await c.result(120);
  assert.equal(c.bridge.performanceMode, 'balanced');
  for (let i = 0; i < 3; i++) await c.result(200);
  assert.equal(c.bridge.performanceMode, 'reduced');
  for (let i = 0; i < 45; i++) await c.result(120);
  assert.equal(c.bridge.performanceMode, 'balanced');
  c.bridge.stop();
});

test('hand-only mode retains its lower pressure threshold', async () => {
  const c = await camera('hands');
  for (let i = 0; i < 3; i++) await c.result(100);
  assert.equal(c.bridge.performanceMode, 'reduced');
  c.bridge.stop();
});

test('overlay draws only current skeleton without trails or blur; data stays intact', async () => {
  const c = await camera('holistic');
  await c.result(80);
  await c.result(80);
  assert.equal(c.strokes(), 2);
  assert.ok(c.shadowValues.every(value => value === 0));
  assert.equal(c.bridge.landmarkRevision, 2);
  assert.equal(JSON.stringify(c.bridge.latestHolisticFrame.hands[0].landmarks),
    JSON.stringify(c.hands[0]));
  c.bridge.stop();
  assert.equal(c.bridge.latestHolisticFrame, null);
});

test('worker reports elapsed inference time after running the model', async () => {
  let now = 0;
  let closed = false;
  const messages = [];
  const self = { postMessage: message => messages.push(message) };
  const context = vm.createContext({ self, console,
    performance: { now: () => now },
    importScripts() {
      self.exports = {
        FilesetResolver: { forVisionTasks: async () => ({}) },
        HolisticLandmarker: { createFromOptions: async () => ({
          detectForVideo() { now += 37; return {}; },
        }) },
      };
    },
  });
  vm.runInContext(fs.readFileSync(path.join(web, 'mediapipe-holistic-worker.js'), 'utf8'), context);
  await self.onmessage({ data: { type: 'init' } });
  await self.onmessage({ data: { type: 'frame', timestampMs: 1000, sessionId: 1,
    bitmap: { close() { closed = true; } } } });
  assert.equal(messages.at(-1).inferenceLatencyMs, 37);
  assert.equal(closed, true);
});
