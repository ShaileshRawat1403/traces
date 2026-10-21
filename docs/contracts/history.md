# History module contract (Traces v1)

Status: DRAFT v2, 2026-10-21 (IST). v2 folds in Architect1's answers to the v1 open items (section 20). Branch `ws/history-contract`, PR into `build/traces-v1`. Architect1 reviews and merges.
Owner of this contract: Git intelligence seat (history). Owner of shared types: Traces seat (Evidence), `backend/traces/evidence`.
Charter: issue #2, sections 1.4, 1.5, 4D, 4E, 5 and 7. Background: `research/foundation/FOUNDATION_REVIEW.md` section 5, `research/foundation/LAB_C_RESULTS.md`. Pattern followed: `research/task002/spec/ADAPTER_CONTRACT.md` (pins, fail closed, contract tests, isolation).

## 1. Scope and non-goals

The history module reads a local Git repository at a pinned commit and emits Traces evidence records about how the repository changed. It covers:

- commit facts: commits, file adds, deletes, modifications, renames and copies, with Git's similarity score;
- file and component lifecycles carried through renames;
- architectural snapshots at milestone commits and the diff between two snapshots;
- churn and hotspots;
- co-change (logical coupling) as a pattern;
- reverts and quick add-then-delete;
- manifest dependency changes (added, removed, version changed);
- alias suggestions for semantic renames (delete plus add where content moved);
- history-side change impact, labeled by source and kept apart from direct code dependencies;
- documented rationale quoted from commit messages and, when cached data is supplied, PR bodies and review comments.

Non-goals:

- No import parser, symbol extractor or language parser. Structure at a commit comes from the Evidence pipeline run at the milestone SHAs this module selects (section 9.7).
- No network access, no GitHub client, no token handling. PR data arrives as cached JSON through an injected provider (section 10).
- No component identity. The Evidence seat owns the component map at a SHA; this module consumes it and carries it through time.
- No writes to the analyzed repository, its refs, config, index or working tree. No hooks, no checkout, no fetch.
- No claims of intent or causation. A change or co-change pattern is not proof of intent or causation (charter 4D).
- No `verified` status on any history record (section 6.1).
- No Code Maat code, translated code or line-by-line ports. Formulas only, from published descriptions. No GitNexus code or artifacts.
- No reuse of Lab C scripts as code. This is a clean rewrite with tests; Lab C's techniques and measured results are reused as requirements and regression baselines.
- Issue and Discussion threads are deferred past v1.

## 2. Package layout (owned by this seat)

| Path | Content |
|---|---|
| `backend/traces/history/__init__.py` | public API re-exports (section 8) |
| `backend/traces/history/gitcmd.py` | hardened read-only Git runner (section 11) |
| `backend/traces/history/ingest.py` | single rename-aware log parse up to the pinned SHA |
| `backend/traces/history/model.py` | frozen dataclasses for inputs and parsed history |
| `backend/traces/history/filters.py` | bot and generated-file filters |
| `backend/traces/history/config.py` | `HistoryConfig`, defaults, digest |
| `backend/traces/history/records.py` | builds 0.4 records, citations and claim ids |
| `backend/traces/history/lifecycle.py` | file set replay, lifecycles, bulk moves |
| `backend/traces/history/snapshots.py` | milestone selection, tree snapshots, evidence-set diff |
| `backend/traces/history/churn.py` | churn, revisions, age, authorship, hotspots |
| `backend/traces/history/cochange.py` | co-change at file and component level |
| `backend/traces/history/reverts.py` | explicit reverts, quick add-then-delete |
| `backend/traces/history/manifests.py` | manifest dependency changes (stdlib `json` and `tomllib`, plain-text requirements) |
| `backend/traces/history/aliases.py` | semantic rename and alias suggestions |
| `backend/traces/history/impact.py` | history-side impact |
| `backend/traces/history/pr_context.py` | consumes cached PR JSON through `PrContextProvider` |
| `backend/traces/history/cache.py` | per-repo, per-commit parse cache |
| `backend/traces/history/errors.py` | `HistoryError` and codes (section 13) |
| `backend/traces/history/__main__.py` | worker entry point: `python -m traces.history <manifest.json>` |
| `tests/history/` | pytest suite (section 18), synthetic repo builders, regression baselines. Placed under the repo-level `tests/` to match `pyproject.toml` `testpaths` on `build/traces-v1` |
| `docs/contracts/history.md` | this file |

Python: 3.14 (CPython 3.14.8, as pinned in `.python-version` and `pyproject.toml` on `build/traces-v1`), managed with uv, stdlib only at runtime. Tests: pytest. Git: minimum 2.47 (the version Lab C measured); the run records `git --version`.

## 3. Inputs

| Input | Type | Required | Notes |
|---|---|---|---|
| `repo_path` | path | yes | local bare mirror or clone made by the API seat. Full history required; shallow repos fail with `E_SHALLOW`. |
| `repo` | string | yes | display identity, for example `fastapi/full-stack-fastapi-template` |
| `repo_sha` | 40-hex string | yes | pinned commit. Abbreviations and ref names are refused (`E_SHA`). |
| `config` | `HistoryConfig` | no | defaults in section 12. Every value is echoed in outputs. |
| `component_map` | `ComponentMap` | no | from the Evidence seat, keyed by the SHA it was built at. Without it, component-level outputs are skipped and the report says so. |
| `generated_paths` | set of paths at `repo_sha` | no | supplied by the Evidence seat (D-H8): CodeGraph `generated = 1` files and output directories detected from generator config (for example the openapi-ts client dir). History consumes them and adds them to the generated filter; it does not detect generators itself. |
| `evidence_sets` | mapping SHA to `EvidenceSet` | no | Evidence pipeline output at milestone SHAs, for snapshot diffs |
| `pr_provider` | `PrContextProvider` | no | cached PR JSON. `None` means offline with no PR context. |
| `cache_dir` | path | no | history parse cache (section 15) |

Worker manifest (`work/<run_id>/history/manifest.json`):

```json
{
  "run_id": "h-20261021T1530-1",
  "repo": "fastapi/full-stack-fastapi-template",
  "repo_sha": "b1125d8839482cb7bbae603ddc6d0081bf87532e",
  "repo_path": "/srv/traces/repos/<repo-id>/mirror.git",
  "config": {},
  "component_map": "work/<run_id>/evidence/component_map.json",
  "generated_paths": "work/<run_id>/evidence/generated_paths.json",
  "evidence_sets": {"<sha>": "work/<run_id>/evidence/<sha>/records.jsonl"},
  "pr_cache": null,
  "cache_dir": "/srv/traces/cache/<repo-id>/history",
  "limits": {"max_commits": 200000, "max_paths_per_commit": 50000, "max_blob_bytes": 2000000, "git_call_timeout_s": 120, "run_timeout_s": 1800}
}
```

Outputs, mirroring the adapter run layout:

| Path | Content |
|---|---|
| `work/<run_id>/history/records.jsonl` | evidence records, sorted by `claim_id` |
| `work/<run_id>/history/report.json` | counts by kind, class, status; filters and thresholds used; warnings; skipped stages with reasons; git version; timings |
| `work/<run_id>/history/milestones.json` | selected milestone SHAs with the reasons each was selected |
| `work/<run_id>/history/errors.json` | on failure only |
| `work/<run_id>/history/netprobe.log` | isolation proof (section 16) |

## 4. Ownership and dependencies on other seats

| Seat | Provides to history | Takes from history |
|---|---|---|
| Traces (Evidence) | `backend/traces/evidence` shared types and the 0.4 schema; schema validator; component map at a SHA; generated-file flags; evidence sets at milestone SHAs (index worker runs the Evidence pipeline at the SHAs history selects) | milestone list; requested 0.4 additions (section 5) |
| API | bare mirror with full history; `repo_sha`; cached PR JSON files and the GitHub client, token, cache and rate limiting behind them; job orchestration | records, report, milestones |
| UX | none | records; required display wording (section 17) |
| Explanation | none | records; wording rules (section 17); impact results grouped by source |
| QA | CI, network isolation harness | test suite (section 18) |

