# Task 002 review package (step 11)

For: Architect1 and ChatGPT. Decision owner: Shailesh.
Author: Traces (lead investigator seat). Date: 2026-10-21 IST.
Run under review: `t002-20261021T1049-3`. Repo: `fastapi/full-stack-fastapi-template` at `b1125d8839482cb7bbae603ddc6d0081bf87532e`.
Rulings I made in this step: `task002/review/RULINGS.md` (six rulings, each pending Architect1 confirmation).
Audit scripts and raw outputs: `task002/review/audit/`.

> Update 2026-10-21: Decision 002-B accepted this package with corrections. The corrected run, counts, tests and conclusion are in `task002/review/CLOSEOUT_002.md`. This package is unchanged below and describes run `t002-20261021T1049-3`.

How to read the evidence tags in this package:

- **TESTED (Lab)**: Lab ran it; I checked the artifact exists and says what Lab reported.
- **TESTED (Traces audit)**: I ran it myself, offline, read-only against Lab's outputs and the source at `b1125d8`.
- **DESK**: reasoning over code, spec or text. Nothing executed.

What I did not do: no network, no app execution, no AI, no GitNexus, no GitHub API. I did not modify Lab's code, outputs, the checkout, the index or the spec. The one Lab tool I ran, `tests/ct_evaluate.py`, writes `ct_results.json` into its run dir, so I ran it on a copy of the run's inputs in `review/audit/ct_rerun/`, under `tools/offline.sh`.

## Headline

The run holds up. All 16 contract tests pass and my rerun reproduces them. The 9 rejections, the N1 and N2 rejections, the fixture lines and the isolation of injected claims all check out against source. My 60-edge independent sample found no edge verified on presence alone. I found one classification defect (36 import edges), two stale numbers in Lab's report, and quantified the EOF leniency: it touches 2,968 records but only through file-range endpoints.

## (a) Verification results

### a.1 Lab's numbers, checked

| Claim from Lab | Result | Evidence |
|---|---|---|
| Final outputs come from run `1049-3` | Confirmed | `out/evidence.jsonl`, `chain.json`, `coverage.json`, `rule_findings.json` byte-identical to `work/t002-20261021T1049-3/v1/validation/`; `out/ct_results.json` identical to the run's (TESTED, Traces audit, `cmp`) |
| CT1 to CT16 pass | Confirmed, 16/16 | My rerun of `ct_evaluate.py` on a copy gives 16/16 with identical detail for every CT (TESTED, Traces audit) |
| CT7 378/379 | Confirmed | parser mode 378/379, miss `setOpen`; lab_route 351/379; original `check_lines.py` 320; checker hashes OK |
| Deterministic: two runs same hash `e72e2d1f`, 41.1 s, 601 MB | **Hash is stale.** `e72e2d1f...` is the canonical validation hash of the earlier run `1047-1`. In `1049-3` it is `47bd353bc6e6...` for both v1 and v2. v1 and v2 evidence differ only in `at` timestamps (TESTED, Traces audit). 41.1 s and 601 MB are from `1049-3` (`inside_stdout.txt`); validation alone is 5.0 s and 288 MB | `inside_result.json` of both runs |
| CT14 hash `e5a53b4b` | **Not found** anywhere under `traces-research/` except this review. CT14 in `1049-3` shows adapter canonical sha256 `201d06863693...` equal for real, copyA and copyB | `ct_results.json` CT14 |
| Edges 4,642: 4,574 verified, 59 unvalidated, 9 rejected, 0 missing_location | Confirmed | recount from `out/evidence.jsonl` |
| 616 name-only: 599 verified, 17 inferred | Confirmed: 599 verified, 9 rejected, 8 unvalidated (label `inferred` for the 17) | recount |
| Nodes 2,075 observed, 1 unvalidated (`setOpen`) | Confirmed (2,076 node records) | recount; ruling R-3 |
| Unresolved refs 3,236 observed, 78 unvalidated | Confirmed (3,314 records) | recount |
| Binding smoke: 18 local and `@/` imports, 228 names, 0 failures, 10 library imports unresolved | Confirmed | `logs/smoke/bindings_101558.log` TALLY line |
| CodeGraph tarball hash not recomputed | Now recomputed, matches, installed package identical to tarball | ruling R-5a (TESTED, Traces audit) |

