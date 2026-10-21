# LAB C results: architecture history from native git + Python stdlib

Detail: `lab/C/evolution.md` (narrative, four evidence classes kept separate), `lab/C/verdict.md` (v1 verdict and costs), outputs in `lab/C/out/`, raw logs and spot-checks in `lab/C/logs/`.

## Setup

- Repo: `fastapi/full-stack-fastapi-template` @ `b1125d8839482cb7bbae603ddc6d0081bf87532e` (same as the lead's clone). Second sample: `ShaileshRawat1403/traces` @ `63103ac4adcb62a1ff31d9a1ca9955e3d855c850` (read-only clone, 1 commit; scripts exit 0 with empty results).
- Tools: git 2.47.3, Python 3.13.5 stdlib only, gh 2.102.0 (already authenticated, GET only). No third-party Python packages.
- Scripts (`lab/C/scripts/`, 650 lines total, my own code): `gitlog.py` (shared parser), `snapshots.py`, `lifecycle.py`, `cochange.py`, `hotspots.py`, `reverts.py`, `deps.py`, `boundary.py`, `decisions.py`, `run_all.sh`.
- Commands: `cd lab/C/scripts && ./run_all.sh` then `python3 decisions.py ../out 25`. Underlying git calls: `git log --name-status -M -C`, `git log --numstat --no-renames`, `git log --numstat -M -z`, `git ls-tree -r`, `git show <rev>:<path>`, `git log --follow`.

## Tested vs only read

- Tested: every script above on both repos; spot-checks against `git log --follow`, `git ls-tree`, `git show` (`lab/C/logs/spotchecks.txt`); 25 + 7 GitHub API reads.
- Read only: Code Maat README (GPL-3.0). I did not open, copy or run its source; techniques were reimplemented from the README descriptions (`lab/desk/code-maat-techniques.md`). `--temporal-period`, `soc`, `communication` and `fragmentation` were not reimplemented.

## Key findings (tested)

- Replayed file lifecycle equals `git ls-tree` at HEAD (252 = 252). 9 bulk moves found, including #630 (247 renames, `src/` to root) and #553 (164 files, cookiecutter removal).
- `git log --follow backend/app/crud.py` stops at #622, where the `crud/` package became one file. Git sees delete plus add; this semantic rename needs extra logic.
- 3 real reverts, 1 false positive from a Dependabot body quoting an upstream changelog.
- 34 files added and deleted within a short window (for example Couchbase-era files deleted 14 days after being added).
- Co-change: `AddUser.tsx`/`EditUser.tsx` degree 0.95. Backend API to generated client co-change confidence only 0.14 (client to API 0.30).
- 18 of 25 architecturally relevant PRs have descriptions that add almost nothing beyond the title. Rationale sits in a few PR bodies (#694, #2393), in comments (13 on #694) and in Discussions (#1862 links Discussion #1555).
- Dependency history shows sequencing the code does not: SQLModel was added in #558 before #559 adopted it.
- Bug found and fixed in my own hotspot code: rename commits were double-counted under `--numstat --no-renames` (`users.py` 48 revisions vs 43 true, churn 2,974 vs 1,188). Fixed with `--numstat -M -z`.

## Cost (measured)

Full suite 15.3 s wall on 1,537 commits; history parse 1.76 s; peak RSS about 80 MB; clone 4.3 s, 7.5 MB. GitHub API: 25 PRs in 57.1 s, rate limit 4964 to 4939. Large repos not measured.

## Verdict

Native git is enough for the v1 history layer (lifecycle, renames, co-change, hotspots, reverts, manifest and import-graph diffs, PR-number linking). It is not enough for rationale (needs PR bodies, comments and Discussions through the API), semantic renames and refactor lineage, framework and cross-language edges (DI, OpenAPI client), and parsing new language syntax (needs tree-sitter or the repo's Python version). See `lab/C/verdict.md`.
