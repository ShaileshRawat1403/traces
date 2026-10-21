"""Read-only SQL against the CodeGraph index, immutable mode (no -shm/-wal access). Usage: qi.py "<sql>" [db]"""
import sqlite3,sys
db = sys.argv[2] if len(sys.argv) > 2 else "/workspace/traces-research/task002/src/fsft/.codegraph/codegraph.db"
c=sqlite3.connect(f"file:{db}?mode=ro&immutable=1",uri=True)
cur=c.execute(sys.argv[1]); cols=[d[0] for d in cur.description]
print("\t".join(cols))
for r in cur: print("\t".join("" if v is None else str(v) for v in r))