Neither stale number changes a result. The property claimed (two runs, one hash) holds in the final run with different values. The report should quote `47bd353b` (validation) and `201d0686` (adapter, CT14).

### a.2 Global invariants (TESTED, Traces audit, `audit/a1_global.py`)

Over all 10,050 records:

- verified without a passing independent check that establishes the relationship: 0;
- observed without a passing `parser_presence`: 0;
- label and status disagree: 0;
- status counts: observed 5,311; verified 4,587 (4,574 CodeGraph plus 13 fixture); unvalidated 140; rejected 12.

Establishing methods on verified edges: `contains` 1,891 by `syntax_structure` (R-contains, AST parent); `imports` 1,177 by `binding_resolution` and 36 by `syntax_structure` only (see finding F-1); `calls` binding; `references` binding, 23 by R1; `renders` binding plus syntax; `depends_on` R2; `implements_operation` R3; `routes_to` R1 and R3; `persistence_path` R4.

### a.3 Stratified sample, 60 verified edges (TESTED, Traces audit)

Method: deterministic random sample (seed 20261021) over every (kind, language, name-only or not) stratum of the 4,574 verified CodeGraph edges, 6 per name-only stratum and 2 per other stratum. 60 edges, 40 of them name-only. For each edge I recorded which Lab check verified it, then re-checked it with my own resolver, written for this audit and sharing no code with Lab's validators: Python through CPython 3.14.8 `ast` with my own scope and import resolution; TypeScript through my own resolver over import, re-export and `@/` alias statements, reading blobs with `git show` at `b1125d8`. Scripts `audit/a2_sample.py`, `audit/a3_independent.py`; per-edge results `audit/sample_results.json`.

| Kind | Provenance | n | Lab establishing check | My re-check |
|---|---|---:|---|---|
| calls | name-match | 12 | binding_resolution | 12 agree |
| calls | resolved-import | 4 | binding_resolution | 4 agree |
| contains | structural | 4 | syntax_structure (R-contains) | 4 agree (2 TS by range nesting only, weaker than AST) |
| extends | name-match | 6 | binding_resolution | 6 agree |
| imports | name-match | 6 | binding_resolution | 6 agree (re-export bindings in `client/index.ts`) |
| imports | resolved-import | 4 | binding_resolution | 4 agree |
| instantiates | name-match | 4 | binding_resolution | 4 agree |
| instantiates | resolved-import | 2 | binding_resolution | 2 agree |
| references | name-match | 6 | deterministic_rule R1 | 6 agree (decorator at site, def at target line) |
| references | name-match | 6 | binding_resolution | 6 agree |
| references | resolved-import, value-ref | 4 | binding_resolution | 4 agree |
| renders | jsx-render | 2 | binding_resolution + syntax_structure | 2 agree (tag at the validator-recovered site) |
| **Total** | | **60** | | **60 agree, 0 presence-only** |

Every sampled name-only edge was verified by a check that resolves the identifier at the site to the target declaration, or by R1. None was verified because a symbol with that name exists. D-002A.1 holds on the sample. My first pass had 8 disagreements; all 8 were gaps in my resolver (it missed `export {...} from` re-exports and used the originator's enclosing-scope site instead of the validator's recovered JSX site). After fixing my resolver, all 60 agree. I report this so the agreement is not read as stronger than it is.

DESK, from reading the validators: Python `resolve_expr` and `resolve_top` do real scope and import resolution and match file, start line and name; the TS validator uses `Program` and `TypeChecker.getSymbolAtLocation`, follows the alias chain, and checks call and render positions. That agrees with the sample.

### a.4 Audit findings

