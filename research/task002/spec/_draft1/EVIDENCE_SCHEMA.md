# Evidence schema (Task 002, step 2)

Status: DESK SPEC, draft 1, 2026-10-21 (IST). Owner: Traces. Machine-readable form: `evidence_record.schema.json` (JSON Schema 2020-12) in this folder.
Nothing here assumes CodeGraph passed step 1. CodeGraph is one extractor among several. Whether it may also act as an independent validator is a flag set at step 1a (section 6).

## 1. What this schema must guarantee

| Requirement | Where it is met |
|---|---|
| Condition B: normalized provenance, extractor identity, validation status, source location on every relationship | sections 2, 4, 5, 8 |
| Condition C: four classes kept separate | section 3 |
| Condition C: L3 is the minimum, not sufficient alone | section 5, rule V2 and V3 |
| Condition C: "verified" needs independent parser or framework-rule validation | section 6 |
| Condition C: unsupported claims stay visible | section 9 |
| Approval condition 3: missing evidence is not false evidence | section 4.3, section 7 |
| Targets: provenance 100% classified as verified, unvalidated or missing_location; N1 and N2 rejected with reason, original kept | sections 5, 9 |

## 2. Claim record

One record per claim. A claim is a node (something declared at a location) or a relationship (from, kind, to). Records are written once. New checks append to `checks`. A status change appends to `status_history`. Nothing is edited in place or deleted.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `schema_version` | string | yes | `traces-evidence/0.1` |
| `claim_id` | string | yes | `c_` + sha256 of canonical JSON of `[repo_sha, claim_kind, relationship_kind, from.symbol, to.symbol, granularity, extractor.name]`. Deterministic: same input, same id. |
| `run_id` | string | yes | id of the run that wrote the record |
| `repo` | string | yes | `fastapi/full-stack-fastapi-template` |
| `repo_sha` | string | yes | 40 hex chars. `b1125d8839482cb7bbae603ddc6d0081bf87532e` for Task 002 |
| `claim_kind` | enum | yes | `node`, `relationship`, `unresolved_reference` |
| `node_kind` | string | node only | as the extractor reports it, for example `function`, `class`, `route`, `method` |
| `relationship_kind` | enum | relationship only | see 2.1 |
| `granularity` | enum | yes | `file`, `symbol`, `handler`, `statement`. N2 depends on this: a file-level claim and a handler-level claim are different claims. |
| `from`, `to` | endpoint | relationship only (`to` optional for `unresolved_reference`) | `{symbol, file, start_line, end_line}`. `symbol` is `<repo path>::<qualified name>`. |
| `statement` | string | yes | one plain sentence of the claim, for reviewers. For external claims, the original wording, quoted. |
| `class` | enum | yes | section 3 |
| `extractor` | object | yes | `{name, version, families[]}`. `families` lists every parser implementation the extractor used (section 6). |
| `provenance_raw` | object | yes | exactly what the source tool wrote, for example `{"provenance": null, "resolvedBy": "import", "confidence": 0.9}` |
| `provenance` | enum | yes | normalized value, section 8 |
| `origin` | object | yes | where the claim came from: `{kind: tool_output, artifact, row_ref}` or `{kind: external_document, artifact, sha256, quote}` or `{kind: negative_control, fixture_id, derived_from}` |
| `locations` | location[] | yes, may be empty only when status is `missing_location` | section 4 |
| `checks` | check[] | yes, may be empty | section 5 |
| `status` | enum | yes | `verified`, `unvalidated`, `missing_location`, `rejected` |
| `status_reason` | string | yes unless `verified` | why it is not verified. For `rejected`, the failing check id and its detail. |
| `status_history` | entry[] | yes | `{from, to, at, run_id, check_ids[], by}`. First entry has `from: null`. |
| `supersedes` | string or null | no | claim_id this record replaces at a new SHA or new extractor version. The old record stays. |
| `visible_to_reviewer` | boolean | yes | always `true`. Section 9. |
| `flags` | string[] | no | for example `generated_file`, `conditional_route`, `runtime_config_dependent` |

