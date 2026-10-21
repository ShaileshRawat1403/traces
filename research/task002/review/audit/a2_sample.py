import json, random, collections, subprocess
SHA='b1125d8839482cb7bbae603ddc6d0081bf87532e'; ROOT='src/fsft'
recs=[json.loads(l) for l in open('out/evidence.jsonl')]
ver=[r for r in recs if r['status']=='verified' and r['originator']['name']=='codegraph']
def lang(r): return 'py' if r['from']['file'].endswith('.py') else 'ts'
strata=collections.defaultdict(list)
for r in ver:
    nm = r['provenance']=='codegraph:name-match'
    strata[(r['relationship_kind'],lang(r),'NM' if nm else 'other')].append(r)
random.seed(20261021)
quota={}
for k,v in strata.items(): quota[k]= (6 if k[2]=='NM' else 2)
sample=[]
for k in sorted(strata):
    v=sorted(strata[k],key=lambda r:r['claim_id'])
    sample += random.sample(v, min(quota[k],len(v)))
print('strata', {('|'.join(k)):len(v) for k,v in sorted(strata.items())})
print('sample size', len(sample), 'name-match', sum(r['provenance']=='codegraph:name-match' for r in sample))
json.dump([r['claim_id'] for r in sample], open('review/audit/sample_ids.json','w'))
