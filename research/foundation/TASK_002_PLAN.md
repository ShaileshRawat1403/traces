# Task 002 plan: verified create-item chain on full-stack-fastapi-template

Status: **PLAN ONLY. Not started.** Task 002 does not start until Shailesh approves this plan and the approval list in section 7.
Author: Traces (lead investigator seat). Date: 2026-10-21 (IST).
Inputs: `FOUNDATION_REVIEW.md` (including "Addendum: Task 001 review decisions (2026-10-21)"), `LAB_B_RESULTS.md`, `lab/B/ground-truth.md`, `lab/B/results.md`, `lab/B/scripts/check_lines.py`.

## 1. Objective

On `fastapi/full-stack-fastapi-template` at `b1125d8839482cb7bbae603ddc6d0081bf87532e`, show that Traces can reconstruct and verify this chain, with every link traced to a source location at that commit:

frontend action > generated client call > API contract (operation ID and full route path) > backend handler (file and line) > dependencies and persistence

Also show that a deliberately false relationship is rejected or labeled unverified, and never shown as verified.

Out of scope: UI, chat, any LLM call, frameworks other than FastAPI plus the hey-api generated TypeScript client, Git history, GitNexus.

## 2. Target chain (from Lab ground truth Q4)

The expected chain is Lab's Q4 answer (`lab/B/ground-truth.md`, "Q4. Feature trace: create an item"). Paths are repo-relative at the pinned SHA, lines 1-based.

| Link | From | To | Expected evidence |
|---|---|---|---|
| L1 | route page `frontend/src/routes/_layout/items.tsx:65` | `AddItem` component | JSX render of `<AddItem />` |
| L2 | `frontend/src/components/Items/AddItem.tsx:88` form submit | `onSubmit` (68-69) and `mutation.mutate` | handler binding |
| L3 | `AddItem.tsx:56` | `ItemsService.createItem` | call expression |
| L4 | `ItemsService.createItem` (`frontend/src/client/sdk.gen.ts:307-318`) | API contract: `POST /api/v1/items/`, operation ID `items-create_item` | generated method, `url` literal, generated type `itemsCreateItemData` |
| L5 | API contract | backend handler `backend/app/api/routes/items.py:61-72` `create_item` | route path composed from `main.py:35` (prefix `settings.API_V1_STR`, `core/config.py:22`), `api/main.py:10`, `items.py:10`; operation ID rule `main.py:14-15` |
| L6 | `create_item` | `SessionDep` (`api/deps.py:21-26`) | FastAPI dependency through `Annotated` alias |
| L7 | `create_item` | `CurrentUser` to `get_current_user` (`api/deps.py:30-49`) | FastAPI dependency through `Annotated[User, Depends(get_current_user)]` at `deps.py:49` |
| L8 | `create_item` | persistence: `Item.model_validate`, `session.add`, `session.commit`, `session.refresh` (`items.py:68-71`) | call expressions |
| L9 | `Item` | table class `backend/app/models.py:87-93`, response model `ItemPublic` (`models.py:97-100`) | class declarations, `response_model=ItemPublic` at `items.py:61` |

Line ranges for a handler run from the decorator line to the last line of the function body. This convention is written into the schema (section 4) so that `items.py:61` (decorator) and `items.py:62` (`def`) are not reported as a conflict.

Negative controls:
- **N1 (required).** GitDiagram's claim "items routes use crud" (public cached page, `lab/B/logs/gitdiagram_page.html`). Ground truth: `items.py` has 0 `crud.` references; `items.py:68-71` writes through `session` directly; `crud.create_item` (`crud.py:63-68`) is called only from `backend/tests/utils/item.py:16`. Expected end state: `rejected`.
- **N2 (extra).** CodeGraph's own file-level reach that makes `backend/app/api/routes/private.py` depend on `get_current_user`. `private.py` imports only `SessionDep` (FOUNDATION_REVIEW.md section 1, T10). Expected end state: `rejected` at handler level. This shows the validator also rejects claims from the chosen engine, not only from a competitor.

## 3. Steps

Legend: **TEST** = hands-on run on the box. **DESK** = writing, reading, review, no tool runs. Owners: **Traces** = lead investigator (spec, adapter contract, review, report). **Lab** = Traces Lab (hands-on runs, ground truth, test harness).

