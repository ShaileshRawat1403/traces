<!-- Copied from the Traces seat's read-only recheck at b37eef2 (2026-10-23 IST). Absolute box paths were replaced with placeholders: <review-clone> (clean clone of this repo), <review-dir>, <research> (Task 002 research workspace, not in this repo), <data>, <cache>, <basetemp> (local scratch). Helper scripts and outputs named here live in the research workspace and are not committed. -->

# Addendum: recheck of review findings at b37eef2

Target: ShaileshRawat1403/traces build/traces-v1 at b37eef2c41fda7aa1cbcc76dc376b31a168f39ab (merge of PR #27), detached in `<review-clone>`, worktree clean.
Base review: REVIEW_V1_EVIDENCE.md (35499bc). Rechecked 2026-10-23, about 12:55 to 13:15 IST. Read-only: no commits, pushes, PR comments or GitHub writes. The target app was not run. No new dependency installs: uv.lock and toolchain locks are unchanged; the pyproject.toml change is lint and mypy config only, and the existing .venv and toolchain were reused.
Tags: [test] executed by me, [code] read in code.

## Results

| Finding | Verdict | Evidence |
|---|---|---|
| F2 isolation | PASS [test][code] | pipeline.py:44-74 resolve_isolation: auto and unshare probe workers/sandbox.sh under unshare and raise IsolationUnavailable (code E_ISOLATION) on failure; none and other values are refused; only off returns off. index.py:213-221 resolves before any fetch and raises isolation_failed "E_ISOLATION: ..."; index.py:252-254 maps adapter E_ISOLATION the same way. adapter/codegraph.py:199-210 skips 4.7 only for off, raises E_ISOLATION otherwise. sandbox.sh:23-27 accepts unshare or off, exit 64 otherwise. store.py:197-204 and migration 0003 store snapshots.isolation; app.py:200 exposes isolation and unisolated (true only for off). Tested by me with a fake failing unshare first on PATH: baseline pipeline with TRACES_ISOLATION=auto, unshare and none each exit 1 with "E_ISOLATION: ..." and create no run directory; resolve_isolation(off) returns off. tests/unit/test_isolation.py 12 passed (auto and none fail closed, nothing fetched, no claims; off gives ready snapshot with isolation=off and unisolated=true; auto gives unshare and unisolated=false). Product index snapshot from my run: isolation unshare, unisolated false. auto no longer falls back. |
| F1 CT4 clause | PASS [test] | tests/contract/_ct.py:47 now ends `and ncode("CT4_resolvedBy_guess") == "E_PROVENANCE_UNKNOWN"` before the comment. Mutation proof in a scratch copy in a temp directory (run copied, CT4 negative errors code changed to E_SOMETHING_ELSE): new _ct.py gives CT4 FAIL on the mutated run and PASS on the real run; the 35499bc _ct.py gives PASS on both. No other CT changed. Scratch deleted afterwards. Research tests/ct_evaluate.py:44 still has the dead clause (outside the repo, not changed). |
| F3 injected marker | PASS [test][code] | views.py:46-55 output_flags adds injected_control; summary views.py:71-72, graph edges views.py:537, trace hops views.py:587; list items app.py:395-396. Probe on the product store: the 3 injected (2 depends_on, 1 uses_crud) have injected=true and flag injected_control in claims and in focused graph edges; the 9 rejected imports have injected=false. tests/api/test_hardening.py:160 passes. |
| F4 truncation | PARTIAL [test][code] | Rejected edges still sort last (views.py:20, 511-516) and are still cut under limit, but are now counted: truncated_counts views.py:519, returned at 556. Probe, unfocused, limit 2000, include_rejected=true: 0 rejected shown, hidden_counts {}, truncated_counts {verified 2551, observed 36, unvalidated 61, rejected 12}. hidden_counts is correct (they are not hidden by the filter). With rel=imports,uses_crud,depends_on (no truncation) all 12 show. Counted, not kept; D-028 (docs/DECISIONS.md:132) chooses "reported, not lost". Acceptable if Architect1 accepts reporting instead of keeping. tests/api/test_hardening.py:173 passes. |
| F5 focused hidden_counts | PARTIAL [test][code] | Now scoped: views.py:492 focus_scope, 502-509. Probe: create_item and create_user focus give rejected 2 each (was 12). New issue: hidden edges count when either end is in the neighbourhood (views.py:508), shown edges need both ends in it (views.py:496). For items.py::create_item, hidden_counts says rejected 2 but include_rejected shows only 1 (N1 uses_crud); the second is N2a create_user depends_on get_current_user, which touches the neighbourhood but is never shown there. tests/api/test_hardening.py:184 passes (its fixture does not hit this case). |
| F7 report.py | PASS [test] | backend/traces/evidence/report.py:9-107 (port), called at pipeline.py:289-291. My run wrote v1/validation/chain.json and coverage.json, report exit 0. Structural diff against task002/out: only run_id differs, both files. chain summary L1 to L9 verified, H1 and H2 unvalidated, N1, N2a, N2b rejected. tests/regression/test_report.py passes. |
| F8 missing_location test | PASS [test][code] | tests/unit/test_index_worker.py:121-135: no missing_location record labeled verified, every verified record has a location, every transition out of missing_location is to unvalidated by location_recovery with check_ids, no missing_location to verified, and seen_ml > 0 so recovery is exercised. Passes. On fastapi, my check: 1,981 through missing_location, 0 direct to verified or observed, 0 verified without locations. |

## Indexer re-run on fastapi b1125d8 (offline)

- Command: `TRACES_CACHE_DIR=<cache> TRACES_DATA_DIR=<data> TRACES_ISOLATION=auto .venv/bin/python -m traces.evidence.pipeline baseline --run-id rv2-b37eef2` (44.3 s; workers ran under unshare, PROBE_SUMMARY a to e pass, wrapper_ns differs from outer_ns).
- Validation canonical hash v1 and v2: 73db432be3babab4922f3158a9ed86b63a2454f61647d883f978701f5ff0053d, equal to task002/out. Product index run: same hash.
- Edges 4,642: verified 4,538, observed 36, unvalidated 59, rejected 9. Unchanged. Records 10,016, claim_id distinct 10,016, 0 shared, 0 recompute mismatch, EOF 0 violations, records and claim_id sets equal to task002 (review_checks_output_b37eef2.json).

## Test suite

- `unshare -rn sh -c 'ip link set lo up && TRACES_BASELINE_RUN=<rv2> TRACES_CACHE_DIR=... .venv/bin/pytest -q -p no:cacheprovider --basetemp=<basetemp> tests'`: 523 passed, 3 skipped (live GitHub, TRACES_NETWORK_TESTS unset), 1 failed. Loopback was brought up inside the namespace, so test_store_concurrency now passes offline.
- The 1 failure is tests/api/test_index_baseline.py: POST index-jobs needs the anonymous GitHub HEAD probe, upstream_unavailable offline. Re-run outside the namespace (anonymous probe only; workers still under unshare): 1 passed.
- Total: 524 passed, 3 skipped, 0 real failures.

## New issues or regressions

| ID | Severity | Blocks v1 | Note |
|---|---|---|---|
| A1 | low | no | F5 scope mismatch above (views.py:496 vs 508): focused hidden_counts can exceed what include_rejected reveals. |
| A2 | info | no | F4 keeps counting, not keeping (views.py:516-519); decision recorded in D-028. |
| A3 | info | no | /meta isolation reports unshare for auto even when unshare is unavailable (app.py:215); jobs still fail closed, so this is display only. |
| A4 | info | no | config.py:25 comment still lists "auto, unshare, none". |
| A5 | info | no | test_index_baseline needs network for the anonymous probe, so the full suite is not fully offline. |
| A6 | info | no | Research tests/ct_evaluate.py:44 still has the dead CT4 clause (outside the repo). |

No regression in evidence: hash, distribution, chain, claim ids and EOF results are unchanged from 35499bc and Task 002.

## Artifacts

v1_review/: api_probe3.py and api_probe3_output.json, f5_probe.py, review_checks_output_b37eef2.json. Run: `<data>/runs/rv2-b37eef2`. Logs: `<review-dir>/baseline_rv2.log`, `tests_b37eef2.log`.
