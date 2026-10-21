# Step 1: CodeGraph 1.6.2 graded against Lab ground truth

Scope: plan step 1 (condition A) only. I did not build or run a harness, fixture, adapter, validator or chain run.
Plan output name was `task002/step1_codegraph_grades.md`; this file is at `task002/step1/GRADING.md` as the brief asked.

- Engine: `@colbymchenry/codegraph@1.6.2` (integrity sha512-hODH/mGn...UH6Q==), index schema 11, extraction version 27. Details in `../ENV.md`.
- Target: throwaway copy `task002/src/fsft` at `b1125d8839482cb7bbae603ddc6d0081bf87532e`, clean. CodeGraph records the same SHA in `project_metadata.indexed_at_commit`.
- Answer key: `lab/B/ground-truth.md` (Task 001). Scale as in `LAB_B_RESULTS.md`: G grounded and correct, P partly correct or partly grounded, W contains a wrong relationship, U ungrounded, N not answered.
- Lead's rules applied: missing evidence is not false evidence, and an edge with no line counts as missing location, not wrong. For N2 I judged the specific handler-level dependency, not file-level impact reach.
- Evidence sources: deterministic CLI output (`status`, `files`, `query`, `callers`, `callees`, `impact`, `context`) plus read-only SQLite reads of the index the CLI uses. Each claim below says which one it came from.
- Network: every command ran inside `unshare -rn` with telemetry off. Proof is in `logs/00_netproof_and_help.log`.

## Index run

`cd src/fsft && codegraph init -y .` under the offline wrapper: 175 files, 2,076 nodes, 4,642 edges, CodeGraph-reported 597 ms; measured wall 1.6 s, peak RSS 377 MB (`logs/02_index.log`).

Edge mix: calls 884, contains 1,893, imports 1,222, references 576, instantiates 47, navigates 14, extends 6. Provenance is `heuristic` on 291 edges and NULL on 4,351. Edges with no line number: 1,981 (all 1,893 `contains`, plus 88 `references`). These match the plan's baseline counts.

## Grades

| Q | grade | basis |
|---|---|---|
| Q1 what the app does | **N** | No summary or purpose output. The route inventory (31 route nodes: items, users, login, password recovery, utils, private, plus 8 TanStack pages) is raw material, not an answer. Same standard as Task 001, where non-summarizing tools got N. |
| Q2 major components | **P** | `files` lists 175 files grouped by language. `status` gives node kinds. Route, class and function nodes with file and line are correct (for example `Item` models.py:87-93, `ItemPublic` 97-100, `User` 51-55, `get_current_user` deps.py:30). No component grouping or boundaries (backend, frontend, client, migrations). Nothing about the build or serving setup (`backend/Dockerfile:1-16`, `main.py:36`). No wrong component claimed. |
| Q3 how they connect | **P** (no W) | Correct and located: all 13 app-level `crud.*` call sites (12 in routes plus `core/db.py:33`) match `git grep` line for line. `crud.create_item` has exactly one caller, `tests/utils/item.py:16`. No edge says `items.py` uses crud. `CurrentUser -> get_current_user` at deps.py:49 and `SessionDep -> get_db` at deps.py:26 are correct. Missing: handler-level DI edges (no `create_item -> CurrentUser/SessionDep`), router composition (`include_router` calls only appear as failed unresolved refs), and any frontend-to-backend edge (0 in either direction). Missing, not wrong. |
| Q4 create-item trace | **P** (no W) | L3, L4 (method) and the route-to-handler half of L5 are present with correct lines. L1 is present with a container-level line. L2 is half present. L6 to L8 have no edges. L9 has the model nodes but not the `response_model` edge. Table below. |
| Q5 change over time | **N** | No history features. The index pins one SHA only. |
| Q6 evidence | **G** | Every node has repo-relative path and 1-based start and end lines. Start lines confirmed 378 of 379 (below). Edge lines are statement-level or container-level; none point at an unrelated line. Gaps are missing locations (1,981 line-less edges), not false ones. |

### Q4 chain, link by link (ground truth from `lab/B/ground-truth.md` Q4 and plan section 2)