## 5. Requested additions to `traces-evidence/0.4`

One Traces-owned schema. The Evidence seat owns the change in `backend/traces/evidence`; these are requests. Nothing below removes or changes a 0.3 value, so every 0.3 record stays valid under 0.4 after its `schema_version` is rewritten.

| Field | 0.3 | Requested 0.4 addition |
|---|---|---|
| `schema_version` | `traces-evidence/0.3` | `traces-evidence/0.4` |
| `relationship_kind` | 21 code kinds | `commit_adds`, `commit_deletes`, `commit_modifies`, `commit_type_changes`, `renamed_to`, `copied_to`, `dependency_added`, `dependency_removed`, `dependency_version_changed`, `component_added`, `component_removed`, `continues_as`, `alias_of`, `prefix_moved`, `co_changed_with`, `reverts`, `deleted_soon_after_add`, `merged_as`, `documents_rationale`, `snapshot_added`, `snapshot_removed`, `history_impact_candidate` |
| `node_kind` (free string) | as reported | conventions: `commit`, `file_history_metrics`, `component_history_metrics`, `milestone` |
| `class` | 4 values | `git_object_fact`, `history_pattern`, `history_inferred`, `documented_rationale`, `snapshot_diff` |
| `granularity` | `file`, `symbol`, `handler`, `statement`, `path` | `commit`, `component`, `dependency`, `repo` |
| `evidence_scope` | const `static` | `history` (derived from Git objects), `documented` (quoted text from commit messages or cached PR JSON). `runtime` stays reserved. |
| `origin.kind` | `tool_output`, `external_document`, `fixture` | `git_object` (fields `commit`, `paths`), `history_derived` (field `derived_from`: claim ids or commit lists), `cached_pr` (fields `artifact`, `sha256`, `quote`) |
| `originator.role` | `extractor`, `external`, `fixture` | `history_analyzer` |
| `provenance` pattern | `codegraph:*`, `external:*`, `fixture:*` | `git:(log|diff-tree|ls-tree|cat-file)`, `history:(replay|lifecycle|cochange|churn|hotspot|revert-match|manifest-diff|alias-suggest|milestone|snapshot-diff|impact)`, `github-cache:(pr-body|pr-review-comment|pr-metadata)` |
| endpoint | `{symbol, file, ...}`, `file` required | optional `entity` enum `symbol`, `file`, `commit`, `component`, `dependency`, `repo`; `file` required only when `entity` is `symbol` or `file` or absent. Symbol forms below. |
| check `method` | 9 methods | `git_object_check` (re-reads the cited objects with plumbing independent of the ingest parse; establishes `presence`), `git_recount` (recomputes a statistic from the cited commits; establishes `presence` of the counts, never `relationship`), `quote_match` (quote bytes equal a slice of the commit message or cached JSON with matching sha256; establishes `presence`) |
| check `validator.family` | includes `git`, `text` | no change; `independent` rule extended (D-H2): a `git` family check using plumbing (`cat-file`, `ls-tree`, `diff-tree`, `rev-list` recount) that does not read the log parse counts as independent for git-object facts and recounts. A `text` family `quote_match` establishes only that the quote exists at the cited commit or PR, nothing about intent |
| new field `citations` | none | array of citation objects (section 7.1). `locations` may be empty for history and documented records. Schema rule (D-H3): every record has at least one entry in `locations` or `citations`. History and documented records always carry citations; file-level claims also carry whole-file `locations` at the cited blob. |
| new field `review_state` | none | `{state: none|confirmed|disputed, reviewer, at}` (D-H4). Separate from `status`; never promotes or demotes status. Default `{state: none, reviewer: null, at: null}`. |
| new field `parameters` | none | `{digest, values}`: the exact config subset that affected the record (thresholds, filters, rename settings) and its sha256 |
| new field `metrics` | none | numeric results for `history_pattern` records (section 6) |
| `flags` | 6 values | `bot_commit`, `generated_path`, `merge_commit`, `similarity_rename`, `rename_detection_limited`, `non_utf8_path`, `complexity_proxy`, `component_map_missing`, `pr_sha_mismatch` |
| status rules | `observed` relationships only for `imports` with qualifier | `observed` also allowed for the relationship kinds marked observed in section 6, each with its required `qualifier`; `verified` forbidden for every 0.4 history class; `locations` `minItems 1` rule replaced by "at least one of `locations` or `citations`" |

Endpoint symbol forms for non-code entities (they already match `^[^:]+::.+$`; the `entity` field removes any ambiguity with code symbols):

| Entity | Symbol | Example |
|---|---|---|
| file | `file::<repo path>` | `file::backend/app/api/routes/users.py` |
| commit | `commit::<40-hex sha>` | `commit::2d0f77421f...` |
| component | `component::<component id from the map>` | `component::backend/app/crud` |
| dependency | `dep::<ecosystem>:<logical manifest>:<name>` | `dep::pypi:backend/pyproject.toml:sqlmodel` |
| repo | `repo::<repo>` | `repo::fastapi/full-stack-fastapi-template` |

## 6. Record kinds

### 6.1 Summary

Max status is the highest status the record may reach. `observed` requires the independent check named in the last column to pass; otherwise the record stays `unvalidated` with a reason.

| Kind (`relationship_kind` or `node_kind`) | claim_kind | granularity | class | scope | Max status | Required qualifier | Check for max status |
|---|---|---|---|---|---|---|---|
| `commit` (node) | node | commit | `git_object_fact` | history | observed | `git commit object` | `git_object_check` (`cat-file -t` is commit, parents match) |
| `commit_adds`, `commit_deletes`, `commit_modifies`, `commit_type_changes` | relationship | file | `git_object_fact` | history | observed | `git tree change` | `git_object_check` (`diff-tree` of commit against parent shows the same status and blobs) |
| `renamed_to` with similarity 100 | relationship | file | `git_object_fact` | history | observed | `exact rename (identical blob)` | `git_object_check` (blob before equals blob after) |
| `renamed_to` with similarity below 100 | relationship | file | `git_object_fact` | history | observed | `similarity rename, score <n>%` | `git_object_check` (`diff-tree -M<threshold>` reproduces the pair and score); flag `similarity_rename` |
| `copied_to` | relationship | file | `git_object_fact` | history | observed | `copy detected, score <n>%` | `git_object_check` |
| `dependency_added`, `dependency_removed`, `dependency_version_changed` | relationship | dependency | `git_object_fact` | history | observed | `manifest entry change` | `git_object_check` (both manifest blobs re-read and re-parsed with `json` or `tomllib`) |
| `component_added`, `component_removed`, `continues_as` | relationship | component | `history_inferred` | history | unvalidated | none | none; depends on the component map and on rename chaining |
| `alias_of` | relationship | file or component | `history_inferred` | history | unvalidated | none | none; reviewer confirmation sets `review_state` (D-H4) and leaves status unchanged |
| `prefix_moved` (bulk move) | relationship | path | `history_pattern` | history | observed | `grouped renames, <k> files` | `git_recount` |
| `co_changed_with` | relationship | file or component | `history_pattern` | history | observed (the counts only) | `changed together in <N> of <M> commits` | `git_recount` (D-H1) |
| `file_history_metrics`, `component_history_metrics` (node: revisions, churn, authors, age, hotspot score) | node | file or component | `history_pattern` | history | observed (the metric values only) | `history pattern` (hotspot adds `complexity is an indentation proxy`) | `git_recount` (D-H1) |
| `deleted_soon_after_add` | relationship | file | `history_pattern` | history | observed | `deleted <d> days after add` | `git_recount` |
| `reverts` | relationship | commit | `history_inferred` | history | unvalidated | none | none; message text is quoted, the claim that one commit undoes another is not established in v1 |
| `merged_as` (PR to commit) | relationship | commit | `documented_rationale` | documented | observed | `cached PR metadata` | `quote_match` on cached JSON, and cached `merge_commit_sha` equals the local commit; mismatch keeps `unvalidated` with flag `pr_sha_mismatch` |
| `documents_rationale` (commit message or PR text to commit) | relationship | commit | `documented_rationale` | documented | observed (the quote exists, nothing more) | `quoted rationale, not proof of intent` | `quote_match` (D-H2) |
| `milestone` (node) | node | commit | `history_pattern` | history | observed | `selected milestone: <reasons>` | `git_object_check` on the commit |
| `snapshot_added`, `snapshot_removed` | relationship | as the underlying claim | `snapshot_diff` | history | the lower of the underlying claim's statuses at the two SHAs, capped at observed | `present at <sha_b>, absent at <sha_a>` or the reverse | set difference recomputed from the two evidence sets by `claim identity` (section 9.8) |
| `history_impact_candidate` | relationship | file or component | `history_pattern` | history | unvalidated | `history signal: changed together in <N> of <M> commits` | none; "may be affected" is an interpretation of coupling (D-H1). It cites the observed `co_changed_with` record it derives from |

