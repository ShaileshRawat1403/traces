// JavaScript module-reference parser for the import check (D-030). TypeScript 6.0.3 parser only (Apache-2.0, already
// pinned in toolchain/); no Program, no type checker, no module resolution here and no target code is executed.
// For each requested file it reads the clean checkout, checks the bytes against the git blob id at the pinned SHA, parses
// it as JavaScript and lists every static module reference: import/export ... from 'x', require('x') and import('x')
// with a string-literal specifier. Resolution of the specifier to a repo file happens in Python (js_imports.py).
// Usage: TS_MODULE=... node js_imports.js <job.json> <out.json>    job = {root, sha, files: [repo-relative paths]}
'use strict';
const ts = require(process.env.TS_MODULE);
const fs = require('fs'), path = require('path'), crypto = require('crypto'), cp = require('child_process');
const [jobPath, outPath] = process.argv.slice(2);
const job = JSON.parse(fs.readFileSync(jobPath, 'utf8'));
const blobs = new Map();
const ls = cp.execFileSync('git', ['-C', job.root, 'ls-tree', '-r', '-z', '--full-tree', job.sha], {encoding: 'utf8', env: {...process.env, GIT_OPTIONAL_LOCKS: '0'}, maxBuffer: 1 << 26});
for (const l of ls.split('\0')) { const i = l.indexOf('\t'); if (i > 0) blobs.set(l.slice(i + 1), l.slice(0, i).split(' ')[2]); }
const isStr = (n) => n && (n.kind === ts.SyntaxKind.StringLiteral || n.kind === ts.SyntaxKind.NoSubstitutionTemplateLiteral);
const out = {};
for (const rel of job.files) {
  const want = blobs.get(rel);
  if (!want) { out[rel] = {error: 'not in the tree at the pinned SHA'}; continue; }
  const buf = fs.readFileSync(path.join(job.root, rel));
  const got = crypto.createHash('sha1').update(`blob ${buf.length}\0`).update(buf).digest('hex');
  if (got !== want) { out[rel] = {error: `blob mismatch (${got} != ${want})`}; continue; }
  const kind = rel.endsWith('.jsx') ? ts.ScriptKind.JSX : ts.ScriptKind.JS;
  const sf = ts.createSourceFile(rel, buf.toString('utf8'), ts.ScriptTarget.Latest, true, kind);
  const line = (pos) => sf.getLineAndCharacterOfPosition(pos).line + 1;
  const refs = []; let shadowed = [];
  const add = (how, node, spec) => refs.push({how, spec: spec.text, start_line: line(node.getStart(sf)), end_line: line(node.getEnd()), spec_line: line(spec.getStart(sf))});
  const visit = (n) => {
    if ((n.kind === ts.SyntaxKind.ImportDeclaration || n.kind === ts.SyntaxKind.ExportDeclaration) && isStr(n.moduleSpecifier)) {
      add(n.kind === ts.SyntaxKind.ImportDeclaration ? 'import' : 'export', n, n.moduleSpecifier);
    } else if (n.kind === ts.SyntaxKind.CallExpression && n.arguments.length === 1 && isStr(n.arguments[0])) {
      if (n.expression.kind === ts.SyntaxKind.Identifier && n.expression.text === 'require') add('require', n, n.arguments[0]);
      else if (n.expression.kind === ts.SyntaxKind.ImportKeyword) add('dynamic_import', n, n.arguments[0]);
    }
    // a local binding named `require` means require(...) is not Node's require: the check will not trust it
    if ((n.kind === ts.SyntaxKind.VariableDeclaration || n.kind === ts.SyntaxKind.FunctionDeclaration || n.kind === ts.SyntaxKind.Parameter
         || n.kind === ts.SyntaxKind.ImportSpecifier || n.kind === ts.SyntaxKind.ImportClause || n.kind === ts.SyntaxKind.BindingElement)
        && n.name && n.name.kind === ts.SyntaxKind.Identifier && n.name.text === 'require') shadowed.push(line(n.getStart(sf)));
    ts.forEachChild(n, visit);
  };
  visit(sf);
  out[rel] = {blob_sha: want, refs, require_shadowed_at: shadowed, parse_errors: (sf.parseDiagnostics || []).length};
}
fs.writeFileSync(outPath, JSON.stringify({parser: 'typescript ' + ts.version, files: out}));