### 2.1 Relationship kinds in Task 002 scope

| Kind | Meaning | Used by |
|---|---|---|
| `contains` | parent declaration contains child declaration | adapter import |
| `imports` | module imports symbol or module | adapter import |
| `calls` | call expression at a site | adapter import, L3, L8 |
| `references` | name reference at a site | adapter import, L2 |
| `instantiates`, `extends`, `navigates` | as CodeGraph reports them | adapter import only |
| `renders` | JSX element of component B inside component A | L1 |
| `binds_handler` | event prop bound to a function | L2 |
| `implements_operation` | SDK method implements an API operation (method, full path, operation ID) | L4 |
| `routes_to` | API operation is served by a backend handler | L5 |
| `depends_on` | handler parameter resolved to a FastAPI dependency callable | L6, L7, N2 |
| `persists_via` | handler writes through a session API | L8, N1 (as `uses_crud`) |
| `uses_crud` | handler calls a function in `app.crud` | N1 |
| `declares_model`, `returns_model` | handler uses a table model, declares a response model | L9 |

## 3. Four claim classes (condition C)

Class says what kind of evidence the claim is. Status says how far it has been checked. They are separate fields and never merged.

| Class | Definition | Examples in scope | Can reach `verified`? |
|---|---|---|---|
| `source_backed_declaration` | the claim restates something written literally in source at one location | `@router.post("/", response_model=ItemPublic)` at `items.py:61`; `API_V1_STR: str = "/api/v1"` at `core/config.py:22`; `def create_item(` at `items.py:62` | yes, section 6 |
| `statically_derived` | the claim joins two or more locations by a stated rule or resolver | call edge `AddItem.tsx:56` to `sdk.gen.ts:307`; full path `/api/v1/items/` from four declarations; `CurrentUser` resolved to `get_current_user` | yes, section 6 |
| `unverified_inference` | the claim comes from an LLM, an external page, a name-only heuristic, or a negative-control fixture | GitDiagram "items routes use crud"; CodeGraph `jsx-render` synthesized calls; N2 | no. A passing check creates a new `statically_derived` record that cites it in `origin.derived_from`; the inference record itself stays `unvalidated` or becomes `rejected`. |
| `runtime_observed` | the claim comes from executing the app | none in Task 002 | not in Task 002. 0 records by design. |

Class assignment is fixed when the record is written and never changes.

## 4. Location

```
{ "file": "backend/app/api/routes/items.py",
  "start_line": 61, "end_line": 72, "start_col": 0, "end_col": 15,
  "line_base": 1, "col_base": 0,
  "precision": "site | declaration | enclosing_scope | file",
  "range_rule": "expression | decorator_to_body_end | def_to_body_end | declaration_line | file",
  "role": "site | from_decl | to_decl | input",
  "blob_sha": "<git blob id of file at repo_sha>",
  "recovered_by": null }
```

4.1 Lines are 1-based. Columns are 0-based. Any tool output with other bases is converted by the adapter and the conversion is recorded in `provenance_raw`.

4.2 `precision`:
- `site`: the line holds the expression that makes the claim true (for example the call).
- `declaration`: the line range of a declaration (function, class, alias).
- `enclosing_scope`: the tool gave the line of an enclosing function, not the site. CodeGraph `jsx-render` edges do this: in the Task 001 index, `Items` to `AddItem` carries line 57 (`function Items() {`), the JSX is at `items.tsx:65`. **TESTED** (read-only query of the Task 001 index).
- `file`: the claim is true of the file as a whole.

L3 (section 5) can pass only on `site` or `declaration` precision. A claim with only `enclosing_scope` or `file` precision cannot be verified at `handler` or `statement` granularity until a site location is recovered (section 7).

