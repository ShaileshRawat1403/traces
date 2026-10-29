// G-5 acceptance: BYOK chat against a local stub provider, on a running Traces app with the real fsft@b1125d8 snapshot.
// Read-only towards Traces: GETs, chat/bundle and explain POSTs (they write nothing). The stub runs in this process on
// 127.0.0.1 and never calls a real or paid API. The key is a random throwaway made for this run.
//   WEB=http://127.0.0.1:5731 API_LOGS=/tmp/box_api.log,/tmp/box_web.log STORE=/path/traces.sqlite3 node tests/e2e/chat_g5.cjs
const path = require('path');
const http = require('http');
const crypto = require('crypto');
const fs = require('fs');
const { chromium } = require(path.join(__dirname, '..', '..', 'web', 'node_modules', 'playwright'));
const W = process.env.WEB || 'http://127.0.0.1:5173';
const SHOTS = process.env.SHOTS || path.join(__dirname, '..', '..', '.traces-data', 'acceptance', 'g5', 'shots');
const REPO = 'github.com__fastapi__full-stack-fastapi-template';
const SHA = 'b1125d8839482cb7bbae603ddc6d0081bf87532e';
const F = `/r/${REPO}/s/${SHA}`;
const API = `${W}/api/v1/repos/${REPO}/snapshots/${SHA}`;
const KEY = 'sk-lab-g5-' + crypto.randomBytes(12).toString('hex');
const FORGED = 'c_' + 'e'.repeat(64);
const sha256 = (t) => crypto.createHash('sha256').update(t, 'utf8').digest('hex');
const results = [];
async function step(name, fn) {
  const t0 = Date.now();
  try { const note = await fn(); results.push(['PASS', name, Date.now() - t0, note || '']); }
  catch (e) { results.push(['FAIL', name, Date.now() - t0, String(e.message).split('\n').slice(0, 4).join(' / ').slice(0, 500)]); }
}
const must = (c, m) => { if (!c) throw new Error(m); };

function startStub() {
  const requests = [];
  const CORS = { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'POST, OPTIONS', 'Access-Control-Allow-Headers': 'content-type, authorization, x-api-key, anthropic-version, anthropic-dangerous-direct-browser-access' };
  const srv = http.createServer((req, res) => {
    let body = '';
    req.on('data', (c) => (body += c));
    req.on('end', () => {
      requests.push({ method: req.method, path: req.url, headers: req.headers, body });
      if (req.method === 'OPTIONS') return res.writeHead(204, CORS).end();
      let content = 'unknown';
      try {
        const p = JSON.parse(body).messages[0].content;
        const id = /^\[(c_[0-9a-f]+)\]/m.exec(p.split('<evidence>\n')[1] || '');
        content = req.url.includes('ungrounded') ? 'It probably stores items somewhere, but I cannot say where.'
          : `The evidence records this [${id ? id[1] : 'none'}]. A second claim [${FORGED}] is cited too.`;
      } catch { /* shape error answer */ }
      res.writeHead(200, { ...CORS, 'Content-Type': 'application/json' }).end(JSON.stringify({ choices: [{ message: { role: 'assistant', content } }] }));
    });
  });
  return new Promise((r) => srv.listen(0, '127.0.0.1', () => r({ url: `http://127.0.0.1:${srv.address().port}`, requests, close: () => srv.close() })));
}

/** Parse a traces-bundle/1 prompt into its parts. */
function parsePrompt(p) {
  const [instr, rest] = p.split('\n\n<evidence>\n');
  const [ev, q] = rest.split('\n</evidence>\n\n<question>\n');
  const lines = ev ? ev.split('\n').filter(Boolean) : [];
  const items = lines.map((l) => { const m = /^\[(c_[0-9a-f]+)\] \(([^,]+), (.*?)\) (.*)$/.exec(l); return m ? { id: m[1], label: m[2], where: m[3], statement: m[4], line: l } : { bad: l }; });
  return { instructions: instr, items, question: q.replace(/\n<\/question>$/, '') };
}

