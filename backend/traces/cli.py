"""`traces` command line: serve the API, run the baseline pipeline, export or migrate evidence."""
from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="traces")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve", help="run the read-only API (default 127.0.0.1:8000)")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    b = sub.add_parser("baseline", help="run the Task 002 baseline verification pipeline")
    b.add_argument("--run-id")
    i = sub.add_parser("import-run", help="migrate a pipeline run to traces-evidence/0.4 and load it into the store")
    i.add_argument("run_dir")
    o = sub.add_parser("openapi", help="print the OpenAPI document")
    o.add_argument("--out")
    a = ap.parse_args(argv)
    if a.cmd == "serve":
        import uvicorn

        uvicorn.run("traces.api.app:app", host=a.host, port=a.port)
    elif a.cmd == "baseline":
        from traces.evidence.pipeline import run_baseline

        print(run_baseline(a.run_id))
    elif a.cmd == "import-run":
        from pathlib import Path

        from traces.evidence.store import import_pipeline_run

        print(import_pipeline_run(Path(a.run_dir)))
    elif a.cmd == "openapi":
        import json

        from traces.api.app import app

        text = json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"
        if a.out:
            open(a.out, "w").write(text)
        else:
            sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
