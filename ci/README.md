# CI workflow (staged)

`github-actions-ci.yml` is the CI workflow for this repository. It lives here because the token used to push `build/traces-v1` lacks GitHub's `workflow` scope, and GitHub refuses pushes that add files under `.github/workflows/` without it (docs/DECISIONS.md D-018).

To activate: with a credential that has the `workflow` scope, run `git mv ci/github-actions-ci.yml .github/workflows/ci.yml`, commit and push. Until then no GitHub CI run exists, and nothing here may be reported as "CI passed".

## Jobs

All jobs run on free GitHub-hosted `ubuntu-latest` runners with `permissions: contents: read`, `persist-credentials: false` on checkout, and no secrets. Third-party actions are pinned to full commit SHAs (release tag in a trailing comment). Python 3.14.8 and uv 0.13.4 are pinned; Node is 22 on CI.

| Job | Commands | Needs |
| --- | --- | --- |
| `lint` | `ruff check backend tests` | |
| `types` | `mypy` (files listed in `pyproject.toml`), `web: tsc --noEmit` | |
| `unit` | `sha256sum -c` on the frozen checker, `pytest tests/unit` | |
| `api` | `pytest tests/api` (includes the `docs/contracts/openapi.json` currency check) | |
| `web-build` | `npm run check:api` (generated TS types current), `npm run build` | |
| `target` | restores or fills the cache of `fastapi/full-stack-fastapi-template` at `b1125d8839482cb7bbae603ddc6d0081bf87532e` (hardened git fetch via `traces.evidence.pipeline.target_checkout`), checks the pinned HEAD | |
| `contract` | toolchain `npm ci --ignore-scripts`, user namespaces on, `pytest tests/contract` (CT1-CT16, fresh baseline under `unshare -rn`) | `target` |
| `regression` | same setup, `pytest tests/regression` (RT1-RT8, baseline distribution, canonical hashes, 0.4 migration) | `target` |
| `e2e` | placeholder that runs only on a manual `workflow_dispatch` with `e2e=true` (and then fails until tests/e2e exists), so push and PR runs show it as skipped, never as passed. The Playwright harness PR replaces it. | `api`, `web-build`, `target` |

Target cache: `actions/cache` with key `target-fastapi-full-stack-fastapi-template-<full sha>-v1` on the exact checkout path under `.cache/targets/`. `contract` and `regression` restore it with `fail-on-cache-miss: true`, so the baseline jobs never fetch from the network themselves. Bump the `-v1` suffix to invalidate.

`contract` and `regression` each run a fresh baseline (3 CodeGraph index runs, D-008) so each job stands alone; about 1 and 2 minutes locally.

## Running it locally

```
ci/run_local.sh                    # every job, in workflow order
ci/run_local.sh lint types unit    # selected jobs
```

`ci/run_local.sh` runs the same commands as the workflow without act or Docker. It unsets every exported variable whose name looks like a token, secret, password, credential or API key before running (values are never read), writes one log per job plus `env.txt` and `summary.txt` to `.traces-data/ci-local/<timestamp>/` (gitignored), prints PASS, FAIL or SKIP per job, and exits 1 if any job failed. Differences from hosted runners: it uses the local Node and uv, and it cannot run the `sudo sysctl` user-namespace step (it only checks `unshare -rn true`).

## act

`nektos/act` 0.2.89 lists and parses the workflow (9 jobs, 2 stages) but cannot execute it on the Traces Lab box: there is no Docker or Podman, and act's `-self-hosted` platform runs JavaScript actions with the host Node (20.19.2), while `setup-uv`, `setup-node` and `cache` declare the `node24` runtime and crash on it (`webidl.util.markAsUncloneable is not a function`). Use `ci/run_local.sh`, or act on a machine with Docker.
