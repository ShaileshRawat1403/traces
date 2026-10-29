#!/usr/bin/env bash
# Per-run isolation probe, CT15 (a) to (d). Port of research/task002/pipeline/probe_inside.sh. Must run INSIDE workers/sandbox.sh, as the first thing the wrapper runs.
# Usage: probe_inside.sh <netprobe.log> ; env OUTER_NS and CONTROL_E (pass|fail) are set by the caller outside the wrapper.
LOG="$1"; WD="$(cd "$(dirname "$0")" && pwd)"
NODE24=$TRACES_TOOLCHAIN_DIR/node_modules/@colbymchenry/codegraph-linux-x64/node
exec 3>>"$LOG"
say(){ echo "$*" >&3; }
WNS=$(readlink /proc/$$/ns/net)
say "=== INSIDE WRAPPER $(date -Iseconds) wrapper shell pid $$ netns $WNS ; HOME=$HOME ; CODEGRAPH_TELEMETRY=$CODEGRAPH_TELEMETRY DO_NOT_TRACK=$DO_NOT_TRACK CODEGRAPH_NO_DOWNLOAD=$CODEGRAPH_NO_DOWNLOAD"
# (a) ip link: only lo, DOWN
IPL=$(sh -c 'echo "[sh child pid $$ netns $(readlink /proc/self/ns/net)]"; ip -o link' 2>&1); say "\$ sh -c 'ip -o link'"; say "$IPL"
A=fail; IFS=$'\n' read -r -d '' -a LINKS < <(echo "$IPL" | grep -E '^[0-9]+:' ; printf '\0')
if [ "${#LINKS[@]}" -eq 1 ] && echo "${LINKS[0]}" | grep -q '^1: lo:' && echo "${LINKS[0]}" | grep -q 'state DOWN'; then A=pass; fi
# (b) sh -c curl
B1=$(sh -c 'curl -sS -m 8 -o /dev/null https://registry.npmjs.org/ 2>&1; echo "exit=$?"'); say "\$ sh -c 'curl -sS -m 8 -o /dev/null https://registry.npmjs.org/'"; say "$B1"
B2=$(sh -c 'curl -sS -m 8 -o /dev/null https://1.1.1.1/ 2>&1; echo "exit=$?"'); say "\$ sh -c 'curl -sS -m 8 -o /dev/null https://1.1.1.1/'"; say "$B2"
B=fail; echo "$B1" | grep -q '^exit=6$' && echo "$B2" | grep -q '^exit=7$' && B=pass
# (c) bundled Node 24 child_process + https + net
say "\$ $NODE24 $WD/netprobe_child.js"
C_OUT=$("$NODE24" "$WD/netprobe_child.js" 2>&1); say "$C_OUT"
C=fail
if echo "$C_OUT" | grep -q 'node v24.16.0' && [ "$(echo "$C_OUT" | grep -c 'result=ERROR')" -eq 2 ] && ! echo "$C_OUT" | grep -q 'CONNECTED' \
   && echo "$C_OUT" | grep -q '^\[exit=6\]' && echo "$C_OUT" | grep -q '^\[exit=7\]'; then C=pass; fi
# (d) namespace ids: wrapper shell, every probe child, all equal and different from outer
NSLIST=$( { echo "$WNS"; echo "$IPL" | grep -o 'netns net:\[[0-9]*\]' | cut -d' ' -f2; echo "$C_OUT" | grep -o 'netns net:\[[0-9]*\]' | cut -d' ' -f2; } | sort | uniq -c)
say "namespace ids seen (count id): $(echo $NSLIST)"
D=fail; NDIST=$(echo "$NSLIST" | wc -l)
if [ "$NDIST" -eq 1 ] && echo "$NSLIST" | grep -qF "$WNS" && [ -n "$OUTER_NS" ] && [ "$WNS" != "$OUTER_NS" ]; then D=pass; fi
say "PROBE_SUMMARY a=$A b=$B c=$C d=$D e=${CONTROL_E:-unknown} wrapper_ns=$WNS outer_ns=${OUTER_NS:-unknown}"
[ "$A$B$C$D" = passpasspasspass ] && [ "$CONTROL_E" = pass ]
