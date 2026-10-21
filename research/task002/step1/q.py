"""Read-only SQL against the CodeGraph index. Usage: q.py "<sql>" """
import sqlite3,sys,json
c=sqlite3.connect("file:/workspace/traces-research/task002/src/fsft/.codegraph/codegraph.db?mode=ro",uri=True)
cur=c.execute(sys.argv[1]); cols=[d[0] for d in cur.description]
print("\t".join(cols))
for r in cur: print("\t".join("" if v is None else str(v) for v in r))
