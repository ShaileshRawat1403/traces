# Task 002 environment (steps 0 and 1)

Recorded 2026-10-21, 07:20 to 07:30 IST. Box: Debian 13 (trixie), kernel 6.12.94+, x86_64. All paths are under `/workspace/traces-research/task002/` unless absolute.

## Pinned tools

| tool | exact version | integrity / hash | license | install command | path |
|---|---|---|---|---|---|
| CodeGraph | npm `@colbymchenry/codegraph@1.6.2` | `dist.integrity` sha512-hODH/mGnCf3IUMs6rzktv/zbecJIKJfdZAYHZ9mqecb0G7ZkHaA8CZafDVnswANFEL1YFcG+lfAwc5SIXzUH6Q== ; `dist.shasum` 372b7b4f0190197b07d444116d6692240883a2d5 | MIT (npm metadata and package.json) | `npm install --save-exact --ignore-scripts --no-audit --no-fund @colbymchenry/codegraph@1.6.2 typescript@5.9.3` (in `tools/`) | `tools/node_modules/@colbymchenry/codegraph` |
| CodeGraph platform bundle (pulled as optionalDependency) | `@colbymchenry/codegraph-linux-x64@1.6.2` | sha512-DJWizz1qHNr1MsbK6fz1mjVUQjeTH3T+L0D2BGaLkygWzBnNMG30MvLq1ae0m6cUV414U8aEow5Eb/kIORA8+w== ; shasum 7fca3d49db06571846ca98bca778c4ee6e83553c | MIT | same command | `tools/node_modules/@colbymchenry/codegraph-linux-x64` |
| CodeGraph bundled runtime | Node v24.16.0 (inside the linux-x64 bundle) | sha256 of `node` binary b2959781cc5a74c357ffa02367efa8a0330cbb1c9cb347732fdfaaaca381cbcd | (Node.js, MIT) | shipped in bundle | `tools/node_modules/@colbymchenry/codegraph-linux-x64/node` |
| CodeGraph index | schema version 11 (`schema_versions` rows 1 and 11), extraction version 27, `indexed_with_version` 1.6.2 | n/a | n/a | n/a | `src/fsft/.codegraph/codegraph.db` (sha256 647c2fea...5898c10) |
| TypeScript (superseded 2026-10-21 10:03 IST by 6.0.3, see below; kept installed for comparison) | npm `typescript@5.9.3` (newest 5.x on the registry: `npm view typescript@5 version` ends at 5.9.3) | sha512-jl1vZzPDinLr9eUt3J/t7V6FgNEw9QjvBPdysz9KfQDD41fQrC2Y4vKQdiaUpFT4bXlb1RHhLpp8wtm6M5TgSw== | Apache-2.0 | same command | `tools/node_modules/typescript` |
| Python | CPython 3.14.8 (python-build-standalone, `cpython-3.14.8-linux-x86_64-gnu`), venv | sha256 of `bin/python3.14` 28299dda2e5c8572d39821fee8552b543dfadc4681a4c4d0b03c69e56d7f9d66 | PSF | `UV_PYTHON_INSTALL_DIR=tools/python UV_CACHE_DIR=tools/uv-cache uv python install 3.14 --no-bin` then `uv venv --python 3.14 --no-project tools/py314` | `tools/python/`, venv `tools/py314/` |
| Node (system) | v20.19.2, npm 11.21.0 | unchanged | | none | `/usr/bin/node` |
| uv | 0.13.1 | unchanged | | none | system |
| git | 2.47.3 | unchanged | | none | system |

Package identity: `TASK_002_PLAN.md` step 1 and section 7 name `@colbymchenry/codegraph` 1.6.2 on npm. This is not the package Task 001 Lab tested (`@lemonberrylabs/codegraph@0.1.0`). `npm view @colbymchenry/codegraph@1.6.2` resolves to one package, so the name is not ambiguous. Logs: `logs/setup_npm.log`, `logs/setup_npm_install.log`.

Task 001 copy: `_tests/cg-npm/package-lock.json` has the same integrity for both the main package and the linux-x64 bundle. Because the hashes match, reusing it would have been allowed. I installed a fresh pinned copy under `tools/` anyway, so task002 is self-contained. Same hashes.

