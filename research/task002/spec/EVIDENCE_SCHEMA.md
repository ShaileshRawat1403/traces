# Evidence schema (Task 002, step 2), version 3

Status: DESK SPEC v3, 2026-10-21 (IST), Decision 002-B applied (section 11). Owner: Traces. Machine-readable form: `evidence_record.schema.json` (JSON Schema 2020-12, `schema_version` `traces-evidence/0.3`). Decisions applied: `DECISIONS.md`. Changes from draft 1: `CHANGELOG.md`. Draft 1 is kept in `_draft1/`.

## 1. What this schema must guarantee

| Requirement | Source | Where |
|---|---|---|
| Normalized provenance, extractor identity, validation status, source location on every relationship | condition B | sections 2, 4, 8 |
| Four classes kept separate | condition C | section 3 |
| L3 is the minimum, not sufficient | condition C | rule V2, V3 |
| Three labels: observed, verified, inferred | D-Q7 | section 3 |
| Validator families are CPython `ast` and the TypeScript Compiler API 6.0.x only; no tree-sitter validator | D-Q1 | section 6 |
| CodeGraph is a structural extractor only; never a validator; never straight to verified | D-002A.2 | sections 6, 8 |
| Verified needs syntax, binding resolution, or a documented deterministic rule | D-002A.3 | rule V3 |
| Symbol existence never verifies a relationship | D-Q1 | rule V3 |
| JSX render is its own relationship type, location checked before verified | D-002A.4 | sections 2.1, 7 |
| Declaration location distinct from body location | D-002A.1 | section 4 |
| Missing evidence is not false evidence | approval condition 3 | section 7 |
| No static evidence presented as runtime | D-002A.9 | `evidence_scope`, `qualifier` |
| Every surfaced claim has classified provenance; inferences stay visibly unverified | D-002A.9 | sections 8, 9 |

## 2. Claim record

A claim is a node (something the source declares at a location), a relationship (from, kind, to), or an unresolved reference (the source mentions a name at a location; the extractor did not resolve it). Claims enter only from **originators**: the extractor (CodeGraph), an external document (N1), or a fixture (expected chain hypotheses, negative controls). Validators never originate claims; they attach checks. Records are written once; checks and status changes are appended; nothing is deleted.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `schema_version` | string | yes | `traces-evidence/0.3` |
| `claim_id` | string | yes | v3 (D-002B.2): `c_` + sha256 of canonical JSON of `{repo_sha, claim_kind, kind, granularity, from {symbol, range}, to {symbol, range}, location, target_name, extractor {name, version}}`; section 11.2 |
| `run_id` | string | yes | run that wrote the record |
| `repo`, `repo_sha` | string | yes | `fastapi/full-stack-fastapi-template`, `b1125d8839482cb7bbae603ddc6d0081bf87532e` |
| `claim_kind` | enum | yes | `node`, `relationship`, `unresolved_reference` |
| `node_kind` | string | node | as reported by the originator |
| `relationship_kind` | enum | relationship | section 2.1 |
| `granularity` | enum | yes | `file`, `symbol`, `handler`, `statement`, `path` |
| `from`, `to` | endpoint | relationship (`to` optional for unresolved) | `{symbol, file, start_line, end_line}`, symbol = `<repo path>::<qualified name>` |
| `statement` | string | yes | plain sentence; for external and fixture claims, the original wording |
| `class` | enum | yes | section 3; origin only, fixed at write time, never changed by validation (D-002B.5) |
| `originator` | object | yes | `{name, version, role}`; `role` is `extractor`, `external`, or `fixture` |
| `provenance_raw` | object | yes | exactly what the originator wrote |
| `provenance` | string | yes | normalized, section 8 |
| `origin` | object | yes | `{kind: tool_output, artifact, row_ref}` or `{kind: external_document, artifact, sha256, quote}` or `{kind: fixture, fixture_id, fixture_file, derived_from}` |
| `injected` | boolean | yes | `true` for negative controls. Injected claims exist only in validator test inputs (D-002A.8). |
| `evidence_scope` | enum | yes | `static` for every Task 002 record. `runtime` is reserved and invalid in Task 002 (D-002A.7). |
| `qualifier` | string or null | no | required display wording when a rule sets one, for example `statically established persistence path` (R4) |
| `locations` | location[] | yes | section 4; empty only when status is `missing_location` |
| `checks` | check[] | yes | section 5 |
| `status` | enum | yes | `observed`, `verified`, `unvalidated`, `missing_location`, `rejected` |
| `label` | enum | yes | `observed`, `verified`, `inferred`; derived from status, section 3 |
| `status_reason` | string | unless `observed` or `verified` | why not established; for `rejected`, failing check ids and detail |
| `status_history` | entry[] | yes | `{from, to, at, run_id, check_ids[], by}` |
| `supersedes` | string or null | no | replaced claim at a new SHA or originator version; old record stays |
| `visible_to_reviewer` | boolean | yes | always `true` |
| `consolidation` | object | no | present only on a record that consolidates exact duplicate originator rows: `{rule, count, members[{row_ref, provenance_raw, status_history}]}` (D-002B.2, section 11.2) |
| `flags` | string[] | no | `generated_file`, `conditional_route`, `runtime_config_dependent`, `extractor_location_is_body`, `extractor_file_errors`, `library_contract` |

