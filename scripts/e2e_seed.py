"""Index one tiny local repository into TRACES_DATA_DIR so Playwright can drive a real snapshot.

No network. The repository is a file path, not a GitHub fetch. History may fail on an old git;
static evidence is still stored.
"""
from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ENV = {
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.invalid",
    "PATH": os.environ.get("PATH", "/usr/bin"),
}


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], env=ENV, check=True, capture_output=True, text=True).stdout


def build_repo(root: Path) -> tuple[Path, str]:
    r = root / "synth"
    r.mkdir(parents=True)
    (r / "app").mkdir()
    (r / "web").mkdir()
    (r / "app" / "util.py").write_text("def helper(x):\n    return x + 1\n")
    (r / "app" / "main.py").write_text("from app.util import helper\n\n\ndef run():\n    return helper(1)\n")
    (r / "web" / "lib.ts").write_text("export function add(a: number, b: number): number {\n  return a + b\n}\n")
    (r / "web" / "index.ts").write_text("import { add } from './lib'\n\nexport const three = add(1, 2)\n")
    git(r, "init", "-q", "-b", "main")
    git(r, "add", "-A")
    git(r, "commit", "-q", "-m", "init")
    return r, git(r, "rev-parse", "HEAD").strip()


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: e2e_seed.py DATA_DIR", file=sys.stderr)
        return 2
    data = Path(sys.argv[1]).resolve()
    data.mkdir(parents=True, exist_ok=True)
    os.environ["TRACES_DATA_DIR"] = str(data)
    os.environ.setdefault("TRACES_ISOLATION", "unshare")

    from traces.core.config import get_settings
    from traces.evidence.index import IndexRun
    from traces.evidence.store import Store, create_job
    from traces.ingest.urls import RepoRef

    @dataclass(frozen=True)
    class LocalRef(RepoRef):
        path: str = ""

        @property
        def clone_url(self) -> str:
            return self.path

    src, sha = build_repo(data / "src")
    ref = LocalRef("github.com", "octo", "synth", path=str(src))
    s = get_settings()
    if not s.codegraph_bin.exists():
        print(f"toolchain missing in {s.toolchain_dir}", file=sys.stderr)
        return 1
    st = Store(s.db_path)
    st.upsert_repo(ref.cache_key, ref.host, ref.owner, ref.name, f"https://github.com/{ref.slug}")
    st.ensure_snapshot(ref.cache_key, sha)
    create_job(st, "e2e", ref.cache_key, "index", f"{ref.cache_key}@{sha}")
    res = IndexRun(st, "e2e", ref, sha, s).execute()
    st.close()
    if res.get("error"):
        print(res["error"], file=sys.stderr)
        return 1
    print(f"{ref.cache_key} {sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
