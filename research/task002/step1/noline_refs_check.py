"""For the 'references' edges with no line: does the target name occur as a whole word inside the source node span at the SHA?"""
import sqlite3, subprocess, re
from collections import Counter
SHA="b1125d8839482cb7bbae603ddc6d0081bf87532e"; R="/workspace/traces-research/task002/src/fsft"
db=sqlite3.connect(f"file:{R}/.codegraph/codegraph.db?mode=ro",uri=True)
rows=db.execute("select s.file_path,s.start_line,s.end_line,s.qualified_name,t.name,t.file_path,t.start_line from edges e join nodes s on s.id=e.source join nodes t on t.id=e.target where e.line is null and e.kind='references'").fetchall()
c=Counter(); cache={}
for f,a,b,sn,tn,tf,ts in rows:
    if f not in cache: cache[f]=subprocess.check_output(["git","-C",R,"show",f"{SHA}:{f}"],text=True).splitlines()
    hits=[i+1 for i in range(a-1,b) if re.search(r"\b%s\b"%re.escape(tn),cache[f][i]) and i+1!=ts]
    c["token_in_source_span" if hits else "token_absent"]+=1
    if not hits: print("ABSENT",f,sn,tn)
print(len(rows),dict(c))
