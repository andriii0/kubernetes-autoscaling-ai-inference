const {test, before, after, beforeEach, afterEach} = require('node:test');
const assert = require('node:assert/strict');
const {spawn} = require('node:child_process');
const {once} = require('node:events');
const fs = require('node:fs/promises');
const path = require('node:path');
const readline = require('node:readline');
const {chromium} = require('playwright');

let server, serverExit, browser, context, page, url, root, errors;
const series = 'main/example';
const first = `${series}/attempt-01-fixed-1-burst`;
const second = `${series}/attempt-02-fixed-1-burst`;

test('custom metrics folder shows its description and preserved failed attempt', {timeout: 15000}, async () => {
  await page.locator('#results-tab').click();
  await page.locator('[data-group="Custom metrics"]').click();
  await page.locator('#preview .result-notes textarea').waitFor({state: 'attached'});
  await page.waitForFunction(() => document.querySelector('#preview textarea')?.value.includes('Active client'));
  assert.equal(await page.locator('#preview summary').innerText(), 'About this folder');
  assert.match(await page.locator('#preview textarea').inputValue(), /Envoy/);
  await page.locator('[data-id="custom-metric/comparison-example"]').click();
  assert.match(await page.locator('.series-summary').innerText(), /0 \/ 6/);
  for (const cell of await page.locator('.policy-comparison td').all()) {
    assert.equal(await cell.innerText(), '—', 'Absent accepted measurements are not zero');
  }
  await page.locator('.attempt[data-id="custom-metric/comparison-example/attempt-01-cpu"]').click();
  await page.waitForFunction(() => document.querySelector('#preview textarea')?.value.includes('clock check'));
  assert.match(await page.locator('#preview').innerText(), /Invalid collection/);
  assert.equal(await page.locator('[data-group="Custom metrics"]').getAttribute('aria-pressed'), 'true');
});

before(async () => {
  server = spawn(process.env.UI_TEST_PYTHON || 'python', ['-B', path.join(__dirname, 'fixture.py')], {
    stdio: ['pipe', 'pipe', 'pipe'],
  });
  serverExit = once(server, 'exit');
  let stderr = '';
  server.stderr.on('data', value => { stderr += value; });
  const lines = readline.createInterface({input: server.stdout});
  const ready = once(lines, 'line').then(([line]) => JSON.parse(line));
  const timer = setTimeout(() => server.kill(), 15000);
  try {
    ({url, root} = await Promise.race([
      ready,
      serverExit.then(([code]) => { throw new Error(`Fixture exited ${code}: ${stderr}`); }),
    ]));
  } finally {
    clearTimeout(timer);
    lines.close();
  }
  browser = await chromium.launch({headless: true, channel: process.env.UI_TEST_CHANNEL || undefined});
});

after(async () => {
  try {
    if (browser) await browser.close();
  } finally {
    if (server) {
      server.stdin.end();
      const timer = setTimeout(() => server.kill(), 5000);
      try { await serverExit; } finally { clearTimeout(timer); }
    }
  }
});

beforeEach(async () => {
  context = await browser.newContext({viewport: {width: 1280, height: 800}});
  // Only this temporary server is reachable from the page.
  await context.route('**/*', route => route.request().url().startsWith(`${url}/`)
    ? route.continue() : route.abort());
  page = await context.newPage();
  page.setDefaultTimeout(5000);
  errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(url);
  await page.waitForFunction(() => !document.getElementById('pilot').disabled);
});

afterEach(async () => {
  await context.close();
  assert.deepEqual(errors, [], 'No unhandled browser JavaScript errors');
});

async function select(id) {
  await page.goto(`${url}/#${encodeURIComponent(id)}`);
  await page.locator('#preview .result-notes textarea').waitFor({state: 'attached'});
  await page.waitForFunction(() => document.querySelector('#preview textarea')?.disabled === false);
}

test('completed series opens results; target miss differs from data failure', {timeout: 15000}, async () => {
  let launches = 0;
  page.on('request', request => { if (request.url().endsWith('/api/launch')) launches++; });
  await page.locator('#series').click();
  await page.locator('#results-page').waitFor({state: 'visible'});
  await page.locator('#preview .series-summary').waitFor();
  assert.match(await page.locator('#preview').innerText(), /18 \/ 18/);
  await page.locator(`#preview [data-id="${first}"]`).click();
  await page.locator('#preview .data-note').waitFor();
  assert.match(await page.locator('#preview').innerText(), /Target missed/);
  assert.match(await page.locator('#preview').innerText(), /Valid collection/);
  assert.match(await page.locator('#preview').innerText(), /6\.000 s/);
  await page.locator('#runs-tab').click();
  await page.locator('#results-tab').click();
  assert.match(await page.locator('#breadcrumb').innerText(), /attempt-01/);
  await page.locator('#back').click();
  await page.locator('#preview .series-summary').waitFor();
  await page.locator('[data-group="Pilots"]').click();
  await page.locator('#preview .data-note').waitFor();
  assert.match(await page.locator('#preview').innerText(), /Data failure/);
  assert.match(await page.locator('#preview').innerText(), /Invalid collection/);
  assert.equal(launches, 0);
});