| # | Step | Owner | Type | Output |
|---|---|---|---|---|
| 0 | Approval gate. Shailesh approves this plan and section 7. Lab confirms the clone at `lab/repos/fsft` (or `_src/full-stack-fastapi-template`) is at the pinned SHA with a clean worktree. | Shailesh, Lab | DESK + one `git status` / `git rev-parse` check | approval note in `task002/APPROVALS.md` |
| 1 | **Condition A.** Grade `@colbymchenry/codegraph` 1.6.2 (pinned; record npm integrity hash and index schema version, currently 11) against Lab's six-question ground truth, same G/P/W/U/N scale as `LAB_B_RESULTS.md`. Use only deterministic CLI output (`index`, `query`, `impact`, `callers`, `callees`, `context`). Run Lab's `check_lines.py` over all function, method and route nodes in `backend/app` and `frontend/src`. Count wrong relationships in the Q3 and Q4 sets. | Lab runs; Traces reviews the grades | TEST | `task002/step1_codegraph_grades.md`, raw logs |
| 1a | Gate decision on step 1 results (see stop conditions S1, S2). Record whether CodeGraph leaves "provisional". | Traces, then Shailesh | DESK | decision line in step 1 file |
| 2 | Evidence record schema (section 4) finalized, including class rules and status transitions. | Traces | DESK | `task002/evidence_schema.md` plus JSON Schema file |
| 3 | Adapter contract (section 5): mapping from CodeGraph SQLite rows to evidence records, provenance normalization table, version pin rules. | Traces | DESK | `task002/adapter_contract.md` |
| 4 | Contract test harness for the adapter, implemented from step 3. | Lab | TEST (writes and runs tests) | `task002/tests/`, test log |
| 5 | Expected-chain fixture L1 to L9 and negative controls N1, N2, encoded from ground truth as machine-readable expectations. Traces spot-checks every line ref against `git show b1125d88:<path>`. | Lab writes; Traces spot-checks | DESK (spot-check is a read) | `task002/fixtures/chain_create_item.json` |
| 6 | Framework rule specs for scope only: (R1) FastAPI router prefix composition, (R2) `Depends` and `Annotated` alias resolution at parameter level, (R3) operation ID join from `custom_generate_unique_id` (`main.py:14-15`) to hey-api generated method and `url` literal. Each rule names its inputs, outputs, and failure cases. | Traces | DESK | `task002/framework_rules.md` |
| 7 | Independent validators: Python AST validator (Python 3.14 stdlib `ast`, because `deps.py:36` uses 3.14 syntax that 3.13 rejects), TypeScript AST validator (TypeScript compiler API), and the R1 to R3 rule implementations. None reads CodeGraph output to decide; each reads source at the SHA. | Lab | TEST | `task002/validators/`, unit test log |
| 8 | Chain reconstruction run: index with pinned CodeGraph, import through the adapter, apply R1 to R3, assemble L1 to L9, run validators, write evidence records. Run twice for determinism. | Lab | TEST | `task002/out/evidence.jsonl`, `task002/out/chain.json`, run logs with time and peak RSS via `_tests/measure.py` |
| 9 | Negative controls: insert N1 as an `unverified_inference` from extractor `external:gitdiagram-page`, and N2 as the CodeGraph-derived handler-level claim. Run the same validators. | Lab | TEST | records with final status and reason |
| 10 | Provenance coverage report over all imported CodeGraph edges (4,642 at last count): share with normalized provenance, extractor, version, location, class, status. State counts of `verified`, `rejected`, `unvalidated`, `location_missing`. | Lab produces numbers; Traces writes | TEST + DESK | `task002/out/coverage.json` |
| 11 | Review and report: check every success criterion, list failures plainly, recommend next scope. | Traces | DESK | `task002/TASK_002_REPORT.md` |

Steps 2, 3, 5 and 6 can run in parallel with step 1. Steps 4, 7, 8 and 9 wait for step 1a.

## 4. Evidence record schema sketch

One record per claim. A claim is either a node (a declared thing at a location) or a relationship (from, kind, to). Records are append-only; a status change writes a new validation entry, it does not edit the old one.

