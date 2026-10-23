# tests/security

Owner: Traces Lab (QA, Integration, CI and Security seat). Charter section 7: errors, unsupported types, missing API keys,
indexing failures, rate limits, malicious paths and oversized repos fail safely and visibly; no unintended outbound calls.

Run: `TRACES_ISOLATION=unshare uv run --frozen pytest -q -rxXs tests/security` (CI job `security`; `ci/run_local.sh security`).
Needs the pinned toolchain (`cd toolchain && npm ci --ignore-scripts`), `unshare -rn`, `ip` and `curl`. No network is used:
the hostile target is a local Git repository built in a temp dir and indexed by the real worker (`IndexRun`) through a file path,
and GitHub is replaced by a `git` shim on `PATH` where a remote is needed.

| File | Covers |
| --- | --- |
| `test_repo_urls.py` | 28 bad URLs (non-GitHub host, lookalike host, userinfo, http, ssh, scp-like, git://, file://, credentials, IP literals, localhost, port, query, fragment, extra path, `..`, `%2e%2e`, newline and NUL injection, overlong, empty, javascript:) refused with 422 before any `ls-remote`; credentials never echoed; bad SHAs refused |
| `test_fetch_limits.py` | clone timeout and clone size cap kill git and remove the partial clone; file-count and tree-size caps before checkout; missing commit; private, unreachable and other git failures classified; git gets no credentials and no prompt; API 504 on ls-remote timeout, 422 on private repo, 429 with `Retry-After` |
| `test_hostile_repo.py` | symlinks out of the tree checked out as plain files; `file://` submodule not fetched; claims stay inside the tree; odd names readable; `../`, absolute, `~`, backslash, NUL, newline, encoded `%2e%2e`, option-like paths refused; repo id traversal; line-range caps; oversized repo is a visible failed job |
| `test_no_key_and_caps.py` | explain and graph useful without any provider key; chat bundle is a manifest, not a call; keys cannot be submitted; worker env strips credentials; step timeout and RSS cap kill the process tree |
| `test_outbound.py` | worker: only the target clone (plus a local clone of the cache) is network-capable, every analysis process goes through `workers/sandbox.sh`, in-sandbox probes show the network denied; app: every read endpoint, explain and chat bundle make no off-loopback connect (audit hook) and serve normally inside an empty `unshare -rn` namespace |

Open findings are `xfail(strict=True)` with the finding id and owning seat in the reason, so they show in `-rxX` output and a fix
makes the test pass unexpectedly (strict), which fails the job until the marker is removed. Findings: docs/ACCEPTANCE.md.
