import json, collections
recs=[json.loads(l) for l in open('out/evidence.jsonl')]
REL={'syntax_structure','binding_resolution','deterministic_rule'}
bad=[];methods=collections.Counter();combo=collections.Counter()
def establishing(r):
    return [c for c in r['checks'] if c['result']=='pass' and c.get('independent') and c.get('establishes')=='relationship' and c['method'] in REL and c['validator']['family'] in ('cpython-ast','typescript-compiler') and not c.get('reads_originator_output')]
for r in recs:
    if r['status']!='verified': continue
    est=establishing(r)
    if not est: bad.append(r['claim_id']); continue
    sites=[l for l in r['locations'] if l['role']=='site']
    # V3: inputs include every site location
    ok=False
    for c in est:
        ins={(i['file'],i['start_line']) for i in c['inputs']}
        if all((s['file'],s['start_line']) in ins for s in sites): ok=True
    if not ok: combo['sites_not_in_establishing_inputs|'+r.get('relationship_kind','?')]+=1
    for c in est: methods[(r.get('relationship_kind'),c['method'],c.get('rule_id'))]+=1
    # presence-only check family
    if any(c['result']=='fail' and c.get('independent') for c in r['checks']): combo['verified_with_independent_fail']+=1
    if r.get('injected'): combo['verified_injected']+=1
print('verified records', sum(r['status']=='verified' for r in recs))
print('verified without establishing check', len(bad), bad[:5])
print(dict(combo))
for k,v in sorted(methods.items(), key=lambda t:(str(t[0][0]),-t[1])): print(v,k)
# observed records: presence check present?
nobs=[r for r in recs if r['status']=='observed' and not any(c['method']=='parser_presence' and c['result']=='pass' and c.get('independent') for c in r['checks'])]
print('observed without parser_presence', len(nobs))
print('status values', collections.Counter(r['status'] for r in recs)); print('labels',collections.Counter(r['label'] for r in recs))
print('label/status mismatch', sum(1 for r in recs if {'observed':'observed','verified':'verified'}.get(r['status'],'inferred')!=r['label']))
print('null required', sum(1 for r in recs for k in ('provenance','class','status','label','originator') if r.get(k) in (None,'')))