```json
{
  "claim_id": "c_<sha256 of repo_sha|kind|from|to|extractor>",
  "repo": "fastapi/full-stack-fastapi-template",
  "repo_sha": "b1125d8839482cb7bbae603ddc6d0081bf87532e",
  "claim_kind": "node | relationship",
  "relationship_kind": "renders | binds_handler | calls | implements_operation | routes_to | depends_on | persists_via | declares_model | returns_model | uses_crud",
  "from": {"symbol": "frontend/src/components/Items/AddItem.tsx::AddItem", "file": "...", "start_line": 56, "end_line": 56},
  "to":   {"symbol": "frontend/src/client/sdk.gen.ts::ItemsService.createItem", "file": "...", "start_line": 307, "end_line": 318},
  "source_location": {"file": "frontend/src/components/Items/AddItem.tsx", "start_line": 56, "end_line": 56, "line_base": 1, "range_rule": "expression | decorator_to_body_end | declaration"},
  "class": "source_backed_declaration | statically_derived | unverified_inference | runtime_observed",
  "extractor": "codegraph | traces:fastapi-rules | traces:py-ast | traces:ts-ast | external:gitdiagram-page | human",
  "extractor_version": "1.6.2 (schema 11) | rules v0.1 | python 3.14.x | typescript 5.x.y",
  "provenance_raw": "null | heuristic | tree-sitter | scip | <other tool value>",
  "provenance": "codegraph:default | codegraph:heuristic | codegraph:tree-sitter | codegraph:scip | rule | parser | external | human",
  "validations": [
    {
      "method": "L1_path_exists | L2_line_in_range | L3_line_contains_token | parser_independent | framework_rule | human_review",
      "validator": "traces:py-ast@3.14.x",
      "validator_independent_of_extractor": true,
      "result": "pass | fail | not_applicable | error",
      "detail": "token 'crud.' not found in items.py:61-72",
      "at": "2026-10-xxTxx:xx+05:30"
    }
  ],
  "status": "verified | unvalidated | rejected | location_missing | contested",
  "status_reason": "free text, required when status is not verified",
  "visible_to_reviewer": true
}
```

Class rules (condition C):
- `source_backed_declaration`: the claim is a literal in source, such as `@router.post("/")`, `prefix="/items"`, `API_V1_STR: str = "/api/v1"`, a class or function definition. Needs L3 plus a parser check that the token is that syntax node, not a comment or string elsewhere.
- `statically_derived`: the claim joins two or more declarations by a rule, such as a call edge, a route path composed from three prefixes, a `Depends` alias resolved to a function, an operation ID joined to an SDK method. Needs L3 on each input location plus `parser_independent` or `framework_rule` by a validator other than the extractor.
- `unverified_inference`: any claim from an LLM, an external tool page, or a heuristic with no rule behind it. Stays in this class even if a later check passes; a passing independent check creates a separate `statically_derived` record that cites it.
- `runtime_observed`: only from executing the app. Task 002 runs nothing, so this class has 0 records by design. The field exists so later work does not overload the other classes.

Status rules:
- `verified` requires: a source location at `repo_sha`, L3 pass, and at least one validation with `validator_independent_of_extractor: true` and result `pass`. An L3 pass alone never yields `verified`.
- `rejected` requires a failed independent validation with `detail`.
- `location_missing` for any record with no line (1,981 CodeGraph edges at last count, 1,893 `contains` and 88 `references`). Never `verified`.
- `unvalidated` is the default for every imported edge, including the 4,351 with unset provenance.
- Every status, including `rejected`, stays in the output with `visible_to_reviewer: true`. Nothing is deleted.

## 5. CodeGraph adapter contract and contract tests

The adapter is Traces-owned. It reads CodeGraph's SQLite index read-only and emits section 4 records. It never asserts `verified`. It does not replace CodeGraph extraction.

Contract tests (Lab implements in step 4, all must pass before step 8):