4.3 A claim with no location is `missing_location`, not false. The Task 001 index has 1,981 such edges (1,893 `contains`, 88 `references` with `valueRef`). Section 7 defines their recovery path.

4.4 Range rule for handlers: `decorator_to_body_end`, so `create_item` is `items.py:61-72`. `def_to_body_end` gives `62-72`. Both are recorded when both are known; a one-line difference between decorator and `def` is not a conflict.

## 5. Checks

```
{ "check_id": "k_<sha256>",
  "method": "L1_path_exists | L2_range_in_file | L3_token_at_location | parser_independent | framework_rule | location_recovery | human_review",
  "validator": {"name": "traces-py-ast", "version": "cpython 3.14.x", "families": ["cpython-ast"]},
  "reads_extractor_output": false,
  "independent": true,
  "inputs": [ <location>, ... ],
  "expected": "token 'crud.' inside items.py:61-72",
  "result": "pass | fail | inconclusive | error",
  "detail": "0 occurrences of 'crud.'; calls found at 68,69,70,71: Item.model_validate, session.add, session.commit, session.refresh",
  "run_id": "...", "at": "2026-10-xxTxx:xx:xx+05:30" }
```

Methods:
- `L1_path_exists`: `git cat-file -e <repo_sha>:<file>`.
- `L2_range_in_file`: `1 <= start_line <= end_line <= line count` of the blob at `repo_sha`.
- `L3_token_at_location`: the expected token or tokens appear inside the cited range, read from the blob at `repo_sha`. Text check only.
- `parser_independent`: a parser from a different family (section 6) finds the syntax node the claim needs at the cited range, for example a `Call` node whose callee is `session.add` at line 69.
- `framework_rule`: one of FASTAPI_RULES.md R1, R2, R3 reproduces the relationship from its own inputs.
- `location_recovery`: section 7.
- `human_review`: a named reviewer's decision. Allowed to move `rejected` back to `unvalidated` with a reason. Never sufficient alone for `verified`.

`independent` is computed, never set by hand: `true` only if `reads_extractor_output` is `false` and the validator's `families` share no member with the claim's `extractor.families`.

## 6. Independence and the step 1a flag

Parser families in Task 002:

| Family id | Implementation | Note |
|---|---|---|
| `codegraph-tree-sitter` | CodeGraph 1.6.2, web-tree-sitter grammars | extractor always; validator only if `codegraph_validator_eligible = true` |
| `cpython-ast` | CPython 3.14 `ast` | needed for `deps.py:36` (`except InvalidTokenError, ValidationError:`) |
| `typescript-compiler` | TypeScript compiler API | version per open question Q2 |
| `second-parser` | fallback, only if step 1a sets the flag false | see open question Q1 |

`codegraph_validator_eligible` is written by Traces at step 1a from Lab's step 1 grades. Default before step 1a: `false`. While `false`, CodeGraph checks may be recorded but have `independent: false` for every claim.

## 7. Status rules and transitions

Status is derived from the checks by one deterministic function. The function is part of the spec, so a reviewer can recompute it.

Validation rules:
- **V1.** No location at all: `missing_location`.
- **V2.** L1, L2 and L3 must pass on every location with `role` in `site`, `from_decl`, `to_decl`, `input`.
- **V3.** At least one check with `independent: true`, method `parser_independent` or `framework_rule`, result `pass`.
- **V4.** No check with `independent: true` and result `fail` that has not been answered by a later `human_review` entry.
- **V5.** `class = unverified_inference` never becomes `verified`.
- **V6.** `granularity` in `handler` or `statement` needs a location with precision `site` or `declaration` at that granularity. A file-level location does not satisfy a handler-level claim, and a handler-level failure does not reject a file-level claim.

Derived status:

