# Traces v1 demo script (10 minutes)

Owner: Traces Lab. Runs against the Traces Lab box app: web `http://127.0.0.1:5731`, API `http://127.0.0.1:8731`, build `0f32d4d`
(`/workspace/traces-review/traces`). Every expected result below was checked on 2026-10-23 at 15:16 IST, after the box re-index, by
`node tests/e2e/demo_walk.cjs` (16 of 16 steps PASS, local, read-only: page loads plus no-key explain, which writes nothing).
Screenshots from that run are in `.traces-data/acceptance/demo/shots/` (local, not committed).

Data is real: `fastapi/full-stack-fastapi-template@b1125d8839482cb7bbae603ddc6d0081bf87532e` (job `j_b3030040192949cd992a`, re-indexed at `0f32d4d` as `j_c43c3a1fc81142d9a19d` with the same 4,642 edges and validation hash `73db432b`) and
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
| 6b | 4:40 | `F/trace?from=read_items` | "From read_items: 3 steps ... 1 gaps." and "Incomplete: this trace has 1 step with calls the trace cannot follow. A gap is not evidence that a call does or does not happen." with "API reasons: gaps: 1". The gap card reads "Gap: calls the trace cannot follow", lists the unresolved calls, and explains "The extractor recorded these calls by name only and did not resolve them to a declaration". Say: a trace never claims to be complete while calls are unresolved (F-9) |
| 7 | 5:15 | `F/review` | "12 matching claims", all Rejected: the 9 wrong CodeGraph imports (for example "imports 'app' at backend/app/api/routes/login.py:8") and the 3 injected negatives (for example "create_item uses_crud crud.py") |
| 8 | 6:00 | `F/history?tab=milestones` | "Showing 1 to 8 of 8 records." Milestone "Move new-frontend to frontend (#652)": "bulk move 96 files: new-frontend -> frontend", "Cites commit 9d703df". Git confirms: 96 renames in 9d703df (91 at 100% similarity) |
| 9 | 6:45 | `F/history?tab=cochange&target=backend/app/crud.py` | "It is not evidence of a code dependency", "backend/app/crud.py ... changed together in 5 of 26 commits". Say: co-change is a pattern, not a cause |
| 10 | 7:30 | `F/ask`, type "When was new-frontend moved to frontend?", click **Explain (no key needed)** | First a summary, "History patterns: 3 recorded directory moves involve new-frontend or frontend, ranked by files moved, then top-level directory renames first." Then the moves in that order: "Commit 9d703df25491 moved 96 files from new-frontend/ to frontend/" first, then the 7-file and 4-file moves inside `new-frontend/`. Each carries the history-pattern caveat. No model and no key |
| 11 | 8:00 | Same page, ask "Does create_item write to the database at runtime?" | The unknown sentence "Static evidence cannot show runtime behavior, so how this behaves when the code runs is unknown.", followed by the verified static persistence path cited at `backend/app/api/routes/items.py:68` (O-13 fixed in `033e1f8`). Say: the static path is evidence, runtime behavior stays unknown |
| 12 | 8:30 | `I` | Second repository (a Python library, not a web app): "@672971d", entry points "No route nodes or routes_to claims are stored. That is an absence of records, not proof the software has no HTTP routes." Unknowns are shown, nothing is invented |
| 13 | 9:00 | `I/graph` | "Rejected claims are never drawn." and "Hidden by current filters: 268 (268 inferred (unvalidated))." No rejected claims: the box app re-indexed itsdangerous at `0f32d4d` (job `j_415d7e33bd7a46aebe41`), and the 46 relative imports and 1 overload call that `35499bc` rejected now pass (F-4, F-5). The package `src/itsdangerous` is in the Library layer (O-3). Say: unvalidated edges are hidden by default, not deleted |
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
- Routes, Components and Source render real data at the pinned commit (G-3 closed), so they are safe to open.
- Ask routes by intent (F-7 fixed). "What does create_item depend on?" answers with get_db and get_current_user, all verified.

## Re-check before a demo

```
WEB=http://127.0.0.1:5731 node tests/e2e/demo_walk.cjs      # needs web/node_modules (Playwright + Chromium)
```
