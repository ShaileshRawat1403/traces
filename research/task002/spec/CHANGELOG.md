SPEC v3 (2026-10-21, Traces): Decision 002-B corrections applied. v2 text is kept in `../_superseded_v1/spec/`.

# Spec changelog

Draft 1 (2026-10-21, before 10:02 IST) is kept unchanged in `_draft1/`. Version 2 applies the decisions recorded in `DECISIONS.md`. Each row names the decision it implements.

## Version 3 (2026-10-21, Decision 002-B)

| # | File | Change | Decision |
|---|---|---|---|
| 1 | DECISIONS.md | New section D-002B: rulings 1 to 5 and corrections A and B, with the review scope (REVIEW_PACKAGE_002.md only) | D-002B |
| 2 | EVIDENCE_SCHEMA.md, JSON Schema | EOF rule: whole-file range [1, n] with `end_exclusive_line` n + 1; original coordinates kept in `original`; `terminal_newline`; the EOF position is never an addressable line or evidence location; strict L2 for every other range | D-002B.1 |
| 3 | EVIDENCE_SCHEMA.md, JSON Schema | claim_id v3 over source location, relationship identity, unresolved target name and extractor identity; `consolidation` field for exact duplicates; `E_COLLISION` for distinct claims sharing an id | D-002B.2 |
| 4 | EXPECTED_CHAIN.md | H1, H2 recorded as inferred, unvalidated library-contract assumptions; no library source | D-002B.3 |
| 5 | FASTAPI_RULES.md, EXPECTED_CHAIN.md | A1 and A2 source-backed framework rules; A3 pinned to hey-api 0.97.3 and its config with generated output corroborating, version pin alone not independent proof | D-002B.4 |
| 6 | EVIDENCE_SCHEMA.md, JSON Schema | `unverified_inference` renamed `analyzer_inference`; class is origin only and no longer constrains status | D-002B.5 |
| 7 | EVIDENCE_SCHEMA.md, JSON Schema | Rule V3i: imports edge to the file's own import statement is `observed`, qualifier `observed import statement`; `schema_version` `traces-evidence/0.3` | D-002B correction A |
| 8 | ADAPTER_CONTRACT.md | CT4 class name; CT5 requires the schema checker self-test to run and pass; CT10 counts consolidated rows; CT15 indexer evidence for runs that reuse an index; consolidation allowed as the one merge | D-002B.2, .5, correction A |

## Version 2 (2026-10-21)

