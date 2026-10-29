"""Index one local repository into TRACES_DATA_DIR so Playwright can drive a real snapshot.

Two seeds, both without network (the repository is a file path, not a GitHub fetch):
  synthetic (default)  a tiny 4-file repo, octo/synth; fast local runs. History may fail on an old git;
                       static evidence is still stored.
  fsft                 the pinned target fastapi/full-stack-fastapi-template@b1125d8, indexed from the
                       cached full-history clone (CI `target` job, or `make target`). Same repo id and SHA
                       as a real ingest, so the browser tests run against the real snapshot.

usage: e2e_seed.py DATA_DIR [--seed synthetic|fsft] [--fsft-repo PATH]
       (--seed also reads TRACES_E2E_SEED; --fsft-repo also reads TRACES_E2E_FSFT_REPO)
"""

from __future__ import annotations

import argparse
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

FSFT_SHA = "b1125d8839482cb7bbae603ddc6d0081bf87532e"
FSFT_CACHE = Path(".cache/targets/github.com__fastapi__full-stack-fastapi-template") / FSFT_SHA / "source"


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


def fsft_repo(path: Path) -> tuple[Path, str]:
    """The cached pinned clone must be a full-history clone that contains b1125d8; fail loudly otherwise."""
    if not (path / ".git").exists():
        raise SystemExit(f"fsft clone not found at {path} (run the CI target job or `make target`)")
    if git(path, "rev-parse", "--is-shallow-repository").strip() != "false":
        raise SystemExit(f"fsft clone at {path} is shallow; history needs the full clone")
    git(path, "cat-file", "-e", f"{FSFT_SHA}^{{commit}}")
    return path, FSFT_SHA


def main() -> int:
    ap = argparse.ArgumentParser(description="seed one snapshot for the Playwright run")
    ap.add_argument("data_dir")
    ap.add_argument("--seed", choices=("synthetic", "fsft"), default=os.environ.get("TRACES_E2E_SEED", "synthetic"))
    ap.add_argument("--fsft-repo", default=os.environ.get("TRACES_E2E_FSFT_REPO", str(FSFT_CACHE)))
    a = ap.parse_args()
    data = Path(a.data_dir).resolve()
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

    if a.seed == "fsft":
        src, sha = fsft_repo(Path(a.fsft_repo).resolve())
        ref = LocalRef("github.com", "fastapi", "full-stack-fastapi-template", path=str(src))
    else:
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