### 2.1 Relationship kinds

| Kind | Meaning | Notes |
|---|---|---|
| `contains` | parent declaration contains child declaration | structural |
| `imports` | module imports module or symbol | |
| `calls` | call expression at a site | not used for JSX |
| `renders` | JSX element `<B ...>` inside component A | **distinct from `calls`** (D-002A.4). CodeGraph `calls` edges with `synthesizedBy: jsx-render` are imported as `renders`, raw kind kept in `provenance_raw`. |
| `references` | name reference at a site | |
| `instantiates`, `extends`, `navigates` | as CodeGraph reports | import only |
| `binds_handler` | an identifier is passed as an event or callback argument at a site | static binding only; what the library does with it is a `library_contract` hop |
| `implements_operation` | SDK method implements an API operation (method, full path, operation ID) | R3 |
| `routes_to` | API operation served by a backend handler | R1, R3 |
| `depends_on` | handler parameter or dependency list resolves to a FastAPI dependency callable | R2 |
| `model_validation` | call that builds or validates a model instance (`Item.model_validate`) | R4 step type, not a write |
| `session_stage` | `Session.add` and peers on the bound session | R4 |
| `session_commit` | `Session.commit` on the bound session | R4; a commit attempt |
| `session_reload` | `Session.refresh` on the bound session | R4; a reload, not a write |
| `persistence_path` | ordered static path from handler through the bound session to stage and commit | R4; `qualifier` = `statically established persistence path` |
| `uses_crud` | handler calls a function in `app.crud` | N1 |
| `uses_model`, `returns_model` | handler uses a table model; declares a response model | L9 |
| `library_contract` | a library invokes a callback (for example `mutate` invokes `mutationFn`) | cannot be established in Task 002; stays `inferred` |

## 3. Classes, statuses and labels

Class says how the claim was produced (origin). Status says what the checks established (verification). Label is what a reviewer sees. Class and status are separate fields and neither constrains the other in the JSON Schema; class never changes when status does (D-002B.5).

**Labels (D-Q7):**
- **observed**: what the source contains (a declaration, an import statement, a call expression), confirmed at its location by a validator parser.
- **verified**: independent evidence for a relationship, established by syntax, binding resolution, or a documented deterministic rule (D-002A.3).
- **inferred**: an analyzer's or other originator's belief that is not (yet) established. This includes everything `unvalidated`, `missing_location` and `rejected`. A rejected claim shows as "inferred, rejected" with its reason.

