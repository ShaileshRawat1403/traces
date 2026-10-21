import sqlite3,sys
c=sqlite3.connect("file:src/fsft/.codegraph/codegraph.db?mode=ro",uri=True)
print("user_version",c.execute("pragma user_version").fetchone())
for (n,s) in c.execute("select name,sql from sqlite_master where type='table'"):
    print("TABLE",n); print(s)
for t in ("schema_versions","project_metadata","metadata"):
    try: print(t, c.execute(f"select * from {t}").fetchall())
    except Exception as e: print(t,"ERR",e)