/** Every outbound byte the manifest promises, and nothing else: ids, hashes of the exact evidence lines, instructions, question. */
function checkManifest(prompt, manifest) {
  const p = parsePrompt(prompt);
  must(!p.items.some((i) => i.bad), 'unparsable evidence line');
  const rows = manifest.filter((m) => m.kind === 'claim_statement');
  const sentIds = p.items.map((i) => i.id);
  must(JSON.stringify(sentIds) === JSON.stringify(rows.map((r) => r.claim_id)), `ids differ: sent ${sentIds.length}, manifest ${rows.length}`);
  p.items.forEach((it, i) => must(sha256(it.line) === rows[i].sha256 && [...it.line].length === rows[i].chars, `line hash differs for ${it.id}`));
  const ins = manifest.find((m) => m.kind === 'instructions'); const q = manifest.find((m) => m.kind === 'question');
  must(ins && sha256(p.instructions) === ins.sha256, 'instructions hash differs');
  must(q && sha256(p.question) === q.sha256, 'question hash differs');
  const other = manifest.filter((m) => !['claim_statement', 'instructions', 'question'].includes(m.kind));
  must(other.length === 0, `manifest has kinds not in the prompt: ${other.map((m) => m.kind)}`);
  return `${rows.length} evidence lines + instructions + question match by sha256`;
}