| link | expected | CodeGraph output | source | verdict |
|---|---|---|---|---|
| L1 | `items.tsx:65` renders `<AddItem />` | `Items -calls-> AddItem` (heuristic), line 57 = the `function Items()` line, not 65 | `callers AddItem`; SQL | present, correct relationship, location container-level. Edge kind `calls` for a JSX render is imprecise |
| L2 | `AddItem.tsx:88` submit binds `onSubmit` (68-69), which calls `mutation.mutate` | `AddItem -references-> AddItem::onSubmit` at 88; `onSubmit` node 68-70. `mutation.mutate` at 69 is only a failed unresolved ref | SQL `09_sql_chain.log` | half present; mutate hop missing |
| L3 | `AddItem.tsx:56` calls `ItemsService.createItem` | `AddItem -calls-> ItemsService::createItem` line 56 | `callees AddItem` | present, exact |
| L4 | `sdk.gen.ts:307-318`, `POST /api/v1/items/`, op id `items-create_item`, type `itemsCreateItemData` | method node 307-318 exact; `createItem -references-> itemsCreateItemData` at 307; that type (types.gen.ts:809-814) contains property `url` at 813 with signature `url: '/api/v1/items/'`. No node or edge for the operation id. HTTP method not captured on the client side | `callees createItem`; SQL | partial: method, type and URL literal are present, op id and method missing |
| L5 | contract -> `items.py:61-72` `create_item`; prefix from `main.py:35`, `config.py:22`, `api/main.py:10`, `items.py:10`; op id rule `main.py:14-15` | route node `POST /items` at items.py:61 `-references->` `create_item` (62-72) at 61. Router prefix `/items` composed. `/api/v1` not composed (`main.py:35` include and `settings.API_V1_STR` are failed unresolved refs; `API_V1_STR` is not a node). Trailing slash dropped (`/items` vs real `/items/`). `custom_generate_unique_id` node at main.py:14-15, referenced at main.py:24, never joined to any route or SDK method. 0 frontend-to-backend edges | `callers create_item -f items.py`; SQL `10_routes.log` | partial: backend half present, cross-boundary join missing, full path incomplete |
| L6 | `create_item` depends on `SessionDep` (deps.py:21-26) | only file-level `items.py imports SessionDep` at line 7. Alias `SessionDep -> get_db` at 26 correct | SQL `05_sql_di.log` | missing at handler level |
| L7 | `create_item` depends on `get_current_user` via `CurrentUser` (deps.py:49) | only file-level `items.py imports CurrentUser` at 7. Alias `CurrentUser -> get_current_user` at 49 correct | `callers get_current_user`; SQL | missing at handler level |
| L8 | `Item.model_validate`, `session.add/commit/refresh` at items.py:68-71 | no edges. All four appear in `unresolved_refs` with correct lines (68, 69, 70, 71), status `failed`. `callees create_item` returns nothing | `callees create_item`; SQL `05_sql_di.log` | missing (location exists only as unresolved refs) |
| L9 | `Item` models.py:87-93, `ItemPublic` 97-100, `response_model=ItemPublic` at items.py:61 | both class nodes exact; no edge from route or handler to `ItemPublic` at 61 (file-level `references ItemPublic` exists only at line 48) | SQL | nodes present, `response_model` edge missing |

Also checked: `context "create an item from the frontend AddItem form through the API to the database"` returns 10 frontend symbols. Its entry points include `Item` from `components/Sidebar/Main.tsx:13`, a sidebar menu type, not the DB model, and it reaches no backend file. This is a retrieval miss, not a stated relationship, so it is not counted as W.

Secondary login trace: `login_access_token -calls-> crud.authenticate` (login.py:30) and `security.create_access_token` (39) are correct. `useAuth.login -calls-> LoginService.loginAccessToken` at useAuth.ts:42 is correct. No backend join.

## Negative controls (assessment only; plan step 9 records are not created)