Rules that apply to all kinds:

- No history record is ever `verified`. Co-change, coupling, hotspots and churn are `history_pattern` and never `verified`.
- `observed` on a `history_pattern` record means the counts were reproduced by an independent recount. It says nothing about why files changed together. Any coupling, "related" or "may be affected" interpretation is a separate record or sentence and stays `unvalidated` (D-H1).
- `review_state` records reviewer confirmation or dispute. It never changes `status` (D-H4).
- `documented_rationale` records quote; they never state a motive in Traces' own words. `statement` reads "Commit <sha> message says: \"<quote>\"", never "The team chose X because Y".
- `injected` is always `false` in production output. Negative controls live only in test inputs, as in Task 002.
- Bot-authored commits are kept as `git_object_fact` records with flag `bot_commit`; filters only remove them from pattern computations (section 12).

### 6.2 Common fields

Every record carries the 0.3 required fields plus, for history: `citations`, `parameters`, `review_state`, and `metrics` on `history_pattern` records. `originator` is `{"name": "traces-history", "version": "<package version>", "role": "history_analyzer"}`. `repo_sha` is the pinned analysis SHA. `status_history` starts at `null -> unvalidated` and appends the check outcome.

### 6.3 Examples

All SHAs and numbers in these examples are illustrative except where marked as Lab C or Task 001 measurements.

`commit_modifies`:

```json
{
  "schema_version": "traces-evidence/0.4",
  "claim_id": "c_5b1e...e9",
  "run_id": "h-20261021T1530-1",
  "repo": "fastapi/full-stack-fastapi-template",
  "repo_sha": "b1125d8839482cb7bbae603ddc6d0081bf87532e",
  "claim_kind": "relationship",
  "relationship_kind": "commit_modifies",
  "granularity": "file",
  "from": {"entity": "commit", "symbol": "commit::<sha>"},
  "to": {"entity": "file", "symbol": "file::backend/app/api/routes/users.py", "file": "backend/app/api/routes/users.py"},
  "statement": "Commit <sha12> modified backend/app/api/routes/users.py (+12 -3).",
  "class": "git_object_fact",
  "originator": {"name": "traces-history", "version": "0.1.0", "role": "history_analyzer"},
  "provenance_raw": {"git": "log --name-status -z -M50% -C50% / --numstat -z -M50%", "status": "M", "added": 12, "deleted": 3},
  "provenance": "git:log",
  "origin": {"kind": "git_object", "commit": "<sha>", "paths": ["backend/app/api/routes/users.py"]},
  "injected": false,
  "evidence_scope": "history",
  "qualifier": "git tree change",
  "citations": [{"commit": "<sha>", "parents": ["<parent sha>"], "paths": [{"path": "backend/app/api/routes/users.py", "old_path": null, "status": "M", "similarity": null, "blob_before": "<blob>", "blob_after": "<blob>"}]}],
  "locations": [],
  "checks": [{"check_id": "k_...", "method": "git_object_check", "establishes": "presence", "rule_id": null, "validator": {"name": "traces-history-gitcheck", "version": "0.1.0", "family": "git"}, "reads_originator_output": false, "independent": true, "inputs": [], "result": "pass", "detail": "diff-tree <parent> <sha> shows M with the same blobs", "run_id": "h-20261021T1530-1", "at": "2026-10-21T15:30:00+05:30"}],
  "status": "observed",
  "label": "observed",
  "status_history": [{"from": null, "to": "unvalidated", "at": "...", "run_id": "...", "check_ids": [], "by": "traces-history"}, {"from": "unvalidated", "to": "observed", "at": "...", "run_id": "...", "check_ids": ["k_..."], "by": "traces-history"}],
  "visible_to_reviewer": true,
  "parameters": {"digest": "<sha256>", "values": {"rename_threshold": 50, "copy_threshold": 50, "rename_limit": 10000}},
  "flags": []
}
```

`renamed_to` (similarity rename):

```json
{
  "relationship_kind": "renamed_to", "granularity": "file", "class": "git_object_fact", "evidence_scope": "history",
  "from": {"entity": "file", "symbol": "file::src/backend/app/app/api/api_v1/endpoints/users.py", "file": "src/backend/app/app/api/api_v1/endpoints/users.py"},
  "to": {"entity": "file", "symbol": "file::backend/app/api/routes/users.py", "file": "backend/app/api/routes/users.py"},
  "statement": "Commit <sha12> renamed src/.../users.py to backend/app/api/routes/users.py (Git similarity 87%).",
  "qualifier": "similarity rename, score 87%",
  "citations": [{"commit": "<sha>", "parents": ["<parent>"], "paths": [{"path": "backend/app/api/routes/users.py", "old_path": "src/backend/app/app/api/api_v1/endpoints/users.py", "status": "R", "similarity": 87, "blob_before": "<blob>", "blob_after": "<blob>"}]}],
  "status": "observed", "label": "observed", "flags": ["similarity_rename"]
}
```