**F-1, defect (classification), 36 records.** 36 `imports` edges are `verified` by `syntax_structure` alone (31 Python, 5 TSX; provenance `codegraph:resolved-qualified`). In every one, the target is the file's own import-statement node: for example `backend/tests/api/routes/test_login.py` imports `test_login.py::unittest.mock`; `frontend/src/main.tsx` imports `main.tsx::./index.css`; `backend/app/core/security.py` imports `security.py::pwdlib.hashers.bcrypt`. The check text is "module ... has ImportFrom of 'unittest.mock' at line 1". It confirms the import statement exists in the file. It resolves nothing: the target is a library module or a CSS file outside the validators' scope. That is presence of an import statement, which is what `observed` means. It is not presence-only verification in the D-002A.1 sense (no claim reaches another file's symbol on name presence), but the label overstates it. Fix: relabel these 36 to `observed` (class `source_backed_declaration`), or hold them under the library-hops ruling. Effect: verified CodeGraph edges 4,574 become 4,538.

**F-2, report accuracy.** Two hashes in Lab's step report are from run `1047-1` or not on disk (a.1). Results unaffected.

**F-3, open item O1 closes.** `tools/offline.sh` exports `HOME=task002/tools/cghome` (empty directory). The wrapper and `logs/netprobe.log` agree; ENV.md's "tools/home" is the inaccurate text. Documentation fix only (ruling R-6).

**F-4, note.** 896 `verified` records carry class `unverified_inference` (599 name-match, 284 jsx-render, 13 fixture). This is correct under the current spec, because class records origin. It reads as a contradiction, which is why the class rename is pending (section e).

### a.5 Fixture spot check, step 5 (TESTED, Traces audit)

I checked every location in `fixtures/chain_create_item.json` (15 claims, 70 locations) against the source at `b1125d8` line by line (`audit/fixture_lines.txt`) and against EXPECTED_CHAIN v2. Every line holds the expected token. Every range starts and ends on the expected declaration lines. Every link in the EXPECTED_CHAIN table has its cited lines in the fixture. The fixture adds some inputs beyond the table (for example `openapi-ts.config.ts:14,16,17` and `main.py:24` for L4; `api/main.py:3,6` for L5; `models.py:87` for L8). Each added line is correct and relevant. No defects. The fixture holds no injected claim; its `injected_set_location` points at the per-run `validator_inputs/injected.jsonl`.

### a.6 Injection placement (TESTED, Traces audit)

- The 3 injected claims (N1, N2a, N2b) are in `work/t002-20261021T1049-3/validator_inputs/injected.jsonl`.
- Searching every artifact for their claim ids, `uses_crud`, `traces-negative-control` and `"injected": true` (binary-safe, hidden and ignored files included) finds them only in that input file and in the validation outputs (`v1`, `v2`, `out/`), where they appear as rejected. The fixture builder source names them because it writes the input file.
- No hits in the checkout `src/fsft` (including `.codegraph/codegraph.db`, `-wal`, `-shm`), in `copyA` or `copyB`, or in adapter outputs `adapter_real`, `adapter_copyA`, `adapter_copyB`.
- Index query (read-only, immutable): no CodeGraph edge from `routes/private.py` to `get_current_user`, `CurrentUser` or `crud.py`, and none from `routes/items.py` to `crud.py`.
- Checkout at `b1125d8`, `git status` shows only the untracked `.codegraph/`.
- Lab's CT16 agrees: adapter opened no injected file, 0 injected records in adapter outputs, no index table with injected markers.

### a.7 The 9 CodeGraph rejections (TESTED, Traces audit, against source)

All 9 are name-only `imports` edges. All 9 rejections are correct.

| # | Importing file:line | Source text | CodeGraph target | Why it is wrong |
|---|---|---|---|---|
| 1 | `backend/tests/api/routes/test_users.py:7` | `from app import crud` | `backend/app/main.py::app` (main.py:21 `app = FastAPI(`) | `app` here is the package `backend/app/` (`__init__.py`, 0 bytes); the statement binds `crud`, which is `backend/app/crud.py` |
| 2 | `backend/tests/utils/user.py:4` | `from app import crud` | same | same |
| 3 | `backend/tests/crud/test_user.py:5` | `from app import crud` | same | same |
| 4 | `backend/app/api/routes/login.py:8` | `from app import crud` | same | same |
| 5 | `backend/app/api/routes/users.py:7` | `from app import crud` | same | same |
| 6 | `backend/app/core/db.py:3` | `from app import crud` | same | same |
| 7 | `backend/tests/utils/item.py:3` | `from app import crud` | same | same |
| 8 | `frontend/src/client/index.ts:3` | `export { ..., type Options, ... } from './sdk.gen'` | `client/client/types.gen.ts:164` `Options` | `Options` from `./sdk.gen` is `sdk.gen.ts:7` `export type Options<...>` |
| 9 | `frontend/src/client/index.ts:4` | `export type { ..., ClientOptions, ... } from './types.gen'` | `client/client/types.gen.ts:85` `ClientOptions` | `ClientOptions` from `./types.gen` is `frontend/src/client/types.gen.ts:3` |

Pattern: CodeGraph matches the name `app` or the type name to a same-named symbol in another file. These are the extractor failures the validators exist to catch.

## (b) L1 to L9 evidence classifications

All links: label `verified`, status `verified`, class `unverified_inference` (origin: Lab fixture claim). Source lines at `b1125d8`, checked by me (a.5). Validator and rule per Lab's establishing checks, TESTED (Lab); line checks TESTED (Traces audit).

| Link | Claim | Label / status | Validator(s) | Source file:line at b1125d8 | Assumptions |
|---|---|---|---|---|---|
| L1 | `Items` renders `AddItem` | verified | TS Compiler API: syntax_structure (JsxSelfClosingElement at 65 inside `Items` 57-70) + binding_resolution (import 8, default export 143 to decl 40-141) | `items.tsx:65`, `:8`, `:57-70`; `AddItem.tsx:40-141`, `:143` | none |
| L2A | `AddItem` binds `onSubmit` as the form handler | verified | TS: syntax (argument 0 of `form.handleSubmit` in JSX attribute `onSubmit` of `<form>`) + binding (to 68-70) | `AddItem.tsx:88`, `:68-70` | none |
| L2B | `onSubmit` calls `mutation.mutate` | verified | TS: syntax (CallExpression at 69 in `onSubmit`) + binding (`mutation` to 55-66) | `AddItem.tsx:69`, `:55-66`, `:68-70` | none |
| L3 | `mutationFn` calls `ItemsService.createItem` | verified | TS: syntax (call inside property `mutationFn` of `useMutation` argument) + binding (import 8, re-export `client/index.ts:3`, class 287-365, method 307-318) | `AddItem.tsx:56`, `:8`; `client/index.ts:3`; `sdk.gen.ts:287`, `:307-318` | none |
| L4 | `createItem` implements `POST /api/v1/items/` (`items-create_item`) | verified | R3 (opid to SDK join): K1 unique `.post` at `sdk.gen.ts:308`, url at `:311`; K2 name match under A3 | `sdk.gen.ts:307`, `:308`, `:311`; `types.gen.ts:809`, `:813`; `openapi-ts.config.ts:14`, `:16`, `:17`; `main.py:14-15`, `:24` | A3 (hey-api naming as a documented claim); flags `generated_file`, `runtime_config_dependent` |
| L5 | `POST /api/v1/items/` routes to `create_item` | verified | R1 (prefix `/api/v1` + `` + `` + `/items` + `/`) and R3 | `config.py:22`; `main.py:9`, `:35`; `api/main.py:3`, `:6`, `:10`; `items.py:10`, `:61-72` (def 62) | A1, A2 (FASTAPI_RULES); flag `runtime_config_dependent` |
| L6 | `create_item` depends on `get_db` | verified | R2 (`session: SessionDep`, alias `deps.py:26` `Annotated[Session, Depends(get_db)]`) | `items.py:63`, `:7`; `deps.py:26`, `:21-23` | none beyond R2's static scope |
| L7 | `create_item` depends on `get_current_user` | verified | R2 (`current_user: CurrentUser`, alias `deps.py:49`) | `items.py:63`, `:7`; `deps.py:49`, `:30-46` | none beyond R2 |
| L7T1, L7T2 | `get_current_user` depends on `get_db` and on `reusable_oauth2` (depth 2, reported separately) | verified | R2 | `deps.py:30`, `:26`, `:21-23`; `deps.py:27`, `:16-18` | none beyond R2 |
| L8 | `create_item` has a statically established persistence path through the `SessionDep` session | verified, qualifier "statically established persistence path" | R4 (steps: model_validation 68, session_stage 69, session_commit 70, session_reload 71; receiver bound by R2 to `sqlmodel.Session`; `Item` is `table=True`) | `items.py:68-71`, `:63`, `:7`, `:8`; `deps.py:26`, `:9`, `:21-23`; `models.py:87` | static only: no runtime write observed; app never started |
| L9A | `create_item` uses model `Item` | verified | Python `ast`: binding (`items.py:8` to `models.py:87`) + syntax (`Item.model_validate` at 68 inside `create_item` 62-72) | `items.py:68`, `:8`; `models.py:87-93` | none |
| L9B | `create_item` returns model `ItemPublic` | verified | Python `ast`: syntax (decorator `response_model=ItemPublic`) + binding (`models.py:97`) | `items.py:61`, `:8`; `models.py:97-100` | none |
| H1 | `form.handleSubmit` calls `onSubmit` | inferred / unvalidated (`library_contract`) | binding_resolution inconclusive: `react-hook-form` not installed | `AddItem.tsx:88` | library behavior |
| H2 | `mutation.mutate` calls `mutationFn` | inferred / unvalidated (`library_contract`) | binding_resolution inconclusive: `@tanstack/react-query` not installed | `AddItem.tsx:69`, `:56` | library behavior |

Chain rule applied by Lab (`out/chain.json`): a link is verified when its fixture claims are verified and every CodeGraph claim for the same link is verified or unvalidated with a stated reason. All nine links meet it. The end-to-end chain from click to commit is verified link by link except the two library hops H1 and H2, which stay visible as unvalidated.

## (c) N1 and N2 rejection evidence

All three were injected only into validator inputs (a.6). All three stay in the output with `visible_to_reviewer: true`, `injected: true`, label `inferred`, status `rejected`. Visible in `out/evidence.jsonl`, `out/chain.json` (`negative_controls`) and `out/coverage.json`.

| Control | Original claim | Originator | Rejection reason (Lab, checks) | My check against source |
|---|---|---|---|---|
| N1 | "items routes use crud": `items.py::create_item` uses `backend/app/crud.py` | `gitdiagram` (external page) | binding_resolution fail: 5 `items.py` handlers (R1); 0 calls resolving into `app.crud`; 0 module bindings to `app.crud`; 0 names containing `crud`; `create_item` writes through the `SessionDep` session at `items.py:68-71` (L8) | `items.py` has 0 occurrences of `crud`; it writes via `session.add/commit/refresh` at 69-71. `crud.py:63-68` does define a `create_item` with the same body shape, used by `tests/utils/item.py:16`. That is the likely source of the wrong claim. Rejection correct |
| N2a | `private.py::create_user` depends on `CurrentUser` | `traces-negative-control` (planted) | R2 fail: parameters `user_in`, `session`; closure `{get_db}` via `SessionDep`; no `dependencies=` on decorator, router, includes or app. Binding fail: no module binding named `CurrentUser`; imports from `app.api.deps`: only `SessionDep` | `private.py:6` `from app.api.deps import SessionDep`; `:23-24` `@router.post("/users/", ...)` / `def create_user(user_in: PrivateUserCreate, session: SessionDep)`. Rejection correct |
| N2b | `private.py::create_user` depends on `get_current_user` | `traces-negative-control` (planted) | same R2 and binding failures | same. Rejection correct |

## (d) Remaining limitations

| # | Limitation | Size | Status |
|---|---|---|---|
| 1 | H1, H2 library hops unvalidated | 2 links | By design; ruling pending (section e) |
| 2 | A1 to A3 assumptions under R1 and R3 (router composition is static; `custom_generate_unique_id` is the opid function; hey-api `byTags` naming, A3 as a documented claim, not a parsed library rule) | L4, L5 | Ruling pending (section e) |
| 3 | EOF trailing-line leniency in L2 | 2,968 records, 152 files, all `file` ranges; 2,959 would change status under a strict count (2,805 verified, 152 observed, 2 unvalidated, all to rejected) | Material; rule proposed in RULINGS R-2 |
| 4 | `claim_id` collisions | 608 ids, 3,334 records; 29 groups mix statuses | Spec defect; formula proposed in RULINGS R-1 (leaves 34 exact extractor duplicates) |
| 5 | Parse-only validation, no type-check | all TS and Python | Validators parse and bind. They do not type-check, and libraries are not installed, so library-typed receivers stay inconclusive (19 of the 59 unvalidated edges are `binding_resolution inconclusive`) |
| 6 | Library imports unresolved | 10 in smoke; 36 verified import-node edges (F-1) | F-1 relabel proposed |
| 7 | CodeGraph tarball hash | | Closed: recomputed offline, match; installed tree identical (RULINGS R-5a) |
| 8 | Custom schema checker instead of `jsonschema` | all records | Accepted for Task 002 with self-test; reference validator for Task 003 (RULINGS R-5b) |
| 9 | Static only | L8 and all links | No runtime evidence; `runtime_observed` has 0 records; app never started; `openapi.json` not generated |
| 10 | Audit resolver strength | 60-edge sample | My TS re-check is text-based over import statements and range nesting, not a second compiler. It corroborates Lab's TS validator; it does not replace it |
| 11 | Stale hashes in Lab's report | 2 values | F-2; correct values in a.1 |

## (e) Rulings pending with Architect1

These three were open before this step and stay open. My recommendation is given for each; none is applied.

1. **Library hops (O2).** H1, H2 and the 36 F-1 import-node edges. Recommendation: library behavior stays `inferred` / `unvalidated` with class `library_contract` until a later task installs pinned library sources offline and adds a rule per library. Import-node edges become `observed`. No link may count a library hop as verified.
2. **A1 to A3 as a documented deterministic rule.** Recommendation: accept A1 and A2 as part of R1 (they are read from repo source). Accept A3 only as a documented claim pinned to `@hey-api/openapi-ts` 0.97.3 (`frontend/package.json:52`) and the config lines `openapi-ts.config.ts:14,16,17`. Any change to that version or those lines turns L4 back to `unvalidated`.
3. **Rename class `unverified_inference` to `analyzer_inference`.** Recommendation: rename. 896 verified records carry the current name (F-4). The class records where a claim came from, and "unverified" contradicts the label once a validator verifies it.

Plus the six rulings in `RULINGS.md` (claim_id formula, EOF rule, setOpen, CT8 wording, tarball and schema limitations, housekeeping including O1).

## Files produced in this step

- `task002/review/REVIEW_PACKAGE_002.md` (this file)
- `task002/review/RULINGS.md`
- `task002/review/audit/a1_global.py`, `a2_sample.py`, `a3_independent.py`, `a4_eof.py`
- `task002/review/audit/sample_ids.json`, `sample_results.json`, `fixture_lines.txt`, `eof_quant.txt`, `claimid_collisions.txt`
- `task002/review/audit/ct_rerun/` (copy of run inputs plus the rerun `ct_results.json`)

Step 11 ends here. No further steps started.
