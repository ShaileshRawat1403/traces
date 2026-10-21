#!/usr/bin/env bash
# Run a command with network cut (new user+net namespace, only a down loopback), telemetry off, sandboxed HOME.
export HOME=/workspace/traces-research/task002/tools/cghome
export CODEGRAPH_TELEMETRY=0 DO_NOT_TRACK=1 NO_UPDATE_NOTIFIER=1 CODEGRAPH_NO_DOWNLOAD=1
export PATH=/workspace/traces-research/task002/tools/node_modules/.bin:$PATH
exec unshare -rn -- "$@"
