<!-- Copied from the Traces seat's read-only review (2026-10-23 IST). Absolute box paths were replaced with placeholders: <review-clone> (a clean clone of this repo at 35499bc), <research> (the Task 002 research workspace, not in this repo), <data>, <cache>, <uv-cache>, <npm-cache>, <basetemp> (local scratch). Helper scripts named here live in the research workspace and are not committed. -->

# Review: v1 indexing and evidence path against the Task 002 rulings

Target: ShaileshRawat1403/traces, branch build/traces-v1, commit 35499bc7b1fa172bc977009d30d63f082be393cb (detached, clean worktree).
Reference: Decision 002-B (task002/spec/DECISIONS.md), CLOSEOUT_002.md, RULINGS.md, corrected run t002-20261021T1356-002b-2 (task002/out/SHA256SUMS).
Pinned target: full-stack-fastapi-template b1125d8839482cb7bbae603ddc6d0081bf87532e (cache clone of task002/src/fsft; the original is untouched).
Reviewed: 2026-10-23, about 12:20 IST. Read-only. No commits, pushes, PR comments or GitHub write calls. The target app was not run. No AI or GitNexus calls.

Evidence tags used below:
- [test] verified by a test or a run I executed
- [code] read in code, not executed
- [inferred] my reading of intent or consequence, not checked

## Verdict summary

| # | Check | Verdict | Blocks v1 |
|---|-------|---------|-----------|
| 1 | claim_id formula, determinism, collisions, consolidation | PASS | no |
| 2 | EOF semantics, with and without terminal newline | PASS | no |
| 3 | L1 to L9 verified, A3 qualified, H1/H2 inferred library_contract unvalidated | PARTIAL (docs only) | no |
| 4 | 9 wrong imports rejected, 36 observed, 4,538/36/59/9 of 4,642 | PASS | no |
| 5 | N1, N2a, N2b rejected and visible | PARTIAL | no |
| 6 | missing_location never becomes verified | PASS (with the D-Q9 recovery caveat) | no |
| 7 | analyzer_inference kept, class separate from status, include_rejected, no static-as-runtime | PARTIAL | no |
| X | Isolation fallback in the product index (found while reviewing check 1 inputs) | FINDING | policy call, see F2 |

No finding blocks v1 on evidence correctness. F2 is the one item that conflicts with a Task 002 ruling (stop when isolation cannot be shown) and needs an explicit Architect1 decision.

## Findings

| ID | Severity | Blocks v1 | Tag | Summary |
|----|----------|-----------|-----|---------|
| F1 | medium | no | [code][test] | CT4 negative assertion is commented out (tests/contract/_ct.py:47). Same defect in research tests/ct_evaluate.py:44 from my 002-B edit. Outcome is correct today, the assertion is dead. |
| F2 | medium | policy (recommend yes for fail-closed default) | [code] | TRACES_ISOLATION=auto falls back to isolation=none with a warning and the product index still stores a ready snapshot (index.py:206-209, pipeline.py:40-47, workers/sandbox.sh:24, adapter/codegraph.py:199-205 skips check 4.7). Conflicts with D-Q5 and D-002A.6 (spec/DECISIONS.md:13, 29): if isolation cannot be shown, stop that run. |
| F3 | low | no | [test][code] | Injected controls (N1, N2a, N2b) carry no injected marker in claim list items (api/app.py:334-338) or graph edges (views.py:498-502); flags are []. With include_rejected they read as repo facts, e.g. private.py::create_user depends_on deps.py::get_current_user, rejected. Only the claim detail page shows "Injected" (web/src/features/evidence/ClaimPage.tsx:178). |
| F4 | low | no | [test][code] | Unfocused graph with include_rejected=true and limit 2000: rejected edges sort last (views.py:20, 477-484) and are truncated away; hidden_counts is then {} so the 12 rejected are neither shown nor counted. truncated=true is the only signal. |
| F5 | low | no | [test][code] | hidden_counts in a focused graph is snapshot-wide (views.py:400-405 counts before focus at 438-475): focus on items.py::create_item reports rejected 12 while 1 rejected edge is in that neighborhood. |
| F6 | low | no | [code] | A3 ruling-4 wording is absent from v1 docs. The code carries the qualification (python_ast.py:438, 445-461, 673-695, detail "K2 (A3, documented claim)"), docs/DECISIONS.md does not. |
| F7 | low | no | [code] | report.py not ported: no chain.json or coverage.json in a v1 run; L1 to L9 traceability is held by tests only (tests/regression/test_regression.py::test_nine_links_and_library_hops). |
| F8 | low | no | [code] | tests/unit/test_index_worker.py:118-120 comment says "missing_location never verified" but the assertion only checks status verified implies label verified. The invariant is held elsewhere (schema 0.4, orchestrator), not by this test. |
| F9 | info | no | [test] | Locations added by R-contains recovery have recovered_by null (source validator), while R-valueRef sets recovered_by. Recovery is still traceable via the location_recovery history entry and its check ids. Inherited from Task 002. |
| F10 | info | no | [code] | docs/DECISIONS.md:36 (D-011) says missing_location "is never verified". True for the status itself; recovered records do become verified after location_recovery by design (D-Q9). Suggest wording: "never verified without recovered source locations". |
| F11 | info | no | [code] | The product store for the fastapi b1125d8 snapshot contains fixture and injected records (index.py:8-16, 236-252). Expected and gated by snapshot, noted so it is not mistaken for indexer output. |
| F12 | info | no | [test] | test_store_concurrency fails under unshare -rn (loopback down in the namespace). Passes 3/3 outside. Environment artifact. |

