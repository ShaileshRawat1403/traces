# Traces v1 demo script (10 minutes)

Owner: Traces Lab. Runs against the Traces Lab box app: web `http://127.0.0.1:5731`, API `http://127.0.0.1:8731`, build `35499bc`
(`/workspace/traces-review/traces`). Every expected result below was checked on 2026-10-23 at 12:32 IST by
`node tests/e2e/demo_walk.cjs` (15 of 15 steps PASS, local, read-only: page loads plus no-key explain, which writes nothing).
Screenshots from that run are in `.traces-data/acceptance/demo/shots/` (local, not committed).

Data is real: `fastapi/full-stack-fastapi-template@b1125d8839482cb7bbae603ddc6d0081bf87532e` (job `j_b3030040192949cd992a`) and
`pallets/itsdangerous@672971d66a2ef9f85151e53283113f33d642dabd` (job `j_d4c00e3c7141453898ef`), both indexed through the API.
No fixture, no manual database edit.

Shorthand: `F` = `/r/github.com__fastapi__full-stack-fastapi-template/s/b1125d8839482cb7bbae603ddc6d0081bf87532e`,
`I` = `/r/github.com__pallets__itsdangerous/s/672971d66a2ef9f85151e53283113f33d642dabd`.

| # | Time | Open or do | You should see |
| --- | --- | --- | --- |
| 1 | 0:00 | `http://127.0.0.1:5731/` | "Public GitHub repository URL", "Add repository", and the registered list: fastapi/full-stack-fastapi-template, pallets/itsdangerous ("latest seen @672971d"), pallets/markupsafe |
| 2 | 0:45 | `/jobs/j_d4c00e3c7141453898ef`, then click **Open the snapshot** | "Indexing finished", 100%, steps Fetch, Pin, Extract, Adapt, Validate, Store, History all Done. The button lands on the itsdangerous snapshot (`I`) |
| 3 | 1:30 | `F` | "@b1125d8" (pinned commit), "Snapshot ready", "Static analysis only. No runtime behavior has been observed.", "Architecture, by stored layer" with bands Frontend, Api, Backend, Data, Infra, Docs, Tests, Other |
| 4 | 2:15 | `F/graph` | "Architecture graph", components first, "155 nodes, 300 relationships, truncated at 300", "Rejected claims are never drawn.", hidden counts include "12 rejected" |
| 5 | 3:00 | `F/graph?q=create_item&view=list`, click **Open evidence** on "create_item depends_on get_db" | Evidence drawer: Verified, "LOCATIONS AT THE PINNED COMMIT", `backend/app/api/routes/items.py:63`, source "lines 60 to 66 of 113" at @b1125d8, and the check text "Depends(get_db) resolves to backend/app/api/deps.py:21" |
| 6 | 4:00 | `F/trace` | "From the screen to the persistence path": "10 steps ... 2 inferred library steps. 1 gap left open." Step 1 "Items shows AddItem." (Verified); step 2 a dashed gap; steps 4 and 6 dotted library steps ("react-hook-form is not installed", TanStack `mutate` to `mutationFn`); step 8 "operation POST /api/v1/items/ (items-create_item)"; step 10 "create_item depends on get_db." with "Static persistence path". Say: nothing was executed and no database was contacted |
| 7 | 5:15 | `F/review` | "12 matching claims", all Rejected: the 9 wrong CodeGraph imports (for example "imports 'app' at backend/app/api/routes/login.py:8") and the 3 injected negatives (for example "create_item uses_crud crud.py") |
| 8 | 6:00 | `F/history?tab=milestones` | "Showing 1 to 8 of 8 records." Milestone "Move new-frontend to frontend (#652)": "bulk move 96 files: new-frontend -> frontend", "Cites commit 9d703df". Git confirms: 96 renames in 9d703df (91 at 100% similarity) |
| 9 | 6:45 | `F/history?tab=cochange&target=backend/app/crud.py` | "It is not evidence of a code dependency", "backend/app/crud.py ... changed together in 5 of 26 commits". Say: co-change is a pattern, not a cause |
| 10 | 7:30 | `F/ask`, type "When was new-frontend moved to frontend?", click **Explain (no key needed)** | Grounded sentences from history records, including "Commit 9d703df25491 moved 96 files from new-frontend/ to frontend/". No model and no key |
| 11 | 8:00 | Same page, ask "Does create_item write to the database at runtime?" | An unknown sentence "Static evidence cannot show runtime behavior ..." and the fact "create_item has a statically established persistence path through get_db" |
| 12 | 8:30 | `I` | Second repository (a Python library, not a web app): "@672971d", entry points "No route nodes or routes_to claims are stored. That is an absence of records, not proof the software has no HTTP routes." Unknowns are shown, nothing is invented |
| 13 | 9:00 | `I/graph` | "Rejected claims are never drawn." with "47 rejected" hidden (see F-4: these rejections are themselves wrong, an open finding) |
| 14 | 9:20 | Phone (Chrome Android, or devtools 360 x 800): `F/trace`, tap **Open evidence** on step 1 | The flow fits the screen; the drawer shows `frontend/src/routes/_layout/items.tsx` with pinned lines |
| 15 | 9:45 | Phone: `F/graph` | "Architecture graph" with no sideways page scroll at 360 px |

## Optional live step (not run on the box app, because it writes to that store)

Paste `https://github.com/pallets/markupsafe` on the home page and index commit `4e111271b1494995708a9e878a10829b5e10c7ba`.
The same API path (`POST /api/v1/repos`, `POST /api/v1/repos/{id}/index-jobs`) was run on a separate scratch store on
2026-10-23: the job succeeded in 8.5 s with 361 CodeGraph edges (231 verified). See SECOND_REPO.md.

## Things to say, and not say

- Say "statically established", never "it saves to the database". Nothing in Traces runs the target code.
- Library steps (react-hook-form, TanStack Query) stay Inferred on purpose.
- History screens show Git facts and patterns. A milestone or co-change is not a statement of intent.
- Do not open Routes, Components or Source as standalone pages: they still say "scheduled for the next UI checkpoint" (gap G-3).
- Ask is keyword retrieval. Use the two questions above; "What does create_item depend on?" returns unrelated matches (finding F-7).

## Re-check before a demo

```
WEB=http://127.0.0.1:5731 node tests/e2e/demo_walk.cjs      # needs web/node_modules (Playwright + Chromium)
```
