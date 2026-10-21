// Task 002 TypeScript validator (family typescript-compiler, TypeScript Compiler API 6.0.3 only). Step 7.
// Reads source at the pinned SHA (working-tree files of the clean checkout, each verified against the git blob id).
// Never reads CodeGraph output: tasks carry only the claim (names, lines) to be checked.
// Usage: TS_MODULE=... node ts_validate.js <tasks.json> <results.json>
'use strict';
const fs = require('fs'), path = require('path');
const P = require('./ts_program.js');
const [tasksPath, outPath] = process.argv.slice(2);
const job = JSON.parse(fs.readFileSync(tasksPath, 'utf8'));
// one Program per repo tsconfig.json project (frontend/, packages/react-email/); each task uses the project that owns its file
const CTXS = {frontend: P.build(job.root, job.sha, 'frontend'), 'packages/react-email': P.build(job.root, job.sha, 'packages/react-email')};
for (const c of Object.values(CTXS)) if (c.blobMismatches.length) throw new Error('blob mismatch ' + JSON.stringify(c.blobMismatches));
const ts = CTXS.frontend.ts;
let ctx = CTXS.frontend, checker = ctx.checker;
function useCtxFor(file) { ctx = file && file.startsWith('packages/react-email/') ? CTXS['packages/react-email'] : CTXS.frontend; checker = ctx.checker; }
const VALIDATOR = {name: 'traces-ts-validator 1.0.0', version: 'typescript ' + ts.version, family: 'typescript-compiler'};
const blobs = (() => { const m = new Map(); const out = require('child_process').execFileSync('git', ['-C', job.root, 'ls-tree', '-r', job.sha], {encoding: 'utf8', env: {...process.env, GIT_OPTIONAL_LOCKS: '0'}, maxBuffer: 1 << 26});
  for (const l of out.split('\n')) { const t = l.split('\t'); if (t.length === 2) m.set(t[1], t[0].split(' ')[2]); } return m; })();
const crypto = require('crypto');
const sfCache = new Map();
function sourceFile(rel) {
  const key = ctx.proj + '|' + rel;
  if (sfCache.has(key)) return sfCache.get(key);
  let sf = ctx.program.getSourceFile(path.join(job.root, rel)); let inProgram = !!sf;
  if (!sf) {
    const buf = fs.readFileSync(path.join(job.root, rel));
    const got = crypto.createHash('sha1').update(`blob ${buf.length}\0`).update(buf).digest('hex');
    if (got !== blobs.get(rel)) throw new Error(`blob mismatch for ${rel}`);
    sf = ts.createSourceFile(rel, buf.toString('utf8'), ts.ScriptTarget.Latest, true, rel.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  }
  const v = {sf, inProgram, parseDiagnostics: sf.parseDiagnostics ? sf.parseDiagnostics.length : 0, decls: null, idents: null};
  sfCache.set(key, v); return v;
}
const ln = (sf, pos) => sf.getLineAndCharacterOfPosition(pos).line + 1;
const loc = (file, s, e, role, range_kind, extra = {}) => Object.assign({file, start_line: s, end_line: e, role, range_kind}, extra);

// ---------- declaration index (container set mirrors the step 1 recheck: functions, classes, interfaces, type aliases, methods, enums, const-with-function) ----------
function decls(rel) {
  const F = sourceFile(rel); if (F.decls) return F.decls;
  const sf = F.sf; const out = [];
  function add(name, kind, node, nameNode, parent, stmt) {
    const e = {name, kind, start: ln(sf, (stmt || node).getStart(sf)), nameLine: ln(sf, nameNode.getStart(sf)), end: ln(sf, (stmt || node).getEnd()), node, parent, fnStart: null};
    out.push(e); return e;
  }
  function visit(node, parent) {
    let here = parent;
    if ((ts.isFunctionDeclaration(node) || ts.isClassDeclaration(node) || ts.isInterfaceDeclaration(node) || ts.isTypeAliasDeclaration(node) || ts.isMethodDeclaration(node) || ts.isEnumDeclaration(node)) && node.name) {
      here = add(node.name.getText(sf), ts.SyntaxKind[node.kind], node, node.name, parent);
    } else if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name)) {
      const init = node.initializer; const fn = init && (ts.isArrowFunction(init) || ts.isFunctionExpression(init));
      const stmt = node.parent && node.parent.parent && ts.isVariableStatement(node.parent.parent) ? node.parent.parent : node;
      const e = add(node.name.text, fn ? 'VariableFunction' : 'Variable', node, node.name, parent, stmt);
      // a function expression passed as an argument of the initializer call (setOpen = React.useCallback(() => ...)): record where its body starts
      if (init && ts.isCallExpression(init)) for (const a of init.arguments) if (ts.isArrowFunction(a) || ts.isFunctionExpression(a)) { e.fnStart = ln(sf, a.getStart(sf)); e.fnEnd = ln(sf, a.getEnd()); break; }
      if (fn) here = e;
    } else if (ts.isImportDeclaration(node)) {
      add(node.moduleSpecifier.text, 'ImportDeclaration', node, node.moduleSpecifier, parent);
    } else if ((ts.isPropertyAssignment(node) || ts.isPropertySignature(node) || ts.isPropertyDeclaration(node) || ts.isMethodSignature(node)) && node.name) {
      add(node.name.getText(sf), ts.SyntaxKind[node.kind], node, node.name, parent);
    }
    ts.forEachChild(node, c => visit(c, here));
  }
  visit(sf, null);
  F.decls = out; return out;
}
function identsOnLine(rel, line) {
  const F = sourceFile(rel); const sf = F.sf;
  if (!F.idents) { F.idents = new Map(); (function w(n) { if (ts.isIdentifier(n) || ts.isPrivateIdentifier(n)) { const l = ln(sf, n.getStart(sf)); if (!F.idents.has(l)) F.idents.set(l, []); F.idents.get(l).push(n); } ts.forEachChild(n, w); })(sf); }
  return F.idents.get(line) || [];
}
function identsInRange(rel, s, e) { let r = []; for (let l = s; l <= e; l++) r = r.concat(identsOnLine(rel, l)); return r; }
const KIND_OK = {
  function: ['FunctionDeclaration', 'VariableFunction', 'Variable', 'MethodDeclaration', 'MethodSignature', 'PropertySignature', 'PropertyAssignment', 'PropertyDeclaration'],
  method: ['MethodDeclaration', 'MethodSignature', 'PropertySignature', 'PropertyDeclaration'],
  class: ['ClassDeclaration'], interface: ['InterfaceDeclaration'], type_alias: ['TypeAliasDeclaration'], constant: ['Variable', 'VariableFunction'],
  property: ['PropertySignature', 'PropertyDeclaration', 'PropertyAssignment', 'MethodSignature'], component: ['FunctionDeclaration', 'VariableFunction', 'Variable', 'ClassDeclaration'],
  import: ['ImportDeclaration'], enum: ['EnumDeclaration'], variable: ['Variable', 'VariableFunction']};