Python default unchanged: `/usr/bin/python3` is still 3.13.5. Python 3.14.8 parses `backend/app/api/deps.py` (`ok`), system 3.13.5 rejects it (`SyntaxError: multiple exception types must be parenthesized`). Log: `logs/setup_python.log`, `logs/setup_source.log`.

TypeScript note: the repo itself declares `"typescript": "^6.0.3"` (`frontend/package.json:62`). The brief fixed 5.x, so 5.9.3 is pinned. TypeScript 5.9.3 parsed all 109 `.ts`/`.tsx` files CodeGraph indexed with 0 parse diagnostics, and Python 3.14.8 `ast` parsed all 43 indexed Python files (`step1/logs/14_parser_coverage.log`). A type-check (as opposed to a parse) under 5.x might differ from 6.x; not tested.

## Source checkout

```
git clone --no-hardlinks /workspace/traces-research/lab/repos/fsft src/fsft
git -C src/fsft checkout -q --detach b1125d8839482cb7bbae603ddc6d0081bf87532e
git -C src/fsft rev-parse HEAD            -> b1125d8839482cb7bbae603ddc6d0081bf87532e
git -C src/fsft status --porcelain | wc -l -> 0
```
252 tracked files, pack hardlink count 1 (not shared). The source clone `lab/repos/fsft` was also at the SHA and clean. `_src/` and lab clones were not indexed. After indexing, the only change in `src/fsft` is the untracked `.codegraph/` directory (`.gitignore`, `codegraph.db`, `-wal`, `-shm`). Log: `logs/setup_source.log`, `step1/logs/02_index.log`, `step1/logs/13_post_state.log`.

## Network off for indexing and validation

Mechanism: `tools/offline.sh` wraps every step 1 command in `unshare -rn` (new user and network namespace with only a down loopback interface). It also sets `HOME=tools/cghome`, `CODEGRAPH_TELEMETRY=0`, `DO_NOT_TRACK=1`, `CODEGRAPH_NO_DOWNLOAD=1`, `NO_UPDATE_NOTIFIER=1`.

Proof, run inside the same wrapper (`step1/logs/00_netproof_and_help.log`):
- `ip -o link`: only `lo`, state DOWN
- `curl https://registry.npmjs.org/` -> exit 6, could not resolve host
- `curl https://1.1.1.1/` (no DNS) -> exit 7, could not connect
- `curl https://telemetry.getcodegraph.com/` -> exit 6
- `codegraph telemetry status` -> "Telemetry: disabled (DO_NOT_TRACK environment variable)"

Every step 1 command ran under this wrapper: index, all CLI queries, SQLite reads, and parser checks. Network was used only for the three setup downloads (npm registry metadata and tarballs, the uv Python build).

## Deviations to note

- My shell still carried `HOME=/workspace/traces-research/lab/tools/gitnexus/home` from a Task 001 sandbox. The `npm view` and `npm install` setup commands therefore wrote npm cache and debug logs into `lab/tools/gitnexus/home/.npm/`. This is a Lab scratch directory, not a user repo and not task002. GitNexus itself was not run. HOME was reset to `/home/box` before writing this file. All CodeGraph runs used the sandboxed `tools/cghome`, which stayed empty.
- `codegraph init` writes `.codegraph/` into the target. This is expected and is why the throwaway copy exists. It made no other writes and installed no agent or editor config (`install` subcommand never run).

## TypeScript 6.0.3 (added 2026-10-21 10:03 IST, approved by the lead; supersedes 5.9.3 for validation)

| field | value |
|---|---|
| range | repo `frontend/package.json:62` declares `"typescript": "^6.0.3"`; `npm view "typescript@^6.0.3" version` returns only `6.0.3`; `npm view "typescript@~6.0.0" version` returns `6.0.2`, `6.0.3` |
| pinned | `typescript@6.0.3` (latest 6.0.x satisfying ^6.0.3) |
| dist.integrity | sha512-y2TvuxSZPDyQakkFRPZHKFm+KKVqIisdg9/CZwm9ftvKXLP8NRWj38/ODjNbr43SsoXqNuAisEf1GdCxqWcdBw== |
| dist.shasum | 90251dc007916e972786cb94d74d15b185577d21 |
| tarball | https://registry.npmjs.org/typescript/-/typescript-6.0.3.tgz |
| license | Apache-2.0 |
| engines | node >=14.17 (runs on system Node v20.19.2) |
| install | `cd tools/ts6 && npm init -y && npm install --save-exact --ignore-scripts --no-audit --no-fund typescript@6.0.3` with `HOME=task002/tools/home` |
| package.json | `tools/ts6/package.json`, dependency `"typescript": "6.0.3"` (exact) |
| lockfile | `tools/ts6/package-lock.json` (sha256 427b97fc486624e5c9b52ff69e4db4bf2f9d90d9196bfedd8c6bcbfafd669899), entry integrity equals dist.integrity above |
| module path | `tools/ts6/node_modules/typescript` |
| log | `logs/setup_ts6.log` |

