// Real-snapshot browser checks for fastapi/full-stack-fastapi-template@b1125d8: real content, WCAG 2.2 AA axe scan
// (same tags as web/e2e/helpers.ts) on desktop 1280 px and a 360 px touch phone, touch navigation, no sideways scroll.
// Read-only: GETs only. Run by scripts/e2e_ui.sh when TRACES_E2E_SEED=fsft, or by hand:
//   WEB=http://127.0.0.1:5731 node tests/e2e/real_snapshot.cjs
const path = require('path');
const NM = path.join(__dirname, '..', '..', 'web', 'node_modules');
const { chromium } = require(path.join(NM, 'playwright'));
const { default: AxeBuilder } = require(path.join(NM, '@axe-core', 'playwright'));
const W = process.env.WEB || 'http://127.0.0.1:5173';
const SHOTS = process.env.SHOTS || path.join(__dirname, '..', '..', '.traces-data', 'acceptance', 'real-snapshot', 'shots');
const F = '/r/github.com__fastapi__full-stack-fastapi-template/s/b1125d8839482cb7bbae603ddc6d0081bf87532e';
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];

// Screen, URL, text that proves real fsft data is on screen (not an empty or error state).
const SCREENS = [
  ['overview', F, ['@b1125d8', 'Static analysis only. No runtime behavior has been observed.', 'backend/app/api']],
  ['graph', F + '/graph', ['Architecture graph', 'Rejected claims are never drawn.', '12 rejected']],
  ['graph-list', F + '/graph?q=create_item&view=list', ['create_item depends_on get_db']],
  ['trace', F + '/trace', ['From the screen to the persistence path', '10 steps', '1 gap left open', 'Static persistence path']],
  ['review', F + '/review', ['12 matching claims']],
  ['claims', F + '/claims', ['Hidden by current filters: 12 (12 rejected)', 'Open evidence']],
  ['milestones', F + '/history?tab=milestones', ['Move new-frontend to frontend (#652)', 'Cites commit 9d703df']],
  ['cochange', F + '/history?tab=cochange&target=backend/app/crud.py', ['It is not evidence of a code dependency']],
  ['ask', F + '/ask', ['Explain (no key needed)']],
];

const results = [];
async function step(name, fn) {
  const t0 = Date.now();
  try { await fn(); results.push(['PASS', name, Date.now() - t0]); }
  catch (e) { results.push(['FAIL', name, Date.now() - t0, String(e.message).split('\n').slice(0, 6).join(' / ').slice(0, 600)]); }
}
async function see(p, texts) {
  for (const t of texts) await p.getByText(t, { exact: false }).first().waitFor({ state: 'visible', timeout: 15000 });
}
async function axe(p) {
  const r = await new AxeBuilder({ page: p }).withTags(TAGS).analyze();
  const v = r.violations.map((x) => `${x.id} (${x.impact}): ${x.nodes.length} nodes, e.g. ${x.nodes[0] && x.nodes[0].target.join(' ')}`);
  if (v.length) throw new Error('axe: ' + v.join('; '));
}
async function noSideways(p) {
  const [sw, cw] = await p.evaluate(() => [document.documentElement.scrollWidth, document.documentElement.clientWidth]);
  if (sw > cw + 1) throw new Error(`page scrolls sideways: scrollWidth ${sw} > clientWidth ${cw}`);
}

(async () => {
  require('fs').mkdirSync(SHOTS, { recursive: true });
  const b = await chromium.launch();
  const desk = await (await b.newContext({ viewport: { width: 1280, height: 860 } })).newPage();
  const phone = await (await b.newContext({ viewport: { width: 360, height: 800 }, isMobile: true, hasTouch: true, deviceScaleFactor: 3 })).newPage();
  for (const [name, url, texts] of SCREENS) {
    await step(`desktop ${name}: real data + axe`, async () => {
      await desk.goto(W + url, { waitUntil: 'networkidle' }); await see(desk, texts); await axe(desk);
    });
    await step(`360 ${name}: real data + axe + no sideways scroll`, async () => {
      await phone.goto(W + url, { waitUntil: 'networkidle' }); await see(phone, texts); await axe(phone); await noSideways(phone);
      await phone.screenshot({ path: `${SHOTS}/360-${name}.png` });
    });
  }
  await step('360 touch: graph list, tap Open evidence, drawer shows pinned source, axe', async () => {
    await phone.goto(W + F + '/graph?q=create_item&view=list', { waitUntil: 'networkidle' });
    const row = phone.locator('li').filter({ hasText: 'create_item depends_on get_db' }).first();
    await row.waitFor({ timeout: 15000 });
    await row.getByRole('button', { name: 'Open evidence' }).tap();
    await see(phone, ['backend/app/api/routes/items.py:63', 'Depends(get_db) resolves to backend/app/api/deps.py:21']);
    await axe(phone); await noSideways(phone);
    await phone.screenshot({ path: `${SHOTS}/360-touch-evidence.png` });
  });
  await step('360 touch: trace, tap Open evidence on step 1, drawer shows the source file', async () => {
    await phone.goto(W + F + '/trace', { waitUntil: 'networkidle' });
    await see(phone, ['STEP 1. Items shows AddItem.']);
    await phone.getByText('Open evidence').first().tap();
    await see(phone, ['frontend/src/routes/_layout/items.tsx']);
    await axe(phone);
  });
  await step('360 touch: bottom bar navigates from overview to trace', async () => {
    await phone.goto(W + F, { waitUntil: 'networkidle' });
    const nav = phone.getByRole('navigation').last();
    await nav.getByRole('link', { name: /trace/i }).first().tap();
    await phone.waitForURL('**' + F + '/trace');
    await see(phone, ['From the screen to the persistence path']);
  });
  await b.close();
  for (const r of results) console.log(r.join(' | '));
  const fails = results.filter((r) => r[0] === 'FAIL').length;
  console.log(`real-snapshot checks: ${results.length - fails} passed, ${fails} failed`);
  process.exit(fails ? 1 : 0);
})();
