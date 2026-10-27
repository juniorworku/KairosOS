/** Real Chromium lifecycle checks against a controlled loopback API, not a live account. */
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { mkdtemp, cp, readFile, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { createRequire } from 'node:module';
import { setTimeout as delay } from 'node:timers/promises';

const require = createRequire(new URL('../../web/package.json', import.meta.url));
const { chromium } = require('@playwright/test');
const EMPTY = { active_session: null, blocklist: [], ends_at: null };
let focus = EMPTY;
let offline = false;
let probeHits = 0;
const observed = [];
const server = createServer(async (request, response) => {
  if (request.url === '/probe') {
    probeHits += 1;
    response.writeHead(200, { 'Content-Type': 'text/plain' });
    response.end('local distraction test page');
    return;
  }
  response.setHeader('Content-Type', 'application/json');
  if (offline) {
    response.writeHead(503);
    response.end('{"error":"controlled test outage"}');
    return;
  }
  if (request.headers.authorization !== 'Bearer lifecycle-test-token') {
    response.writeHead(401);
    response.end('{"error":"test token required"}');
    return;
  }
  let raw = '';
  for await (const chunk of request) raw += chunk;
  const body = raw ? JSON.parse(raw) : {};
  if (request.url === '/api/v1/ext/state') {
    response.end(JSON.stringify(focus));
    return;
  }
  if (request.url === '/api/v1/ext/event') {
    observed.push({ path: 'event', ...body });
    if (body.type === 'pause' && body.session_id === focus.active_session?.id) {
      focus = { ...focus, pause_until: body.pause_until };
    }
    response.end('{"status":"recorded"}');
    return;
  }
  if (request.url === '/api/v1/ext/end') {
    observed.push({ path: 'end', ...body });
    if (body.session_id === focus.active_session?.id) focus = EMPTY;
    response.end('{"status":"ended"}');
    return;
  }
  response.writeHead(404);
  response.end('{}');
});
await new Promise((accept) => server.listen(0, '127.0.0.1', accept));
const { port } = server.address();
const apiBase = `http://127.0.0.1:${port}`;
const temp = await mkdtemp(join(tmpdir(), 'kairos-extension-lifecycle-'));
const extensionPath = join(temp, 'extension');
let context;

async function eventually(check, label, timeout = 10000) {
  const deadline = Date.now() + timeout;
  let error;
  while (Date.now() < deadline) {
    try {
      if (await check()) return;
    } catch (caught) {
      error = caught;
    }
    await delay(100);
  }
  throw new Error(`${label} did not complete within ${timeout}ms`, { cause: error });
}
function session(id, seconds = 90) {
  return {
    active_session: { id, title: 'Lifecycle test session' },
    blocklist: ['distraction.test'],
    ends_at: new Date(Date.now() + seconds * 1000).toISOString(),
  };
}

try {
  await cp(resolve('dist'), extensionPath, { recursive: true });
  const manifestPath = join(extensionPath, 'manifest.json');
  const manifest = JSON.parse(await readFile(manifestPath, 'utf8'));
  // The tested source/build is unchanged. Only a fixture API origin is granted in this temp copy.
  manifest.host_permissions = [...manifest.host_permissions, `${apiBase}/*`];
  await writeFile(manifestPath, JSON.stringify(manifest));
  const launchOptions = {
    channel: 'chromium',
    headless: true,
    executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || chromium.executablePath(),
    args: [
      `--disable-extensions-except=${extensionPath}`,
      `--load-extension=${extensionPath}`,
      '--host-resolver-rules=MAP distraction.test 127.0.0.1',
      '--no-proxy-server',
    ],
  };
  context = await chromium.launchPersistentContext(join(temp, 'profile'), launchOptions);
  let worker = context.serviceWorkers()[0] || await context.waitForEvent('serviceworker');
  const extensionId = new URL(worker.url()).hostname;
  await worker.evaluate(async ({ apiBase }) => {
    await chrome.storage.local.set({ apiBase, token: 'lifecycle-test-token' });
  }, { apiBase });
  let control = await context.newPage();
  await control.goto(`chrome-extension://${extensionId}/popup.html`);
  const rules = () => control.evaluate(() => chrome.declarativeNetRequest.getDynamicRules());
  const sync = () => control.evaluate(() => chrome.runtime.sendMessage({ type: 'SYNC' }));

  focus = session('native-block');
  await sync();
  await eventually(async () => (await rules()).length === 1, 'Native DNR rule installation');
  assert.equal((await rules())[0].action.type, 'block');
  assert.deepEqual((await rules())[0].condition.resourceTypes, ['main_frame']);
  let navigation = await context.newPage();
  const beforeBlock = probeHits;
  let blocked = false;
  try {
    await navigation.goto(`http://distraction.test:${port}/probe`, { timeout: 5000 });
  } catch (error) {
    blocked = String(error).includes('ERR_BLOCKED_BY_CLIENT');
  }
  assert.equal(blocked, true, 'Chrome must reject navigation using its native DNR block action');
  assert.equal(probeHits, beforeBlock, 'Blocked navigation must not reach the loopback server');
  console.log('PASS native navigation blocking');

  // Closing Chromium actually terminates the extension worker. Reopen the same profile,
  // rather than relying on CDP idle-stop semantics while Playwright's debugger is attached.
  await context.close();
  context = await chromium.launchPersistentContext(join(temp, 'profile'), launchOptions);
  worker = context.serviceWorkers()[0] || await context.waitForEvent('serviceworker');
  assert.equal(new URL(worker.url()).hostname, extensionId);
  control = await context.newPage();
  await control.goto(`chrome-extension://${extensionId}/popup.html`);
  navigation = await context.newPage();
  await sync();
  await eventually(async () => (await rules()).length === 1, 'Restarted worker rule recovery');
  const storedAfterRestart = await control.evaluate(() => chrome.storage.local.get('focusState'));
  assert.equal(storedAfterRestart.focusState.active_session.id, 'native-block');
  console.log('PASS Chromium/extension-worker restart and persistent state recovery');

  focus = session('alarm-expiry', 3);
  await sync();
  await eventually(async () => (await rules()).length === 1, 'Deadline rule installation');
  offline = true;
  await eventually(async () => (await rules()).length === 0, 'Offline Chrome alarm expiry', 15000);
  await navigation.goto(`http://distraction.test:${port}/probe`);
  assert.equal(await navigation.textContent('body'), 'local distraction test page');
  console.log('PASS native alarm expiry during API outage');

  offline = false;
  focus = session('offline-pause');
  await sync();
  await eventually(async () => (await rules()).length === 1, 'Pause session installation');
  offline = true;
  await control.getByRole('button', { name: 'Pause blocking for 5 minutes' }).click();
  await eventually(async () => (await rules()).length === 0, 'Local offline pause', 2000);
  const paused = await control.evaluate(() => chrome.storage.local.get(['pendingEvents', 'localPauseUntil']));
  assert.ok(Date.parse(paused.localPauseUntil) > Date.now());
  assert.ok(paused.pendingEvents.some((event) => event.kind === 'pause' && event.sessionId === 'offline-pause'));
  console.log('PASS local pause removes actual rules without API');

  offline = false;
  focus = session('offline-end');
  await sync();
  await eventually(async () => (await rules()).length === 1, 'End session installation');
  offline = true;
  await control.getByRole('button', { name: 'End session', exact: true }).click();
  await eventually(async () => (await rules()).length === 0, 'Local offline end', 2000);
  const ended = await control.evaluate(() => chrome.storage.local.get(['pendingEvents', 'locallyEndedSession']));
  assert.equal(ended.locallyEndedSession, 'offline-end');
  assert.ok(ended.pendingEvents.some((event) => event.kind === 'end' && event.sessionId === 'offline-end' && event.endedAt));
  offline = false;
  await sync();
  await eventually(async () => {
    const stored = await control.evaluate(() => chrome.storage.local.get('pendingEvents'));
    return stored.pendingEvents.length === 0;
  }, 'Session-bound replay');
  assert.ok(observed.some((event) => event.path === 'end' && event.session_id === 'offline-end' && event.ended_at));
  assert.equal((await rules()).length, 0);
  console.log('PASS local end and safe replay after reconnection');
  console.log('5 Chromium lifecycle checks passed against a controlled loopback API.');
} finally {
  await context?.close();
  server.closeAllConnections();
  await new Promise((accept) => server.close(accept));
  await rm(temp, { recursive: true, force: true });
}