- **N1** (GitDiagram "items routes use crud"): CodeGraph makes no such claim. There are 0 `calls` edges from `items.py` to `crud.py` (`06_sql_q3_crud.log`), and `crud.create_item`'s only caller is the test util. Consistent with ground truth.
- **N2** (CodeGraph making `private.py` depend on `get_current_user`): no handler-level claim exists.
  - The only `private.py -> deps.py` edges are `imports deps.py` and `imports SessionDep` at private.py:6. Both are true (`05_sql_di.log`).
  - `private.py` `create_user` has edges only to `User` (29), `get_password_hash` (32) and the route at 23.
  - `impact get_current_user` lists `private.py` as a **file** node. The path is `private.py imports deps.py (file)`, then deps.py contains `get_current_user`. That is file-level reach through a real import, lacking handler precision. Under the lead's rule it is not a wrong handler-level dependency.
  - Same pattern elsewhere: `impact CurrentUser` does not list `private.py`, and `impact SessionDep` does, correctly.
  - Result: N2 would be rejected at handler level because CodeGraph states no such handler edge. The broader impact output stays imprecise, and an adapter must not promote file-level reach to a handler claim.

## Line accuracy (start lines of function, method and route nodes in `backend/app` and `frontend/src`)

Scope: 379 nodes (312 function, 36 method, 31 route).

| check | exact | share | log |
|---|---|---|---|
| Lab `check_lines.py` `defline()`, verbatim | 320 / 379 | 84.4% | `logs/08_check_lines_verbatim.log` |
| Lab `defline()` for function and method, plus a route rule (decorator call on the reported line contains the method and path literal, or `createFileRoute` line for TanStack routes) | 351 / 379 | 92.6% | `logs/07_analysis.log` (A1) |
| Independent parsers (CPython 3.14.8 `ast` for Python, TypeScript 5.9.3 compiler API for TS/TSX) for function and method, plus the route rule above | **378 / 379** | **99.7%** | `logs/07_analysis.log` (A2, START_confirmed_by_either) |

Why the first two numbers are lower:
- The verbatim script has no route rule. Route names such as `POST /items` are not identifiers, so its regex reports all 23 backend routes as `decorator_line` and all 8 TanStack routes as `other`. With the route rule, 31 of 31 route start lines are the decorator or `createFileRoute` line, including multi-line decorators (login.py:100, users.py:32, 54, 182, utils.py:11).
- The 27 remaining TS method misses are a regex blind spot. `\bname\s*[:=(]` does not match `createItem<ThrowOnError ...>(` (22 generated SDK methods) or `onRequest?:` (4 optional method signatures). The TypeScript compiler confirms each reported line is the declaration line. `createItem` at sdk.gen.ts:307 is one of them.
- The one real mismatch: `setOpen` in `components/ui/sidebar.tsx`. CodeGraph puts it at 87-97, the arrow function inside `React.useCallback(`. The `const setOpen` binding is at 86 (statement ends at 99). This is a defensible location for the function body, but not the declaration line, so it is counted as not exact.

End lines (secondary, not part of S2):
- 341 of 348 function and method nodes match the independent parser.
- The 7 misses are 6 Alembic `upgrade`/`downgrade` functions, where CodeGraph's end line is one more than `ast` because it includes the trailing `# ### end Alembic commands ###` comment, plus `setOpen`.