function shortName(n) { return n.split('::').pop().split('.').pop(); }
function findDecl(rel, name, line, kind) {
  const ds = decls(rel).filter(d => d.name === name);
  const atLine = ds.filter(d => d.start === line || d.nameLine === line);
  const ok = atLine.filter(d => !kind || !KIND_OK[kind] || KIND_OK[kind].includes(d.kind));
  const body = ds.filter(d => d.fnStart === line);
  return {all: ds, atLine, ok, body};
}
function declOfSymbolMatches(d, t) { // d from P.declInfo + extra, t = target endpoint
  return d.file === t.file && (d.start_line === t.start_line || d.name_line === t.start_line || d.stmt_line === t.start_line);
}
function declInfo2(d) {
  const sf = d.getSourceFile(); const i = P.declInfo(ctx, d);
  i.name_line = d.name ? ln(sf, d.name.getStart(sf)) : i.start_line;
  let st = d; if (ts.isVariableDeclaration(d) && d.parent && d.parent.parent && ts.isVariableStatement(d.parent.parent)) st = d.parent.parent;
  i.stmt_line = ln(sf, st.getStart(sf)); i.stmt_end = ln(sf, st.getEnd());
  if (ts.isExportAssignment(d)) i.kind = 'ExportAssignment';
  return i;
}
function resolveIdent(id) {
  let s = checker.getSymbolAtLocation(id);
  if (!s && ts.isJsxOpeningLikeElement(id.parent)) s = checker.getSymbolAtLocation(id.parent.tagName);
  if (s && id.parent && ts.isShorthandPropertyAssignment(id.parent) && id.parent.name === id) { const v = checker.getShorthandAssignmentValueSymbol(id.parent); if (v) s = v; }
  if (!s) return {state: 'unresolved', reason: 'no symbol (library or unknown)'};
  const chain = [];
  for (let g = 0; g < 10 && s && (s.flags & ts.SymbolFlags.Alias); g++) { chain.push(...(s.declarations || []).map(declInfo2)); const t = checker.getImmediateAliasedSymbol(s) || checker.getAliasedSymbol(s); if (!t || t === s) break; s = t; }
  if (!s || (s.flags & ts.SymbolFlags.Alias) || !s.declarations || !s.declarations.length) return {state: 'unresolved', reason: 'alias does not resolve (library not installed or unknown symbol)', chain};
  // follow object destructuring (const { x } = f()) through the property of the initializer's type, then shorthand/identifier property values
  for (let g = 0; g < 4; g++) {
    const d0 = s.declarations.length === 1 ? s.declarations[0] : null;
    if (!d0) break;
    let next = null;
    if (ts.isBindingElement(d0) && ts.isObjectBindingPattern(d0.parent)) {
      const pname = (d0.propertyName || d0.name).getText(); const ty = checker.getTypeAtLocation(d0.parent); const prop = ty && ty.getProperty(pname);
      if (prop) next = prop;
      else return {state: 'unresolved', reason: `destructured property '${pname}' not found on the initializer type`, chain: chain.concat([declInfo2(d0)])};
    } else if (ts.isShorthandPropertyAssignment(d0)) next = checker.getShorthandAssignmentValueSymbol(d0);
    else if (ts.isPropertyAssignment(d0) && ts.isIdentifier(d0.initializer)) next = checker.getSymbolAtLocation(d0.initializer);
    if (!next || next === s || !next.declarations || !next.declarations.length) break;
    chain.push(declInfo2(d0)); s = next;
    for (let h = 0; h < 10 && (s.flags & ts.SymbolFlags.Alias); h++) { chain.push(...(s.declarations || []).map(declInfo2)); const t2 = checker.getImmediateAliasedSymbol(s) || checker.getAliasedSymbol(s); if (!t2 || t2 === s) break; s = t2; }
    if (!s.declarations || !s.declarations.length) return {state: 'unresolved', reason: 'property value does not resolve', chain};
  }
  const ds = s.declarations.map(declInfo2);
  if (ds.every(d => d.file.startsWith('..') || d.file.includes('node_modules'))) return {state: 'unresolved', reason: 'resolves outside the repo', chain, decls: ds};
  return {state: 'resolved', decls: ds, chain, name: s.getName()};
}
function isDeclName(id) { const p = id.parent; return p && p.name === id && (ts.isVariableDeclaration(p) || ts.isFunctionDeclaration(p) || ts.isClassDeclaration(p) || ts.isInterfaceDeclaration(p) || ts.isTypeAliasDeclaration(p) || ts.isMethodDeclaration(p) || ts.isPropertySignature(p) || ts.isPropertyDeclaration(p) || ts.isParameter(p) || ts.isPropertyAssignment(p) || ts.isMethodSignature(p) || ts.isEnumDeclaration(p) || ts.isImportSpecifier(p) || ts.isBindingElement(p)); }
function calleeOf(id) { // id is the callee name of a call/new expression (f(), a.f(), new F())
  let n = id; if (ts.isPropertyAccessExpression(n.parent) && n.parent.name === n) n = n.parent;
  while (ts.isNonNullExpression(n.parent) || ts.isParenthesizedExpression(n.parent)) n = n.parent;
  const p = n.parent; if (!p) return null;
  if ((ts.isCallExpression(p) || ts.isNewExpression(p)) && p.expression === n) return p;
  if (ts.isTaggedTemplateExpression(p) && p.tag === n) return p;
  if (ts.isDecorator(p)) return p;
  return null;
}
function jsxElementOf(id) { const p = id.parent; if (p && (ts.isJsxOpeningElement(p) || ts.isJsxSelfClosingElement(p)) && p.tagName === id) return p; if (p && ts.isPropertyAccessExpression(p) && p.name === id && p.parent && (ts.isJsxOpeningElement(p.parent) || ts.isJsxSelfClosingElement(p.parent)) && p.parent.tagName === p) return p.parent; return null; }
function roleOk(kind, id) {
  if (isDeclName(id)) return false;
  if (kind === 'calls') return !!calleeOf(id) && !jsxElementOf(id);
  if (kind === 'instantiates') { const c = calleeOf(id); return !!c && ts.isNewExpression(c); }
  if (kind === 'renders') return !!jsxElementOf(id);
  if (kind === 'extends') { let n = id; while (n && !ts.isHeritageClause(n)) n = n.parent; return !!n; }
  return true; // references
}
function enclosingDecls(node) { const r = []; let n = node.parent; while (n) { if ((ts.isFunctionDeclaration(n) || ts.isMethodDeclaration(n) || ts.isClassDeclaration(n)) && n.name) r.push({name: n.name.getText(), line: ln(n.getSourceFile(), n.getStart(n.getSourceFile())), end: ln(n.getSourceFile(), n.getEnd())}); else if (ts.isVariableDeclaration(n) && ts.isIdentifier(n.name)) { const sf = n.getSourceFile(); const st = n.parent && n.parent.parent && ts.isVariableStatement(n.parent.parent) ? n.parent.parent : n; r.push({name: n.name.text, line: ln(sf, st.getStart(sf)), nameLine: ln(sf, n.name.getStart(sf)), end: ln(sf, st.getEnd())}); } n = n.parent; } return r; }
const chk = (method, establishes, rule_id, inputs, expected, result, detail) => ({method, establishes, rule_id, validator: VALIDATOR, inputs, expected, result, detail});
const fmtD = d => `${d.file}:${d.start_line}-${d.end_line} ${d.kind}`;