| Status | Label | Allowed for claim kinds |
|---|---|---|
| `observed` | observed | `node`, `unresolved_reference`; `relationship` only for `imports` edges whose target is the file's own import statement, with `qualifier` `observed import statement` (D-002B, correction A) |
| `verified` | verified | `relationship` |
| `unvalidated` | inferred | all |
| `missing_location` | inferred | all |
| `rejected` | inferred | all |

**Classes (condition C, renamed by D-002B.5). Origin only; the right column is the usual status path, not a constraint:**

| Class | What it covers | Usual status path |
|---|---|---|
| `source_backed_declaration` | nodes; unresolved references (the source text at a line) | `observed` |
| `statically_derived` | relationships the extractor resolved through something written down: an import, a qualified name, a typed receiver, a function reference, a framework pattern, a file path, or structural containment | `verified` |
| `analyzer_inference` (was `unverified_inference`) | name-only matches (`exact-match`, `fuzzy`), synthesized heuristic edges, external documents, fixture hypotheses, injected negative controls | `verified` only through rule V3, never through symbol existence (D-Q1, D-Q3) |
| `runtime_observed` | execution evidence | nothing in Task 002: the app is never started (D-002A.7). 0 records. |

Naming note: the label "observed" refers to source text only. It never means runtime observation.

## 4. Location

```
{ "file": "backend/app/api/routes/items.py",
  "start_line": 61, "end_line": 72, "start_col": 0, "end_col": 15,
  "line_base": 1, "col_base": 0,
  "range_kind": "declaration | body | site | enclosing_scope | file",
  "range_rule": "decorator_to_body_end | header_to_body_end | binding_statement | body_only | expression | file",
  "role": "site | from_decl | to_decl | input",
  "blob_sha": "<git blob id at repo_sha>",
  "source": "originator | validator",
  "recovered_by": null }
```

- Lines 1-based, columns 0-based.
- Whole-file ranges (`range_kind: file`) follow the EOF rule of section 11.1 and carry `original`, `end_exclusive_line` and `terminal_newline`. No other range may carry them, and no other range may reach the EOF position.
- **`range_kind` separates declaration from body (D-002A.1).**
  - `declaration`: from the declaring line (decorator, `def`, `class`, `function`, or the `const` binding for a function-valued `const`) to the end of the statement.
  - `body`: the function body or the function expression only, without the declaring line.
  - `site`: the expression that makes a relationship true.
  - `enclosing_scope`: the originator gave the line of an enclosing declaration instead of the site.
  - `file`: the whole file.
- Recorded example: CodeGraph gives `frontend/src/components/ui/sidebar.tsx` `setOpen` as 87 to 97, which is the arrow function inside `React.useCallback(` (`body`). The declaration is line 86 to 99 (`const setOpen`). The adapter emits CodeGraph's range as `declaration` by default; when the frozen line checker finds the start is a body start, the validator appends a `declaration` location with `source: validator`, and the record gets flag `extractor_location_is_body`. The node can still be `observed`; the CodeGraph range is never relabeled in place.
### 4.1 Which range each claim type uses

| Claim or relationship | Location that must be checked | Range kind | Rule |
|---|---|---|---|
| node: function, method, class | declaration | `declaration` | from `def`/`class`/`function`/method name, or the `const` binding for a function-valued `const`, to statement end. A CodeGraph body range (for example `setOpen` 87 to 97) is kept, appended with the validator's declaration range, flag `extractor_location_is_body`. |
| node: route (FastAPI) | decorator | `declaration` | decorator line to body end (`decorator_to_body_end`) |
| node: route (TanStack) | `createFileRoute` call | `declaration` | binding statement |
| node: variable, alias (`SessionDep`) | binding statement | `declaration` | `binding_statement` |
| `contains` | both ends | `declaration` for parent and child; a child that is a function expression may match by `body` (setOpen case) | AST nesting |
| `calls`, `references`, `imports`, `binds_handler` | the expression | `site` | `expression`; the multi-line import's first line |
| `renders` | the JSX element | `site` | `expression`; `enclosing_scope` never suffices (V6) |
| `depends_on` | the parameter annotation or `dependencies=` entry, plus the alias binding as `input` | `site` + `declaration` | |
| `routes_to`, `implements_operation` | every rule input (decorator, prefixes, url literal, client call) | `site` / `declaration` | per R1, R3 |
| `model_validation`, `session_stage`, `session_commit`, `session_reload` | the call expression | `site` | `expression` |
| `persistence_path` | each step site plus the receiver binding chain | `site` + `declaration` | per R4 |
| `uses_model`, `returns_model` | the call or the `response_model=` keyword, plus the model declaration | `site` + `declaration` | |

