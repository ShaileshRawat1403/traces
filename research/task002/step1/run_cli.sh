#!/usr/bin/env bash
# Step 1 CLI runs. Must be invoked through tools/offline.sh (network namespace, telemetry off).
cd /workspace/traces-research/task002/src/fsft
run(){ echo; echo "================================================================"; echo "\$ codegraph $*"; codegraph "$@"; echo "[exit=$?]"; }
# Q1/Q2 overview
run status --json
run files --format grouped --no-metadata
run query "route" -k route -l 50 -j
# Q3 connections
run callers create_user -f backend/app/crud.py -j
run callers authenticate -f backend/app/crud.py -j
run callers create_item -f backend/app/crud.py -j
run callers get_current_user -f backend/app/api/deps.py -j
run impact get_current_user -f backend/app/api/deps.py -j
run impact get_current_user -f backend/app/api/deps.py -d 3
run callers get_db -f backend/app/api/deps.py -j
run impact CurrentUser -f backend/app/api/deps.py -j
run impact SessionDep -f backend/app/api/deps.py -j
# Q4 create item trace
run query AddItem -l 10 -j
run callees AddItem -f frontend/src/components/Items/AddItem.tsx -j
run callers AddItem -f frontend/src/components/Items/AddItem.tsx -j
run query createItem -l 10 -j
run callers createItem -f frontend/src/client/sdk.gen.ts -j
run callees createItem -f frontend/src/client/sdk.gen.ts -j
run query create_item -l 10 -j
run callees create_item -f backend/app/api/routes/items.py -j
run callers create_item -f backend/app/api/routes/items.py -j
run impact create_item -f backend/app/api/routes/items.py -j
run query Item -k class -l 10 -j
run query ItemPublic -l 5 -j
run context "create an item from the frontend AddItem form through the API to the database" -f json --no-code
# login secondary trace
run callees login_access_token -f backend/app/api/routes/login.py -j
run callers loginAccessToken -f frontend/src/client/sdk.gen.ts -j
