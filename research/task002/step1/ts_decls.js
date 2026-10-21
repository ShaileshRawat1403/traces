// Independent TS/TSX declaration extractor using the TypeScript compiler API (pinned 5.9.3).
// Usage: node ts_decls.js <repo_root> <file>... ; reads files from disk (clean checkout at the pinned SHA).
// Emits JSON lines: {file, name, kind, start (1-based line of node start, no trivia), nameLine, end, parent}
const ts = require(process.env.TS_MODULE || '/workspace/traces-research/task002/tools/node_modules/typescript');
const fs = require('fs'), path = require('path');
const root = process.argv[2];
for (const rel of process.argv.slice(3)) {
  const text = fs.readFileSync(path.join(root, rel), 'utf8');
  const sf = ts.createSourceFile(rel, text, ts.ScriptTarget.Latest, true, rel.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  const ln = p => sf.getLineAndCharacterOfPosition(p).line + 1;
  const out = (name, kind, node, nameNode, parent) => console.log(JSON.stringify({file: rel, name, kind, start: ln(node.getStart(sf)), nameLine: ln(nameNode.getStart(sf)), end: ln(node.getEnd()), parent}));
  function visit(node, parent) {
    let here = parent;
    if ((ts.isFunctionDeclaration(node) || ts.isClassDeclaration(node) || ts.isInterfaceDeclaration(node) || ts.isTypeAliasDeclaration(node) || ts.isMethodDeclaration(node) || ts.isEnumDeclaration(node)) && node.name) {
      const k = ts.SyntaxKind[node.kind]; out(node.name.getText(sf), k, node, node.name, parent); here = node.name.getText(sf);
    } else if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name)) {
      const init = node.initializer; const fn = init && (ts.isArrowFunction(init) || ts.isFunctionExpression(init));
      // report the statement span for the variable (matches 'const X = ...' line)
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