// ---------- node presence ----------
function routeLiteralMatches(lit, name) { const segs = lit.split('/').filter(s => s && !s.startsWith('_')); const norm = '/' + segs.join('/'); return norm.replace(/\/$/, '') === (name.replace(/\/$/, '') || '/') || (norm === '/' && name === '/'); }
function nodePresence(t) {
  const F = sourceFile(t.file); const sf = F.sf; const res = {checks: [], add_locations: [], flags: []};
  const inp = [loc(t.file, t.start_line, t.end_line, 'from_decl', 'declaration')];
  if (t.kind === 'file') {
    const ok = F.parseDiagnostics === 0;
    res.checks.push(chk('parser_presence', 'presence', null, [loc(t.file, 1, t.end_line, 'from_decl', 'file')], 'file parses as TS/TSX with 0 parse diagnostics', ok ? 'pass' : 'fail', `${F.parseDiagnostics} parse diagnostics; in tsconfig program: ${F.inProgram}`));
    return res;
  }
  if (t.kind === 'route') {
    let hit = null;
    (function w(n) { if (!hit && ts.isCallExpression(n) && ts.isIdentifier(n.expression) && n.expression.text === 'createFileRoute' && ln(sf, n.getStart(sf)) <= t.start_line && ln(sf, n.getEnd()) >= t.start_line) hit = n; ts.forEachChild(n, w); })(sf);
    if (!hit) { res.checks.push(chk('parser_presence', 'presence', null, inp, `createFileRoute call at line ${t.start_line}`, 'fail', 'no createFileRoute call spans this line')); return res; }
    const lit = hit.arguments[0] && ts.isStringLiteral(hit.arguments[0]) ? hit.arguments[0].text : null;
    const ok = lit !== null && routeLiteralMatches(lit, t.name);
    res.checks.push(chk('parser_presence', 'presence', null, inp, `createFileRoute("<path for ${t.name}>") at line ${t.start_line}`, ok ? 'pass' : 'inconclusive', `createFileRoute(${JSON.stringify(lit)}) at ${t.file}:${ln(sf, hit.getStart(sf))}; path segments starting with '_' are pathless layouts and dropped for comparison`));
    return res;
  }
  const nm = t.kind === 'import' ? t.name : shortName(t.name);
  const f = findDecl(t.file, nm, t.start_line, t.kind);
  if (f.ok.length) {
    const d = f.ok[0];
    res.checks.push(chk('parser_presence', 'presence', null, inp, `${t.kind} '${nm}' declared at line ${t.start_line}`, 'pass', `${d.kind} '${d.name}' first token line ${d.start}, name line ${d.nameLine}, end ${d.end}`));
  } else if (f.atLine.length) {
    res.checks.push(chk('parser_presence', 'presence', null, inp, `${t.kind} '${nm}' declared at line ${t.start_line}`, 'inconclusive', `declaration '${nm}' at this line has syntax kind ${f.atLine.map(d => d.kind).join(',')}, not mapped to CodeGraph kind ${t.kind}`));
  } else if (f.body.length) {
    const d = f.body[0];
    res.checks.push(chk('parser_presence', 'presence', null, [inp[0], loc(t.file, d.start, d.end, 'from_decl', 'declaration')], `${t.kind} '${nm}' declared at line ${t.start_line}`, 'pass',
      `extractor range ${t.start_line}-${t.end_line} is the body: the function expression inside the initializer of '${d.name}' starts at ${d.fnStart} (ends ${d.fnEnd}); the declaration ('${d.kind}', const binding) is ${d.start}-${d.end}. Validator declaration location appended.`));
    res.add_locations.push(loc(t.file, d.start, d.end, 'from_decl', 'declaration', {range_rule: 'binding_statement'}));
    res.flags.push('extractor_location_is_body');
  } else if (f.all.length) {
    res.checks.push(chk('parser_presence', 'presence', null, inp, `${t.kind} '${nm}' declared at line ${t.start_line}`, 'fail', `'${nm}' is declared at ${f.all.map(d => d.start + (d.nameLine !== d.start ? '/' + d.nameLine : '')).join(', ')}, not at ${t.start_line}`));
  } else {
    res.checks.push(chk('parser_presence', 'presence', null, inp, `${t.kind} '${nm}' declared at line ${t.start_line}`, 'fail', `no declaration named '${nm}' in ${t.file}`));
  }
  return res;
}
// ---------- unresolved reference presence ----------
function unresolvedPresence(t) {
  const F = sourceFile(t.file); const sf = F.sf; const res = {checks: [], add_locations: [], flags: []};
  const inp = [loc(t.file, t.line, t.line, 'site', 'site')];
  const last = t.ref_name.split(/[.]/).pop();
  const ids = identsOnLine(t.file, t.line).filter(i => i.text === last || i.text === t.ref_name);
  if (last === 'this') (function w(n) { if (n.kind === ts.SyntaxKind.ThisKeyword && ln(sf, n.getStart(sf)) === t.line) ids.push(n); ts.forEachChild(n, w); })(sf);
  let strs = [];
  if (!ids.length) (function w(n) { if ((ts.isStringLiteral(n) || ts.isNoSubstitutionTemplateLiteral(n)) && ln(sf, n.getStart(sf)) === t.line && (n.text === t.ref_name || n.text.endsWith('/' + last) || n.text === last)) strs.push(n); ts.forEachChild(n, w); })(sf);
  if (ids.length) {
    const kinds = ids.map(i => ts.SyntaxKind[i.parent.kind]);
    res.checks.push(chk('parser_presence', 'presence', null, inp, `'${t.ref_name}' (${t.ref_kind}) at line ${t.line}`, 'pass', `${ids.length} identifier(s) '${last}' at line ${t.line}; parents ${[...new Set(kinds)].join(',')}`));
  } else if (strs.length) {
    res.checks.push(chk('parser_presence', 'presence', null, inp, `'${t.ref_name}' (${t.ref_kind}) at line ${t.line}`, 'pass', `string literal ${JSON.stringify(strs[0].text)} in ${ts.SyntaxKind[strs[0].parent.kind]} at line ${t.line}`));
  } else {
    // multi-line constructs that START at the reported line: import declarations (specifier on a later line), call/member chains, call text
    const hits = [];
    const CHAIN = n => ts.isPropertyAccessExpression(n) || ts.isCallExpression(n) || ts.isElementAccessExpression(n) || ts.isNonNullExpression(n) || ts.isAwaitExpression(n);
    (function w(n) {
      const st = ln(sf, n.getStart(sf));
      if (ts.isImportDeclaration(n) && st === t.line && ts.isStringLiteral(n.moduleSpecifier) && n.moduleSpecifier.text === t.ref_name) hits.push(`import declaration starting at ${st}, specifier ${JSON.stringify(n.moduleSpecifier.text)} at line ${ln(sf, n.moduleSpecifier.getStart(sf))}`);
      if (ts.isCallExpression(n) && st === t.line && n.getText(sf).replace(/\s+/g, '') === t.ref_name.replace(/\s+/g, '')) hits.push(`call expression ${JSON.stringify(n.getText(sf).slice(0, 60))} starting at ${st}`);
      if (ts.isIdentifier(n) && n.text === last) { let a = n.parent, top = null; while (a && CHAIN(a)) { top = a; a = a.parent; }
        if (top && ln(sf, top.getStart(sf)) === t.line && ln(sf, n.getStart(sf)) !== t.line) hits.push(`identifier '${last}' at line ${ln(sf, n.getStart(sf))} inside a ${ts.SyntaxKind[top.kind]} chain starting at ${t.line}`); }
      ts.forEachChild(n, w); })(sf);
    if (hits.length) res.checks.push(chk('parser_presence', 'presence', null, inp, `'${t.ref_name}' (${t.ref_kind}) at line ${t.line}`, 'pass', `not on line ${t.line} itself; ${hits.slice(0, 3).join('; ')}`));
    else res.checks.push(chk('parser_presence', 'presence', null, inp, `'${t.ref_name}' (${t.ref_kind}) at line ${t.line}`, 'fail', `no identifier or string literal '${last}' at line ${t.line}, and no import, call or member chain starting at line ${t.line} that contains it`));
  }
  return res;
}
// ---------- relationship checks ----------
function siteBinding(t, kind, line, siteInputs) {
  // binding_resolution of identifiers named like the target at one site line
  const s = t.src, g = t.tgt; const nm = g.kind === 'import' ? g.name : shortName(g.name);
  const ids = identsOnLine(s.file, line).filter(i => i.text === nm);
  const exp = `an identifier '${nm}' at ${s.file}:${line} in a ${kind} position resolves to ${g.file}:${g.start_line}`;
  if (s.kind !== 'file' && !(s.start_line <= line && line <= s.end_line)) return chk('binding_resolution', 'relationship', null, siteInputs, exp, 'inconclusive', `site line ${line} is outside the source declaration ${s.start_line}-${s.end_line}`);
  if (!ids.length) return chk('binding_resolution', 'relationship', null, siteInputs, exp, 'inconclusive', `no identifier '${nm}' at line ${line}`);
  const inRole = ids.filter(i => roleOk(kind, i));
  if (!inRole.length) {
    const rs = ids.map(resolveIdent); const m = rs.some(r => r.state === 'resolved' && r.decls.some(d => declOfSymbolMatches(d, g)));
    return chk('binding_resolution', 'relationship', null, siteInputs, exp, 'inconclusive', `identifier '${nm}' at line ${line} is in a ${ids.map(i => ts.SyntaxKind[i.parent.kind]).join(',')} position, not a ${kind} position${m ? ' (it does resolve to the target)' : ''}; relationship kind ${kind} not established`);
  }
  const rs = inRole.map(i => ({i, r: resolveIdent(i)}));
  const hit = rs.find(x => x.r.state === 'resolved' && x.r.decls.some(d => declOfSymbolMatches(d, g)));
  if (hit) return chk('binding_resolution', 'relationship', null, siteInputs.concat(hit.r.chain.slice(0, 3).map(c => loc(c.file, c.start_line, c.end_line, 'input', 'declaration')), [loc(g.file, g.start_line, g.end_line, 'to_decl', 'declaration')]), exp, 'pass',
    `'${nm}' at ${s.file}:${line} resolves${hit.r.chain.length ? ' via ' + hit.r.chain.map(fmtD).join(' -> ') : ''} to ${hit.r.decls.map(fmtD).join('; ')}`);
  const resolved = rs.filter(x => x.r.state === 'resolved');
  if (resolved.length === rs.length) {
    // body-range target (setOpen case): the resolved declaration contains the target start
    const bodyCase = resolved.some(x => x.r.decls.some(d => d.file === g.file && d.stmt_line < g.start_line && g.start_line <= d.stmt_end));
    if (bodyCase) return chk('binding_resolution', 'relationship', null, siteInputs, exp, 'inconclusive', `'${nm}' resolves to ${resolved.map(x => x.r.decls.map(fmtD).join(';')).join(' | ')}, whose declaration line differs from the extractor line ${g.start_line}`);
    return chk('binding_resolution', 'relationship', null, siteInputs, exp, 'fail', `'${nm}' at line ${line} resolves to ${resolved.map(x => x.r.decls.map(fmtD).join(';')).join(' | ')}, not to ${g.file}:${g.start_line}`);
  }
  return chk('binding_resolution', 'relationship', null, siteInputs, exp, 'inconclusive', `'${nm}' at line ${line} does not resolve: ${rs.filter(x => x.r.state !== 'resolved').map(x => x.r.reason).join('; ')}`);
}
const IMPORT_FIRST_LINE = [];
function importCheck(t) {
  IMPORT_FIRST_LINE.length = 0;
  const s = t.src, g = t.tgt; const sf = sourceFile(s.file).sf; const site = [loc(s.file, t.line, t.line, 'site', 'site')];
  // the statement that starts at, or spans, the reported line (CodeGraph gives the imported name's line inside a multi-line import)
  const st = sf.statements.filter(x => (ts.isImportDeclaration(x) || (ts.isExportDeclaration(x) && x.moduleSpecifier)) && ln(sf, x.getStart(sf)) <= t.line && t.line <= ln(sf, x.getEnd()));
  const exp = `import statement at ${s.file}:${t.line} binds ${g.kind === 'file' ? 'module ' + g.file : "'" + g.name + "'"}`;
  if (!st.length) return [chk('syntax_structure', 'relationship', null, site, exp, 'inconclusive', `no import or re-export statement starts at or spans line ${t.line}`)];
  const x = st[0]; const spec = x.moduleSpecifier.text; const x0 = ln(sf, x.getStart(sf));
  if (x0 !== t.line) { const first = loc(s.file, x0, x0, 'site', 'site', {range_rule: 'expression'}); site.push(first); IMPORT_FIRST_LINE.push(first); }
  if (g.kind === 'import') {
    const ok = spec === g.name && g.file === s.file;
    // Decision 002-B correction A: target is this file's own import node (library module or asset); presence of the statement only
    return [chk('parser_presence', 'presence', null, site.concat([loc(g.file, g.start_line, g.end_line, 'to_decl', 'declaration')]), exp, ok ? 'pass' : 'fail', `file ${s.file} has import statement at line ${t.line} with specifier ${JSON.stringify(spec)} (import statement observed; target outside validator scope, not resolved)`)];
  }
  const r = ts.resolveModuleName(spec, path.join(job.root, s.file), ctx.options, ts.sys);
  const target = r.resolvedModule ? P.rel(ctx, r.resolvedModule.resolvedFileName) : null;
  if (g.kind === 'file') {
    if (!target) return [chk('binding_resolution', 'relationship', null, site, exp, 'inconclusive', `module ${JSON.stringify(spec)} does not resolve (library not installed or unknown)`)];
    return [chk('binding_resolution', 'relationship', null, site.concat([loc(g.file, 1, g.end_line, 'to_decl', 'file')]), exp, target === g.file ? 'pass' : 'fail', `module ${JSON.stringify(spec)} resolves to ${target} (moduleResolution ${ts.ModuleResolutionKind[ctx.options.moduleResolution]}, paths ${JSON.stringify(ctx.options.paths)})`)];
  }
  const nm = shortName(g.name);
  const names = [];
  if (ts.isImportDeclaration(x) && x.importClause) { if (x.importClause.name) names.push(x.importClause.name); const nb = x.importClause.namedBindings; if (nb && nb.elements) nb.elements.forEach(e => names.push(e.name)); }
  if (ts.isExportDeclaration(x) && x.exportClause && x.exportClause.elements) x.exportClause.elements.forEach(e => names.push(e.name));
  const cand = names.filter(n => n.text === nm || (n.parent.propertyName && n.parent.propertyName.text === nm));
  if (!cand.length) return [chk('binding_resolution', 'relationship', null, site, exp, 'inconclusive', `import at line ${t.line} binds ${names.map(n => n.text).join(', ') || '(namespace or side-effect)'}; no binding named '${nm}'`)];
  const rs = cand.map(resolveIdent); const hit = rs.find(r => r.state === 'resolved' && r.decls.some(d => declOfSymbolMatches(d, g)));
  if (hit) return [chk('binding_resolution', 'relationship', null, site.concat([loc(g.file, g.start_line, g.end_line, 'to_decl', 'declaration')]), exp, 'pass', `'${nm}' imported at line ${t.line} from ${JSON.stringify(spec)} resolves to ${hit.decls.map(fmtD).join('; ')}`)];
  const res = rs.filter(r => r.state === 'resolved');
  if (res.length === rs.length) return [chk('binding_resolution', 'relationship', null, site, exp, 'fail', `'${nm}' resolves to ${res.map(r => r.decls.map(fmtD).join(';')).join(' | ')}, not ${g.file}:${g.start_line}`)];
  return [chk('binding_resolution', 'relationship', null, site, exp, 'inconclusive', `'${nm}' does not resolve: ${rs.map(r => r.reason).filter(Boolean).join('; ')}`)];
}
function contains(t) {
  const p = t.src, c = t.tgt; const res = {checks: [], add_locations: [], flags: []};
  const nm = c.kind === 'import' ? c.name : shortName(c.name);
  const f = findDecl(c.file, nm, c.start_line, null);
  const exp = `${c.kind} '${nm}' (start ${c.start_line}) is a direct syntax child of ${p.kind === 'file' ? 'the module' : "'" + shortName(p.name) + "'"}`;
  const inputs0 = [loc(c.file, c.start_line, c.end_line, 'to_decl', 'declaration'), loc(p.file, p.start_line, p.end_line, 'from_decl', p.kind === 'file' ? 'file' : 'declaration')];
  if (!f.atLine.length && f.body.length) {
    // setOpen case (EVIDENCE_SCHEMA 4.1 and 7): the child matches as a body; recovery adds the body location for the child and the parent declaration
    const b = f.body[0]; const pf = p.kind === 'file' ? null : findDecl(p.file, shortName(p.name), p.start_line, null).atLine[0];
    const bodyLoc = loc(c.file, b.fnStart, b.fnEnd, 'to_decl', 'body', {range_rule: 'body_only'});
    const parLoc = p.kind === 'file' ? loc(p.file, 1, p.end_line, 'from_decl', 'file', {range_rule: 'file'}) : (pf ? loc(p.file, pf.start, pf.end, 'from_decl', 'declaration', {range_rule: 'header_to_body_end'}) : null);
    if (b.fnStart === c.start_line && parLoc && b.parent && (p.kind === 'file' ? false : b.parent.name === shortName(p.name))) {
      res.checks.push(chk('location_recovery', 'location', 'R-contains', [bodyLoc, parLoc], exp, 'pass', `child '${nm}' matches as a body: function expression ${b.fnStart}-${b.fnEnd} inside the initializer of const '${b.name}' (${b.start}-${b.end}); parent ${pf.kind} '${pf.name}' at ${pf.start}-${pf.end}`));
      res.add_locations.push(bodyLoc, parLoc);
      res.checks.push(chk('syntax_structure', 'relationship', 'R-contains', [bodyLoc, parLoc], exp, 'inconclusive', `'${nm}' is declared at ${b.start}-${b.end}; its function expression (body) starts at ${b.fnStart}, which is the extractor line ${c.start_line}; declaration line differs from extractor line`));
      res.reason = 'declaration line differs from extractor line'; return res;
    }
  }
  if (!f.atLine.length) {
    const why = f.body.length ? 'declaration line differs from extractor line' : `child declaration '${nm}' not found at line ${c.start_line} by the parser`;
    const det = f.body.length ? `'${nm}' is declared at ${f.body[0].start}-${f.body[0].end}; its function expression (body) starts at ${f.body[0].fnStart}, which is the extractor line ${c.start_line}` : why;
    res.checks.push(chk('location_recovery', 'location', 'R-contains', inputs0, exp, 'inconclusive', det)); res.reason = why; return res;
  }
  const d = f.atLine[0];
  const parentOk = p.kind === 'file' ? d.parent === null : (d.parent && d.parent.name === shortName(p.name) && (d.parent.start === p.start_line || d.parent.nameLine === p.start_line));
  // locations for both ends from the validator parser
  let pdecl = null;
  if (p.kind !== 'file') { const pf = findDecl(p.file, shortName(p.name), p.start_line, null); pdecl = pf.atLine[0] || null; }
  if (parentOk || pdecl || p.kind === 'file') {
    const childLoc = loc(c.file, d.start, d.end, 'to_decl', 'declaration', {range_rule: 'header_to_body_end'});
    const parLoc = p.kind === 'file' ? loc(p.file, 1, p.end_line, 'from_decl', 'file', {range_rule: 'file'}) : loc(p.file, pdecl.start, pdecl.end, 'from_decl', 'declaration', {range_rule: 'header_to_body_end'});
    res.checks.push(chk('location_recovery', 'location', 'R-contains', [childLoc, parLoc], exp, 'pass', `child ${d.kind} '${d.name}' at ${d.start}-${d.end}; parent ${p.kind === 'file' ? 'module' : pdecl.kind + " '" + pdecl.name + "' at " + pdecl.start + '-' + pdecl.end}`));
    res.add_locations.push(childLoc, parLoc);
    if (parentOk) { res.checks.push(chk('syntax_structure', 'relationship', 'R-contains', [childLoc, parLoc], exp, 'pass', `nearest enclosing declaration of '${d.name}' is ${d.parent ? d.parent.kind + " '" + d.parent.name + "' at " + d.parent.start : 'the module'}`)); return res; }
  }
  // not the immediate parent: transitive or wrong
  let anc = d.parent; let transitive = false; while (anc) { if (p.kind !== 'file' && anc.name === shortName(p.name) && (anc.start === p.start_line || anc.nameLine === p.start_line)) { transitive = true; break; } anc = anc.parent; }
  if (p.kind === 'file' && d.parent) transitive = true;
  if (transitive) { res.checks.push(chk('syntax_structure', 'relationship', 'R-contains', inputs0, exp, 'inconclusive', `'${d.name}' is inside '${shortName(p.name)}' but its immediate enclosing declaration is ${d.parent.kind} '${d.parent.name}' at ${d.parent.start}`)); res.reason = 'transitive containment, immediate parent not a node'; return res; }
  res.checks.push(chk('syntax_structure', 'relationship', 'R-contains', inputs0, exp, 'fail', `'${d.name}' immediate enclosing declaration is ${d.parent ? d.parent.kind + " '" + d.parent.name + "' at " + d.parent.start : 'the module'}, not '${shortName(p.name)}'`));
  return res;
}
function recoverInScope(t, kind, rule) {
  // R-enclosing / R-valueRef: inside the source declaration's range find identifiers naming the target that resolve to it
  const s = t.src, g = t.tgt; const res = {checks: [], add_locations: [], flags: []};
  const nm = shortName(g.name); const s0 = s.kind === 'file' ? 1 : s.start_line, s1 = s.end_line;
  const scopeLoc = loc(s.file, s0, s1, 'input', s.kind === 'file' ? 'file' : 'declaration');
  const cands = identsInRange(s.file, s0, s1).filter(i => i.text === nm && !isDeclName(i) && (kind !== 'renders' || jsxElementOf(i)));
  const exp = `inside ${s.file}:${s0}-${s1}, ${kind === 'renders' ? 'a JSX element tag' : 'an identifier'} '${nm}' that resolves to ${g.file}:${g.start_line}`;
  const hits = []; const other = [];
  for (const i of cands) { const r = resolveIdent(i); if (r.state === 'resolved' && r.decls.some(d => declOfSymbolMatches(d, g))) hits.push({i, r}); else other.push({i, r}); }
  if (!hits.length) {
    res.checks.push(chk('location_recovery', 'location', rule, [scopeLoc], exp, 'inconclusive', `${cands.length} candidate(s), 0 resolve to the target${other.length ? ': ' + other.slice(0, 3).map(x => `line ${ln(x.i.getSourceFile(), x.i.getStart())} ${x.r.state === 'resolved' ? 'resolves to ' + x.r.decls.map(fmtD).join(';') : x.r.reason}`).join(' | ') : ''}`));
    res.reason = cands.length ? 'no candidate in scope resolves to the target' : `no ${kind === 'renders' ? 'JSX element' : 'identifier'} named '${nm}' inside the source range`;
    return res;
  }
  const lines = [...new Set(hits.map(h => ln(h.i.getSourceFile(), h.i.getStart())))].sort((a, b) => a - b);
  const sites = lines.map(l => loc(s.file, l, l, 'site', 'site', {range_rule: 'expression', recovered_by: rule}));
  res.add_locations.push(...sites);
  res.checks.push(chk('location_recovery', 'location', rule, [scopeLoc].concat(sites), exp, 'pass', `${hits.length} hit(s) at line(s) ${lines.join(', ')} resolve to ${hits[0].r.decls.map(fmtD).join('; ')}`));
  res.recovered_lines = lines;
  return res;
}
function edge(t) {
  const res = {checks: [], add_locations: [], flags: []}; const s = t.src;
  if (t.rel_kind === 'contains') return contains(t);
  if (t.rel_kind === 'navigates') { res.checks.push(chk('binding_resolution', 'relationship', null, t.line ? [loc(s.file, t.line, t.line, 'site', 'site')] : [], 'navigation target route', 'inconclusive', 'TanStack navigation uses a route path string; no Task 002 rule covers string-route resolution (FASTAPI_RULES scope)')); res.reason = 'no Task 002 rule for TanStack route-string navigation'; return res; }
  let siteLines = [], extraSites = [];
  if (t.missing || t.enclosing) {
    const rule = t.missing ? 'R-valueRef' : 'R-enclosing';
    if (t.missing && !t.value_ref) { res.checks.push(chk('location_recovery', 'location', null, [], 'a line', 'inconclusive', 'edge without line and without valueRef: no recovery rule')); return res; }
    const r = recoverInScope(t, t.rel_kind, rule); res.checks.push(...r.checks); res.add_locations.push(...r.add_locations); if (!r.recovered_lines) { res.reason = r.reason; return res; }
    siteLines = r.recovered_lines; if (t.enclosing) extraSites = [loc(s.file, t.line, t.line, 'site', 'enclosing_scope')];
  } else siteLines = [t.line];
  if (t.rel_kind === 'imports') { res.checks.push(...importCheck(t)); res.add_locations.push(...IMPORT_FIRST_LINE); return res; }
  const inputs = siteLines.map(l => loc(s.file, l, l, 'site', 'site')).concat(extraSites);
  const per = siteLines.map(l => siteBinding(t, t.rel_kind, l, inputs));
  // one check covering all sites: pass only if every site passes
  const allPass = per.every(c => c.result === 'pass'); const anyFail = per.some(c => c.result === 'fail');
  const c0 = per.find(c => c.result !== 'pass') || per[0];
  res.checks.push(chk('binding_resolution', 'relationship', null, allPass ? per[0].inputs.concat(extraSites.filter(x => !per[0].inputs.includes(x))) : inputs, c0.expected, allPass ? 'pass' : anyFail ? 'fail' : 'inconclusive', per.map((c, i) => `line ${siteLines[i]}: ${c.result}: ${c.detail}`).join(' || ')));
  if (t.rel_kind === 'renders' && allPass) {
    // syntax_structure: the JSX element lies inside the source component body
    const nm = shortName(t.tgt.name); const ids = siteLines.flatMap(l => identsOnLine(s.file, l).filter(i => i.text === nm && jsxElementOf(i)));
    const inside = ids.every(i => enclosingDecls(i).some(d => d.name === shortName(s.name) && (d.line === s.start_line || d.nameLine === s.start_line)));
    res.checks.push(chk('syntax_structure', 'relationship', null, inputs.concat([loc(s.file, s.start_line, s.end_line, 'from_decl', 'declaration')]), `JSX element <${nm}> inside the body of '${shortName(s.name)}'`, inside ? 'pass' : 'fail', `${ids.length} JSX element(s) <${nm}> at line(s) ${siteLines.join(', ')}; enclosing declarations ${ids.length ? enclosingDecls(ids[0]).map(d => d.name + '@' + d.line).join(' > ') : '(none)'}`));
  }
  return res;
}
// ---------- fixture claims (EXPECTED_CHAIN) ----------
function nodeAt(file, line, pred) { const sf = sourceFile(file).sf; let hit = null; (function w(n) { if (!hit && ln(sf, n.getStart(sf)) <= line && ln(sf, n.getEnd()) >= line) { if (ln(sf, n.getStart(sf)) === line && pred(n)) { hit = n; return; } ts.forEachChild(n, w); } })(sf); return hit; }
function identAt(file, line, text, pred = () => true) { return identsOnLine(file, line).filter(i => i.text === text && pred(i)); }
const AT = 'frontend/src/components/Items/AddItem.tsx', IT = 'frontend/src/routes/_layout/items.tsx', IDX = 'frontend/src/client/index.ts', SDK = 'frontend/src/client/sdk.gen.ts', TYP = 'frontend/src/client/types.gen.ts', CFG = 'frontend/openapi-ts.config.ts';
function chainOk(r, wants) { return wants.every(w => r.chain.some(c => c.file === w.file && c.start_line <= w.line && w.line <= c.end_line)); }
const fixture = {
  L1(t) {
    const res = {checks: []}; const site = loc(IT, 65, 65, 'site', 'site');
    const tag = identAt(IT, 65, 'AddItem', i => !!jsxElementOf(i))[0];
    const inItems = tag && enclosingDecls(tag).some(d => d.name === 'Items' && d.line === 57 && d.end === 70);
    res.checks.push(chk('syntax_structure', 'relationship', null, [site, loc(IT, 57, 70, 'from_decl', 'declaration')], 'JSX element <AddItem /> at items.tsx:65 lies inside the body of function Items (57-70)', tag && inItems ? 'pass' : 'fail',
      tag ? `${ts.SyntaxKind[jsxElementOf(tag).kind]} <AddItem> at 65; enclosing declarations ${enclosingDecls(tag).map(d => d.name + '@' + d.line + '-' + d.end).join(' > ')}` : 'no JSX element AddItem at line 65'));
    const r = tag ? resolveIdent(tag) : {state: 'none', chain: []};
    // default export at AddItem.tsx:143 must name the same symbol
    const sfA = sourceFile(AT).sf; const ea = sfA.statements.find(s => ts.isExportAssignment(s) && !s.isExportEquals);
    const eaSym = ea && ts.isIdentifier(ea.expression) ? resolveIdent(ea.expression) : null;
    const eaLine = ea ? ln(sfA, ea.getStart(sfA)) : null;
    const ok = r.state === 'resolved' && r.decls.some(d => d.file === AT && d.stmt_line === 40 && d.stmt_end === 141) && chainOk(r, [{file: IT, line: 8}]) && eaLine === 143 && eaSym && eaSym.state === 'resolved' && eaSym.decls.some(d => d.file === AT && d.stmt_line === 40);
    res.checks.push(chk('binding_resolution', 'relationship', null, [site, loc(IT, 8, 8, 'input', 'site'), loc(AT, 143, 143, 'input', 'declaration'), loc(AT, 40, 141, 'to_decl', 'declaration')], 'tag AddItem at items.tsx:65 resolves through the default import at items.tsx:8 and the default export at AddItem.tsx:143 to const AddItem declared at AddItem.tsx:40-141', ok ? 'pass' : (r.state === 'resolved' ? 'fail' : 'inconclusive'),
      `tag resolves via ${r.chain.map(fmtD).join(' -> ')} to ${r.decls ? r.decls.map(fmtD).join('; ') : r.reason}; export default at line ${eaLine} names ${eaSym && eaSym.decls ? eaSym.decls.map(fmtD).join(';') : '?'}`));
    return res;
  },
  L2A(t) {
    const res = {checks: []}; const site = loc(AT, 88, 88, 'site', 'site');
    const arg = identAt(AT, 88, 'onSubmit', i => ts.isCallExpression(i.parent) && i.parent.arguments.includes(i))[0];
    let detail = 'no identifier onSubmit as a call argument at line 88'; let ok = false;
    if (arg) { const call = arg.parent; const callee = call.expression; const attr = call.parent && ts.isJsxExpression(call.parent) && call.parent.parent && ts.isJsxAttribute(call.parent.parent) ? call.parent.parent : null;
      const el = attr && attr.parent && attr.parent.parent; const tagName = el && (ts.isJsxOpeningElement(el) || ts.isJsxSelfClosingElement(el)) ? el.tagName.getText() : null;
      ok = ts.isPropertyAccessExpression(callee) && callee.name.text === 'handleSubmit' && ts.isIdentifier(callee.expression) && callee.expression.text === 'form' && attr && attr.name.getText() === 'onSubmit' && tagName === 'form' && enclosingDecls(arg).some(d => d.name === 'AddItem' && d.line === 40);
      detail = `identifier onSubmit is argument 0 of ${callee.getText()}(...) in JSX attribute ${attr ? attr.name.getText() : '?'} of <${tagName}>; enclosing ${enclosingDecls(arg).map(d => d.name + '@' + d.line).join(' > ')}`; }
    res.checks.push(chk('syntax_structure', 'relationship', null, [site], 'identifier onSubmit is the argument of form.handleSubmit(...) in the onSubmit attribute of <form> at AddItem.tsx:88, inside AddItem', ok ? 'pass' : 'fail', detail));
    const r = arg ? resolveIdent(arg) : {state: 'none'};
    const ok2 = r.state === 'resolved' && r.decls.some(d => d.file === AT && d.stmt_line === 68 && d.stmt_end === 70);
    res.checks.push(chk('binding_resolution', 'relationship', null, [site, loc(AT, 68, 70, 'to_decl', 'declaration')], 'onSubmit at AddItem.tsx:88 resolves to const onSubmit at AddItem.tsx:68-70', ok2 ? 'pass' : r.state === 'resolved' ? 'fail' : 'inconclusive', r.decls ? `resolves to ${r.decls.map(d => fmtD(d) + ' stmt ' + d.stmt_line + '-' + d.stmt_end).join('; ')}` : (r.reason || 'not found')));
    return res;
  },
  L2B(t) {
    const res = {checks: []}; const site = loc(AT, 69, 69, 'site', 'site');
    const recv = identAt(AT, 69, 'mutation', i => ts.isPropertyAccessExpression(i.parent) && i.parent.expression === i && i.parent.name.text === 'mutate' && ts.isCallExpression(i.parent.parent) && i.parent.parent.expression === i.parent)[0];
    const inside = recv && enclosingDecls(recv).some(d => d.name === 'onSubmit' && d.line === 68 && d.end === 70);
    res.checks.push(chk('syntax_structure', 'relationship', null, [site, loc(AT, 68, 70, 'from_decl', 'declaration')], 'call mutation.mutate(...) at AddItem.tsx:69 inside the body of onSubmit (68-70)', recv && inside ? 'pass' : 'fail', recv ? `CallExpression mutation.mutate(...) at 69; enclosing ${enclosingDecls(recv).map(d => d.name + '@' + d.line + '-' + d.end).join(' > ')}` : 'no call mutation.mutate at line 69'));
    const r = recv ? resolveIdent(recv) : {state: 'none'};
    const ok2 = r.state === 'resolved' && r.decls.some(d => d.file === AT && d.stmt_line === 55 && d.stmt_end === 66);
    res.checks.push(chk('binding_resolution', 'relationship', null, [site, loc(AT, 55, 66, 'input', 'declaration')], 'receiver mutation at AddItem.tsx:69 resolves to const mutation = useMutation({...}) at AddItem.tsx:55-66', ok2 ? 'pass' : r.state === 'resolved' ? 'fail' : 'inconclusive', r.decls ? `resolves to ${r.decls.map(d => fmtD(d) + ' stmt ' + d.stmt_line + '-' + d.stmt_end).join('; ')}` : (r.reason || 'not found')));
    return res;
  },
  L3(t) {
    const res = {checks: []}; const site = loc(AT, 56, 56, 'site', 'site');
    const svc = identAt(AT, 56, 'ItemsService', i => ts.isPropertyAccessExpression(i.parent) && i.parent.expression === i && i.parent.name.text === 'createItem')[0];
    let ok = false, detail = 'no ItemsService.createItem(...) call at line 56';
    if (svc) { const pa = svc.parent; const call = pa.parent; let n = call; while (n && !(ts.isPropertyAssignment(n))) n = n.parent;
      const obj = n && n.parent; const outer = obj && obj.parent;
      ok = ts.isCallExpression(call) && call.expression === pa && n && n.name.getText() === 'mutationFn' && ts.isObjectLiteralExpression(obj) && ts.isCallExpression(outer) && outer.expression.getText() === 'useMutation' && outer.arguments[0] === obj && enclosingDecls(svc).some(d => d.name === 'AddItem' && d.line === 40);
      detail = `call ${pa.getText()}(...) inside property ${n ? n.name.getText() : '?'} of the object passed to ${outer && outer.expression ? outer.expression.getText() : '?'}(...); enclosing ${enclosingDecls(svc).map(d => d.name + '@' + d.line).join(' > ')}`; }
    res.checks.push(chk('syntax_structure', 'relationship', null, [site], 'call ItemsService.createItem(...) at AddItem.tsx:56 inside the mutationFn property of the object passed to useMutation, in AddItem', ok ? 'pass' : 'fail', detail));
    const r1 = svc ? resolveIdent(svc) : {state: 'none', chain: []}; const mem = svc ? resolveIdent(svc.parent.name) : {state: 'none'};
    const ok1 = r1.state === 'resolved' && r1.decls.some(d => d.file === SDK && d.start_line === 287) && chainOk(r1, [{file: AT, line: 8}, {file: IDX, line: 3}]);
    const ok2 = mem.state === 'resolved' && mem.decls.some(d => d.file === SDK && d.start_line <= 307 && 307 <= d.end_line && d.name_line === 307);
    res.checks.push(chk('binding_resolution', 'relationship', null, [site, loc(AT, 8, 8, 'input', 'site'), loc(IDX, 3, 3, 'input', 'site'), loc(SDK, 287, 287, 'input', 'declaration'), loc(SDK, 307, 318, 'to_decl', 'declaration')],
      'ItemsService at AddItem.tsx:56 resolves through the import at AddItem.tsx:8 and the re-export at client/index.ts:3 to class ItemsService (sdk.gen.ts:287); member createItem resolves to sdk.gen.ts:307-318', ok1 && ok2 ? 'pass' : (r1.state === 'resolved' && mem.state === 'resolved') ? 'fail' : 'inconclusive',
      `ItemsService via ${r1.chain.map(fmtD).join(' -> ')} to ${r1.decls ? r1.decls.map(fmtD).join(';') : r1.reason}; createItem to ${mem.decls ? mem.decls.map(d => fmtD(d) + ' name line ' + d.name_line).join(';') : mem.reason}`));
    return res;
  },
  H1(t) { const id = identAt(AT, 88, 'handleSubmit')[0]; const r = id ? resolveIdent(id) : {reason: 'not found'};
    return {checks: [chk('binding_resolution', 'relationship', null, [loc(AT, 88, 88, 'site', 'site')], 'form.handleSubmit invokes onSubmit (library behavior)', 'inconclusive', `handleSubmit at AddItem.tsx:88: ${r.state === 'resolved' ? 'resolves to ' + r.decls.map(fmtD).join(';') : r.reason}; react-hook-form is not installed, and what the library does with the callback is not visible in repo source`)]}; },
  H2(t) { const id = identAt(AT, 69, 'mutate')[0]; const r = id ? resolveIdent(id) : {reason: 'not found'};
    return {checks: [chk('binding_resolution', 'relationship', null, [loc(AT, 69, 69, 'site', 'site'), loc(AT, 56, 56, 'input', 'site')], 'mutation.mutate invokes the mutationFn given to useMutation (library behavior)', 'inconclusive', `mutate at AddItem.tsx:69: ${r.state === 'resolved' ? 'resolves to ' + r.decls.map(fmtD).join(';') : r.reason}; @tanstack/react-query is not installed, and what the library does with mutationFn is not visible in repo source`)]}; },
};
// R3 TS facts: every static method of every *Service class in sdk.gen.ts; Data type url literals; openapi-ts config
function r3facts() {
  const out = {sdk_methods: [], data_types: [], config: {}, file_versions: {}};
  const sf = sourceFile(SDK).sf;
  for (const st of sf.statements) {
    if (!ts.isClassDeclaration(st) || !st.name || !/Service$/.test(st.name.text)) continue;
    for (const m of st.members) {
      if (!ts.isMethodDeclaration(m) || !(m.modifiers || []).some(x => x.kind === ts.SyntaxKind.StaticKeyword)) continue;
      const param = m.parameters[0]; let dataType = null, dataLine = null;
      if (param && param.type && ts.isTypeReferenceNode(param.type) && param.type.typeArguments && param.type.typeArguments[0] && ts.isTypeReferenceNode(param.type.typeArguments[0])) { dataType = param.type.typeArguments[0].typeName.getText(sf); dataLine = ln(sf, param.type.typeArguments[0].getStart(sf)); }
      let call = null; (function w(n) { if (!call && ts.isCallExpression(n) && ts.isPropertyAccessExpression(n.expression) && ['get', 'post', 'put', 'patch', 'delete', 'head', 'options'].includes(n.expression.name.text)) call = n; ts.forEachChild(n, w); })(m);
      let url = null, urlLine = null;
      if (call && call.arguments[0] && ts.isObjectLiteralExpression(call.arguments[0])) for (const p of call.arguments[0].properties) if (ts.isPropertyAssignment(p) && p.name.getText(sf) === 'url' && ts.isStringLiteral(p.initializer)) { url = p.initializer.text; urlLine = ln(sf, p.getStart(sf)); }
      let dataResolves = null;
      if (dataType) { const tn = param.type.typeArguments[0].typeName; const r = resolveIdent(ts.isIdentifier(tn) ? tn : tn.right); dataResolves = r.state === 'resolved' ? r.decls.map(d => ({file: d.file, start_line: d.start_line, end_line: d.end_line})) : r.reason; }
      out.sdk_methods.push({class: st.name.text, class_line: ln(sf, st.getStart(sf)), method: m.name.getText(sf), method_line: ln(sf, m.getStart(sf)), method_end: ln(sf, m.getEnd()), name_line: ln(sf, m.name.getStart(sf)),
        http: call ? call.expression.name.text : null, http_line: call ? ln(sf, call.expression.name.getStart(sf)) : null, url, url_line: urlLine, data_type: dataType, data_type_line: dataLine, data_type_resolves_to: dataResolves});
    }
  }
  const tf = sourceFile(TYP).sf;
  for (const st of tf.statements) {
    if (!ts.isTypeAliasDeclaration(st) || !/Data$/.test(st.name.text) || !ts.isTypeLiteralNode(st.type)) continue;
    let url = null, urlLine = null;
    for (const m of st.type.members) if (ts.isPropertySignature(m) && m.name.getText(tf) === 'url' && m.type && ts.isLiteralTypeNode(m.type) && ts.isStringLiteral(m.type.literal)) { url = m.type.literal.text; urlLine = ln(tf, m.getStart(tf)); }
    out.data_types.push({name: st.name.text, line: ln(tf, st.getStart(tf)), end: ln(tf, st.getEnd()), url, url_line: urlLine});
  }
  const cf = sourceFile(CFG).sf;
  (function w(n) { if (ts.isPropertyAssignment(n)) { const k = n.name.getText(cf); if (['input', 'output', 'strategy', 'containerName', 'methodName', 'name'].includes(k) || k === 'plugins') {
      if (!out.config[k]) out.config[k] = []; out.config[k].push({line: ln(cf, n.getStart(cf)), text: n.initializer.getText(cf).slice(0, 200), kind: ts.SyntaxKind[n.initializer.kind],
        regex: ts.isArrowFunction(n.initializer) ? (() => { let rx = null; (function q(x) { if (!rx && ts.isRegularExpressionLiteral(x)) rx = x.text; ts.forEachChild(x, q); })(n.initializer); return rx; })() : null,
        replace_with: ts.isArrowFunction(n.initializer) ? (() => { let s = null; (function q(x) { if (s === null && ts.isCallExpression(x) && ts.isPropertyAccessExpression(x.expression) && x.expression.name.text === 'replace' && x.arguments[1] && ts.isStringLiteral(x.arguments[1])) s = x.arguments[1].text; ts.forEachChild(x, q); })(n.initializer); return s; })() : null}); } }
    ts.forEachChild(n, w); })(cf);
  // generator version header comments
  out.sdk_header = sf.getFullText().split('\n')[0]; out.types_header = tf.getFullText().split('\n')[0];
  return out;
}
const results = {};
for (const t of job.tasks) {
  try {
    useCtxFor(t.file || (t.src ? (t.rel_kind === 'contains' ? t.tgt.file : t.src.file) : 'frontend/'));
    let r;
    if (t.type === 'node') r = nodePresence(t);
    else if (t.type === 'unresolved') r = unresolvedPresence(t);
    else if (t.type === 'edge') r = edge(t);
    else if (t.type === 'fixture') r = fixture[t.fixture](t);
    else if (t.type === 'r3facts') r = {facts: r3facts()};
    results[t.rk] = r;
  } catch (e) { results[t.rk] = {checks: [chk('parser_presence', 'presence', null, [], 'validator ran', 'error', String(e && e.stack || e).slice(0, 500))], error: true}; }
}
fs.writeFileSync(outPath, JSON.stringify({validator: VALIDATOR, node: process.version, programs: Object.fromEntries(Object.entries(CTXS).map(([k, c]) => [k, {repo_files: c.repoFiles.length, config_errors: c.configErrors.map(e => ts.flattenDiagnosticMessageText(e.messageText, ' ')), options: {moduleResolution: c.options.moduleResolution, paths: c.options.paths, jsx: c.options.jsx}}])), results}));
console.log(`ts_validate: ${job.tasks.length} tasks, typescript ${ts.version}, node ${process.version}, program repo files ${Object.entries(CTXS).map(([k, c]) => k + '=' + c.repoFiles.length).join(' ')}`);
