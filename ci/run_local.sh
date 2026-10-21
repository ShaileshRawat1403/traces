#!/usr/bin/env bash
# shellcheck disable=SC2329  # job_* and helpers are invoked indirectly via "job_${name}"
# Local equivalent of .github/workflows/ci.yml without act or Docker. Same jobs, same commands, run on this machine.
#
#   ci/run_local.sh                 # all jobs: lint types unit api web-build target contract regression e2e
#   ci/run_local.sh lint unit api   # selected jobs, in the order given
#
# Each job's output goes to $TRACES_CI_LOG_DIR/<job>.log (default .traces-data/ci-local/<timestamp>/, gitignored).
# The summary prints PASS, FAIL or SKIP per job; the script exits 1 if any job failed. A skipped job is never a pass.
# Credentials: every exported variable whose name looks like a token, secret, password or key is unset first, so a
# local pass means the jobs need no secrets (CI runs with none). Values are never read or printed.
# Differences from GitHub-hosted runners: the local Node and uv versions are used and recorded (CI: Node 22, uv from
# astral-sh/setup-uv); uv and npm use their local caches; the target cache is .cache/targets as in CI.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 2
ROOT=$(pwd)

PYTHON_VERSION="3.14.8"
TARGET_SHA="b1125d8839482cb7bbae603ddc6d0081bf87532e"
TARGET_PATH=".cache/targets/github.com__fastapi__full-stack-fastapi-template/${TARGET_SHA}/source"
ALL_JOBS=(lint types unit api web-build target contract regression e2e)

for v in $(compgen -e); do
  case "${v^^}" in
    *TOKEN*|*SECRET*|*PASSWORD*|*PASSWD*|*API_KEY*|*APIKEY*|*PRIVATE_KEY*|*CREDENTIAL*) unset "$v" ;;
  esac
done
export UV_NO_PROGRESS=1 NPM_CONFIG_AUDIT=false NPM_CONFIG_FUND=false

LOG_DIR="${TRACES_CI_LOG_DIR:-$ROOT/.traces-data/ci-local/$(date +%Y%m%dT%H%M%S)}"
mkdir -p "$LOG_DIR"

py_env()        { uv python install "$PYTHON_VERSION" && uv sync --frozen; }
web_env()       { (cd web && npm ci --ignore-scripts); }
toolchain_env() { (cd toolchain && npm ci --ignore-scripts); }
userns()        { unshare -rn true && echo "unshare available"; }  # CI also runs: sudo sysctl kernel.apparmor_restrict_unprivileged_userns=0

job_lint()      { py_env && uv run --frozen ruff check backend tests; }
job_types()     { py_env && uv run --frozen mypy && web_env && (cd web && npm run typecheck); }
job_unit()      { py_env && (cd backend/traces/validators/checker && sha256sum -c SHA256SUMS) && uv run --frozen pytest -q tests/unit; }
job_api()       { py_env && uv run --frozen pytest -q tests/api; }
job_web_build() { web_env && (cd web && npm run check:api && npm run build); }
job_target() {
  if [ -d "$TARGET_PATH/.git" ]; then
    echo "target cache hit: $TARGET_PATH"
  else
    echo "target cache miss: fetching with hardened git"
    py_env && uv run --frozen python -c "from traces.core.config import get_settings; from traces.evidence.pipeline import target_checkout; print(target_checkout(get_settings()))" || return 1
  fi
  test "$(git -C "$TARGET_PATH" rev-parse HEAD)" = "$TARGET_SHA" && echo "pinned HEAD ok: $TARGET_SHA"
}
need_target()   { [ -d "$TARGET_PATH/.git" ] || { echo "target cache missing (run the target job first)" >&2; return 1; }; }
job_contract()  { need_target && py_env && toolchain_env && userns && TRACES_ISOLATION=unshare uv run --frozen pytest -q tests/contract; }
job_regression(){ need_target && py_env && toolchain_env && userns && TRACES_ISOLATION=unshare uv run --frozen pytest -q tests/regression; }
job_e2e() {
  # Mirrors the CI placeholder (skipped on push and PR): reported as SKIP until the Playwright harness lands.
  [ -f tests/e2e/playwright.config.ts ] || return 77
  echo "tests/e2e exists but the e2e job is still a placeholder; wire it in .github/workflows/ci.yml and here" >&2
  return 1
}

{
  echo "date: $(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "git: $(git rev-parse HEAD) on $(git rev-parse --abbrev-ref HEAD)$(git diff --quiet HEAD -- . 2>/dev/null || echo ' (worktree modified)')"
  echo "uv: $(uv --version 2>&1)"; echo "node: $(node --version 2>&1)"; echo "npm: $(npm --version 2>&1)"
  echo "kernel: $(uname -sr)"
} > "$LOG_DIR/env.txt"
cat "$LOG_DIR/env.txt"

JOBS=("$@"); [ ${#JOBS[@]} -eq 0 ] && JOBS=("${ALL_JOBS[@]}")
declare -A RESULT DURATION
fail=0
for j in "${JOBS[@]}"; do
  fn="job_${j//-/_}"
  if ! declare -F "$fn" >/dev/null; then echo "unknown job: $j (jobs: ${ALL_JOBS[*]})" >&2; exit 2; fi
  echo "==> $j"
  start=$(date +%s)
  ( set -o pipefail; "$fn" ) > "$LOG_DIR/$j.log" 2>&1
  rc=$?
  DURATION[$j]=$(( $(date +%s) - start ))
  case $rc in
    0) RESULT[$j]=PASS ;;
    77) RESULT[$j]=SKIP ;;
    *) RESULT[$j]="FAIL($rc)"; fail=1 ;;
  esac
  echo "    ${RESULT[$j]} in ${DURATION[$j]}s  (log: $LOG_DIR/$j.log)"
done

echo
printf '%-12s %-9s %s\n' job result seconds | tee "$LOG_DIR/summary.txt"
for j in "${JOBS[@]}"; do printf '%-12s %-9s %s\n' "$j" "${RESULT[$j]}" "${DURATION[$j]}"; done | tee -a "$LOG_DIR/summary.txt"
exit $fail
