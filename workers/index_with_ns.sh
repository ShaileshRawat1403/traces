#!/usr/bin/env bash
# Port of research/task002/pipeline/index_with_ns.sh. Run the CodeGraph indexer INSIDE the wrapper and log the net namespace of the indexer process and every descendant.
# Usage: index_with_ns.sh <checkout copy> <netprobe.log> <index.log>
SRC="$1"; LOG="$2"; ILOG="$3"; WNS=$(readlink /proc/$$/ns/net)
exec 3>>"$LOG"; say(){ echo "$*" >&3; }
cd "$SRC" || exit 1
say "=== INDEXER $(date -Iseconds) in $SRC ; wrapper netns $WNS ; \$ codegraph init -y ."
( exec codegraph init -y . ) >"$ILOG" 2>&1 &
ROOT=$!
declare -A SEEN
desc(){ local p=$1; echo $p; for c in $(cat /proc/$p/task/*/children 2>/dev/null); do desc $c; done; }
while kill -0 $ROOT 2>/dev/null; do
  for p in $(desc $ROOT); do
    if [ -z "${SEEN[$p]}" ]; then ns=$(readlink /proc/$p/ns/net 2>/dev/null); cmd=$(tr '\0' ' ' </proc/$p/cmdline 2>/dev/null | cut -c1-140); [ -n "$ns" ] && SEEN[$p]="$ns|$cmd"; fi
  done
  sleep 0.02
done
wait $ROOT; RC=$?
BAD=0; for p in "${!SEEN[@]}"; do v=${SEEN[$p]}; say "INDEXER_PROC pid=$p netns=${v%%|*} cmd=${v#*|}"; [ "${v%%|*}" = "$WNS" ] || BAD=1; done
N=${#SEEN[@]}
S=pass; [ $BAD -eq 0 ] && [ $N -ge 1 ] && [ $RC -eq 0 ] || S=fail
say "INDEXER_SUMMARY d_indexer=$S processes_seen=$N exit=$RC wrapper_ns=$WNS"
[ $S = pass ]