`dependency_added` (Lab C measurement: SQLModel added in #558 before #559 adopted it):

```json
{
  "relationship_kind": "dependency_added", "granularity": "dependency", "class": "git_object_fact", "evidence_scope": "history",
  "from": {"entity": "commit", "symbol": "commit::<sha of #558>"},
  "to": {"entity": "dependency", "symbol": "dep::pypi:backend/pyproject.toml:sqlmodel"},
  "statement": "Commit <sha12> (#558) added sqlmodel to backend/pyproject.toml.",
  "qualifier": "manifest entry change",
  "citations": [{"commit": "<sha>", "parents": ["<parent>"], "paths": [{"path": "<manifest path at that commit>", "old_path": null, "status": "M", "similarity": null, "blob_before": "<blob>", "blob_after": "<blob>"}]}],
  "metrics": null, "status": "observed", "label": "observed"
}
```

`co_changed_with` (Lab C measurement, under Lab's own thresholds: `AddUser.tsx` and `EditUser.tsx` support 18, degree 0.95):

```json
{
  "relationship_kind": "co_changed_with", "granularity": "file", "class": "history_pattern", "evidence_scope": "history",
  "from": {"entity": "file", "symbol": "file::frontend/src/components/Admin/AddUser.tsx", "file": "frontend/src/components/Admin/AddUser.tsx"},
  "to": {"entity": "file", "symbol": "file::frontend/src/components/Admin/EditUser.tsx", "file": "frontend/src/components/Admin/EditUser.tsx"},
  "statement": "AddUser.tsx and EditUser.tsx changed together in 18 of 19 commits that touched either file. This is a history pattern, not evidence that one change caused the other.",
  "qualifier": "changed together in 18 of 19 commits",
  "provenance": "history:cochange",
  "origin": {"kind": "history_derived", "derived_from": ["<18 commit shas>"]},
  "citations": [{"commit": "<sha>", "parents": ["<parent>"], "paths": [{"path": "frontend/src/components/Admin/AddUser.tsx", "status": "M", "old_path": null, "similarity": null, "blob_before": "<blob>", "blob_after": "<blob>"}, {"path": "frontend/src/components/Admin/EditUser.tsx", "status": "M", "old_path": null, "similarity": null, "blob_before": "<blob>", "blob_after": "<blob>"}]}],
  "metrics": {"support": 18, "revs_a": 19, "revs_b": 19, "union_commits": 19, "confidence_a_to_b": 0.95, "confidence_b_to_a": 0.95, "degree": 0.95, "commits_considered": 1234, "commits_skipped_large": 41, "commits_skipped_merge": 0, "commits_skipped_bot": 262},
  "parameters": {"digest": "<sha256>", "values": {"min_revs": 5, "min_shared_revs": 5, "min_coupling": 0.30, "max_changeset_size": 30, "bot_filter": "default", "generated_filter": "default", "rename_normalization": "head_paths"}},
  "status": "observed", "label": "observed"
}
```

In the example, `M` (union) and the two revision counts are placeholders; the real values are frozen at the first regression run (HT9).

`alias_of` (Lab C: `crud/` became `crud.py` in `2d0f774`, #622; `git log --follow` stops there):

```json
{
  "relationship_kind": "alias_of", "granularity": "file", "class": "history_inferred", "evidence_scope": "history",
  "from": {"entity": "file", "symbol": "file::backend/app/crud/crud_user.py", "file": "backend/app/crud/crud_user.py"},
  "to": {"entity": "file", "symbol": "file::backend/app/crud.py", "file": "backend/app/crud.py"},
  "statement": "Suggested alias: content of backend/app/crud/crud_user.py appears to continue in backend/app/crud.py after commit 2d0f774 (#622). Git recorded a delete and an add, not a rename.",
  "metrics": {"line_set_jaccard": 0.0, "lines_moved": 0, "method": "normalized line-set overlap"},
  "status": "unvalidated", "label": "inferred", "status_reason": "suggestion from content similarity; identity not established by Git",
  "review_state": {"state": "none", "reviewer": null, "at": null}
}
```

The paths and `metrics` above are placeholders until the HT13 run fixes them.

`documents_rationale` (cached PR body):

```json
{
  "relationship_kind": "documents_rationale", "granularity": "commit", "class": "documented_rationale", "evidence_scope": "documented",
  "from": {"entity": "repo", "symbol": "repo::fastapi/full-stack-fastapi-template#694"},
  "to": {"entity": "commit", "symbol": "commit::<merge sha of #694>"},
  "statement": "PR #694 description says: \"When choosing Celery I evaluated RQ, Dramatiq, and a couple of other options...\"",
  "qualifier": "quoted rationale, not proof of intent",
  "provenance": "github-cache:pr-body",
  "origin": {"kind": "cached_pr", "artifact": "<cache path>", "sha256": "<sha256 of cached JSON>", "quote": "When choosing Celery I evaluated RQ, Dramatiq, and a couple of other options..."},
  "citations": [{"commit": "<merge sha>", "parents": ["<p1>"], "paths": [], "pr": {"number": 694, "fetched_at": "<from cache>", "merge_commit_sha": "<sha>"}}],
  "status": "observed", "label": "observed"
}
```

`snapshot_removed`:

```json
{
  "relationship_kind": "snapshot_removed", "granularity": "handler", "class": "snapshot_diff", "evidence_scope": "history",
  "from": {"entity": "commit", "symbol": "commit::<milestone a>"},
  "to": {"entity": "commit", "symbol": "commit::<milestone b>"},
  "statement": "The relationship <underlying statement> is present at <a12> and absent at <b12>.",
  "qualifier": "present at <a12>, absent at <b12>",
  "origin": {"kind": "history_derived", "derived_from": ["<claim_id at a>"]},
  "metrics": {"underlying_status_a": "verified", "underlying_status_b": null},
  "status": "observed", "label": "observed"
}
```

## 7. Citations and claim ids

### 7.1 Citation

```json
{
  "commit": "<40-hex>",
  "parents": ["<40-hex>", "..."],
  "paths": [
    {"path": "<repo path after>", "old_path": "<repo path before or null>", "status": "A|M|D|R|C|T",
     "similarity": "<0-100 or null>", "blob_before": "<40-hex or null>", "blob_after": "<40-hex or null>"}
  ],
  "pr": {"number": 0, "merge_commit_sha": "<40-hex>", "fetched_at": "<ISO 8601 with offset>"}
}
```

- Every history record cites at least one commit with its full parent list and the paths it relies on.
- File-level claims carry blob SHAs on both sides of the change (`null` only for the missing side of an add or delete). When a file-level claim refers to file content at one commit, it also carries a whole-file `location` at that blob, following the EOF rule of `EVIDENCE_SCHEMA.md` section 11.1.
- Pattern records cite every supporting commit, ordered by commit time then SHA. The UI may show the last three; the record keeps all.
- `pr` appears only on `documented_rationale` records built from cached PR JSON.
- Links use the pinned commit SHA, never a branch name.

### 7.2 claim_id

`claim_id` = `c_` + sha256 of canonical JSON (sorted keys, no whitespace, UTF-8) of:

```json
{
  "family": "traces-history",
  "claim_kind": "...",
  "kind": "<relationship_kind or node_kind>",
  "granularity": "...",
  "subject": {"from": "<normalized symbol>", "to": "<normalized symbol or null>"},
  "anchor": {"commit": "<sha>"}  or  {"range": ["<first commit considered or null>", "<range end sha>"], "first_parent": true|false},
  "extractor": {"name": "traces-history", "version": "<version>"},
  "parameters_digest": "<sha256 of canonical parameters that affect this kind>"
}
```

- Same family as Task 002 claim_id v3 (canonical JSON, sha256, `c_` prefix). The inputs differ because history claims are anchored to a commit or range, not to a source line.
- Git-object facts anchor to their own commit, not to `repo_sha` (D-H6). The same fact keeps its id when the pinned SHA moves forward, which lets the cache reuse records. This differs from Task 002 claim_id v3, which hashes `repo_sha`; see section 20. Pattern records anchor to the range they were computed over, so a new pinned SHA gives new ids and the old records stay with `supersedes` links.
- Symmetric kinds (`co_changed_with`) order `from` and `to` by the byte order of their symbols before hashing.
- Paths are normalized before hashing: repo-relative, `/` separated, no leading `./`, decoded from `-z` output as UTF-8. Non-UTF-8 bytes are percent-encoded and the record gets flag `non_utf8_path`.
- `parameters_digest` covers every config value the kind reads: thresholds, filter criteria, rename and copy thresholds, rename limit, mailmap source, component map digest where used. Changing a threshold changes the id.
- Collisions: two records with the same id and different content stop the run with `E_COLLISION`. Exact duplicates are consolidated with every contributing row kept, as in `EVIDENCE_SCHEMA.md` section 11.2. Target: zero collisions, regression-tested (HT4).

## 8. Public Python API

All functions are pure with respect to the repository: they read Git objects through `gitcmd`, write nothing to the repo, and return immutable values. Record lists are sorted by `claim_id`. Signatures are the contract; internal helpers are not.

```python
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from traces.evidence import EvidenceRecord, EvidenceSet   # Traces seat, 0.4

Sha = str  # 40 lowercase hex, validated

@dataclass(frozen=True)
class RepoRef:
    path: Path          # bare mirror or clone, full history
    repo: str           # display identity
    sha: Sha            # pinned commit

@dataclass(frozen=True)
class Thresholds:
    min_revs: int = 5
    min_shared_revs: int = 5
    min_coupling: float = 0.30
    max_changeset_size: int = 30
    rename_threshold: int = 50       # git -M
    copy_threshold: int = 50         # git -C
    rename_limit: int = 10000        # diff.renameLimit
    quick_delete_days: int = 30
    bulk_move_min_files: int = 3
    alias_min_similarity: float = 0.5

@dataclass(frozen=True)
class FilterSpec:
    bot_author_patterns: tuple[str, ...]        # case-insensitive regex on %aN and %aE
    generated_globs: tuple[str, ...]
    extra_generated_paths: frozenset[str] = frozenset()
    exclude_bots_from_patterns: bool = True
    exclude_generated_from_patterns: bool = True

@dataclass(frozen=True)
class HistoryConfig:
    thresholds: Thresholds = Thresholds()
    filters: FilterSpec = ...           # defaults in section 12
    mailmap: Literal["pinned_blob", "none"] = "pinned_blob"
    limits: "Limits" = ...
    def digest(self) -> str: ...

@dataclass(frozen=True)
class ComponentMap:
    sha: Sha
    components: Mapping[str, "ComponentDef"]     # id -> member paths at sha
    digest: str
    def component_of(self, path: str) -> str | None: ...

@dataclass(frozen=True)
class CachedPr:
    number: int
    merge_commit_sha: Sha | None
    body: str | None
    review_comments: Sequence["CachedComment"]
    source_artifact: str
    sha256: str
    fetched_at: str

class PrContextProvider(Protocol):
    def get(self, pr_number: int) -> CachedPr | None: ...

@dataclass(frozen=True)
class HistoryLog:            # parsed, immutable, cacheable
    repo: RepoRef
    commits: Sequence["Commit"]        # oldest first, all commits reachable from sha
    first_parent: Sequence[Sha]        # first-parent chain, oldest first
    config_digest: str
    git_version: str
    warnings: Sequence[str]

@dataclass(frozen=True)
class HistoryResult:
    records: Sequence[EvidenceRecord]
    report: Mapping[str, object]       # counts, parameters, skipped stages, warnings

# 8.1 Ingest
def ingest(repo: RepoRef, config: HistoryConfig = HistoryConfig(), *, cache_dir: Path | None = None) -> HistoryLog: ...
def commit_facts(log: HistoryLog) -> HistoryResult: ...
    # commit nodes, commit_adds/deletes/modifies/type_changes, renamed_to, copied_to

# 8.2 Lifecycle
def lifecycle(log: HistoryLog, components: ComponentMap | None = None) -> HistoryResult: ...
    # file lifecycles through renames, prefix_moved, component_added/removed/continues_as
    # report includes replay_check: {replayed_files, ls_tree_files, missing, extra}

# 8.3 Milestones, snapshots, evidence-set diff
@dataclass(frozen=True)
class Milestone:
    sha: Sha
    reasons: tuple[str, ...]           # e.g. "first commit", "bulk move 247 files", "dependency change: +sqlmodel"

MAX_MILESTONES_DEFAULT = 8      # index worker automatic run (D-H9)
MAX_MILESTONES_ON_DEMAND = 20   # hard cap for on-demand compare (D-H9)

def select_milestones(log: HistoryLog, *, max_milestones: int = MAX_MILESTONES_DEFAULT, components: ComponentMap | None = None) -> Sequence[Milestone]: ...
    # max_milestones above MAX_MILESTONES_ON_DEMAND raises E_CONFIG
def snapshot_compare(log: HistoryLog, base: Sha, head: Sha, *, components: ComponentMap | None = None) -> HistoryResult: ...
    # tree-level: files and components present at each, from ls-tree; no parsing
def evidence_set_diff(base: EvidenceSet, head: EvidenceSet, *, aliases: Sequence[EvidenceRecord] = ()) -> HistoryResult: ...
    # snapshot_added / snapshot_removed; matches claims by claim identity (section 9.8)

# 8.4 Churn and hotspots
def churn(log: HistoryLog, *, components: ComponentMap | None = None) -> HistoryResult: ...
def hotspots(log: HistoryLog, *, components: ComponentMap | None = None) -> HistoryResult: ...

# 8.5 Co-change
def cochange(log: HistoryLog, *, level: Literal["file", "component"] = "file", components: ComponentMap | None = None) -> HistoryResult: ...

# 8.6 Reverts
def reverts(log: HistoryLog) -> HistoryResult: ...

# 8.7 Manifest changes
def manifest_changes(log: HistoryLog) -> HistoryResult: ...

# 8.8 Alias suggestions
def alias_suggestions(log: HistoryLog, *, components: ComponentMap | None = None) -> HistoryResult: ...

# 8.9 History impact
@dataclass(frozen=True)
class ImpactResult:
    target: str                                    # normalized symbol (file:: or component::)
    by_source: Mapping[str, Sequence[EvidenceRecord]]   # keys: "history:co_change", "history:alias"
    known_gaps: tuple[str, ...]                    # always present, e.g. "history signals do not show code dependencies"
    parameters: Mapping[str, object]

def history_impact(target: str, cochange_records: Sequence[EvidenceRecord], *, aliases: Sequence[EvidenceRecord] = (), limit: int = 20) -> ImpactResult: ...

# 8.10 PR context
def pr_context(log: HistoryLog, provider: PrContextProvider | None) -> HistoryResult: ...

# 8.11 Whole run (used by the worker)
def run(repo: RepoRef, config: HistoryConfig, *, components: ComponentMap | None = None,
        evidence_sets: Mapping[Sha, EvidenceSet] | None = None,
        pr_provider: PrContextProvider | None = None, cache_dir: Path | None = None) -> HistoryResult: ...
```

`history_impact` never reads or returns code-dependency edges. The API or Explanation seat may show it next to CodeGraph and framework-rule impact, under its own heading. An empty result returns `known_gaps`, never a bare empty list.

## 9. Computation rules

### 9.1 Ingest

- One `git log` stream over all commits reachable from `repo_sha`, oldest first, `-z`, `--name-status`, `-M<rename_threshold>%`, `-C<copy_threshold>%`, `-l<rename_limit>`, author identity `%aN` and `%aE` (mailmap applied), committer time `%ct` and author time `%at`, parents `%P`, raw message `%B`.
- One `git log -z --numstat -M<rename_threshold>%` stream for line counts, keyed by the new path. This is the fix for Lab C's double count (`--no-renames` counted `users.py` as 48 revisions and 2,974 churn instead of 43 and 1,188).
- Merge commits: no diff in the stream. Merges appear as commit records with flag `merge_commit`. The first-parent chain is read separately with `--first-parent`.
- Rename detection limited: if Git reports that inexact rename detection was skipped, the affected commit's records get flag `rename_detection_limited` and the report lists the commits.
- Mailmap: read from the pinned commit's `.mailmap` blob (`-c mailmap.blob=<repo_sha>:.mailmap`, `-c mailmap.file=`), so a later or uncommitted mailmap cannot change results. No `.mailmap` at `repo_sha` means raw identities, recorded in the report.
- Times are stored as Unix seconds plus offset. Displays convert to the viewer's zone.

### 9.2 Lifecycle

- Per-path events come from every non-merge commit that changed the path, so a change made on a side branch is cited at the commit that made it. This is the confirmed meaning of "all commits" (D-H5).
- File set replay along the first-parent chain, diffing each merge against its first parent, must equal `git ls-tree -r --name-only <repo_sha>`. A mismatch is `E_REPLAY` (fail closed).
- Rename chains follow `R` entries newest to oldest to map historical paths to HEAD paths. Copies do not move identity; the source path keeps its own lifecycle.
- Bulk moves: rename pairs in one commit grouped by common-suffix stripping into `old_prefix -> new_prefix`, at least `bulk_move_min_files` files.
- Component lifecycle: the component map is built at one SHA. History assigns historical paths to components through rename chains back from that SHA. A component is `added` at the first commit where any member path exists and `removed` when its last member is deleted. These are `history_inferred`.

### 9.3 Churn and hotspots

- Counted over non-merge commits, rename-normalized to HEAD paths. Revisions = commits touching the path. Churn = added plus deleted lines from the rename-aware numstat. Binary changes count one revision and zero lines.
- Also reported: number of authors (mailmapped), main author share, first seen, last changed, age in days at `repo_sha` commit time.
- Hotspot score = average-rank-normalized revisions (commits with at most `max_changeset_size` paths) times average-rank-normalized indentation complexity at `repo_sha`. Indentation complexity is the sum of leading-indent levels over non-blank lines of the blob read with `cat-file`; it is a proxy, flagged `complexity_proxy`, and the formula is stated in the record.
- Scope: files alive at `repo_sha`, generated filter applied, bot filter applied by default.

### 9.4 Co-change

- Non-merge commits only. Commits with more than `max_changeset_size` paths after filtering are skipped and counted.
- Bot and generated filters apply by default.
- Paths are rename-normalized to HEAD paths. Component level maps paths through the component map.
- revs(A) = commits touching A. support(A,B) = commits touching both. confidence(A to B) = support / revs(A). degree = support / mean(revs(A), revs(B)).
- Kept when revs(A) and revs(B) are at least `min_revs`, support at least `min_shared_revs`, and degree at least `min_coupling`.
- These are the published Code Maat defaults (5, 5, 30%, 30), implemented from formulas only. Every record carries the thresholds used.

### 9.5 Reverts and quick deletes

- Explicit reverts: subject `Revert "<title>"` or body `This reverts commit <sha>`. The target is resolved to a full SHA in the history. The record quotes the message and stays `history_inferred`, `unvalidated`. Bot-authored commits are skipped by default (Lab C found one false revert from a Dependabot body quoting an upstream changelog).
- Quick add-then-delete: same path deleted within `quick_delete_days` of its add, generated filter applied.

### 9.6 Manifest changes

- Manifests: `package.json` (`dependencies`, `devDependencies`, `peerDependencies`, `optionalDependencies`), `pyproject.toml` (PEP 621 `project.dependencies` and `optional-dependencies`, `dependency-groups`, `tool.poetry` dependencies and groups), `Pipfile`, `requirements*.txt`. Parsed with stdlib `json` and `tomllib` from blobs read by `cat-file`. This is manifest data, not source parsing.
- Events: added, removed, version specifier changed. Lockfile-only changes are not dependency events.
- Logical manifest identity follows renames of the manifest file. An unparseable manifest blob yields a report warning with commit and path, and no event for that commit.

### 9.7 Milestone selection

- On the first-parent chain only.
- Candidates: the first commit, `repo_sha`, bulk moves, commits with large directory births or deaths, dependency add or remove events, explicit reverts, and the last first-parent commit of each calendar year. Bot-authored commits are not candidates unless they change a manifest's dependency set.
- Ranked by number of distinct reasons, then commit time. Capped at `max_milestones`: default 8 for the index worker's automatic run; an on-demand compare requested by a user may raise it, up to a hard cap of 20 (D-H9). Deterministic for a given log and config.
- History hands the milestone list to the index worker. The worker runs the Evidence pipeline at each milestone SHA. History does not parse source at any SHA.

### 9.8 Evidence-set diff

- Inputs are two Evidence seat outputs at two SHAs. Claims are matched by claim identity: `claim_kind`, kind, granularity and endpoint symbols, with file paths mapped through rename chains and confirmed aliases. Line numbers are excluded from matching, so a moved but unchanged relationship is not reported as removed plus added.
- Output: `snapshot_added`, `snapshot_removed`, each citing the underlying claim ids. Status is the lower of the underlying claim's statuses, capped at `observed`. A rejected underlying claim stays rejected and is shown as such, never as architecture.

### 9.9 PR context

- Commits are linked to PR numbers by subject patterns `(#N)` and `Merge pull request #N`. Linking alone creates no record.
- With a provider, each linked PR returns cached JSON or `None`. Records: `merged_as` and `documents_rationale` for the PR body and each review comment that is non-empty after whitespace trim. Quotes are byte-exact slices of the cached text.
- `None` from the provider or no provider: no PR records, report entry `pr_context: none` with the reason. No error.
- Cached JSON that fails its own sha256 or shape check: that PR is skipped with a warning; the run continues.

## 10. PR context boundary

The API seat owns the GitHub client, token, cache files and rate limiting. History imports no HTTP library and reads no credential. `PrContextProvider` is the only path for PR data. The default is `None`. v1 uses PR bodies and review comments only; issue and Discussion threads are deferred.

## 11. Git runner (`backend/traces/history/gitcmd.py`)

- argv lists only, never a shell. The Git binary path is resolved once at start and recorded.
- Allowed subcommands: `rev-parse --verify`, `cat-file`, `log`, `rev-list`, `ls-tree`, `diff-tree`, `for-each-ref` (read only). Anything else raises before execution.
- Global options on every call: `--no-pager`, `--git-dir=<repo_path>` (bare) or `-C <repo_path>`, `-c core.hooksPath=/dev/null`, `-c core.quotePath=false`, `-c core.fsmonitor=false`, `-c core.attributesFile=/dev/null`, `-c diff.external=`, `-c log.showSignature=false`, `-c protocol.allow=never`, `-c mailmap.file=`, `-c mailmap.blob=<repo_sha>:.mailmap` (or empty when mailmap is off).
- Diff-producing calls add `--no-ext-diff --no-textconv -z`. Output parsing is NUL-delimited only.
- Environment is built from scratch: `PATH` limited to the Git binary's directory, `HOME` and `XDG_CONFIG_HOME` set to an empty private temp dir, `GIT_CONFIG_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL=/dev/null`, `GIT_ATTR_NOSYSTEM=1`, `GIT_TERMINAL_PROMPT=0`, `GIT_NO_REPLACE_OBJECTS=1`, `GIT_NO_LAZY_FETCH=1`, `GIT_OPTIONAL_LOCKS=0`, `LC_ALL=C`. No credential helpers, no `SSH_*`, no proxy variables.
- Refuses repos that have `info/grafts`, a `shallow` file (`E_SHALLOW`), or a promisor remote with missing objects (`E_MISSING_OBJECT` instead of a lazy fetch).
- SHA validation: input must match `^[0-9a-f]{40}$`, `rev-parse --verify <sha>^{commit}` must return the same SHA, and `cat-file -t` must be `commit`.
- Per-call timeout and output byte cap from `limits`. stderr is captured, truncated and stripped of paths outside the repo before it reaches logs.
- The index worker runs history under the same OS-level network isolation as Task 002 (`unshare -rn` or a container with no network).

## 12. Filters and thresholds

Defaults (all configurable; the values used are echoed in `report.json` and in each affected record's `parameters`):

| Setting | Default |
|---|---|
| Bot author filter (regex, case-insensitive, on `%aN` and `%aE`) | `\[bot\]`, `dependabot`, `renovate`, `github-actions`, `pre-commit-ci` |
| Generated path filter (globs, any depth unless rooted) | lockfiles: `package-lock.json`, `npm-shrinkwrap.json`, `yarn.lock`, `pnpm-lock.yaml`, `bun.lock`, `bun.lockb`, `uv.lock`, `poetry.lock`, `Pipfile.lock`, `Cargo.lock`, `go.sum`, `composer.lock`, `Gemfile.lock`; `*.gen.*`; generated client dirs `**/__generated__/**`, `**/generated/**`, plus `generated_paths` from the Evidence seat, including generator-config-detected output dirs (D-H8); minified `*.min.js`, `*.min.css`; `vendor/`, `dist/`, `build/` at any depth, matching whole directory segments only (D-H7): `web/dist/app.js` and `build/x.o` match, `distance/x.py`, `rebuild/x.py` and `build.py` do not |
| Where filters apply | co-change, churn, hotspots, quick deletes, milestone candidates, revert detection (bots). Never to commit facts or lifecycle: those keep every commit and carry flags `bot_commit` and `generated_path` |
| Co-change thresholds | `min_revs` 5, `min_shared_revs` 5, `min_coupling` 0.30, `max_changeset_size` 30 |
| Rename and copy detection | `-M50%`, `-C50%`, rename limit 10,000 |
| Quick delete window | 30 days |
| Bulk move minimum | 3 files |
| Alias suggestion minimum similarity | 0.5 normalized line-set overlap |
| Timeline and milestones | first-parent; milestone cap 8 for the index worker, 20 hard cap on demand |
| Lifecycle events and churn | all non-merge commits; replay check along first-parent with merges diffed against the first parent |

Every user-facing filtered view states what was filtered and how many commits or paths were removed, by rule. The criteria (patterns, globs, segment rule, source of `generated_paths`) are echoed verbatim in `report.json` and in each affected record's `parameters`.

## 13. Error codes and fail-closed behavior

On any error below: write `errors.json` (`{code, detail, stage, at}`), write no `records.jsonl`, exit nonzero. Partial output is never published.

| Code | When |
|---|---|
| `E_SHA` | `repo_sha` not 40-hex, not present, not a commit, or `rev-parse` returns a different SHA |
| `E_REPO` | path is not a Git repository or is not readable |
| `E_SHALLOW` | shallow repository or grafts present |
| `E_MISSING_OBJECT` | a needed object is absent (partial clone); never triggers a fetch |
| `E_GIT_VERSION` | Git older than the minimum |
| `E_GIT` | a Git call exits nonzero |
| `E_TIMEOUT` | per-call or run timeout exceeded |
| `E_LIMIT` | commit, path, blob size or output caps exceeded |
| `E_CONFIG` | unknown config key, threshold out of range, invalid glob or regex |
| `E_COMPONENT_MAP` | component map SHA not in history, overlapping members, or digest mismatch |
| `E_EVIDENCE_SET` | evidence set's `repo_sha` does not match the milestone it was supplied for, or its schema version is not 0.4 |
| `E_REPLAY` | lifecycle replay differs from `ls-tree` at `repo_sha` |
| `E_PATH` | an emitted path is absolute, contains `..`, or escapes the repo |
| `E_COLLISION` | two different records share a claim id |
| `E_SCHEMA` | an emitted record fails the 0.4 schema |
| `E_ISOLATION` | the network probe shows network access inside the worker |
| `E_CACHE` | a cache entry fails its digest and the recomputation disagrees with it |

Not errors (report warnings, run continues): no `.mailmap`; no component map (component outputs skipped); no PR provider or no cached PR; a cached PR that fails its checks (that PR skipped); an unparseable manifest blob (that event skipped); rename detection limited (records flagged).

## 14. Determinism and ordering

- Same repository objects, `repo_sha`, config, component map, evidence sets, PR cache and history package version give byte-identical canonical `records.jsonl` (excluding `run_id` and `at`).
- Records sorted by `claim_id`. Inside a record: `citations` by commit time then SHA, `paths` by path bytes, `derived_from` sorted.
- No dependence on dict ordering, locale, time zone, wall clock or filesystem order. Ties in ranking break by SHA.
- Floats rounded to 4 decimals before hashing and output.

## 15. Caching

- Cache key: `(repo identity, commit SHA, ingest-relevant config digest, history package version, git version)`. One entry per commit holding its parsed name-status and numstat.
- Incremental: on a new `repo_sha`, only commits not already cached are parsed. Pattern computations rerun over the full range; they are cheap (Lab C: 1.76 s parse and 15.3 s full suite on 1,537 commits).
- Entries are content-addressed and written atomically to `cache_dir`, never inside the repository.
- A corrupt entry is discarded and recomputed. If a recomputation disagrees with a valid-looking entry, `E_CACHE`.
- The cache never stores credentials or PR data; PR caching belongs to the API seat.

## 16. No-network guarantee

- The package imports no HTTP, socket or subprocess-network library. `gitcmd` is the only subprocess path and blocks transports (`protocol.allow=never`, `GIT_NO_LAZY_FETCH=1`).
- The worker runs under OS-level isolation. Each run writes `netprobe.log` with the same probe set as Task 002 CT15 (interfaces, `curl` attempts, child-process attempts, namespace ids, outside control).
- Tests enforce it (HT10).

## 17. Wording rules for user-facing explanations

- Co-change is always phrased "changed together in N of M commits", where M is the number of commits in the considered range that touched either side. Never "depends on", "causes", "drives", "because", "is coupled to", or "breaks when".
- Every co-change, churn or hotspot sentence ends with, or sits under, the label "history pattern". Co-change is not evidence of a code dependency, and its absence is not evidence of independence (Lab C: backend API to generated client co-change was 0.14 because client regenerations often land in separate commits).
- Rationale appears only as a quote with commit or PR link: "PR #694 description says: ...". Traces never restates a motive as fact.
- Similarity renames show their score: "renamed (Git similarity 87%)".
- Alias suggestions read "suggested, not confirmed" while `review_state` is `none`, "confirmed by <reviewer>" when `confirmed`, and "disputed by <reviewer>" when `disputed`. The label stays "inferred" in all three.
- `observed` on a co-change or metric record is shown as "count checked against Git", never as "confirmed relationship".
- Impact answers keep "Code dependencies" and "History signals" as separate sections, each with its known gaps.

## 18. Test plan

pytest under `tests/history/`. Synthetic repos are built by test fixtures with Git plumbing in a temp dir, under the same isolated environment as `gitcmd`. Regression tests on the real repo use `fastapi/full-stack-fastapi-template` at `b1125d8839482cb7bbae603ddc6d0081bf87532e`, cloned read-only by the test harness, never executed. Names: `test_ht<N>_<short_name>`.

**HT1. Rename-aware churn baseline.** Given fsft at `b1125d8`, bot filter off, generated filter off (the Lab C setting). When `churn` runs. Then `backend/app/api/routes/users.py` has 43 revisions and 1,188 churn, and its revisions equal the count from `git log --follow` (43, re-checked 2026-10-21). Pass: exactly 43 and 1,188. The values with default filters are recorded and frozen as a second baseline on first run.

**HT2. Lifecycle replay.** Given fsft at `b1125d8`. When `lifecycle` runs. Then the replayed file set equals `git ls-tree -r --name-only b1125d8` (252 files, re-checked 2026-10-21) with zero missing and zero extra. Pass: 252 = 252. A mismatch raises `E_REPLAY`.

**HT3. Bulk moves.** Given fsft. When `lifecycle` runs. Then `prefix_moved` records include `8558cf0` (#630, `src/` to root, 247 renames) and the #553 cookiecutter removal event, and the total bulk moves are 9 (Lab C). Pass: present, and any count other than 9 is reported with the list.

**HT4. claim_id zero collisions.** Given a full fsft run. Then every `claim_id` is unique, every id recomputes from record content, and synthetic cases hold: same content gives the same id; another commit, path, kind, threshold, filter or extractor version gives another id; symmetric co-change gives one id for (A,B) and (B,A); distinct content under one id raises `E_COLLISION`. Pass: 0 collisions, 0 mismatches, all synthetic cases.

**HT5. Determinism.** Given two runs on fsft with the same inputs, one with a cold cache and one warm. Then canonical `records.jsonl` sha256 values are equal. Pass: equal.

**HT6. Exact and similarity renames.** Given a synthetic repo with an unchanged move, a move with edits at about 80% similarity, and a copy. Then: `renamed_to` with similarity 100, status `observed`, qualifier `exact rename (identical blob)`; `renamed_to` with the Git score, status `observed`, flag `similarity_rename`; `copied_to` with score; source keeps its lifecycle. Pass: all three as stated.

**HT7. Merges.** Given a synthetic repo with a feature branch merged with a merge commit, and a file changed on both sides. Then the timeline and milestones use the first-parent chain; lifecycle events cite the side-branch commits; churn counts each authored change once; co-change ignores the merge commit; replay equals `ls-tree`. Pass: all hold.

**HT8. Odd paths.** Given a synthetic repo with paths containing spaces, a tab, a newline, a leading dash, double quotes, non-ASCII UTF-8, and non-UTF-8 bytes. Then every path round-trips byte-exact through `-z` parsing; non-UTF-8 paths are percent-encoded with flag `non_utf8_path`; no path is absolute or contains `..`. Pass: all paths, no `E_PATH`.

**HT9. Co-change defaults and wording.** Given fsft with default config. Then a `co_changed_with` record exists for `frontend/src/components/Admin/AddUser.tsx` and `frontend/src/components/Admin/EditUser.tsx`; its `parameters` show 5, 5, 0.30, 30 and the filters; every `co_changed_with` statement matches `changed together in \d+ of \d+ commits` and contains none of `causes`, `caused`, `because`, `depends on`, `drives`, `breaks`; class `history_pattern`; status never `verified`. Pass: all hold. Support, revs and degree are frozen as baselines on first run.

**HT10. No network.** Given the worker under the isolation wrapper, plus a pytest fixture that makes socket creation raise. When a full fsft run executes, and when a synthetic partial clone with a missing blob is analyzed. Then the probe log shows no reachable network, the socket fixture is never triggered, and the partial clone gives `E_MISSING_OBJECT` with no fetch attempt. Pass: all hold.

**HT11. Mailmap.** Given a synthetic repo where one person commits under two emails, a `.mailmap` at the pinned SHA that joins them, and a later commit beyond the pinned SHA that changes the mailmap. Then authors are counted once; the later mailmap has no effect; with `mailmap: none` the two identities stay separate and the report says so. Pass: all hold.

**HT12. Bot and generated filters.** Given a synthetic repo with commits by `dependabot[bot]`, `renovate[bot]`, `github-actions[bot]`, `pre-commit-ci[bot]` and a human, and changes to `package-lock.json`, `src/client/sdk.gen.ts`, `dist/app.min.js` and source files. Then bot commits and generated paths are excluded from co-change, churn and hotspots, are present as commit facts with flags, and the report lists each rule with its removal counts. Also: `web/dist/app.js` and `build/out.o` are filtered; `distance/calc.py`, `rebuild/run.py` and `build.py` are not (whole-segment rule); a path in `generated_paths` is filtered. Pass: all hold, and turning a filter off changes the pattern outputs and their claim ids.

**HT13. Alias suggestion.** Given fsft. When `alias_suggestions` runs. Then a suggestion links paths under `backend/app/crud/` to `backend/app/crud.py` at `2d0f774` (#622), status `unvalidated`, class `history_inferred`, with its similarity metric. Pass: present, not `observed`, not `verified`.

**HT14. Manifest history.** Given fsft. When `manifest_changes` runs. Then `dependency_added` for `sqlmodel` appears at the #558 commit, before the #559 commit (Lab C ordering). Pass: present, ordered.

**HT15. Status ceilings.** Given all records from a full fsft run and from the synthetic repos. Then no history record is `verified`; every `observed` record has the check and qualifier its kind requires (section 6.1); every `history_impact_candidate`, `alias_of`, `continues_as` and `reverts` record is `unvalidated`; every record has at least one entry in `locations` or `citations`; every record validates against `traces-evidence/0.4`. Pass: 0 violations, 100% valid.

**HT16. Hooks and drivers never run.** Given a synthetic repo whose local config and `.gitattributes` define a textconv driver, an external diff, an fsmonitor command, and hooks, each of which would create a sentinel file. When a full run executes. Then no sentinel file exists. Pass: none created.

**HT17. SHA and repo refusal.** Given an abbreviated SHA, a branch name, an unknown SHA, a tree SHA, a shallow clone, and a repo with grafts. Then `E_SHA` for the first four, `E_SHALLOW` for the last two, no records written. Pass: 6 of 6.

**HT18. PR context degrade.** Given no provider; a provider returning `None`; a cached PR whose `merge_commit_sha` differs from the local commit; a cached PR with a corrupted sha256. Then: no PR records and a report reason; no PR records and a report reason; `merged_as` `unvalidated` with flag `pr_sha_mismatch`; that PR skipped with a warning. Quotes in passing cases are byte-exact. Pass: all four.

**HT19. Evidence-set diff.** Given two small evidence sets where one relationship moved lines without changing, one was removed, one was added, and one is rejected at both SHAs. Then: no record for the moved one; one `snapshot_removed`; one `snapshot_added`; the rejected one is never reported as added architecture. Pass: all hold.

**HT20. Component map.** Given a component map built at a SHA not in history, and one with overlapping members. Then `E_COMPONENT_MAP`. Given no component map, component outputs are skipped and the report says so. Pass: all hold.

**HT21. Limits and rename limit.** Given a synthetic commit renaming more files than `rename_limit`, and a run with `max_commits` below the history size. Then the first gives flag `rename_detection_limited` on that commit's records; the second gives `E_LIMIT` and no records. Pass: both.

**HT22. Milestones.** Given fsft. When `select_milestones` runs twice. Then the lists are identical, all SHAs lie on the first-parent chain, the first commit and `b1125d8` are included, every milestone has at least one reason, and the default list has at most 8 entries. With `max_milestones=20` the list has at most 20; `max_milestones=21` raises `E_CONFIG`. Pass: all hold.

**HT23. Impact separation.** Given co-change records for a target file. When `history_impact` runs. Then results appear only under `history:*` keys, `known_gaps` is non-empty, and no code-dependency record is present. Pass: all hold.

**HT24. Review state never changes status.** Given an `alias_of` record. When `review_state` is set to `confirmed` and then `disputed`. Then `status`, `label`, `class` and `claim_id` are unchanged and `status_history` gains no entry. Pass: all unchanged.

**HT25. Independent checks.** Given a synthetic repo. When the ingest parse is deliberately corrupted for one commit in a test double (wrong blob SHA, wrong count). Then the `git_object_check` or `git_recount` built on `cat-file`, `ls-tree`, `diff-tree` or `rev-list` fails for that record, which stays `unvalidated` with the failing check, and a `quote_match` pass never sets anything beyond `observed` on a `documented_rationale` record. Pass: all hold.

## 19. Open items

Closed in v2 by Architect1's answers (section 20): v1 items 2 to 10.

Still open:

1. **Schema names.** Section 5 lists requested 0.4 additions. The Evidence seat decides final names in `backend/traces/evidence/schema/evidence_record.schema.json`. History codes against the names in this document until 0.4 lands, then follows the merged schema.
2. **Decision log location.** Architect1 asked for the claim_id anchor difference (D-H6) to be recorded in DECISIONS.md. `build/traces-v1` has no `docs/DECISIONS.md` at the time of this draft, and it is not this seat's file, so the entry is requested in the PR body and recorded here in section 20 meanwhile.
3. **Lab C code.** Clean rewrite. Lab C scripts stay outside the repo and are not vendored.
4. **Discussions and issue threads.** Deferred past v1. Charter open question 10 stays open.

## 20. Decisions (Architect1, 2026-10-21 IST)

Binding. They supersede any conflicting text above.

| Id | Decision | Where applied |
|---|---|---|
| D-H1 | Co-change, churn and hotspot metric values may reach `observed` after an independent recount, because the count is a Git fact. Class stays `history_pattern`, never `verified`. Any coupling or "related" interpretation stays `unvalidated`. | 6.1, 6.1 rules, 17, HT15 |
| D-H2 | Git plumbing checks (`cat-file`, `ls-tree`, `diff-tree`, `rev-list` recount) that do not read the log parse count as independent checks for git-object facts. `quote_match` establishes only that a quote exists at the cited commit or PR, nothing about intent. | 5, 6.1, HT25 |
| D-H3 | New `citations` field. `locations` may be empty for history records. The schema requires at least one of `locations` or `citations`. | 5, 7.1, HT15 |
| D-H4 | New `review_state` `{state: none|confirmed|disputed, reviewer, at}`, separate from `status`. It never promotes status. | 5, 6.1, 6.2, 17, HT24 |
| D-H5 | "All commits" for lifecycle and churn means all non-merge commits for events and churn; the file-set replay runs along first-parent with merges diffed against the first parent. | 9.2, 9.3, 12 |
| D-H6 | Git-object fact `claim_id`s anchor to their commit, not `repo_sha`. Difference from Task 002 claim_id v3: v3 hashes `repo_sha`, so the same source claim at a new pinned SHA gets a new id and the old one is linked by `supersedes`. A Git-object fact is immutable once its commit exists, so anchoring to the commit keeps its id stable across re-pins and lets the cache reuse it. Pattern records still anchor to their computed range and change id when the range changes. Requested as a DECISIONS.md entry (section 19 item 2). | 7.2 |
| D-H7 | Generated filter applies `dist/` and `build/` at any depth, matching whole directory segments only. Configurable and echoed in the criteria. | 12, HT12 |
| D-H8 | The Evidence seat supplies `generated_paths`, including output dirs detected from generator config (for example the openapi-ts client). History consumes them. | 3, 12, HT12 |
| D-H9 | Milestone cap: default 8 for the index worker; on-demand compare capped at 20. | 8.3, 9.7, 12, HT22 |
