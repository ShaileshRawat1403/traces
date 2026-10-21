"""Quantify records whose L2 result changes if the EOF position after a final newline is not a valid line (strict count)."""
import json, subprocess, collections, os
SHA='b1125d8839482cb7bbae603ddc6d0081bf87532e'; env=dict(os.environ,GIT_OPTIONAL_LOCKS='0')
C={}
def counts(f):
    if f not in C:
        t=subprocess.run(['git','-C','src/fsft','show',f'{SHA}:{f}'],capture_output=True,text=True,env=env).stdout
        C[f]=(len(t.split('\n')), len(t.splitlines()), t.endswith('\n'))
    return C[f]
recs=[json.loads(l) for l in open('out/evidence.jsonl')]
aff=[]; locaff=collections.Counter(); over=0
for r in recs:
    hit=[]
    for l in r['locations']:
        if l['role'] not in ('site','from_decl','to_decl','input'): continue
        nl,ns,_=counts(l['file'])
        if l['end_line']>nl: over+=1
        if ns < l['end_line'] <= nl: hit.append(l)
    if hit:
        aff.append((r,hit))
        for l in hit: locaff[(l['role'],l['range_kind'],l['range_rule'])]+=1
print('records total',len(recs),'records affected',len(aff),'locations beyond lenient count (should be 0):',over)
print('by claim_kind/status now -> strict:',collections.Counter((r['claim_kind'],r.get('relationship_kind') or r.get('node_kind') or '-',r['status']) for r,_ in aff).most_common())
print('by originator',collections.Counter(r['originator']['name'] for r,_ in aff))
print('by location role/range_kind/rule',locaff.most_common())
print('files involved',len({l['file'] for _,h in aff for l in h}))
# non-file range locations ending at EOF position (the substantive ones)
nf=[(r,h) for r,h in aff if any(l['range_kind']!='file' for l in h)]
print('records with a NON-file range ending at the EOF position:',len(nf))
for r,h in nf[:15]: print('  ',r['claim_kind'],r.get('relationship_kind'),r['status'],[(l['file'],l['start_line'],l['end_line'],l['range_kind'],l['role']) for l in h if l['range_kind']!='file'])
print('status change under strict L2: all affected -> rejected; from',collections.Counter(r['status'] for r,_ in aff))