test('notes save literal text, retain drafts, and preserve disk content after a conflict', {timeout: 15000}, async () => {
  await select(first);
  const panel = page.locator('.result-notes');
  await panel.locator('summary').click();
  const text = 'Log recovery — перевірка <script>window.injected=true</script>';
  await panel.locator('textarea').fill(text);
  await panel.getByRole('button', {name: 'Save notes'}).click();
  await page.waitForFunction(() => document.querySelector('.result-notes [role=status]').textContent === 'Saved');
  const notePath = path.join(root, 'results', first, 'notes.md');
  assert.equal(await fs.readFile(notePath, 'utf8'), text);
  await page.reload();
  await page.waitForFunction(() => document.querySelector('.result-notes textarea')?.disabled === false);
  assert.equal(await panel.locator('textarea').inputValue(), text);
  assert.equal(await page.evaluate(() => window.injected), undefined);
  await panel.locator('textarea').fill('local draft');
  await page.locator('#runs-tab').click();
  await page.locator('#results-tab').click();
  await page.locator(`#entries [data-id="${second}"]`).click();
  await page.waitForFunction(() => document.querySelector('#preview h3')?.textContent === 'Attempt 02');
  await page.locator(`#entries [data-id="${first}"]`).click();
  await page.waitForFunction(() => document.querySelector('.result-notes textarea')?.value === 'local draft');
  const previousInput = await panel.locator('textarea').elementHandle();
  await page.locator('#refresh').click();
  await page.waitForFunction(element => !element.isConnected, previousInput);
  await page.waitForFunction(() => document.querySelector('.result-notes textarea')?.value === 'local draft');
  await fs.writeFile(notePath, 'external edit');
  await panel.getByRole('button', {name: 'Save notes'}).click();
  await page.waitForFunction(() => document.querySelector('.result-notes [role=status]')?.textContent.includes('changed on disk'));
  assert.equal(await panel.locator('textarea').inputValue(), 'local draft');
  assert.equal(await fs.readFile(notePath, 'utf8'), 'external edit');
});

test('pilot form rejects invalid rates, displays launch failure and allows a dry retry', {timeout: 15000}, async () => {
  let launches = 0;
  let payload;
  await page.route('**/api/launch', async route => {
    launches++;
    payload = route.request().postDataJSON();
    if (launches === 1) {
      await route.fulfill({status: 400, contentType: 'application/json', body: '{"error":"Launch unavailable"}'});
    } else await route.continue();
  });
  await page.locator('#pilot').click();
  await page.locator('#pilot-mode').selectOption('autoscaling');
  assert.equal(await page.locator('#pilot-profile').inputValue(), 'burst');
  assert.equal(await page.locator('#pilot-duration').isDisabled(), true);
  await page.locator('#pilot-rate').fill('1');
  await page.locator('#start-pilot').click();
  assert.equal(await page.locator('#pilot-form').evaluate(form => form.checkValidity()), false);
  assert.equal(launches, 0);
  await page.locator('#pilot-rate').fill('12');
  await page.locator('#start-pilot').click();
  await page.locator('#pilot-error').waitFor({state: 'visible'});
  assert.equal(await page.locator('#pilot-error').innerText(), 'Launch unavailable');
  assert.equal(await page.locator('#pilot-rate').inputValue(), '12');
  await page.locator('#start-pilot').click();
  await page.locator('#pilot-dialog').waitFor({state: 'hidden'});
  await page.waitForFunction(() => document.getElementById('phase').textContent === 'Dry run passed');
  assert.equal(launches, 2);
  assert.equal(payload.dry_run, true);
  assert.deepEqual(payload.pilot, {mode: 'autoscaling', profile: 'burst', rate: 12, low_rate: 2, slo_ms: 5000});
  assert.match(await page.locator('#command-output').textContent(), /--dry-run/);
});