## Check 1: claim_id

Verdict: PASS.

- [code] Formula: backend/traces/core/common.py:50-60 claim_id hashes canonical JSON (common.py:120-125) over repo_sha, claim_kind, kind, granularity, from and to (symbol plus range), anchor, target_name, extractor {name, version}. Anchor order site, to_decl, from_decl, input at common.py:63-72. Matches Decision 002-B ruling 1.
- [code] Adapter call: backend/traces/adapter/codegraph.py:310-312. Consolidation and E_COLLISION: codegraph.py:374-409.
- [code] Store: backend/traces/evidence/store.py:166-181 plain INSERT with PK (snapshot_id, claim_id) in migrations/0001_init.sql:52-65, so a duplicate id cannot be stored silently.
- [test] Recompute on run rv1 (review_checks.py): 10,016 records, 10,016 distinct ids, 0 shared, 0 recompute mismatches. Same id set as task002 out and as the product index run.
- [test] Consolidation: 34 consolidated records covering 68 rows, each with status_history entry and raw provenance kept.
- [test] RT1, RT2, RT3 pass in tests/regression/_rt.py:36, 51, 75.

## Check 2: EOF

Verdict: PASS.

- [code] line_count common.py:22-25; normalize_file_range common.py:28-41 maps whole-file [1, n] with end_exclusive_line n+1 and keeps original coordinates; adapter endpoints codegraph.py:278-284, decl file ranges codegraph.py:295-299, eof report codegraph.py:430; strict L2 elsewhere orchestrator.py:308-316.
- [test] 94,472 locations and inputs checked, 16,959 file ranges, 0 violations; 2,968 normalized records.
- [test] RT4 (with terminal newline, _rt.py:102) and RT5 (without newline and empty file, _rt.py:111) pass on synthetic files. RT5 reports 0 real indexed files without a terminal newline, so the no-newline branch is covered only synthetically. RT6 (_rt.py:126) passes.

## Check 3: chain L1 to L9, A3, H1/H2

Verdict: PARTIAL (code and data pass; docs gap F6, artifact gap F7).

- [test] L1, L2A, L2B, L3, L4, L5, L6, L7, L7T1, L7T2, L8, L9A, L9B are verified at b1125d8, traced through fixture records (backend/traces/fixtures/task002/chain.py:115-127). Establishing methods: TS syntax_structure plus binding_resolution for L1, L2A, L2B, L3; R3 for L4; R1+R3 for L5; R2 for L6, L7; R4 for L8 with qualifier; syntax plus binding for L9A, L9B.
- [test] H1, H2: status unvalidated, label inferred, class library_contract, no establishing check. API trace labels library_contract hops (views.py:537-551).
- [code] A3: version pin python_ast.py:438 ({"fastapi": "0.141.1", "@hey-api/openapi-ts": "0.97.3"}), version read 445-457, gate 459-461, K2 config read (methodName, containerName, strategy) and generated-output cross-check 673-695 with detail "K2 (A3, documented claim)". Matches the rulings in code.
- [code] F6: docs/DECISIONS.md has no A3 or ruling-4 text.
- [test] test_nine_links_and_library_hops passes.