| Condition | Status |
|---|---|
| V1 | `missing_location` |
| any independent `fail` not answered (V4 broken) | `rejected` |
| V2 broken because L1 or L2 fails (path or range does not exist at SHA) | `rejected` |
| V2 broken because L3 fails | `rejected` if an independent check also fails; otherwise `unvalidated` with reason `L3 fail, no independent confirmation` |
| V2, V3, V4, V6 hold and V5 does not apply | `verified` |
| anything else | `unvalidated` |

Allowed transitions (each appends to `status_history`):

| From | To | Trigger |
|---|---|---|
| (new) | `unvalidated` | record written with a location |
| (new) | `missing_location` | record written with no location |
| `missing_location` | `unvalidated` | `location_recovery` check passes and adds a location |
| `missing_location` | `missing_location` | recovery inconclusive. Stays, with reason. Never becomes `rejected` for lack of a location alone. |
| `unvalidated` | `verified` | derived status becomes `verified` |
| `unvalidated` | `rejected` | derived status becomes `rejected` |
| `verified` | `unvalidated` | a later independent check fails or is inconclusive and needs review |
| `rejected` | `unvalidated` | `human_review` overturns the failing check, with a reason |

Not allowed: `missing_location` to `verified` in one step; `missing_location` to `rejected` without a location; any transition that deletes a check.

Location recovery (approval condition 3), method `location_recovery`:
- **R-contains.** For a `contains` edge with no line: take the child declaration's own range from its node record; parse the file with a family other than the extractor's; confirm the child's syntax node lies inside the parent's syntax node (file, class, function, interface, or type alias body) and the ranges nest. Pass adds a `declaration` location for the child and a `from_decl` location for the parent. Expected to recover most of the 1,893, since every child node carries start and end lines.
- **R-valueRef.** For a `references` edge with `valueRef: true` and no line: inside the source node's range, find identifier nodes that name the target. One hit: add a `site` location. Several hits: add all as `site` locations. Zero hits: `inconclusive`, status stays `missing_location`.
- **R-enclosing.** For an `enclosing_scope` location (for example `jsx-render`): inside that scope, find the JSX element or call whose tag or callee names the target. Same hit rules as R-valueRef. Pass adds a `site` location.
- Recovery never changes the claim's class or extractor. The recovered location records `recovered_by: <check_id>`.

## 8. Provenance normalization map for CodeGraph 1.6.2

Raw values from CodeGraph source: `provenance` is `'tree-sitter' | 'scip' | 'heuristic'` or unset (`src/types.ts:227`, column default `NULL` at `src/db/schema.sql:53`); `metadata.resolvedBy` is `'exact-match' | 'import' | 'qualified-name' | 'framework' | 'fuzzy' | 'instance-method' | 'file-path' | 'function-ref'` (`src/resolution/types.ts:48`). **VERIFIED-IN-CODE**. CodeGraph's own comment says bare `exact-match` "is what invents cross-module links out of common method names" (`src/db/queries.ts:2833-2838`). **VERIFIED-IN-CODE**

Counts are from the Task 001 index (`_work/fastapi-codegraph/.codegraph/codegraph.db`, read-only). They are a baseline for step 10, not an expectation that step 8 must match.