(async () => {
  fs.mkdirSync(SHOTS, { recursive: true });
  const stub = await startStub();
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  const traffic = []; // everything between the browser and the Traces app
  page.on('request', (r) => { if (r.url().startsWith(W)) traffic.push(JSON.stringify({ u: r.url(), h: r.headers(), b: r.postData() })); });
  page.on('response', async (r) => { if (r.url().startsWith(W + '/api/')) { try { traffic.push(await r.text()); } catch { /* redirects */ } } });
  page.on('console', (m) => traffic.push('console: ' + m.text()));
  const posts = () => stub.requests.filter((r) => r.method === 'POST');
  const openDialog = async (q) => {
    await page.goto(W + F + '/ask?mode=chat', { waitUntil: 'networkidle' });
    await page.getByLabel('Message').fill(q);
    const bundle = page.waitForResponse((r) => r.url().endsWith('/chat/bundle'));
    await page.getByRole('button', { name: 'Review what will be sent' }).click();
    const json = await (await bundle).json();
    await page.getByTestId('consent-dialog').waitFor({ timeout: 15000 });
    return json;
  };

  await step('no provider: the chat says so and shows no fake chat', async () => {
    await page.goto(W + F + '/ask?mode=chat', { waitUntil: 'networkidle' });
    await page.getByTestId('chat-setup').waitFor();
    must((await page.getByTestId('chat-message').count()) === 0, 'a chat message is shown without a provider');
    return (await page.getByTestId('chat-setup').innerText()).slice(0, 120);
  });
  await step('settings: key saved for the session only, field cleared, not in localStorage', async () => {
    await page.goto(W + '/settings', { waitUntil: 'networkidle' });
    await page.getByLabel('Base URL').fill(`${stub.url}/cors/v1`);
    await page.getByLabel('Model', { exact: true }).fill('stub-model');
    await page.getByLabel('API key').fill(KEY);
    await page.getByRole('button', { name: 'Save provider' }).click();
    await page.getByTestId('provider-status').waitFor();
    must((await page.getByLabel('API key').inputValue()) === '', 'key field not cleared');
    const ls = await page.evaluate(() => JSON.stringify(localStorage)); const ss = await page.evaluate(() => JSON.stringify(sessionStorage));
    must(!ls.includes(KEY), 'key in localStorage'); must(ss.includes(KEY), 'expected the key in sessionStorage (session-only design)');
    return 'key only in sessionStorage (plain text, by design): ' + (await page.getByTestId('provider-status').innerText()).slice(0, 90);
  });
  let bundle1;
  await step('consent dialog appears before anything is sent; it shows no key', async () => {
    bundle1 = await openDialog('What does create_item depend on?');
    must(posts().length === 0, 'stub got a request before consent');
    const d = page.getByTestId('consent-dialog');
    must(!(await d.innerText()).includes(KEY), 'key shown in the dialog');
    must((await d.getByTestId('consent-url').innerText()).trim() === `${stub.url}/cors/v1/chat/completions`, 'wrong consent url');
    const items = await d.getByTestId('consent-item').count(); const rows = await d.getByTestId('consent-manifest-row').count();
    must(items === bundle1.prompt_bundle.evidence.length, `dialog items ${items} != bundle ${bundle1.prompt_bundle.evidence.length}`);
    must(rows === bundle1.outbound_manifest.length, `manifest rows ${rows} != ${bundle1.outbound_manifest.length}`);
    await page.screenshot({ path: SHOTS + '/consent.png', fullPage: true });
    return `${items} evidence items, ${rows} manifest rows shown`;
  });
  await step('declining (Cancel) sends nothing and records nothing', async () => {
    await page.getByRole('button', { name: 'Cancel, send nothing' }).click();
    await page.getByTestId('consent-dialog').waitFor({ state: 'detached' });
    await page.waitForTimeout(1500);
    must(posts().length === 0, 'stub got a request after cancel');
    must((await page.evaluate(() => localStorage.getItem('traces.chat.sent'))) === null, 'sent record written');
  });
  await step('declining (Escape) sends nothing', async () => {
    await openDialog('What does create_item depend on?');
    await page.keyboard.press('Escape');
    await page.getByTestId('consent-dialog').waitFor({ state: 'detached' });
    await page.waitForTimeout(1500);
    must(posts().length === 0, 'stub got a request after Escape');
  });
  await step('send: the stub receives exactly the server prompt, and it matches the outbound manifest', async () => {
    const bun = await openDialog('What does create_item depend on?');
    await page.getByTestId('consent-dialog').getByRole('button', { name: /^Send to 127\.0\.0\.1/ }).click();
    await page.getByTestId('grounding').waitFor({ timeout: 15000 });
    const p = posts(); must(p.length === 1, `stub POSTs ${p.length}`);
    const body = JSON.parse(p[0].body);
    must(body.messages.length === 1 && body.messages[0].content === bun.prompt_bundle.prompt, 'sent prompt differs from the server bundle prompt');
    must(JSON.stringify(Object.keys(body).sort()) === JSON.stringify(['max_tokens', 'messages', 'model']), 'extra body fields: ' + Object.keys(body));
    must(p[0].headers.authorization === `Bearer ${KEY}`, 'key not in the provider auth header');
    must(!p[0].headers.cookie && !p[0].headers.referer, 'cookie or referer sent to the provider');
    must(!p[0].body.includes(KEY), 'key in the provider body');
    const note = checkManifest(body.messages[0].content, bun.outbound_manifest);
    await page.screenshot({ path: SHOTS + '/answer.png', fullPage: true });
    return note;
  });
  await step('UI is honest about the answer: forged citation flagged, real one checked', async () => {
    must((await page.getByTestId('grounding').getAttribute('data-grounded')) === 'true', 'not grounded');
    const inv = await page.getByTestId('invalid-citations').innerText();
    must(/1 citation points at claims that were not sent/.test(inv), 'forged citation not flagged: ' + inv);
    return inv.slice(0, 100);
  });
  await step('UI is honest about an ungrounded answer', async () => {
    await page.goto(W + '/settings', { waitUntil: 'networkidle' });
    await page.getByLabel('Base URL').fill(`${stub.url}/cors/ungrounded/v1`);
    await page.getByLabel('Model', { exact: true }).fill('stub-model');
    await page.getByLabel('API key').fill(KEY);
    await page.getByRole('button', { name: 'Save provider' }).click();
    await openDialog('Where are items stored?');
    await page.getByTestId('consent-dialog').getByRole('button', { name: /^Send to/ }).click();
    await page.getByTestId('grounding').waitFor({ timeout: 15000 });
    must((await page.getByTestId('grounding').getAttribute('data-grounded')) === 'false', 'ungrounded answer shown as grounded');
    return (await page.getByTestId('grounding').innerText()).slice(0, 110);
  });
  await step('rejected claims: a rejected item slipped into the bundle never reaches the provider', async () => {
    // The real bundle, with one of the stored rejected claims added as the server would format it (client-side only).
    const rej = await (await page.request.get(`${API}/claims?status=rejected&limit=50&include_rejected=true`)).json();
    const r0 = (rej.items || [])[0]; must(r0, 'no rejected claim found to inject');
    await page.route('**/chat/bundle', async (route) => {
      const res = await route.fetch(); const j = await res.json(); const pb = j.prompt_bundle;
      const item = { claim_id: r0.claim_id, status: 'rejected', label: 'rejected', where: 'backend/app/api/routes/login.py:8', statement: r0.statement };
      pb.evidence = [item, ...pb.evidence];
      pb.prompt = [pb.instructions, '', '<evidence>', ...pb.evidence.map((e) => `[${e.claim_id}] (${e.label}, ${e.where}) ${e.statement}`), '</evidence>', '', '<question>', pb.question, '</question>'].join('\n');
      j.outbound_manifest.splice(1, 0, { kind: 'claim_statement', claim_id: r0.claim_id, file: null, start_line: null, end_line: null, chars: r0.statement.length, sha256: sha256(r0.statement) });
      await route.fulfill({ response: res, json: j });
    });
    const before = posts().length;
    await openDialog('What does create_item depend on?');
    must(!(await page.getByTestId('consent-dialog').innerText()).includes(r0.claim_id), 'rejected id shown for sending');
    await page.getByTestId('consent-dialog').getByRole('button', { name: /^Send to/ }).click();
    await page.getByTestId('grounding').or(page.getByTestId('chat-error')).first().waitFor({ timeout: 15000 });
    const p = posts().slice(before); must(p.length === 1, 'no send');
    must(!p[0].body.includes(r0.claim_id), 'rejected claim id reached the provider');
    await page.unroute('**/chat/bundle');
    return `injected ${r0.claim_id.slice(0, 14)}..., stripped before consent and send`;
  });
  await step('rejected claims: server bundles never contain a stored rejected claim (12 targeted questions)', async () => {
    const rej = (await (await page.request.get(`${API}/claims?status=rejected&limit=50&include_rejected=true`)).json()).items || [];
    must(rej.length === 12, `expected 12 rejected claims on fsft, got ${rej.length}`);
    const ids = new Set(rej.map((r) => r.claim_id)); let hits = 0;
    for (const r of rej) {
      const j = await (await page.request.post(`${API}/chat/bundle`, { data: { question: r.statement } })).json();
      const text = JSON.stringify(j.prompt_bundle) + JSON.stringify(j.outbound_manifest);
      for (const id of ids) if (text.includes(id)) hits++;
      must(!j.prompt_bundle.evidence.some((e) => e.status === 'rejected' || e.label === 'rejected'), 'rejected status in bundle');
    }
    must(hits === 0, `${hits} rejected ids found in bundles`);
    return '0 rejected ids in 12 bundles asked with each rejected statement verbatim';
  });
  await step('sent record keeps no key; shows the placeholder', async () => {
    const ls = await page.evaluate(() => localStorage.getItem('traces.chat.sent') || '');
    must(ls.length > 0, 'no sent record'); must(!ls.includes(KEY), 'key in the sent record');
    must(ls.includes('(your key, not shown)'), 'placeholder missing');
    return `sent record ${ls.length} chars, placeholder only`;
  });
  await step('no key in any browser-to-Traces request, any Traces API response, or the console', async () => {
    const hit = traffic.filter((t) => t.includes(KEY));
    must(hit.length === 0, `key found in ${hit.length} items: ${hit[0] && hit[0].slice(0, 120)}`);
    return `${traffic.length} requests, responses and console lines scanned`;
  });
  await b.close();
  await step('no key in the server logs or the store file', async () => {
    const files = [...(process.env.API_LOGS || '').split(','), process.env.STORE || ''].filter(Boolean);
    const scanned = [];
    for (const f of files) {
      for (const g of [f, f + '-wal']) {
        if (!fs.existsSync(g)) continue;
        must(!fs.readFileSync(g).includes(Buffer.from(KEY)), `key found in ${g}`);
        scanned.push(g);
      }
    }
    must(scanned.length > 0 || !files.length, 'no file scanned');
    return scanned.length ? 'scanned ' + scanned.join(', ') : 'no log or store paths given (skipped)';
  });
  stub.close();
  for (const r of results) console.log(r.join(' | '));
  const fails = results.filter((r) => r[0] === 'FAIL').length;
  console.log(`chat G-5 checks: ${results.length - fails} passed, ${fails} failed (stub provider ${stub.url}, ${stub.requests.length} stub requests)`);
  process.exit(fails ? 1 : 0);
})();
