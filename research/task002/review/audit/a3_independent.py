"""Traces audit re-check of sampled verified edges. Own implementation, not Lab's validators.
Python: CPython 3.14 ast with an auditor-written resolver. TS: auditor-written text resolver of import statements.
Reads blobs with git show at the pinned SHA. Writes only review/audit/."""
import json, ast, re, subprocess, os, sys
SHA='b1125d8839482cb7bbae603ddc6d0081bf87532e'; ROOT='src/fsft'
env=dict(os.environ, GIT_OPTIONAL_LOCKS='0')
_c={}
def blob(p):
    if p not in _c:
        try: _c[p]=subprocess.run(['git','-C',ROOT,'show',f'{SHA}:{p}'],capture_output=True,text=True,env=env,check=True).stdout
        except subprocess.CalledProcessError: _c[p]=None
    return _c[p]
def exists(p): return blob(p) is not None
def line(p,n):
    t=blob(p); L=t.split('\n'); return L[n-1] if 0<n<=len(L) else None
ids=json.load(open('review/audit/sample_ids.json'))
recs={}
for l in open('out/evidence.jsonl'):
    r=json.loads(l)
    if r['claim_id'] in ids: recs[r['claim_id']]=r
def short(sym): return sym.split('::')[-1].split('.')[-1]
# ---------- python ----------
def pymodfile(mod):
    for root in ('backend',):
        for c in (f"{root}/{mod.replace('.','/')}.py", f"{root}/{mod.replace('.','/')}/__init__.py"):
            if exists(c): return c
    return None
def py_decl_at(p, name, ln):
    tr=ast.parse(blob(p))
    for n in ast.walk(tr):
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) and n.name==name:
            if ln in [n.lineno]+[d.lineno for d in n.decorator_list]: return True
        if isinstance(n,(ast.Assign,ast.AnnAssign)):
            tg=n.targets if isinstance(n,ast.Assign) else [n.target]
            if any(isinstance(x,ast.Name) and x.id==name for x in tg) and n.lineno==ln: return True
    return False
def py_bind(p, name):
    """where does module-level name come from in p: ('file', path) for from-imports/defs, ('module', path) for module imports"""
    tr=ast.parse(blob(p)); pkg=os.path.dirname(p).replace('backend/','',1).replace('/','.')
    out=[]
    for n in tr.body:
        if isinstance(n,ast.ImportFrom):
            mod=n.module or ''
            if n.level: base=pkg.split('.'); base=base[:len(base)-(n.level-1)] if n.level>1 else base; mod='.'.join(base+([mod] if mod else []))
            for a in n.names:
                if (a.asname or a.name)==name:
                    sub=pymodfile(f'{mod}.{a.name}')
                    out.append(('module',sub) if sub and not (pymodfile(mod) and a.name in [getattr(x,'name',None) for x in ast.walk(ast.parse(blob(pymodfile(mod))))]) else ('from',pymodfile(mod),a.name))
        if isinstance(n,ast.Import):
            for a in n.names:
                if (a.asname or a.name.split('.')[0])==name: out.append(('module',pymodfile(a.name)))
        if isinstance(n,(ast.FunctionDef,ast.ClassDef,ast.AsyncFunctionDef)) and n.name==name: out.append(('local',p,name))
        if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in n.targets): out.append(('local',p,name))
    return out