Network was used only for the `npm view` and `npm install` above. HOME was `task002/tools/home` for this download (npm cache in `tools/home/.npm`). Nothing new was written to `lab/tools/gitnexus/home` (checked with `find -newermt "2026-10-21 10:00"`, empty). Target checkout check, before and after, in `logs/setup_ts6.log`: HEAD `b1125d8839482cb7bbae603ddc6d0081bf87532e`, only the untracked `.codegraph/` index present, no tracked changes.

Selecting the TS version: `step1/ts_decls.js` and `step1/ts_parse_diag.js` read `TS_MODULE` (default: the 5.9.3 path, so earlier runs reproduce). `step1/analyze.py` reads `TS_MODULE` for the reported version and `ANALYSIS_OUT` for its output file. No other change to the scripts.

## Network isolation, re-verified 2026-10-21 10:04 IST

`tools/offline.sh` is the wrapper every validation run used (index, CLI queries, SQLite reads, parser checks). Its content is unchanged since 07:21:59 IST, before the index run at 07:22 (sha256 81042fecf68704913ba73359291e9b658f481e1d1853065fd7b845b0cb9d6466). The two earliest logs (`step1/logs/00_netproof_and_help.log`, `01_subcommand_help.log`) ran with an earlier version that lacked `CODEGRAPH_NO_DOWNLOAD=1`. Same `unshare -rn` line. Isolation is OS level: a new network namespace with only a down loopback. Probes inside and a control outside: `logs/netprobe.log`.

## Environment hygiene issue H-001: npm cache and debug logs written to the Task 001 GitNexus sandbox HOME

| field | value |
|---|---|
| what | npm wrote its cache and debug logs to `/workspace/traces-research/lab/tools/gitnexus/home/.npm/` instead of under `task002/`. Contents: 6 debug logs in `_logs/`, `_update-notifier-last-checked`, and `_cacache/` (tarballs and index for `@colbymchenry/codegraph@1.6.2`, `@colbymchenry/codegraph-linux-x64@1.6.2`, `typescript@5.9.3`, plus registry metadata). 29 files, 85,337,695 bytes (82 MB by `du -sh`). |
| when | 2026-10-21 07:20 to 07:21 IST (file mtimes: 5 files at 07:20, 24 at 07:21; log names `2026-10-21T01_50_58Z` to `01_51_13Z` UTC). No file there is newer than 07:21. |
| commands that wrote it | per the logs' `verbose argv` lines: four `npm view` calls (codegraph, codegraph-linux-x64, `typescript dist-tags`, `typescript@5`), `npm init --yes`, `npm install --save-exact --ignore-scripts --no-audit --no-fund @colbymchenry/codegraph@1.6.2 typescript@5.9.3` |
| cause | stale HOME. My shell still exported `HOME=/workspace/traces-research/lab/tools/gitnexus/home` from Task 001, where GitNexus ran with a sandboxed HOME. npm resolves its cache and log dir from HOME (`load:file:.../gitnexus/home/.npmrc` in each log). The CodeGraph runs were unaffected: `tools/offline.sh` sets its own HOME (`tools/cghome`). |
| GitNexus | never ran in Task 002. The GitNexus state files in that HOME (`.gitnexus/registry.json`, `.lbdb/`) were last modified 2026-10-20 23:15 IST (Task 001). No gitnexus process was running (`ps`). In the npm logs "gitnexus" appears only as part of the HOME path. |
| fix | HOME reset to `/home/box` at about 07:30 IST, then set to `task002/tools/home` for all work since 10:02 IST. The TS 6.0.3 install wrote its npm cache to `task002/tools/home/.npm`. No new files in the GitNexus HOME since (`find -newermt "2026-10-21 10:00"` empty). |
| status | **retained, not deleted**, so the record stays auditable. Deletion would need its own approval. |
