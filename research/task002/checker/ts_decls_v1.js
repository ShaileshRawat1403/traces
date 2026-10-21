// line_checker_v1 TypeScript helper. VERSION = "line_checker_v1.0.0"
// Declaration extractor using the TypeScript compiler API (parser only, no type checking).
// Usage: TS_MODULE=<path to typescript package> node ts_decls_v1.js <source_root> <repo-relative file>...
// Output: one JSON object per line:
//   {file, name, kind, start, nameLine, end, parent}
//   start    = 1-based line of the node's first token (leading comments and whitespace excluded)
//   nameLine = 1-based line of the declared name
//   end      = 1-based line of the node's last character
//   parent   = name of the nearest enclosing named function/class/interface/type/enum/arrow-variable, or null
// For `const X = <arrow|function expression>` the node is the whole VariableStatement, so start is the `const` line.
'use strict';
const VERSION = 'line_checker_v1.0.0';
if (!process.env.TS_MODULE) { console.error('TS_MODULE not set'); process.exit(2); }
const ts = require(process.env.TS_MODULE);
const fs = require('fs'), path = require('path');
const root = process.argv[2];
for (const rel of process.argv.slice(3)) {
  const text = fs.readFileSync(path.join(root, rel), 'utf8');
  const sf = ts.createSourceFile(rel, text, ts.ScriptTarget.Latest, true, rel.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  if (sf.parseDiagnostics.length) console.log(JSON.stringify({file: rel, parse_diagnostics: sf.parseDiagnostics.length}));
  const ln = p => sf.getLineAndCharacterOfPosition(p).line + 1;
  const out = (name, kind, node, nameNode, parent) => console.log(JSON.stringify({file: rel, name, kind, start: ln(node.getStart(sf)), nameLine: ln(nameNode.getStart(sf)), end: ln(node.getEnd()), parent}));
  function visit(node, parent) {
    let here = parent;
    if ((ts.isFunctionDeclaration(node) || ts.isClassDeclaration(node) || ts.isInterfaceDeclaration(node) || ts.isTypeAliasDeclaration(node) || ts.isMethodDeclaration(node) || ts.isEnumDeclaration(node)) && node.name) {
      out(node.name.getText(sf), ts.SyntaxKind[node.kind], node, node.name, parent); here = node.name.getText(sf);
    } else if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name)) {
      const init = node.initializer; const fn = init && (ts.isArrowFunction(init) || ts.isFunctionExpression(init));
      const stmt = node.parent && node.parent.parent && ts.isVariableStatement(node.parent.parent) ? node.parent.parent : node;
      out(node.name.text, fn ? 'VariableFunction' : 'Variable', stmt, node.name, parent); if (fn) here = node.name.text;
    } else if (ts.isImportDeclaration(node)) {
      out(node.moduleSpecifier.text, 'ImportDeclaration', node, node.moduleSpecifier, parent);
    } else if ((ts.isPropertyAssignment(node) || ts.isPropertySignature(node) || ts.isPropertyDeclaration(node)) && node.name) {
      out(node.name.getText(sf), ts.SyntaxKind[node.kind], node, node.name, parent);
    }
    ts.forEachChild(node, c => visit(c, here));
  }
  visit(sf, null);
}
