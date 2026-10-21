#!/usr/bin/env bash
# Traces worker sandbox (port of research/task002/tools/offline.sh).
# Runs a command in a new user + network namespace (only a DOWN loopback), telemetry off, sandboxed HOME,
# credentials stripped from the environment, and resource limits. Usage: sandbox.sh <command> [args...]
# Env in: TRACES_SANDBOX_HOME (empty dir), TRACES_TOOLCHAIN_DIR, TRACES_ISOLATION (unshare|none),
#         TRACES_LIMIT_CPU_S (default 1800), TRACES_LIMIT_NOFILE (default 4096), TRACES_LIMIT_FSIZE_KB (default 4 GiB),
#         TRACES_LIMIT_AS_KB (default unset: V8/WebAssembly reserve large virtual ranges, so an address-space
#         limit breaks CodeGraph; memory capping is an open item, see docs/DECISIONS.md D-006).
set -u
: "${TRACES_SANDBOX_HOME:?TRACES_SANDBOX_HOME not set}"; : "${TRACES_TOOLCHAIN_DIR:?TRACES_TOOLCHAIN_DIR not set}"
mkdir -p "$TRACES_SANDBOX_HOME"
export HOME="$TRACES_SANDBOX_HOME"
export CODEGRAPH_TELEMETRY=0 DO_NOT_TRACK=1 NO_UPDATE_NOTIFIER=1 CODEGRAPH_NO_DOWNLOAD=1
export GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_TERMINAL_PROMPT=0 GIT_OPTIONAL_LOCKS=0
export PATH="$TRACES_TOOLCHAIN_DIR/node_modules/.bin:$PATH"
# never hand credentials to analysis workers
for v in $(env | cut -d= -f1 | grep -E -i '(TOKEN|SECRET|PASSWORD|API_KEY|CREDENTIAL|^GH_|^GITHUB_|^AWS_|^OPENAI|^ANTHROPIC|^XAI)' ); do unset "$v"; done
[ -n "${TRACES_LIMIT_AS_KB:-}" ] && ulimit -v "$TRACES_LIMIT_AS_KB"
ulimit -f "${TRACES_LIMIT_FSIZE_KB:-4194304}" 2>/dev/null || true
ulimit -t "${TRACES_LIMIT_CPU_S:-1800}" 2>/dev/null || true
ulimit -n "${TRACES_LIMIT_NOFILE:-4096}" 2>/dev/null || true
case "${TRACES_ISOLATION:-unshare}" in
  unshare) exec unshare -rn -- "$@" ;;
  none) echo "sandbox.sh: WARNING isolation=none, network NOT isolated" >&2; exec "$@" ;;
  *) echo "sandbox.sh: unknown TRACES_ISOLATION=${TRACES_ISOLATION}" >&2; exit 64 ;;
esac