## Check 4: distribution and imports

Verdict: PASS.

- [test] rv1 and product index: 4,642 edges, 4,538 verified, 36 observed, 59 unvalidated, 9 rejected. Exact match to 002b-2.
- [test] The 9 rejected are import edges 2024, 2052, 2085, 2157, 2189, 2200, 2210, 2310, 2315 (independent check fails, orchestrator.py:344-347).
- [test] All 36 observed carry qualifier "observed import statement" (orchestrator.py:22, 362-368, 385-390).
- [test] Overall records: verified 4,551, observed 5,313, unvalidated 140, rejected 12.
- [test] Validation canonical hash 73db432b... equal for rv1, product index and task002 out. Records equal after stripping volatile fields. RT7 (_rt.py:136), test_baseline_distribution, test_canonical_hashes_match_task002, test_index_baseline pass.

## Check 5: N1, N2a, N2b

Verdict: PARTIAL (rejected and reachable, not marked as injected in lists and graph).

- [code] v1 has them as injected validator inputs, only for the fastapi b1125d8 snapshot (index.py:8-16, 236-252; chain.py:182 negative_controls expected rejected).
- [test] Store: injected=3, all status rejected, label rejected. API: claims default hidden_counts {"rejected": 12}; include_rejected=true with status=rejected returns 12 items (9 imports, 2 depends_on, 1 uses_crud). Focused graph: items.py::create_item shows uses_crud to crud.py rejected (N1); private.py::create_user shows depends_on get_current_user and CurrentUser rejected (N2a, N2b).
- [test][code] F3: flags [] and no injected key in list items or graph edges.

## Check 6: missing_location

Verdict: PASS, with the D-Q9 caveat (F10).

Every status writer [code]:
- adapter: codegraph.py:319 (unvalidated or missing_location, label inferred), 345-347 (missing_location).
- fixture builder: chain.py:115-127 (starts unvalidated).
- orchestrator status(): orchestrator.py:339-382. No locations returns missing_location (341-343) before any verified branch (371-373).
- orchestrator apply(): 392-422. missing_location goes to unvalidated only through location_recovery with recovered locations (410-413), then status() (416-417).
- migrate: migrate.py:23-35 sets label and the no_source_location flag only, status untouched.
- No API route mutates claim status (api/app.py read-only claim routes 305-341, 410-415, 428-431).

Schema [code][test]: v0.4 allOf/4 forces label inferred for missing_location; allOf/7 forces at least 1 location for any non-missing_location static record. Probe (ml_probe.py): a verified record with locations removed fails schema 0.4 (2 errors, stdlib checker also invalid); a missing_location record labeled verified fails (1 error); status() on a record with no locations and passing checks returns missing_location.

Data [test]: 1,981 records passed through missing_location; 1,979 end verified and 2 unvalidated, all via missing_location to unvalidated (location_recovery, passing check id) then the computed status. 0 went straight to verified or observed, 0 verified records lack locations, 0 records end as missing_location. Recovered locations: 3,782 validator-sourced (recovered_by null, F9) and 112 R-valueRef.

## Check 7: class, status, include_rejected, runtime wording

Verdict: PARTIAL (F1, F4, F5).