| ID | Test | Pass condition |
|---|---|---|
| CT1 | Version pin | Adapter refuses any CodeGraph version other than 1.6.2 and any index schema version other than 11, with a clear error. |
| CT2 | Schema drift | Adapter checks the `nodes`, `edges`, `files`, `unresolved_refs` columns it reads; a missing or renamed column fails loudly, not silently. |
| CT3 | SHA binding | Adapter records `git rev-parse HEAD` and refuses a dirty worktree or a SHA other than the pinned one. |
| CT4 | Provenance mapping is total | `NULL` maps to `codegraph:default`, `heuristic` to `codegraph:heuristic`, `tree-sitter` and `scip` to their own values; an unknown value fails the run. `provenance_raw` is kept. |
| CT5 | Every record complete | 100% of emitted records have `extractor`, `extractor_version`, `provenance`, `class`, `status`. Zero nulls. |
| CT6 | No verified from adapter | 0 records leave the adapter with status `verified`. |
| CT7 | Line base | For a fixed set of 20 functions and handlers from ground truth (including `items.py` `create_item`, `deps.py` `get_current_user`, `crud.py` `create_item`, `sdk.gen.ts` `createItem`), adapter `start_line` equals the 1-based line of `def`, decorator, or method as the range rule states. |
| CT8 | Missing lines | Edges with no line become `location_missing`; count reported. |
| CT9 | Path normalization | All paths are repo-relative POSIX and exist at the SHA (`git cat-file -e <sha>:<path>`). |
| CT10 | Unresolved refs kept | Rows in `unresolved_refs` are emitted as `unvalidated` claims with no `to` target, not dropped. Count matches the table. |
| CT11 | Generated files flagged | `frontend/src/client/sdk.gen.ts` and the other files with `generated = 1` (20 at last count) carry a generated flag on their records. |
| CT12 | Known present | Fixture edges exist: `users.py:68` to `crud.create_user`, `login.py:30` to `crud.authenticate`, `AddItem.tsx:56` to `ItemsService.createItem`. |
| CT13 | Known absent | No adapter record says `items.py` `create_item` calls any `crud.*` function. |
| CT14 | Determinism | Two index runs on the same SHA give the same sorted record set (hash of normalized JSONL, timestamps excluded). |
| CT15 | No network, no telemetry | Run with CodeGraph telemetry disabled per `TELEMETRY.md` and outbound network blocked for the index and adapter steps; the run succeeds and makes no outbound connection. |

## 6. Success criteria (all measurable)

1. Step 1 grading table exists for Q1 to Q6 with the G/P/W/U/N scale, pinned version 1.6.2 and npm integrity hash recorded, and `check_lines.py` line accuracy stated as a count (for example "n of m exact").
2. L1 to L9 each have a source location (file, start and end line, 1-based) at `b1125d88`: 9 of 9.
3. Every chain link has a final status. Target: 9 of 9 `verified`. Any link not verified is listed with its reason; the task still reports honestly rather than passing.
4. Zero records with status `verified` lack an independent validation (`validator_independent_of_extractor: true`, result `pass`). Checked by a query over `evidence.jsonl`.
5. N1 ends `rejected` with a detail that cites `items.py:61-72` and the absence of `crud.`. N2 ends `rejected` at handler level. Neither is ever `verified`, and both stay visible.
6. L4 and L5 contain the exact operation ID `items-create_item` and full path `POST /api/v1/items/`, each built from cited locations (`main.py:14-15`, `main.py:35`, `core/config.py:22`, `api/main.py:10`, `items.py:10`, `items.py:61`, `sdk.gen.ts:307-318`).
7. L7 resolves `CurrentUser` to `get_current_user` at parameter level for `create_item`, citing `deps.py:49`, and does not mark `private.py` handlers as dependent.
8. Provenance coverage stated: 100% of imported records carry normalized provenance, extractor, version, class and status; counts per status reported; the unset-provenance count reported against the 4,351 baseline.
9. All 15 contract tests pass. CT14 hashes match.
10. 0 LLM calls, 0 GitNexus runs, 0 writes to any ShaileshRawat1403 repo, 0 GitHub API calls.
11. The full step 8 run completes in under 10 minutes wall time and under 2 GB peak RSS on the box (CodeGraph indexed this repo in seconds in T5; the budget leaves room for validators).

## 7. Installs, access and approvals needed

Shailesh approves each line before Task 002 starts:

