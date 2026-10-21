#!/usr/bin/env bash
# Task 002 steps 4 to 10 driver. Outside: snapshots + CT15(e) control. Inside ONE offline.sh invocation: probe (a)-(d) first, then inside_run.py.
set -u
T=/workspace/traces-research/task002; R=/workspace/traces-research
RID="t002-$(date +%Y%m%dT%H%M)-${1:-1}"; RUN=$T/work/$RID; mkdir -p "$RUN"
export GIT_OPTIONAL_LOCKS=0
snap(){ # $1 = before|after
  local o=$RUN/snapshot_$1.txt
  { echo "# $1 $(date -Iseconds)"
    echo "## src/fsft"; git -C $T/src/fsft --no-optional-locks status --porcelain; git -C $T/src/fsft rev-parse HEAD
    for f in $T/src/fsft/.codegraph/*; do echo "$(sha256sum "$f" | cut -c1-64) $(stat -c '%y %s' "$f") $f"; done
    echo "git index mtime $(stat -c '%y' $T/src/fsft/.git/index)"
    echo "## lead _src clones"
    for g in $(find $R/_src -maxdepth 3 -name .git -type d 2>/dev/null); do d=${g%/.git}; echo "$d HEAD $(git -C $d rev-parse HEAD) index mtime $(stat -c '%y' $g/index 2>/dev/null) status_lines $(git -C $d --no-optional-locks status --porcelain | wc -l)"; done
    echo "## spec"; sha256sum $T/spec/*.md $T/spec/*.json
    echo "## checker"; sha256sum $T/checker/* 2>/dev/null
    echo "## offline.sh"; sha256sum $T/tools/offline.sh; stat -c '%y' $T/tools/offline.sh
  } >"$o" 2>&1
  find $T $R/_src -path $T/work -prune -o -path '*/node_modules' -prune -o -path $T/tools/uv-cache -prune -o -path $T/tools/python -prune -o -type f -printf '%T@ %s %p\n' 2>/dev/null | sort -k3 >"$RUN/files_$1.txt"
}
snap before
read CE ONS < <(bash $T/pipeline/control_outside.sh "$RUN/netprobe.log")
echo "control e=$CE outer_ns=$ONS"
export PYTHONDONTWRITEBYTECODE=1
# step 8 timing and peak RSS: _tests/measure.py wraps the whole wrapper invocation (probe, 2 index runs, adapter x3, CTs, checker, validation x2)
python3 $R/_tests/measure.py "$T/tools/offline.sh env OUTER_NS='$ONS' CONTROL_E='$CE' PYTHONDONTWRITEBYTECODE=1 bash -c \"bash $T/pipeline/probe_inside.sh '$RUN/netprobe.log' && $T/tools/py314/bin/python $T/pipeline/inside_run.py '$RUN'\"" >"$RUN/inside_stdout.txt" 2>&1
echo "inside exit=$?"; grep MEASURE "$RUN/inside_stdout.txt"
snap after
# CT evaluation (read-only) under the wrapper, after the after-snapshot
$T/tools/offline.sh env PYTHONDONTWRITEBYTECODE=1 $T/tools/py314/bin/python $T/tests/ct_evaluate.py "$RUN" >"$RUN/ct_stdout.txt" 2>&1; cat "$RUN/ct_stdout.txt"
echo "$RUN"