def py_check(r, site):
    p=r['from']['file']; tgt=r['to']; nm=short(tgt['symbol']); k=r['relationship_kind']
    tr=ast.parse(blob(p)); L=site
    if k=='contains':
        par=r['from']; 
        for n in ast.walk(tr):
            for ch in ast.iter_child_nodes(n): pass
        # nearest enclosing def/class of the child
        best=None
        def walk(n,anc):
            nonlocal best
            for ch in ast.iter_child_nodes(n):
                nm2=getattr(ch,'name',None)
                if isinstance(ch,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) and ch.name==nm and tgt['start_line'] in [ch.lineno]+[d.lineno for d in ch.decorator_list]: best=anc
                walk(ch, ch if isinstance(ch,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) else anc)
        walk(tr,None)
        if best is None and par['symbol'].endswith('::'+par['file']): 
            top=[n for n in tr.body if getattr(n,'lineno',0)==tgt['start_line'] or (hasattr(n,'decorator_list') and any(d.lineno==tgt['start_line'] for d in n.decorator_list))]
            return bool(top), f"module-level statement at {tgt['start_line']}: {bool(top)}"
        return (best is not None and best.name==short(par['symbol'])), f"nearest enclosing of {nm}: {getattr(best,'name',None)}"
    if k=='imports':
        st=[n for n in tr.body if isinstance(n,(ast.Import,ast.ImportFrom)) and n.lineno<=L<=n.end_lineno]
        if not st: return False,'no import stmt'
        n=st[0]
        if tgt['symbol']==tgt['file']+'::'+tgt['file']: # file target
            b=[]; mod=n.module if isinstance(n,ast.ImportFrom) else None
            fs=[pymodfile(a.name) for a in n.names] if isinstance(n,ast.Import) else [pymodfile(n.module)]+[pymodfile(f"{n.module}.{a.name}") for a in n.names]
            return tgt['file'] in fs, f"import resolves to {fs}"
        names=[a for a in n.names if (a.asname or a.name)==nm]
        if not names: return False, f"stmt binds {[a.name for a in n.names]}"
        f=pymodfile(n.module) if isinstance(n,ast.ImportFrom) else None
        return f==tgt['file'] and py_decl_at(f,nm,tgt['start_line']), f"from {n.module} ({f}) import {nm}; decl at {tgt['start_line']}"
    if k in ('calls','instantiates','references','extends'):
        hits=[]
        for n in ast.walk(tr):
            if isinstance(n,ast.Name) and n.id==nm and n.lineno==L: hits.append(('name',n))
            if isinstance(n,ast.Attribute) and n.attr==nm and n.lineno<=L<=n.end_lineno: hits.append(('attr',n))
        if not hits: return False,'name not at site'
        for kind,n in hits:
            if kind=='name':
                for b in py_bind(p,nm):
                    if b[0]=='from' and b[1]==tgt['file'] and py_decl_at(b[1],nm,tgt['start_line']): return True, f"{nm} from-import of {b[1]}"
                    if b[0]=='local' and p==tgt['file'] and py_decl_at(p,nm,tgt['start_line']): return True, f"{nm} module-level in same file"
                if p==tgt['file'] and py_decl_at(p,nm,tgt['start_line']): return True, f"{nm} defined in same file (nested or module)"
            else:
                v=n.value
                if isinstance(v,ast.Name):
                    for b in py_bind(p,v.id):
                        if b[0]=='module' and b[1]==tgt['file'] and py_decl_at(b[1],nm,tgt['start_line']): return True, f"{v.id}.{nm}: {v.id} is module {b[1]}"
                        if b[0] in ('from','local') and (b[1]==tgt['file']):
                            # class attribute
                            if py_decl_at(tgt['file'],nm,tgt['start_line']): return True, f"{v.id}.{nm}: {v.id} bound to {b[1]}"
        return False, f"hits {[(k2,ast.unparse(n)) for k2,n in hits]} did not resolve to target"
    return None,'kind not covered'
# ---------- typescript (text resolver) ----------
EXT=['','.ts','.tsx','/index.ts','/index.tsx','.d.ts']
def ts_resolve(fromf, spec):
    if spec.startswith('@/'): base='frontend/src/'+spec[2:]
    elif spec.startswith('.'): base=os.path.normpath(os.path.join(os.path.dirname(fromf),spec))
    else: return None
    for e in EXT:
        if exists(base+e) and not (base+e).endswith('/'): 
            if e=='' and not re.search(r'\.(tsx?|js)$',base): continue
            return base+e
    return None
IMP=re.compile(r'(?:import|export)\s+(type\s+)?([\s\S]*?)\s+from\s+["\']([^"\']+)["\']',re.M)
EXP=re.compile(r'export\s+(type\s+)?\{([\s\S]*?)\}\s+from\s+["\']([^"\']+)["\']',re.M)
def ts_imports(f):
    t=blob(f); out={}
    for m in IMP.finditer(t):
        clause, spec = m.group(2), m.group(3); start=t[:m.start()].count('\n')+1; end=t[:m.end()].count('\n')+1
        dm=re.match(r'^([A-Za-z_$][\w$]*)\s*(,|$)',clause.strip())
        if dm and not clause.strip().startswith('{'): out[dm.group(1)]=(spec,'default',start,end)
        for b in re.findall(r'\{([\s\S]*?)\}',clause):
            for part in b.split(','):
                part=part.strip().replace('type ','')
                if not part: continue
                a=re.split(r'\s+as\s+',part); out[a[-1].strip()]=(spec,a[0].strip(),start,end)
        nm=re.search(r'\*\s+as\s+(\w+)',clause)
        if nm: out[nm.group(1)]=(spec,'*',start,end)
    return out
def ts_follow(f, name, depth=0):
    """file where exported `name` is declared, following one re-export layer"""
    t=blob(f)
    if re.search(rf'(export\s+)?(default\s+)?(async\s+)?(function|class|interface|type|const|let|enum)\s+{re.escape(name)}\b',t): return f
    if depth<2:
        for m in EXP.finditer(t):
            names=[re.split(r'\s+as\s+',x.strip().replace('type ',''))[-1] for x in m.group(2).split(',')]
            if name in names:
                g=ts_resolve(f,m.group(3)); return ts_follow(g,name,depth+1) if g else None
        for m in re.finditer(r'export\s+\*\s+from\s+["\']([^"\']+)["\']',t):
            g=ts_resolve(f,m.group(1))
            if g:
                h=ts_follow(g,name,depth+1)
                if h: return h
    return None
