# tests/perf

`bench.py` measures a local baseline: `IndexRun` wall time per phase for fsft@b1125d8 (from the cached full-history clone) and any extra local clones, then p50/p95 latency of the key read endpoints on a scratch `traces serve`. No network. Not part of CI: hosted runners vary too much for latency gates. Results and the last run's numbers are in [docs/acceptance/PERF.md](../../docs/acceptance/PERF.md).

    TRACES_ISOLATION=unshare uv run --frozen python tests/perf/bench.py .traces-data/acceptance/perf \
      --repo pallets/itsdangerous=/path/to/itsdangerous@672971d66a2ef9f85151e53283113f33d642dabd