- [code] analyzer_inference kept: adapter/codegraph.py:36-46, 83. [test] 0 old class names; 896 analyzer_inference records verified; class unchanged by validation (RT8, _rt.py:143).
- [code][test] F1: tests/contract/_ct.py:47 has `# [002-B] ruling 5 rename and ncode("CT4_resolvedBy_guess") == "E_PROVENANCE_UNKNOWN"` after the active expression, so the negative half is a comment. The 002b-2 run did produce E_PROVENANCE_UNKNOWN, so behavior is right. docs/TEST_MAPPING.md:12 lists the CT4 port change as "none", which is accurate because the defect came over from research tests/ct_evaluate.py:44 (my 002-B edit; pre-002-B _superseded_v1/tests/ct_evaluate.py:44 had the clause active). Fix: move the clause before the comment in both files.
- [code] include_rejected: views.py:88-94 (_allowed), graph 389-405, trace 554-563, list api/app.py:305-341. [test] default hides 12 with hidden_counts; include_rejected shows them in list and focused graph; F4 and F5 as above.
- [code] Static vs runtime: api/app.py:86, api/models.py:147 and 252 disclaimer "Static analysis only. No runtime behavior has been observed."; explain/engine.py:25-45 runtime word guard and forbidden phrases, rejected excluded at 93-94 and 134-138; persistence phrasing "statically established persistence path" (engine.py:54); web UserFlow.tsx:99 "Nothing was executed, and no database was contacted."
- [test] All static records have evidence_scope static. Explain "Does creating an item write to the database?" answers with the static persistence path at backend/app/api/routes/items.py:68 (verified), categories.runtime_observations empty. tests/explain runtime-unknown test passes. I found no static evidence presented as runtime behavior.

## Commands run

Setup (network used only here):
```
git clone https://github.com/ShaileshRawat1403/traces <review-clone>
git -C <review-clone> fetch origin build/traces-v1
git -C <review-clone> checkout --detach 35499bc
UV_CACHE_DIR=<uv-cache> uv sync --frozen --python <pinned CPython 3.14.8>
cd toolchain && unshare -rn npm ci --offline --ignore-scripts --no-audit --no-fund --cache <npm-cache>   # TS 6.0.3, CodeGraph 1.6.2
git clone --no-hardlinks <research>/task002/src/fsft <cache>/targets/github.com__fastapi__full-stack-fastapi-template/b1125d8839482cb7bbae603ddc6d0081bf87532e/source
```

Baseline indexer run (offline, 47.9 s):
```
TRACES_CACHE_DIR=<cache> TRACES_DATA_DIR=<data> TRACES_ISOLATION=unshare .venv/bin/python -m traces.evidence.pipeline baseline --run-id rv1
```

Tests:
```
TRACES_BASELINE_RUN=<data>/runs/rv1 .venv/bin/pytest -q -p no:cacheprovider tests/contract tests/regression    # 32 passed (16 CT, 8 RT, plus regression tests)
unshare -rn .venv/bin/pytest -q -p no:cacheprovider tests/unit tests/api tests/explain tests/history --deselect tests/api/test_index_baseline.py    # 268 passed, 2 skipped (live network), 1 failed (test_store_concurrency, loopback, F12)
.venv/bin/pytest -q -p no:cacheprovider tests/api/test_store_concurrency.py    # 3 passed (outside the namespace)
.venv/bin/pytest -q -p no:cacheprovider --basetemp=<basetemp> tests/api/test_index_baseline.py    # 1 passed (product index reproduces Task 002)
```

Independent checks (all offline, read-only):
```
unshare -rn .venv/bin/python <research>/v1_review/review_checks.py <data>/runs/rv1 <pt>/data/runs/idx-j_ad6bf937b9724da9af07 <pt>/data/traces.sqlite3   # review_checks_output.json
unshare -rn .venv/bin/python <research>/v1_review/ml_probe.py <data>/runs/rv1      # ml_probe_output.json
unshare -rn .venv/bin/python <research>/v1_review/api_probe.py <pt>/data/traces.sqlite3                 # api_probe_output.json (works on a /tmp copy of the store)
unshare -rn .venv/bin/python <research>/v1_review/api_probe2.py                                         # api_probe2_output.json
```
`<pt>` = `<basetemp>/test_product_index_reproduces_0`

## Recommended fixes before or soon after v1

1. F2: make the product index fail closed when isolation resolves to none, unless an explicit opt-in is set, and record isolation on the snapshot.
2. F1: restore the CT4 negative clause in tests/contract/_ct.py:47 and research tests/ct_evaluate.py:44.
3. F3: add injected to claim list items and graph edges, or a flag such as injected_control.
4. F4, F5: rank rejected edges so include_rejected keeps them under truncation, or report truncated-away counts; scope hidden_counts to the focused selection.
5. F6, F10: add the A3 ruling-4 text and adjust the D-011 wording.
6. F8: make the test_index_worker assertion match its comment.
