# Fixtures and third-party content

- The target repository `fastapi/full-stack-fastapi-template` is never committed. The pipeline fetches it at `b1125d8839482cb7bbae603ddc6d0081bf87532e` into `.cache/targets/github.com__fastapi__full-stack-fastapi-template/<sha>/source` (gitignored), then makes throwaway clones per run under `.traces-data/runs/<run_id>/` (gitignored). Clones use hardened git config (hooks off, symlinks off, protocol allowlist, LFS off). Its code, hooks, installs and tests are never run.
- The expected chain fixture (`backend/traces/fixtures/task002/chain.py`) is generated at run time from the pinned checkout; it stores file paths, line numbers and token names only. Its provenance label stays `task002/fixtures/chain_create_item.json` so records match Task 002.
- Negative control N1 originally quoted a GitDiagram page. Only its sha256 and byte offsets are committed (D-010); set `TRACES_GITDIAGRAM_PAGE=/path/to/page` to re-verify against a local copy.
- Unit and API tests use synthetic records written in the tests (no template text).
