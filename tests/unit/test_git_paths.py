"""F-1: every place that lists tracked paths parses `git ls-tree -z` (NUL-terminated, raw bytes), so non-ASCII and
otherwise quoted names keep their real spelling and a repository with one such file still indexes."""
from __future__ import annotations

import subprocess
from pathlib import Path

from tests.unit.test_ingest import g
from traces.core.common import Blobs
from traces.evidence.components import tree_files
from traces.ingest.fetch import FetchLimits, _check_tree

NAMES = ["app/café.py", "docs/日本語.md", 'q"uote.py', "sp ace/\u00e9t\u00e9.ts", "-rf.py", "back\\slash.py"]


def _repo(tmp_path: Path) -> tuple[Path, str]:
    r = tmp_path / "r"
    r.mkdir()
    g(r, "init", "-q", "-b", "main")
    for n in NAMES:
        p = r / n
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"# {n}\n")
    g(r, "add", "-A")
    g(r, "commit", "-q", "-m", "names")
    return r, g(r, "rev-parse", "HEAD").strip()


def test_blobs_reads_raw_names(tmp_path):
    r, sha = _repo(tmp_path)
    quoted = subprocess.run(["git", "-C", str(r), "ls-tree", "-r", "--name-only", sha], capture_output=True, text=True).stdout
    assert '"app/caf\\303\\251.py"' in quoted  # what the old parser saw
    b = Blobs(str(r), sha)
    assert set(b.tree) == set(NAMES)
    for n in NAMES:
        assert b.exists(n) and b.text(n) == f"# {n}\n"


def test_check_tree_counts_every_file(tmp_path):
    r, sha = _repo(tmp_path)
    assert _check_tree(r, sha, "octo/r", FetchLimits())["files"] == len(NAMES)


def test_components_list_raw_names(tmp_path):
    r, sha = _repo(tmp_path)
    assert set(tree_files(r, sha)) == set(NAMES)
