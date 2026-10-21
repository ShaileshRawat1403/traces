#!/usr/bin/env bash
# CT15 (e): same probe set OUTSIDE the wrapper; must connect. Prints CONTROL_SUMMARY. Usage: control_outside.sh <netprobe.log>
LOG="$1"; T=/workspace/traces-research/task002; NODE24=$T/tools/node_modules/@colbymchenry/codegraph-linux-x64/node
exec 3>>"$LOG"; say(){ echo "$*" >&3; }
ONS=$(readlink /proc/$$/ns/net)
say "=== OUTSIDE WRAPPER (control) $(date -Iseconds) shell pid $$ netns $ONS"
IPL=$(ip -o link 2>&1); say "\$ ip -o link"; say "$IPL"
B1=$(curl -sS -m 8 -o /dev/null -w 'http_code=%{http_code}' https://registry.npmjs.org/ 2>&1; echo " exit=$?"); say "\$ curl https://registry.npmjs.org/ -> $B1"
B2=$(curl -sS -m 8 -o /dev/null -w 'http_code=%{http_code}' https://1.1.1.1/ 2>&1; echo " exit=$?"); say "\$ curl https://1.1.1.1/ -> $B2"
C_OUT=$("$NODE24" "$T/tools/netprobe_child.js" 2>&1); say "\$ $NODE24 $T/tools/netprobe_child.js"; say "$C_OUT"
E=fail
echo "$B1" | grep -q 'exit=0' && echo "$B2" | grep -q 'exit=0' && [ "$(echo "$C_OUT" | grep -c 'result=CONNECTED')" -eq 2 ] && E=pass
say "CONTROL_SUMMARY e=$E outer_ns=$ONS"
echo "$E $ONS"