| # | File | Change | Decision |
|---|---|---|---|
| 1 | DECISIONS.md | New file: D-Q1 to D-Q10, D-002A.1 to .10, Lab environment facts, frozen checker, isolation evidence, hygiene H-001, open items | D-Q, D-002A |
| 2 | EVIDENCE_SCHEMA.md, JSON Schema | Validator families limited to CPython `ast` 3.14.8 and TypeScript Compiler API 6.0.3; "second parser" option and any tree-sitter validator removed | D-Q1 |
| 3 | all specs | TypeScript 6.0.3 replaces 5.x, with integrity, shasum, lockfile and log from Lab | D-Q2 |
| 4 | EVIDENCE_SCHEMA.md | `codegraph_validator_eligible` flag removed; CodeGraph is extractor only; every CodeGraph record starts `inferred`; `originator` replaces `extractor`, validators never originate claims | D-002A.2 |
| 5 | EVIDENCE_SCHEMA.md, JSON Schema | Three labels `observed`, `verified`, `inferred`; status `observed` added for nodes and unresolved references; label derived from status; mapping table to the four classes | D-Q7 |
| 6 | EVIDENCE_SCHEMA.md, JSON Schema | Check methods split: `parser_presence` (presence only) vs `syntax_structure`, `binding_resolution`, `deterministic_rule` (relationship); `establishes` field; V3 requires a relationship-establishing independent check; symbol existence never verifies | D-Q1, D-002A.3 |
| 7 | EVIDENCE_SCHEMA.md | `unverified_inference` can reach `verified` only through V3 (draft 1 forbade it entirely) | D-Q3 ("unless independently validated") |
| 8 | EVIDENCE_SCHEMA.md | 616 `exact-match` edges: `unverified_inference`, label `inferred`, kept with provenance | D-Q3 |
| 9 | EVIDENCE_SCHEMA.md, JSON Schema | `renders` is its own kind; CodeGraph `jsx-render` `calls` map to `renders`; V6 requires a `site` at the JSX element | D-002A.4 |
| 10 | EVIDENCE_SCHEMA.md, JSON Schema | `range_kind` with `declaration` vs `body`; table 4.1 of which range each claim type uses; `setOpen` recorded (declaration 86, body 87 to 97, CodeGraph 87 to 97) | D-002A.1 |
| 11 | EVIDENCE_SCHEMA.md | `contains` reclassed `statically_derived` (relationship); R-contains expected outcome 1,891 of 1,893 with the two exceptions ending `unvalidated`, not `rejected` | D-Q9, approval condition 3 |
| 12 | EVIDENCE_SCHEMA.md, JSON Schema | `evidence_scope` fixed to `static`; `qualifier`; `injected`; `library_contract` kind that cannot be `verified` | D-002A.7, .8, .9 |
| 13 | FASTAPI_RULES.md | New R4, static persistence path: step types `model_validation`, `session_stage`, `session_commit`, `session_reload`; receiver check through `SessionDep` to `Session` and `get_db`; label "statically established persistence path" | D-Q4, D-002A.5 |
| 14 | FASTAPI_RULES.md | Rules are validators, not originators; binding resolution defined for Python and TS; app never started; `openapi.json` deferred, needs separate authorization; assumption A4 added | D-Q6, D-002A.3, D-002A.7 |
| 15 | ADAPTER_CONTRACT.md | Pins filled (CodeGraph integrity and shasum); paths set to Lab's `task002/src/fsft` and `task002/tools/offline.sh`; adapter never sets `observed` or `verified`; `E_ISOLATION`, `E_INJECTED` added | D-002A.2, D-002A.6 |
| 16 | ADAPTER_CONTRACT.md | CT7 uses frozen `line_checker_v1.0.0` `--mode parser` (378 of 379 authoritative; 351 and 320 logged for audit) | D-002A.1 |
| 17 | ADAPTER_CONTRACT.md | CT8 expects 1,981 missing locations, 0 rejected, 1,891 of 1,893 recovered | D-Q9 |
| 18 | ADAPTER_CONTRACT.md | CT15 rewritten: OS-level `unshare -rn` only; per-run probe from a wrapper-spawned child covering `sh -c curl`, bundled Node 24.16.0 `child_process`, direct `https` and `net`; namespace ids logged; outside control; stop on failure; env vars do not count. Cites `task002/logs/netprobe.log` | D-Q5, D-002A.6 |
| 19 | ADAPTER_CONTRACT.md | New CT16: injected claims never enter the adapter, the index or the checkout. Contract tests are now 16 (TASK_002_PLAN.md said 15) | D-002A.8 |
| 20 | EXPECTED_CHAIN.md | Each link lists claims, establishing method and expected label; L8 rewritten for R4; L2 claims limited to what syntax and bindings show; library hops H1, H2 added as `library_contract`, staying `inferred` | D-Q1, D-002A.3, D-002A.5 |
| 21 | EXPECTED_CHAIN.md | N1 and N2 are both injected into validator inputs only; N2 is the planted "`private.py:create_user` depends on `CurrentUser`/`get_current_user`" as two records; CodeGraph's true `private.py:6` import edges stay separate and not rejected | D-Q8, D-002A.8 |
| 22 | EXPECTED_CHAIN.md | Step 11 review package defined | D-002A.10 |
| 23 | DECISIONS.md | Hygiene H-001 (`lab/tools/gitnexus/home/.npm`) recorded, retained, not deleted | D-002A.6 |

## Not changed

- `TASK_002_PLAN.md` (outside `spec/`) still says TypeScript 5.x and 15 contract tests. The specs here supersede it on those points.
- Gates: `b1125d8`, CodeGraph 1.6.2, read-only checkout, L1 to L9 independently verified, N1 and N2 rejected and visible, 100% of records classified. Unchanged; a failed criterion is reported, not relaxed (D-Q10).