| Item | Detail | Why |
|---|---|---|
| CodeGraph pinned install | `@colbymchenry/codegraph@1.6.2` via npm, exact version, `--ignore-scripts` unless a script is required and reviewed. A copy exists under `_tests/cg-npm` from Task 001; reuse it if its integrity hash matches. | Step 1, step 8 |
| Node | v20.19.2 is on the box. CodeGraph 1.6.2 `package.json` declares no `engines` field (read from `_tests/cg-npm`), and Task 001 runs used Node 20.19.2. Keep it; no Node install unless step 1 fails on Node version. | CodeGraph runtime |
| Python 3.14 | Install a CPython 3.14.x build (for example via `uv python install 3.14`), about 30 to 50 MB download. Box default is 3.13.5, which rejects `deps.py:36`. | Python AST validator |
| TypeScript | `typescript` npm package, pinned 5.x, for the compiler API. | TS AST validator |
| Network | npm registry and the Python build download only, during setup. No network during index, adapter, validator, or chain runs. | Installs |
| GitHub API | None. All evidence comes from the local clone at the pinned SHA. | n/a |
| LLM keys | None. No LLM calls of any kind. | n/a |
| GitNexus | Not installed, not run, outputs not used as fixtures or ground truth (addendum decision). | n/a |
| Write scope | Only under `/workspace/traces-research/task002/`. The shared test repo clone stays read-only and is not moved. | Safety |

## 8. Stop conditions

Stop, write up what happened, and wait for Shailesh if any of these occur:

- **S1.** Step 1 finds a W (wrong relationship stated as an edge) in Q3 or Q4 from CodeGraph output. Report it before building the adapter; CodeGraph stays provisional.
- **S2.** Step 1 line accuracy below 95% exact on function, method and route nodes. The adapter cannot rely on CodeGraph locations.
- **S3.** The clone is not at `b1125d8839482cb7bbae603ddc6d0081bf87532e` or is dirty, and cannot be reset without touching shared files.
- **S4.** Any step needs an install, network access, key, or tool not in section 7.
- **S5.** Any tool tries to write into the target repo, run its install scripts, or modify editor or agent config.
- **S6.** A rule needs a framework or pattern beyond FastAPI routing, FastAPI dependencies, and the hey-api client to close a link. Record the gap; do not widen scope.
- **S7.** Effort passes 2 times the estimate in section 10.

## 9. Risks

- **Ground truth errors.** The answer key is Lab's work. Mitigation: Traces spot-checks every line ref in the fixture (step 5) with `git show` before any grading.
- **Validator independence is partial.** CodeGraph uses tree-sitter; the validators use CPython `ast` and the TypeScript compiler. They are different implementations, but all are static. A shared misreading of the source is unlikely, not impossible. Runtime evidence is out of scope by design.
- **Rule overfit.** R3 depends on this repo's `custom_generate_unique_id` and hey-api naming. The rule must read the operation ID function from source, not hardcode `"{tag}-{name}"`, and must fail cleanly on a repo that differs.
- **Line range conventions.** Decorator line vs `def` line already caused a one-line gap between sources (`items.py:61` vs `62`). The schema `range_rule` field handles it; CT7 tests it.
- **CodeGraph churn.** 412 open PRs at Task 001 time. Pinning (CT1, CT2) contains this; upgrades become a deliberate task.
- **Telemetry.** CodeGraph telemetry is on by default. CT15 checks it is off and network is blocked.
- **Python 3.14 availability.** If no 3.14 build installs cleanly, the Python validator fails on `deps.py`. Fallback needs approval (S4); do not swap parsers silently.
- **Scope pressure.** A passing chain invites adding chat or UI. Out of scope; the report recommends, it does not build.

## 10. Estimated effort

| Seat | Work | Estimate |
|---|---|---|
| Lab | Step 1 grading run and logs | 2 to 3 hours |
| Lab | Step 4 contract test harness | 2 to 3 hours |
| Lab | Step 5 fixture | 1 hour |
| Lab | Step 7 validators and rules | 3 to 4 hours |
| Lab | Steps 8 to 10 runs and numbers | 1 to 2 hours |
| Traces | Steps 2, 3, 6 specs | 3 to 4 hours |
| Traces | Reviews (1a, 5 spot-check) and step 11 report | 2 to 3 hours |
| Total | | about 14 to 20 seat-hours, about 2 working days elapsed with both seats in parallel |

These are estimates, not measurements. **INFERRED** from Task 001 run times.