Edge lines (secondary): 2,661 of 4,642 edges carry a line (`logs/07_analysis.log` B, `11_jsx_heuristic.log`).
- 2,373 point at the statement that holds the relationship. That is the target token on the line, or the start of a multi-line import (37), the route decorator for route-to-handler (23), or a `<Link to=...>` line (3).
- 288 point at the enclosing declaration instead of the expression:
  - all 280 `heuristic` JSX render edges (line = the component's `function` line; in 288 of 288 heuristic call edges the `<Target` tag is inside the source span);
  - 8 TanStack route-to-component edges (line = `createFileRoute`, component on the next line).
- 0 point at an unrelated line.

The 88 line-less `references` edges all have the target name inside the source node's span (`logs/12_noline_refs.log`), so none is wrong. They are location_missing.

## Containment edges recoverable from AST parent-child structure

All 1,893 `contains` edges have no line (`logs/07_analysis.log` C). Each was checked against the independent parsers' parent-child structure, matching the target by name and start line.
- **1,891 of 1,893 recovered.** Kinds covered:
  - file to import (675), function (373), type_alias (191), constant (99), variable (52), class (27), interface (37), component (1);
  - class to method (28), interface/type_alias to property (359) and method (8);
  - function to nested function (41).
- 1 ancestor right, immediate parent skipped: `createSseClient -> abortHandler` (`client/core/serverSentEvents.gen.ts:143`). The TS AST's nearest named parent is `createStream`, which has no CodeGraph node. Generated file.
- 1 not matched by line: `SidebarProvider -> setOpen`, the same 86 vs 87 offset as above. The parent is correct by name.

So containment can be rebuilt from AST nesting plus node start lines, with the two exceptions above to handle.

## Stop conditions

- **S1 (wrong relationship in Q3 or Q4): does not trigger.**
  - No CodeGraph edge in the Q3 or Q4 sets states a wrong relationship.
  - Checked: all 48 `calls` edges into `crud.py` (13 app edges matched line for line against `git grep`, 34 test edges and 1 inside `crud.py` at line 46 passed the line token check; the one bare-name edge, `test_login.py:94` `create_user`, resolves correctly via `from app.crud import create_user` at line 9); every DI edge into `deps.py`; all edges from `items.py`, `private.py`, `AddItem.tsx`, `items.tsx`, `sdk.gen.ts` `createItem`; all 288 heuristic JSX edges; all 2,661 line-bearing edges by token check.
  - The gaps (handler-level DI, HTTP join, `/api/v1` prefix, persistence calls, `response_model`) are missing edges, not wrong ones.
  - Imprecisions that are not W: JSX render typed as `calls`; route path `/items` without `/api/v1` and without the trailing slash; `impact` reach at file level, including `private.py`.
- **S2 (start-line accuracy below 95%): does not trigger on the adjudicated count, 378 / 379 = 99.7%.**
  - Stated plainly: the verbatim `check_lines.py` number is 320 / 379 = 84.4%, and with a route rule 351 / 379 = 92.6%. Both are below 95%.
  - The gap is a checker limitation (no route rule; regex misses TS generics and optional signatures). The independent TypeScript and Python parsers confirm 58 of the 59 lines it did not match; the exception is `setOpen`.
  - If the gate must use the unmodified Lab script, S2 triggers. That decision is for step 1a.

## Step 1a inputs (decision not mine)

Neither S1 nor S2 triggers on the evidence above. Whether CodeGraph leaves "provisional" is for Traces, then Shailesh. Points the adapter will need regardless:
- treat heuristic and route-component edge lines as container-level;
- drop route trailing-slash normalization;
- never read `impact` file reach as handler dependency;
- check `.codegraph/` writes stay in the throwaway copy.

## Raw logs (`step1/logs/`)

| file | content |
|---|---|
| `00_netproof_and_help.log` | network-off proof, `codegraph --version` and `--help` |
| `01_subcommand_help.log` | subcommand help, telemetry status |
| `02_index.log` | index command, time and RSS, git status before and after, `status --json` |
| `03_schema.log` | SQLite schema, `schema_versions`, `project_metadata` |
| `04_cli.log`, `cli_json/*.json` | all CLI runs from `run_cli.sh`, split per command by `parse_cli.py` |
| `05_sql_di.log` | DI edges into `deps.py`, all `private.py` edges, unresolved refs for `items.py` and `private.py` |
| `06_sql_q3_crud.log` | all `calls` into `crud.py` and `git grep` ground truth |
| `07_analysis.log`, `analysis.json` | line accuracy (A1, A2), edge lines (B), containment (C) |
| `08_check_lines_verbatim.log` | Lab `defline()` unchanged |
| `09_sql_chain.log`, `10_routes.log` | chain link facts, route nodes |
| `11_jsx_heuristic.log`, `12_noline_refs.log` | heuristic JSX and line-less reference checks |
| `13_post_state.log`, `14_parser_coverage.log` | post-run state, independent parser coverage |

Scripts (`step1/`): `run_cli.sh`, `parse_cli.py`, `q.py`, `schema_probe.py`, `analyze.py`, `py_decls.py`, `ts_decls.js`, `verbatim_check_lines.py`, `jsx_check.py`, `noline_refs_check.py`, `ts_parse_diag.js`. All read only. None calls an LLM, GitNexus or the GitHub API.