def ts_decl_line(f,name,ln):
    s=line(f,ln) or ''
    return re.search(rf'\b{re.escape(name)}\b',s) is not None
def ts_check(r, site):
    f=r['from']['file']; tgt=r['to']; nm=short(tgt['symbol']); k=r['relationship_kind']; L=site
    s=line(f,L) or ''
    if k=='contains':
        par=r['from']; ok=par['start_line']<=tgt['start_line']<=tgt['end_line']<=par['end_line'] and ts_decl_line(tgt['file'],nm,tgt['start_line'])
        return ok, f"range nesting {par['start_line']}-{par['end_line']} contains {tgt['start_line']}-{tgt['end_line']} and '{nm}' on decl line (weak: no AST)"
    imps=ts_imports(f)
    if k=='imports':
        hit=[(n,v) for n,v in imps.items() if v[2]<=L<=v[3]]
        if not hit: return False,'no import spanning site'
        spec=hit[0][1][0]; g=ts_resolve(f,spec)
        if tgt['symbol']==tgt['file']+'::'+tgt['file']: return g==tgt['file'], f"'{spec}' resolves to {g}"
        cand=[v for n,v in hit if n==nm or v[1]==nm]
        if not cand: return False, f"no binding {nm} in {[n for n,_ in hit]}"
        v=cand[0]; src=ts_follow(g, v[1] if v[1] not in ('default','*') else nm) if g else None
        if v[1]=='default' and g: src=g
        return src==tgt['file'] and ts_decl_line(tgt['file'], nm if v[1]=='default' else v[1], tgt['start_line']), f"'{nm}' from '{spec}' -> {src}"
    if not re.search(rf'\b{re.escape(nm)}\b',s): return False,f"'{nm}' not on site line {L}: {s.strip()[:80]}"
    if k=='renders' and not re.search(rf'<{re.escape(nm)}\b|<[\w.]*\.{re.escape(nm)}\b',s): return False,'no JSX tag'
    # receiver: X.nm or bare nm
    m=re.search(rf'([A-Za-z_$][\w$]*)\s*\??\.\s*{re.escape(nm)}\b',s)
    head = m.group(1) if m and m.group(1)!='this' else nm
    if head in imps:
        spec,orig,_,_=imps[head]; g=ts_resolve(f,spec)
        if not g: return False, f"{head} from library '{spec}'"
        if head==nm:
            src = g if orig=='default' else ts_follow(g, orig)
        else:
            cls = g if orig=='default' else ts_follow(g, orig); src=cls
        return src==tgt['file'] and ts_decl_line(tgt['file'],nm,tgt['start_line']), f"{head} imported from '{spec}' -> {src}"
    if tgt['file']==f and ts_decl_line(f,nm,tgt['start_line']): return True, f"'{nm}' declared in same file at {tgt['start_line']}"
    return False, f"'{head}' not imported and target not in same file"
rows=[]
for cid in ids:
    r=recs[cid]
    sites=[l['start_line'] for l in sorted(r['locations'],key=lambda l:l['source']!='validator') if l['role']=='site' and l['range_kind']=='site']
    site=sites[0] if sites else r['to']['start_line']
    est=[c for c in r['checks'] if c['establishes']=='relationship' and c['result']=='pass']
    if r['from']['file'].endswith('.py'):
        if (r['provenance_raw'].get('endpoint_rows',{}).get('source') or {}).get('kind')=='route':
            dec=line(r['from']['file'],site) or ''; nxt=py_decl_at(r['to']['file'],short(r['to']['symbol']),r['to']['start_line'])
            ok,why=('@router.' in dec and nxt), f"decorator line '{dec.strip()[:60]}' and def {short(r['to']['symbol'])} at {r['to']['start_line']}"
        else: ok,why=py_check(r,site)
    else: ok,why=ts_check(r,site)
    rows.append({'claim_id':cid,'kind':r['relationship_kind'],'prov':r['provenance'],'from':r['from']['symbol'],'to':r['to']['symbol'],'to_line':r['to']['start_line'],'site':site,
      'site_text':(line(r['from']['file'],site) or '').strip()[:100] if site else None,
      'lab_methods':sorted({(c['method'],c.get('rule_id')) for c in est}),'lab_detail':est[0]['detail'][:160] if est else None,
      'audit_ok':ok,'audit_why':why})
json.dump(rows,open('review/audit/sample_results.json','w'),indent=1)
import collections
print(collections.Counter((r['audit_ok']) for r in rows))
for r in rows:
    if r['audit_ok'] is not True: print(json.dumps(r)[:600])