- Handler range rule is `decorator_to_body_end` (`items.py:61-72`). `header_to_body_end` (`62-72`) is also kept when known. CodeGraph function nodes use the `def` line (62); route nodes use the decorator line (61).

## 5. Checks

```
{ "check_id": "k_<sha256>",
  "method": "L1_path_exists | L2_range_in_file | L3_token_at_location | parser_presence | syntax_structure | binding_resolution | deterministic_rule | location_recovery | human_review",
  "establishes": "presence | location | relationship | none",
  "rule_id": "R1 | R2 | R3 | R4 | R-contains | R-valueRef | R-enclosing | null",
  "validator": {"name": "traces-ts-compiler", "version": "typescript 6.0.3", "family": "typescript-compiler"},
  "reads_originator_output": false,
  "independent": true,
  "inputs": [ <location>, ... ],
  "expected": "...", "result": "pass | fail | inconclusive | error",
  "detail": "...", "run_id": "...", "at": "2026-10-xxTxx:xx:xx+05:30" }
```

| Method | What it shows | `establishes` |
|---|---|---|
| `L1_path_exists` | file exists at `repo_sha` | `location` |
| `L2_range_in_file` | range inside the file | `location` |
| `L3_token_at_location` | expected text inside the range (text only) | `location` |
| `parser_presence` | a validator parser finds the declaration, import statement or call expression at the range | `presence` |
| `syntax_structure` | the relationship is a direct syntax fact: child node inside parent node; JSX element inside a component body; keyword argument on a decorator | `relationship` |
| `binding_resolution` | a name at the site resolves through scope and imports to the target declaration (Python: module scope plus `import`/`from ... import`; TS: `Program` with the repo `tsconfig.json`, `TypeChecker.getSymbolAtLocation` and `getAliasedSymbol`) | `relationship` |
| `deterministic_rule` | FASTAPI_RULES R1 to R4 reproduce the relationship from source | `relationship` |
| `location_recovery` | section 7 | `location` |
| `human_review` | a named reviewer's note | `none`; can move `rejected` to `unvalidated` with a reason; never establishes anything |

`independent` is computed: `true` only if the validator family is `cpython-ast` or `typescript-compiler`, `reads_originator_output` is `false`, and the validator is not the claim's originator. CodeGraph checks do not exist: CodeGraph is never a validator (D-002A.2).

## 6. Validator families (D-Q1, D-Q2, D-002A.2)

| Family | Implementation | Pin |
|---|---|---|
| `cpython-ast` | CPython stdlib `ast` | 3.14.8 (needed: `deps.py:36` uses 3.14 syntax) |
| `typescript-compiler` | official TypeScript Compiler API | `typescript@6.0.3`, integrity `sha512-y2TvuxSZPDyQakkFRPZHKFm+KKVqIisdg9/CZwm9ftvKXLP8NRWj38/ODjNbr43SsoXqNuAisEf1GdCxqWcdBw==`, lockfile `task002/tools/ts6/package-lock.json` |

No other family exists in Task 002. Tree-sitter in any form is not a validator, because CodeGraph is built on it. Deterministic rules R1 to R4 run on these two families and count as `deterministic_rule` checks.

Limit: the 6.0.3 recheck covered parsing only (`task002/step1/RECHECK_TS6.md`). `binding_resolution` on TS needs a `Program` and `TypeChecker`; this has not been run on this repo yet. Library packages are not installed, so only repo-local bindings can resolve; library symbols resolve to nothing and give `inconclusive`.

