"""For heuristic 'calls' edges (JSX render edges), check that '<Target' appears inside the source node span at the SHA."""
import sqlite3, subprocess, re
from collections import Counter
SHA="b1125d8839482cb7bbae603ddc6d0081bf87532e"; R="/workspace/traces-research/task002/src/fsft"
db=sqlite3.connect(f"file:{R}/.codegraph/codegraph.db?mode=ro",uri=True)
rows=db.execute("select s.file_path,s.start_line,s.end_line,s.name,t.name,t.file_path,e.line from edges e join nodes s on s.id=e.source join nodes t on t.id=e.target where e.kind='calls' and e.provenance='heuristic'").fetchall()
c=Counter(); bad=[]; cache={}
for f,a,b,sn,tn,tf,l in rows:
    if f not in cache: cache[f]=subprocess.check_output(["git","-C",R,"show",f"{SHA}:{f}"],text=True).splitlines()
    span="\n".join(cache[f][a-1:b]); m=re.search(r"<%s[\s/>.]"%re.escape(tn.split('::')[-1]),span)
    k=("jsx_tag_in_span" if m else "no_jsx_tag_in_span", "line_eq_source_start" if l==a else "line_is_tag_line" if m and cache[f][l-1].find("<"+tn)>=0 else "other_line")
    c[k]+=1
    if not m: bad.append((f,sn,tn,tf,l))
print(len(rows), dict(c)); [print(" ",x) for x in bad]
