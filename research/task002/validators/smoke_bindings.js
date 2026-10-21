// Early binding-resolution smoke test (Task 002 request item 2). Read-only. Usage: TS_MODULE=... node smoke_bindings.js <root> <sha>
'use strict';
const P = require('./ts_program.js');
const [root, sha] = process.argv.slice(2);
const ctx = P.build(root, sha); const ts = ctx.ts;
console.log(`typescript ${ts.version}; node ${process.version}`);
console.log(`tsconfig parse errors: ${ctx.configErrors.length}`); ctx.configErrors.forEach(e => console.log('  ' + ts.flattenDiagnosticMessageText(e.messageText, ' ')));
console.log(`options: moduleResolution=${ts.ModuleResolutionKind[ctx.options.moduleResolution]} baseUrl=${ctx.options.baseUrl || '(none)'} paths=${JSON.stringify(ctx.options.paths)} pathsBasePath=${ctx.options.pathsBasePath}`);
console.log(`program repo files loaded: ${ctx.repoFiles.length}; blob mismatches vs ls-tree ${sha.slice(0,8)}: ${ctx.blobMismatches.length}`);
ctx.blobMismatches.forEach(m => console.log('  MISMATCH', JSON.stringify(m)));
const globalDiag = ctx.program.getGlobalDiagnostics().concat(ctx.program.getOptionsDiagnostics());
console.log(`options/global diagnostics: ${globalDiag.length}`); globalDiag.slice(0, 5).forEach(d => console.log('  ' + ts.flattenDiagnosticMessageText(d.messageText, ' ')));
const files = ['frontend/src/routes/_layout/items.tsx', 'frontend/src/components/Items/AddItem.tsx', 'frontend/src/client/index.ts', 'frontend/src/client/sdk.gen.ts', 'frontend/src/client/types.gen.ts'];
const tally = {module_resolved: 0, module_unresolved_local: 0, module_unresolved_library: 0, names_resolved: 0, names_unresolved: 0};
for (const f of files) {
  const sf = ctx.program.getSourceFile(root + '/' + f);
  console.log(`\n=== ${f} (in program: ${!!sf})`); if (!sf) continue;
  for (const st of sf.statements) {
    if (!(ts.isImportDeclaration(st) || (ts.isExportDeclaration(st) && st.moduleSpecifier))) continue;
    const spec = st.moduleSpecifier.text; const line = P.lineOf(sf, st.getStart(sf));
    const r = ts.resolveModuleName(spec, sf.fileName, ctx.options, ts.sys);
    const local = spec.startsWith('.') || spec.startsWith('@/');
    const target = r.resolvedModule ? P.rel(ctx, r.resolvedModule.resolvedFileName) : null;
    const k = target ? 'module_resolved' : (local ? 'module_unresolved_local' : 'module_unresolved_library'); tally[k]++;
    console.log(`${f}:${line} ${ts.isImportDeclaration(st) ? 'import' : 'export'} from "${spec}" -> ${target ? 'RESOLVED ' + target + (r.resolvedModule.isExternalLibraryImport ? ' (external)' : '') : 'UNRESOLVED' + (local ? ' (LOCAL)' : ' (library, not installed)')}`);
    const named = ts.isImportDeclaration(st) ? [st.importClause && st.importClause.name, ...((st.importClause && st.importClause.namedBindings && st.importClause.namedBindings.elements) || [])].filter(Boolean)
                                             : ((st.exportClause && st.exportClause.elements) || []);
    for (const el of named) {
      const id = el.name || el; if (!local) continue;
      const res = P.resolveAt(ctx, id);
      if (res.resolved) tally.names_resolved++; else tally.names_unresolved++;
      if (named.length > 6 && res.resolved && !['ItemsService', 'ItemCreate', 'itemsCreateItemData', 'AddItem', 'Options', 'client'].includes(id.text)) continue;
      console.log(`    name ${id.text}: ${res.resolved ? 'RESOLVED -> ' + res.decls.map(d => `${d.file}:${d.start_line}-${d.end_line} ${d.kind}`).join('; ') : 'UNRESOLVED (' + res.reason + ')'}${res.chain.length ? ' via ' + res.chain.length + ' alias hop(s)' : ''}`);
    }
  }
}
// Use-site checks for L1 to L4
function findIdent(f, line, text, nth = 0) {
  const sf = ctx.program.getSourceFile(root + '/' + f); let hits = [];
  (function walk(n) { if (ts.isIdentifier(n) && n.text === text && P.lineOf(sf, n.getStart(sf)) === line) hits.push(n); ts.forEachChild(n, walk); })(sf);
  return hits[nth];
}
console.log('\n=== use sites');
const sites = [['L1 tag <AddItem />', 'frontend/src/routes/_layout/items.tsx', 65, 'AddItem'], ['L2 onSubmit arg', 'frontend/src/components/Items/AddItem.tsx', 88, 'onSubmit', 1],
  ['L2 mutation receiver', 'frontend/src/components/Items/AddItem.tsx', 69, 'mutation'], ['L3 ItemsService', 'frontend/src/components/Items/AddItem.tsx', 56, 'ItemsService'],
  ['L3 createItem member', 'frontend/src/components/Items/AddItem.tsx', 56, 'createItem'], ['L4 itemsCreateItemData type arg', 'frontend/src/client/sdk.gen.ts', 307, 'itemsCreateItemData'],
  ['L2 handleSubmit (library)', 'frontend/src/components/Items/AddItem.tsx', 88, 'handleSubmit'], ['H2 mutate (library)', 'frontend/src/components/Items/AddItem.tsx', 69, 'mutate']];
for (const [label, f, line, text, nth] of sites) {
  const id = findIdent(f, line, text, nth || 0);
  if (!id) { console.log(`${label}: identifier ${text} not found at ${f}:${line}`); continue; }
  const res = P.resolveAt(ctx, id);
  console.log(`${label} ${f}:${line} '${text}': ${res.resolved ? 'RESOLVED -> ' + res.decls.map(d => `${d.file}:${d.start_line}-${d.end_line} ${d.kind}`).join('; ') : 'UNRESOLVED (' + res.reason + ')'}${res.chain.length ? ' via ' + res.chain.length + ' alias hop(s)' : ''}`);
}
console.log('\nTALLY ' + JSON.stringify(tally));