| Raw `provenance` | Raw metadata | Normalized `provenance` | Initial class | Initial status | Task 001 count |
|---|---|---|---|---|---|
| NULL | none (`contains`) | `codegraph:structural` | `source_backed_declaration` | `missing_location` (no line) | 1,893 |
| NULL | `resolvedBy: import` | `codegraph:resolved-import` | `statically_derived` | `unvalidated` | 1,628 (1,024 imports, 455 calls, 106 references, 43 instantiates) |
| NULL | `resolvedBy: qualified-name` | `codegraph:resolved-qualified` | `statically_derived` | `unvalidated` | 36 |
| NULL | `resolvedBy: instance-method` | `codegraph:resolved-instance` | `statically_derived` | `unvalidated` | 13 |
| NULL | `resolvedBy: function-ref` | `codegraph:resolved-function-ref` | `statically_derived` | `unvalidated` | 65 |
| NULL | `resolvedBy: framework` | `codegraph:resolved-framework` | `statically_derived` | `unvalidated` | 12 |
| NULL | `resolvedBy: exact-match` | `codegraph:name-match` | `unverified_inference` | `unvalidated` | 616 (317 references, 162 imports, 127 calls, 6 extends, 4 instantiates) |
| NULL | `resolvedBy: fuzzy` | `codegraph:fuzzy` | `unverified_inference` | `unvalidated` | 0 |
| NULL | `resolvedBy: file-path` | `codegraph:resolved-file-path` | `statically_derived` | `unvalidated` | 0 |
| NULL | `valueRef: true`, no line | `codegraph:value-ref` | `statically_derived` | `missing_location` | 88 |
| `heuristic` | `synthesizedBy: <x>` | `codegraph:synthesized:<x>` | `unverified_inference` | `unvalidated`, precision `enclosing_scope` when the line is the enclosing function | 291 (288 `jsx-render`, 3 `tanstack-link`) |
| `tree-sitter` | any | `codegraph:tree-sitter` | by resolver as above | `unvalidated` | 0 |
| `scip` | any | `codegraph:scip` | `statically_derived` | `unvalidated` | 0 |
| any other value | any | none | none | adapter fails the run (ADAPTER_CONTRACT CT4) | 0 |

Totals: 4,642 edges. Node records (2,076) map to `source_backed_declaration`, provenance `codegraph:declaration`, status `unvalidated`. Unresolved references (3,314, all `failed`) map to `claim_kind: unresolved_reference`, `statically_derived`, provenance `codegraph:unresolved`, status `unvalidated`, `site` location from their line and col.

`exact-match` is classed `unverified_inference` on purpose: it is a name-only join. Reason: CodeGraph's own comment above. This is a Traces decision; see open question Q3.

Non-CodeGraph extractors:

| Extractor | Normalized `provenance` | Class |
|---|---|---|
| `traces-py-ast`, `traces-ts-ast` declarations | `traces:parser` | `source_backed_declaration` |
| `traces-fastapi-rules` R1, R2, R3 | `traces:rule:R1` (R2, R3) | `statically_derived` |
| GitDiagram page claim (N1) | `external:gitdiagram-page` | `unverified_inference` |
| negative-control fixture (N2) | `fixture:negative-control` | `unverified_inference` |

## 9. Visibility and never-delete

- Every record has `visible_to_reviewer: true`. The field exists so a later consumer cannot silently drop a class; any later filter must report how many records it hides and by status.
- `rejected` records keep their original `statement`, `origin` and `locations`, plus the failing check. The reviewer sees what was claimed, by whom, and why it failed.
- No record or check is deleted. A new SHA or new extractor version writes new records and sets `supersedes`.
- The JSONL output is append-only within a run. A re-run writes a new file.

## 10. Coverage report fields (feeds step 10)

`total_records`, counts by `claim_kind`, `class`, `status`, normalized `provenance`, `extractor.name`; count of records with any null required field (target 0); count of `verified` records with no independent passing check (target 0); count of `missing_location` recovered, by recovery method; count of `rejected` with reason.

## 11. Open questions

- **Q1 (Architect1 or Shailesh).** If step 1a sets `codegraph_validator_eligible = false`, which second parser is approved? Candidates: `tree-sitter` Python bindings with `tree-sitter-python` and `tree-sitter-typescript` grammars (pip, small). This needs an install approval not in the current list.
- **Q2 (Architect1).** TypeScript version. TASK_002_PLAN.md said "pinned 5.x". The test repo declares `"typescript": "^6.0.3"` (`frontend/package.json:62`). Proposal: pin 6.0.x to match the repo, so the validator reads the same syntax the project compiles with.
- **Q3 (Architect1).** Accept classing CodeGraph `exact-match` edges (616 in Task 001) as `unverified_inference`, not `statically_derived`?