test('late detail response cannot replace the newly selected run', {timeout: 15000}, async () => {
  await select(first);
  let release, started;
  const waiting = new Promise(resolve => { started = resolve; });
  const gate = new Promise(resolve => { release = resolve; });
  await page.route('**/api/detail?*', async route => {
    if (new URL(route.request().url()).searchParams.get('id') === first) {
      const response = await route.fetch();
      started();
      await gate;
      await route.fulfill({response});
    } else await route.continue();
  });
  await page.locator(`#entries [data-id="${first}"]`).click();
  await waiting;
  await page.locator(`#entries [data-id="${second}"]`).click();
  await page.waitForFunction(() => document.querySelector('#preview h3')?.textContent === 'Attempt 02');
  const completed = page.waitForResponse(response => new URL(response.url()).searchParams.get('id') === first);
  release();
  await completed;
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  assert.equal(await page.locator('#preview h3').innerText(), 'Attempt 02');
});

test('lost status connection disables launch and shows a readable error', {timeout: 15000}, async () => {
  await page.route('**/api/status', route => route.fulfill({
    status: 503, contentType: 'application/json', body: '{"error":"Server unavailable"}',
  }));
  await page.locator('#results-tab').click();
  await page.locator('#refresh').click();
  await page.waitForFunction(() => document.getElementById('notice').textContent.includes('Connection lost'));
  assert.equal(await page.locator('#pilot').isDisabled(), true);
  assert.match(await page.locator('#notice').innerText(), /Server unavailable/);
});

test('comparison separates policies and counts only accepted runs', {timeout: 15000}, async () => {
  await select('custom-metric/comparison-complete');
  assert.match(await page.locator('.preview-subtitle').innerText(), /CPU \/ request HPA/);
  const cpu = page.locator('.policy-comparison [data-policy="cpu"]');
  const custom = page.locator('.policy-comparison [data-policy="active-1"]');
  assert.match(await cpu.innerText(), /16\.0% \(173 \/ 1,080\)/);
  assert.match(await cpu.innerText(), /194/);
  assert.match(await cpu.innerText(), /28\.322 s – 28\.912 s/);
  assert.match(await cpu.innerText(), /0 \/ 3/);
  assert.match(await custom.innerText(), /83\.6% \(903 \/ 1,080\)/);
  assert.match(await custom.innerText(), /4\.820 s – 11\.361 s/);
  assert.match(await custom.innerText(), /1 \/ 3/);
  assert.match(await custom.locator('td').nth(1).innerText(), /^0$/);
  assert.match(await page.locator('.attempt[data-id$="attempt-05-cpu"]').innerText(), /original/);
  assert.match(await page.locator('.attempt[data-id$="attempt-05-cpu"]').innerText(), /Data failure/);
  await page.locator('.attempt[data-id$="attempt-02-active-1"]').click();
  await page.locator('.data-note').waitFor();
  assert.match(await page.locator('.preview-subtitle').innerText(), /Request HPA · target 1/);
  assert.match(await page.locator('#entries [data-id$="attempt-01-cpu"]').innerText(), /CPU HPA/);
  assert.match(await page.locator('#entries [data-id$="attempt-02-active-1"]').innerText(), /Request HPA/);
});

test('pending collection remains unverified and does not claim live activity', {timeout: 15000}, async () => {
  await select('custom-metric/preparation-pending/target-2');
  const preview = await page.locator('#preview').innerText();
  assert.match(preview, /Incomplete/);
  assert.match(preview, /Collection not verified/);
  assert.match(preview, /Request HPA · target 2/);
  assert.doesNotMatch(preview, /Data failure|Invalid collection|Running/);
});

test('preparation exposes parent cycle notes without copying them into its draft', {timeout: 15000}, async () => {
  const id = 'custom-metric/series-stopped/preparation-new';
  await select(id);
  await page.locator('.parent-note').waitFor();
  assert.match(await page.locator('.parent-note').innerText(), /target 2 stopped on a clock difference/);
  assert.match(await page.locator('.parent-note').innerText(), /<script>literal<\/script>/);
  assert.equal(await page.locator('.parent-note script').count(), 0);
  assert.equal(await page.locator('.result-notes textarea').inputValue(), '');
  assert.equal(await page.locator('.result-notes').getAttribute('open'), '');
  await page.locator('.result-notes textarea').fill('Local preparation note');
  await page.getByRole('button', {name: 'Save notes', exact: true}).click();
  await page.waitForFunction(() => document.querySelector('.result-notes [role=status]').textContent === 'Saved');
  assert.equal(await fs.readFile(path.join(root, 'results', id, 'notes.md'), 'utf8'), 'Local preparation note');
  assert.match(await fs.readFile(path.join(root, 'results/custom-metric/series-stopped/notes.md'), 'utf8'), /target 2 stopped/);
});