## 7. Status rules, transitions and location recovery

Status is computed from checks by one deterministic function.

- **V1.** No location: `missing_location`.
- **V2.** `L1`, `L2`, `L3` pass on every location with role `site`, `from_decl`, `to_decl`, `input`.
- **V3 (verified).** At least one independent check with `establishes: relationship`, method `syntax_structure`, `binding_resolution` or `deterministic_rule`, result `pass`, whose inputs include every `site` location of the claim. A `parser_presence` pass on both ends never satisfies V3: two parsers agreeing that symbols exist does not verify a dependency or call (D-Q1).
- **V3o (observed).** For `node` and `unresolved_reference`: V2 plus an independent `parser_presence` pass at the declaration or site.
- **V3i (observed import statement, D-002B correction A).** For an `imports` relationship whose target is the import node of the same file (library and CSS imports, 36 at `b1125d8`): V2 plus an independent `parser_presence` pass at the site gives `observed` with `qualifier` `observed import statement`. The validator confirms the statement exists; it does not establish what the imported library or stylesheet provides, so V3 does not apply.
- **V4.** No independent `fail` left unanswered by `human_review`.
- **V5.** `granularity` `handler`, `statement` or `path` needs `site` or `declaration` locations at that granularity. A file-level location never satisfies a handler-level claim; a handler-level failure never rejects a file-level claim.
- **V6.** `renders` needs a `site` location at the JSX element before V3 can apply. An `enclosing_scope` location is not enough (D-002A.4).

| Condition | Status |
|---|---|
| V1 | `missing_location` |
| independent `fail` unanswered | `rejected` |
| L1 or L2 fails | `rejected` |
| L3 fails, no independent fail | `unvalidated`, reason `L3 fail, not established` |
| relationship: V2, V3, V4, V5, V6 hold | `verified` |
| node or unresolved reference: V2, V3o, V4 hold | `observed` |
| import statement edge: V2, V3i, V4 hold | `observed`, qualifier `observed import statement` |
| otherwise | `unvalidated` |

Transitions (appended to `status_history`):

| From | To | Trigger |
|---|---|---|
| new | `unvalidated` or `missing_location` | record written |
| `missing_location` | `unvalidated` | `location_recovery` pass |
| `missing_location` | `missing_location` | recovery inconclusive; never `rejected` for lack of location alone |
| `unvalidated` | `verified` / `observed` | computed status changes |
| `unvalidated` | `rejected` | independent fail |
| `verified` / `observed` | `unvalidated` | later independent fail or inconclusive needing review |
| `rejected` | `unvalidated` | `human_review` with reason |

Not allowed: `missing_location` straight to `verified` or `observed`; any deletion.

**Location recovery** (method `location_recovery`, validator families only):
- **R-contains**, for `contains` edges with no line. Take the child's start line from its node record; parse the file; confirm the child's syntax node sits inside the parent's (matching by name and start line). Pass adds a `declaration` location for both ends, then V3 can apply through `syntax_structure`. **Expected outcome: 1,891 of 1,893 recovered** (Lab step 1 and the 6.0.3 recheck, `task002/step1/GRADING.md` section "Containment", `RECHECK_TS6.md`). The 2 known exceptions are not rejected:
  - `createSseClient` contains `abortHandler` (`frontend/src/client/core/serverSentEvents.gen.ts:143`): ancestor correct, immediate parent `createStream` has no CodeGraph node. Result `inconclusive`, status `unvalidated`, reason `transitive containment, immediate parent not a node`. Generated file.
  - `SidebarProvider` contains `setOpen`: the body versus declaration offset (86 vs 87). With the `body` range kind of section 4 the child matches as a body; until the validator records the declaration, status `unvalidated`, reason `declaration line differs from extractor line`.
