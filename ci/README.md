# CI workflow (staged)

`github-actions-ci.yml` is the CI workflow for this repository. It lives here because the token used to push `build/traces-v1` lacks GitHub's `workflow` scope, and GitHub refuses pushes that add files under `.github/workflows/` without it (docs/DECISIONS.md D-018).

To activate: with a credential that has the `workflow` scope, run `git mv ci/github-actions-ci.yml .github/workflows/ci.yml`, commit and push. Jobs: python (ruff, mypy, checker integrity, unit + API tests including the OpenAPI currency check), web (typecheck, generated API types currency, build), baseline (CT1-CT16, RT1-RT8 and the 0.4 migration under `unshare -rn`). All on free GitHub-hosted `ubuntu-latest` runners with read-only permissions and no secrets.
