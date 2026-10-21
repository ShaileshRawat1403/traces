// Shared TS Program builder for Task 002 validators. TypeScript Compiler API only (D-Q1).
// Builds a Program from the repo's frontend/tsconfig.json, reading the checkout read-only.
// Every repo file the Program loads is hashed as a git blob and compared to `git ls-tree` at the pinned SHA.
'use strict';
const ts = require(process.env.TS_MODULE);
const fs = require('fs'), path = require('path'), crypto = require('crypto'), cp = require('child_process');

function blobMap(root, sha) {
  const out = cp.execFileSync('git', ['-C', root, 'ls-tree', '-r', sha], {encoding: 'utf8', env: {...process.env, GIT_OPTIONAL_LOCKS: '0'}, maxBuffer: 1 << 26});
  const m = new Map();
  for (const l of out.split('\n')) { const t = l.split('\t'); if (t.length === 2) m.set(t[1], t[0].split(' ')[2]); }
  return m;
}
function gitBlobSha(buf) { return crypto.createHash('sha1').update(`blob ${buf.length}\0`).update(buf).digest('hex'); }

function build(root, sha, proj = 'frontend') {
  const fe = path.join(root, proj);
  const cfgPath = path.join(fe, 'tsconfig.json');
  const cfg = ts.readConfigFile(cfgPath, ts.sys.readFile);
  if (cfg.error) throw new Error('tsconfig: ' + ts.flattenDiagnosticMessageText(cfg.error.messageText, ' '));
  const parsed = ts.parseJsonConfigFileContent(cfg.config, ts.sys, fe, {noEmit: true}, cfgPath);
  const host = ts.createCompilerHost(parsed.options, true);
  host.writeFile = () => { throw new Error('write attempted'); };
  const program = ts.createProgram({rootNames: parsed.fileNames, options: parsed.options, host, projectReferences: parsed.projectReferences});
  const blobs = blobMap(root, sha);
  const repoFiles = []; let mismatches = [];
  for (const sf of program.getSourceFiles()) {
    const abs = path.resolve(sf.fileName);
    if (!abs.startsWith(root + path.sep)) continue;
    const rel = path.relative(root, abs).split(path.sep).join('/');
    const want = blobs.get(rel); const got = gitBlobSha(fs.readFileSync(abs));
    repoFiles.push(rel);
    if (want !== got) mismatches.push({rel, want: want || null, got});
  }
  return {ts, program, checker: program.getTypeChecker(), options: parsed.options, configErrors: parsed.errors, repoFiles, blobMismatches: mismatches, root, proj};
}
function rel(ctx, fileName) { return path.relative(ctx.root, path.resolve(fileName)).split(path.sep).join('/'); }
function lineOf(sf, pos) { return sf.getLineAndCharacterOfPosition(pos).line + 1; }
function declInfo(ctx, d) { const sf = d.getSourceFile(); return {file: rel(ctx, sf.fileName), start_line: lineOf(sf, d.getStart(sf)), end_line: lineOf(sf, d.getEnd()), kind: ctx.ts.SyntaxKind[d.kind]}; }
// Resolve the symbol at an identifier through aliases (imports and re-exports) to its declarations.
function resolveAt(ctx, node) {
  const c = ctx.checker; let s = c.getSymbolAtLocation(node); const chain = [];
  if (!s) return {resolved: false, reason: 'no symbol', chain};
  let guard = 0;
  while (s && (s.flags & ctx.ts.SymbolFlags.Alias) && guard++ < 10) {
    chain.push((s.declarations || []).map(d => declInfo(ctx, d)));
    const t = c.getAliasedSymbol(s); if (!t || t === s) break; s = t;
  }
  if (!s || s.flags & ctx.ts.SymbolFlags.Alias) return {resolved: false, reason: 'alias did not resolve (unknown symbol)', chain};
  const decls = (s.declarations || []).map(d => declInfo(ctx, d));
  if (!decls.length) return {resolved: false, reason: 'symbol without declarations', chain};
  const inRepo = decls.filter(d => !d.file.startsWith('..'));
  return {resolved: inRepo.length > 0, name: s.getName(), decls, chain, reason: inRepo.length ? null : 'resolves outside repo'};
}
module.exports = {build, rel, lineOf, declInfo, resolveAt};
