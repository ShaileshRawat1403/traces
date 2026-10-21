// Count TypeScript 5.9.3 parse diagnostics per indexed TS/TSX file. Usage: node ts_parse_diag.js <root> <files...>
const ts = require(process.env.TS_MODULE || '/workspace/traces-research/task002/tools/node_modules/typescript'); const fs = require('fs'), path = require('path');
let n = 0, bad = 0;
for (const rel of process.argv.slice(3)) { n++;
  const sf = ts.createSourceFile(rel, fs.readFileSync(path.join(process.argv[2], rel), 'utf8'), ts.ScriptTarget.Latest, true, rel.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  if (sf.parseDiagnostics.length) { bad++; console.log(rel, sf.parseDiagnostics.length, ts.flattenDiagnosticMessageText(sf.parseDiagnostics[0].messageText, ' ')); } }
console.log(`typescript ${ts.version}: files=${n} files_with_parse_diagnostics=${bad}`);
