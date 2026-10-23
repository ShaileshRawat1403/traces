// Read-only walk of docs/acceptance/DEMO_SCRIPT.md against a running Traces app (default: the Traces Lab box app, web 5731 -> API 8731).
// It only issues GETs and no-key explain POSTs (explain writes nothing). Usage: WEB=http://127.0.0.1:5731 node tests/e2e/demo_walk.cjs
const { chromium, devices } = require(require('path').join(__dirname, '..', '..', 'web', 'node_modules', 'playwright'));
const W = process.env.WEB || 'http://127.0.0.1:5731';
const SHOTS = process.env.SHOTS || require('path').join(__dirname, '..', '..', '.traces-data', 'acceptance', 'demo', 'shots');
const F = '/r/github.com__fastapi__full-stack-fastapi-template/s/b1125d8839482cb7bbae603ddc6d0081bf87532e';
const I = '/r/github.com__pallets__itsdangerous/s/672971d66a2ef9f85151e53283113f33d642dabd';
const results = [];
async function step(name, fn) {
  const t0 = Date.now();
  try { await fn(); results.push(['PASS', name, Date.now() - t0]); }
  catch (e) { results.push(['FAIL', name, Date.now() - t0, String(e.message).split('\n')[0].slice(0, 300)]); }
}
async function see(p, texts) {
  for (const t of texts) await p.getByText(t, { exact: false }).first().waitFor({ state: 'visible', timeout: 15000 });
}
(async () => {
  require('fs').mkdirSync(SHOTS, { recursive: true });
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1280, height: 860 } });
  const go = async (u) => { await p.goto(W + u, { waitUntil: 'networkidle' }); };
  await step('1 home lists the indexed repos', async () => {
    await go('/'); await see(p, ['Public GitHub repository URL', 'Add repository', 'fastapi/full-stack-fastapi-template', 'pallets/itsdangerous', 'latest seen @672971d']);
    await p.screenshot({ path: SHOTS + '/01-home.png' });
  });
  await step('2 job page shows phases and opens the snapshot', async () => {
    await go('/jobs/j_d4c00e3c7141453898ef'); await see(p, ['Indexing finished', '100%', 'Fetch', 'Extract', 'Validate', 'History']);
    await p.screenshot({ path: SHOTS + '/02-job.png' });
    await p.getByRole('link', { name: 'Open the snapshot' }).click();
    await p.waitForURL('**' + I);
  });
  await step('3 fsft overview: pinned SHA, layers, static-only banner', async () => {
    await go(F); await see(p, ['@b1125d8', 'Snapshot ready', 'Static analysis only. No runtime behavior has been observed.', 'Architecture, by stored layer', 'frontend/src/client', 'backend/app/api']);
    await p.screenshot({ path: SHOTS + '/03-overview.png', fullPage: false });
  });
  await step('4 graph: components first, rejected never drawn', async () => {
    await go(F + '/graph'); await see(p, ['Architecture graph', '155 nodes, 300 relationships, truncated at 300', 'Rejected claims are never drawn.', '12 rejected']);
    await p.screenshot({ path: SHOTS + '/04-graph.png' });
  });
  await step('5 graph list for create_item, open evidence for depends_on get_db', async () => {
    await go(F + '/graph?q=create_item&view=list');
    const row = p.locator('li').filter({ hasText: 'create_item depends_on get_db' }).first();
    await row.waitFor({ timeout: 15000 });
    await row.getByRole('button', { name: 'Open evidence' }).click();
    await see(p, ['LOCATIONS AT THE PINNED COMMIT', 'backend/app/api/routes/items.py:63', 'lines 60 to 66 of 113', 'Depends(get_db) resolves to backend/app/api/deps.py:21']);
    await p.screenshot({ path: SHOTS + '/05-evidence.png' });
  });
  await step('6 trace: create-item flow with library steps and a gap', async () => {
    await go(F + '/trace'); await see(p, ['From the screen to the persistence path', '10 steps', '2 inferred library steps', '1 gap left open',
      'STEP 1. Items shows AddItem.', 'react-hook-form is not installed', 'operation POST /api/v1/items/ (items-create_item)', 'STEP 10. create_item depends on get_db.', 'Static persistence path']);
    await p.screenshot({ path: SHOTS + '/06-trace.png' });
  });
  await step('6b symbol trace: unresolved calls are a gap and the trace says why it is incomplete (F-9, #38)', async () => {
    await go(F + '/trace?from=read_items'); await see(p, ['From read_items: 3 steps', '1 gaps',
      'Incomplete: this trace has 1 step with calls the trace cannot follow. A gap is not evidence that a call does or does not happen.',
      'API reasons: gaps: 1', 'Gap: calls the trace cannot follow', 'Unresolved calls:',
      'The extractor recorded these calls by name only and did not resolve them to a declaration, so the trace cannot follow them.']);
    if (await p.getByText('Complete: every step is backed by a recorded relationship').count()) throw new Error('trace with unresolved calls says Complete');
    await p.screenshot({ path: SHOTS + '/06b-trace-unresolved.png' });
  });
  await step('7 review: 12 rejected claims incl. the wrong CodeGraph imports and injected negative', async () => {
    await go(F + '/review'); await see(p, ['12 matching claims', "imports 'app' at backend/app/api/routes/login.py:8", 'create_item']);
    await p.screenshot({ path: SHOTS + '/07-review.png' });
  });
  await step('8 history milestones: new-frontend moved to frontend, cites commit', async () => {
    await go(F + '/history?tab=milestones'); await see(p, ['Showing 1 to 8 of 8 records.', 'Move new-frontend to frontend (#652)', 'bulk move 96 files: new-frontend -> frontend', 'Cites commit 9d703df']);
    await p.getByText('Move new-frontend to frontend (#652)').first().scrollIntoViewIfNeeded();
    await p.screenshot({ path: SHOTS + '/08-milestones.png' });
  });
  await step('9 history co-change: pattern, not dependency', async () => {
    await go(F + '/history?tab=cochange&target=backend/app/crud.py'); await see(p, ['It is not evidence of a code dependency', 'changed together in 5 of 26 commits']);
    await p.screenshot({ path: SHOTS + '/09-cochange.png' });
  });
  const ask = async (q, expect, shot) => {
    await go(F + '/ask');
    await p.getByLabel('Question about this snapshot').fill(q);
    await p.getByRole('button', { name: 'Explain (no key needed)' }).click();
    await see(p, expect);
    await p.screenshot({ path: SHOTS + '/' + shot });
    return p.locator('main').innerText();
  };
  // Order check: each phrase must appear after the previous one in the rendered answer.
  const inOrder = (text, phrases) => {
    let at = -1;
    for (const ph of phrases) {
      const i = text.indexOf(ph, at + 1);
      if (i < 0 || i <= at) throw new Error(`out of order or missing: ${ph}`);
      at = i;
    }
  };
  await step('10 ask (no key): rename question answered from history records', async () => {
    const moves = ['History patterns: 3 recorded directory moves involve new-frontend or frontend, ranked by files moved, then top-level directory renames first.',
      'Commit 9d703df25491 moved 96 files from new-frontend/ to frontend/', 'Commit b470f59ce296 moved 7 files', 'Commit e44777f91904 moved 4 files'];
    const text = await ask('When was new-frontend moved to frontend?', moves, '10-ask-history.png');
    inOrder(text, moves); // summary first, then the 96-file move ranked first (O-12)
  });
  await step('11 ask (no key): runtime question marked unknown, with the verified static persistence path (O-13)', async () => {
    await ask('Does create_item write to the database at runtime?', ['Static evidence cannot show runtime behavior, so how this behaves when the code runs is unknown.',
      'create_item has a statically established persistence path through get_db', '(verified)'], '11-ask-runtime.png');
  });
  await step('12 itsdangerous overview: unknown purpose and entry points', async () => {
    await go(I); await see(p, ['@672971d', 'No route nodes or routes_to claims are stored', 'not proof the software has no HTTP routes', 'src/itsdangerous']);
    await p.screenshot({ path: SHOTS + '/12-itsd-overview.png' });
  });
  await step('13 itsdangerous graph: 0 rejected after the F-4/F-5 re-index, unvalidated hidden', async () => {
    await go(I + '/graph'); await see(p, ['Rejected claims are never drawn.', 'Hidden by current filters: 268 (268 inferred (unvalidated)).']);
    if (await p.getByText(/\d+ rejected/).count()) throw new Error('itsdangerous graph still reports rejected claims');
    await p.screenshot({ path: SHOTS + '/13-itsd-graph.png' });
  });
  // phone
  const ctx = await b.newContext({ ...devices['Pixel 7'], viewport: { width: 360, height: 800 } });
  const m = await ctx.newPage();
  await step('14 phone 360: trace, tap Open evidence, drawer shows source', async () => {
    await m.goto(W + F + '/trace', { waitUntil: 'networkidle' });
    await see(m, ['From the screen to the persistence path', 'STEP 1. Items shows AddItem.']);
    await m.getByText('Open evidence').first().tap();
    await see(m, ['frontend/src/routes/_layout/items.tsx']);
    await m.screenshot({ path: SHOTS + '/14-phone-trace-evidence.png' });
  });
  await step('15 phone 360: graph opens with no horizontal page scroll', async () => {
    await m.goto(W + F + '/graph', { waitUntil: 'networkidle' });
    await see(m, ['Architecture graph']);
    const sw = await m.evaluate(() => document.documentElement.scrollWidth);
    if (sw > 361) throw new Error('page scrollWidth ' + sw + ' > 360');
    await m.screenshot({ path: SHOTS + '/15-phone-graph.png' });
  });
  await b.close();
  for (const r of results) console.log(r.join(' | '));
  process.exit(results.some((r) => r[0] === 'FAIL') ? 1 : 0);
})();
