#!/usr/bin/env bash
# Probe commands, run identically inside and outside tools/offline.sh. Each prints command, output, exit code.
p(){ echo "\$ $*"; "$@" 2>&1; echo "[exit=$?]"; }
p id -u
p cat /proc/self/ns/net 2>/dev/null; echo "netns: $(readlink /proc/self/ns/net)"
p ip addr
p ip link
p curl -sS -m 8 -o /dev/null -w "http_code=%{http_code}\n" https://registry.npmjs.org/
p curl -sS -m 8 -o /dev/null -w "http_code=%{http_code}\n" https://1.1.1.1/