- **R-valueRef**, for the 88 `references` edges with `valueRef: true` and no line. Inside the source node's range, find identifiers naming the target with the validator parser; then resolve them (`binding_resolution`). One or more resolved hits: add `site` locations. Zero: stays `missing_location`. Lab found the target name inside the source span for 88 of 88 (`step1/logs/12_noline_refs.log`), which is text evidence only and does not establish the reference.
- **R-enclosing**, for `enclosing_scope` locations, mainly the CodeGraph `jsx-render` edges (line = enclosing component). Inside that scope, find the JSX element whose tag resolves (`binding_resolution`) to the target. Hits add `site` locations. Lab found the `<Target` tag inside the source span for all heuristic JSX edges (`step1/GRADING.md`), again text evidence only.
- Recovery never changes class or originator.

## 8. Provenance normalization map for CodeGraph 1.6.2

Raw values: `provenance` is `'tree-sitter' | 'scip' | 'heuristic'` or unset (`src/types.ts:227`, default `NULL` at `src/db/schema.sql:53`); `metadata.resolvedBy` is one of `'exact-match' | 'import' | 'qualified-name' | 'framework' | 'fuzzy' | 'instance-method' | 'file-path' | 'function-ref'` (`src/resolution/types.ts:48`). **VERIFIED-IN-CODE**. CodeGraph's own comment: bare `exact-match` "is what invents cross-module links out of common method names" (`src/db/queries.ts:2833-2838`).

Every CodeGraph record starts with label `inferred` (D-002A.2). Counts: Task 001 index and Lab's step 1 index (same totals, `step1/GRADING.md` "Index run"). Baseline for step 10, not a target.

| Raw `provenance` | Raw metadata | Normalized `provenance` | Class | Initial status | Count |
|---|---|---|---|---|---|
| NULL | none (`contains`) | `codegraph:structural` | `statically_derived` | `missing_location` | 1,893 |
| NULL | `resolvedBy: import` | `codegraph:resolved-import` | `statically_derived` | `unvalidated` | 1,628 |
| NULL | `resolvedBy: qualified-name` | `codegraph:resolved-qualified` | `statically_derived` | `unvalidated` | 36 |
| NULL | `resolvedBy: instance-method` | `codegraph:resolved-instance` | `statically_derived` | `unvalidated` | 13 |
| NULL | `resolvedBy: function-ref` | `codegraph:resolved-function-ref` | `statically_derived` | `unvalidated` | 65 |
| NULL | `resolvedBy: framework` | `codegraph:resolved-framework` | `statically_derived` | `unvalidated` | 12 |
| NULL | `resolvedBy: exact-match` | `codegraph:name-match` | `analyzer_inference` | `unvalidated` | **616** (D-Q3) |
| NULL | `resolvedBy: fuzzy` | `codegraph:fuzzy` | `analyzer_inference` | `unvalidated` | 0 |
| NULL | `resolvedBy: file-path` | `codegraph:resolved-file-path` | `statically_derived` | `unvalidated` | 0 |
| NULL | `valueRef: true`, no line | `codegraph:value-ref` | `statically_derived` | `missing_location` | 88 |
| `heuristic` | `synthesizedBy: jsx-render` | `codegraph:synthesized:jsx-render` | `analyzer_inference`, kind `renders` | `unvalidated`, `enclosing_scope` location | 288 |
| `heuristic` | `synthesizedBy: tanstack-link` | `codegraph:synthesized:tanstack-link` | `analyzer_inference` | `unvalidated` | 3 |
| `tree-sitter` or `scip` | any | `codegraph:tree-sitter` / `codegraph:scip` | by resolver as above | `unvalidated` | 0 |
| any other | any | none | none | adapter fails (CT4) | 0 |

Total 4,642 edges. Nodes (2,076): `codegraph:declaration`, `source_backed_declaration`, `unvalidated` until V3o. Unresolved references (3,314, all `failed`): `codegraph:unresolved`, `source_backed_declaration`, `unvalidated` until V3o; they can reach `observed` (the call text is there), never `verified`.

The 616 name-only matches: kept in output with provenance; label `inferred` unless V3 passes for the same endpoints; never displayed as confirmed (D-Q3).

Other originators:

