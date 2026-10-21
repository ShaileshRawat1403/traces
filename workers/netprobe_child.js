// Child-process and in-process network probe. Run with CodeGraph's bundled Node.
'use strict';
const cp = require('child_process'), https = require('https'), net = require('net'), fs = require('fs');
const ns = () => fs.readlinkSync('/proc/self/ns/net');
console.log(`[node parent] node ${process.version} pid ${process.pid} netns ${ns()}`);
function run(label, cmd, args) {
  console.log(`$ (${label}) ${cmd} ${args.map(a => JSON.stringify(a)).join(' ')}`);
  const r = cp.spawnSync(cmd, args, {encoding: 'utf8', timeout: 20000});
  process.stdout.write(r.stdout || ''); process.stdout.write(r.stderr || '');
  console.log(`[exit=${r.status}${r.error ? ' error=' + r.error.code : ''}]`);
}
run('child_process.spawnSync -> sh', 'sh', ['-c', 'echo "[sh child] pid $$ netns $(readlink /proc/self/ns/net)"']);
run('child_process.spawnSync -> curl', 'curl', ['-sS', '-m', '8', '-o', '/dev/null', '-w', 'http_code=%{http_code}\\n', 'https://registry.npmjs.org/']);
run('child_process.spawnSync -> curl', 'curl', ['-sS', '-m', '8', '-o', '/dev/null', '-w', 'http_code=%{http_code}\\n', 'https://1.1.1.1/']);
const done = (label, code, msg) => console.log(`[in-process ${label}] result=${code} ${msg}`);
const tests = [
  new Promise(res => {
    console.log('$ (in-process) https.get("https://registry.npmjs.org/", {timeout: 8000})');
    const q = https.get('https://registry.npmjs.org/', {timeout: 8000}, r => { done('https registry', 'CONNECTED', `status ${r.statusCode}`); r.resume(); res(); });
    q.on('timeout', () => { q.destroy(new Error('timeout')); });
    q.on('error', e => { done('https registry', 'ERROR', `${e.code || ''} ${e.message}`); res(); });
  }),
  new Promise(res => {
    console.log('$ (in-process) net.connect({host: "1.1.1.1", port: 443, timeout: 8000})');
    const s = net.connect({host: '1.1.1.1', port: 443, timeout: 8000}, () => { done('net 1.1.1.1:443', 'CONNECTED', ''); s.destroy(); res(); });
    s.on('timeout', () => { done('net 1.1.1.1:443', 'ERROR', 'timeout'); s.destroy(); res(); });
    s.on('error', e => { done('net 1.1.1.1:443', 'ERROR', `${e.code || ''} ${e.message}`); res(); });
  }),
];
Promise.all(tests).then(() => console.log('[node parent done]'));