| Originator | Normalized `provenance` | Class | `injected` |
|---|---|---|---|
| Expected-chain fixture (Lab step 5, from ground truth) | `fixture:expected-chain` | `analyzer_inference` | false |
| GitDiagram public page (N1) | `external:gitdiagram-page` | `analyzer_inference` | true |
| Planted false dependency (N2) | `fixture:negative-control` | `analyzer_inference` | true |

## 9. Visibility, never-delete, acceptance principles

- `visible_to_reviewer: true` on every record. Any later filter reports how many records it hides, by status.
- `rejected` records keep `statement`, `origin`, `locations` and the failing checks.
- No deletion. New SHA or originator version: new records with `supersedes`.
- Injected claims (N1, N2) live only in the validator test input set, never in the target checkout or in CodeGraph's index (D-002A.8). The adapter output and the injected set are separate files, merged only in the validation output, each record carrying `injected`.
- `evidence_scope` is `static` everywhere. No record states or implies runtime behavior; R4 output carries `qualifier: statically established persistence path`.
- Git-history motives are out of Task 002; if any record ever states a motive, its class is `analyzer_inference` and it can never be `verified`.

## 10. Coverage report fields (step 10)

Totals by `claim_kind`, `class`, `status`, `label`, normalized `provenance`, `originator.name`, `injected`. Targets: 0 records with a null required field; 0 `verified` records without an independent relationship-establishing check; 100% of records classified (status in the five values, label in the three); recovery counts by method against the expected 1,891 of 1,893; the 616 name-only matches reported by final label.

## 11. Decision 002-B additions (2026-10-21)

### 11.1 EOF rule (D-002B.1)

- `n` = number of addressable lines of the blob at `repo_sha`: the count of newline characters, plus 1 when the blob is non-empty and does not end in a newline. An empty blob has `n = 0`.
- A whole-file range is `start_line 1`, `end_line n`, `end_exclusive_line n + 1`, `terminal_newline` true, false, or null for an empty blob. The extractor's coordinates are kept unchanged in `original` (`{start_line, end_line}`), and file endpoints keep `original_end_line`.
- The position after the final newline (line `n + 1`) is allowed only as the exclusive end boundary of a whole-file range. It is never an addressable source line and never an evidence location. L2 enforces `1 <= start_line <= end_line <= n` for every other range kind.
- CodeGraph 1.6.2 reports file ranges ending at newline count + 1. At `b1125d8` every non-empty indexed file ends in a newline, so `original.end_line` = `n + 1`; empty files give `original.end_line` 1 and normalized `end_line` 0. The case without a terminal newline does not occur in this repo and is covered by synthetic regression tests only.

### 11.2 claim_id v3 and consolidation (D-002B.2)

- Inputs: `repo_sha`, `claim_kind`, kind (`relationship_kind` or `node_kind`), `granularity`, `from` and `to` as `{symbol, range [file, start_line, end_line]}`, `location` (the anchor: the first originator location in role order `site`, `to_decl`, `from_decl`, `input`, as `[role, range_kind, file, start_line, start_col, end_line, end_col]`, normalized per 11.1), `target_name` (`[reference_name, reference_kind]` for unresolved references, otherwise null) and `extractor` (`{name, version}` of the originator). Canonical JSON, sorted keys, no whitespace.
- Ids are regenerated deterministically from record content (regression RT1 recomputes every id).
- Exact duplicates: originator rows that yield the same id and identical content apart from their row ids are one claim. The adapter keeps the record of the lowest row and adds `consolidation`, which lists every contributing row with its `row_ref`, full `provenance_raw` and `status_history`. Nothing is dropped.
- Distinct claims never share an id: if rows with one id differ in any other content, the adapter stops with `E_COLLISION`.

### 11.3 Class is origin only (D-002B.5)

`class` values: `source_backed_declaration`, `statically_derived`, `analyzer_inference`, `runtime_observed`. The JSON Schema no longer ties a status to a class; for example an `analyzer_inference` record can be `verified` through V3 and keeps class `analyzer_inference`.
