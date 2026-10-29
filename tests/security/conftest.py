"""Shared fixtures for the safe-failure and abuse suite (charter section 7).

Everything here is local: the target repository is a tiny Git repository built in a temp dir with hostile
contents (symlinks out of the tree, odd file names, a .gitmodules pointing at file://), indexed by the real
index worker (traces.evidence.index.IndexRun) through a file path, never through the network.
"""
from __future__ import annotations

import ipaddress
import os
import shutil
import socket
import subprocess
import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from traces.ingest.urls import RepoRef

GIT_ENV = {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid", "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z",
           "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z", "PATH": os.environ.get("PATH", "/usr/bin")}
REAL_GIT = shutil.which("git") or "/usr/bin/git"

# Odd but legal paths committed into the hostile fixture. Values are file contents.
ODD_FILES = {
    "app/main.py": "from app.util import helper\n\n\ndef run():\n    return helper(1)\n",
    "app/util.py": "def helper(x):\n    return x + 1\n",
    "has space.py": "SPACE = 1\n",
    "-rf.py": "DASH = 1\n",
    "a:b.py": "COLON = 1\n",
    "..hidden.py": "DOTS = 1\n",
    "web/index.ts": "import { add } from './lib'\n\nexport const three = add(1, 2)\n",
    "web/lib.ts": "export function add(a: number, b: number): number {\n  return a + b\n}\n",
    ".gitmodules": '[submodule "evil"]\n\tpath = evil\n\turl = file:///etc\n',
}
# Non-ASCII names are kept out of the main fixture: they make the adapter fail closed (finding F-1, see
# test_non_ascii_path_indexes). The main fixture must index so the other checks run.
UNICODE_FILES = {"\u00fcn\u00efcode.py": "UNI = 1\n"}
# name -> link target. All point outside the repository.
SYMLINKS = {"evil_link": "/etc/passwd", "up_link": "../../../../../../etc/passwd", "dirlink": "/etc", "app/up.py": "../../../../etc/hostname"}


def git(repo: Path, *args: str) -> str:
    return subprocess.run([REAL_GIT, "-C", str(repo), *args], env=GIT_ENV, check=True, capture_output=True, text=True).stdout


def build_hostile_repo(root: Path, *, extra: dict[str, str] | None = None) -> tuple[Path, str]:
    r = root / "hostile"
    r.mkdir(parents=True)
    for name, text in {**ODD_FILES, **(extra or {})}.items():
        p = r / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    for name, target in SYMLINKS.items():
        p = r / name
        p.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(target, p)
    git(r, "init", "-q", "-b", "main")
    git(r, "add", "-A")
    git(r, "commit", "-q", "-m", "hostile fixture")
    return r, git(r, "rev-parse", "HEAD").strip()


@dataclass(frozen=True)
class LocalRef(RepoRef):
    """A RepoRef whose clone URL is a local path (same pattern as scripts/e2e_seed.py). Only tests use it."""
    path: str = ""

    @property
    def clone_url(self) -> str:
        return self.path


def toolchain_ready() -> tuple[bool, str]:
    from traces.core.config import get_settings

    s = get_settings()
    if not s.codegraph_bin.exists():
        return False, f"CodeGraph toolchain missing in {s.toolchain_dir} (cd toolchain && npm ci --ignore-scripts)"
    if subprocess.run(["unshare", "-rn", "true"], capture_output=True).returncode != 0:
        return False, "unshare -rn is not available (user namespaces off)"
    return True, ""


# ------------------------------------------------------------------------------------------------ outbound monitor
@dataclass
class Outbound:
    """Records every socket connect and every process spawn in this Python process (sys.addaudithook)."""
    connects: list[tuple[int, Any]] = field(default_factory=list)
    spawns: list[list[str]] = field(default_factory=list)

    def non_local_connects(self) -> list[Any]:
        bad = []
        for fam, addr in self.connects:
            if fam == socket.AF_UNIX:
                continue
            host = addr[0] if isinstance(addr, tuple) else addr
            try:
                if ipaddress.ip_address(host).is_loopback:
                    continue
            except ValueError:
                pass
            bad.append(addr)
        return bad


_active: list[Outbound] = []
_lock = threading.Lock()
_installed = False


def _hook(event: str, args: tuple[Any, ...]) -> None:
    if not _active:
        return
    if event == "socket.connect":
        sock, addr = args[0], args[1]
        with _lock:
            for o in _active:
                o.connects.append((getattr(sock, "family", -1), addr))
    elif event == "subprocess.Popen":
        argv = [os.fsdecode(a) for a in (args[1] or [])] if isinstance(args[1], (list, tuple)) else [str(args[1])]
        with _lock:
            for o in _active:
                o.spawns.append(argv)


@contextmanager
def monitor_outbound() -> Iterator[Outbound]:
    global _installed
    if not _installed:
        sys.addaudithook(_hook)
        _installed = True
    o = Outbound()
    _active.append(o)
    try:
        yield o
    finally:
        _active.remove(o)


# ------------------------------------------------------------------------------------------------ indexed hostile snapshot
@dataclass
class Indexed:
    root: Path
    src: Path
    sha: str
    ref: LocalRef
    result: dict[str, Any]
    outbound: Outbound
    data_dir: Path
    cache_dir: Path

    @property
    def repo_id(self) -> str:
        return self.ref.cache_key


def index_local(root: Path, data: Path, cache: Path, *, extra: dict[str, str] | None = None, name: str = "hostile",
                job: str = "sec") -> Indexed:
    """Build the hostile repo under root and run the real index worker on it (TRACES_DATA_DIR/CACHE_DIR must point at data/cache)."""
    from traces.core.config import get_settings
    from traces.evidence.index import IndexRun
    from traces.evidence.store import Store, create_job

    src, sha = build_hostile_repo(root / "src", extra=extra)
    ref = LocalRef("github.com", "secfixture", name, path=str(src))
    s = get_settings()
    st = Store(s.db_path)
    st.upsert_repo(ref.cache_key, ref.host, ref.owner, ref.name, f"https://github.com/{ref.slug}")
    st.ensure_snapshot(ref.cache_key, sha)
    create_job(st, job, ref.cache_key, "index", f"{ref.cache_key}@{sha}")
    with monitor_outbound() as ob:
        res = IndexRun(st, job, ref, sha, s).execute()
    st.close()
    return Indexed(root, src, sha, ref, res, ob, data, cache)


@pytest.fixture(scope="session")
def indexed_hostile(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Indexed]:
    ok, why = toolchain_ready()
    if not ok:
        pytest.skip(why)
    root = tmp_path_factory.mktemp("sec")
    data, cache = root / "data", root / "cache"
    old = {k: os.environ.get(k) for k in ("TRACES_DATA_DIR", "TRACES_CACHE_DIR", "TRACES_ISOLATION")}
    os.environ.update(TRACES_DATA_DIR=str(data), TRACES_CACHE_DIR=str(cache), TRACES_ISOLATION="unshare")
    try:
        yield index_local(root, data, cache)
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


@pytest.fixture()
def hostile_client(indexed_hostile: Indexed, monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    from fastapi.testclient import TestClient

    from traces.api.app import app, get_store
    from traces.evidence.store import Store

    monkeypatch.setenv("TRACES_DATA_DIR", str(indexed_hostile.data_dir))
    monkeypatch.setenv("TRACES_CACHE_DIR", str(indexed_hostile.cache_dir))
    st = Store(indexed_hostile.data_dir / "traces.sqlite3")
    app.dependency_overrides[get_store] = lambda: st
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        st.close()


# ------------------------------------------------------------------------------------------------ fake git on PATH
@pytest.fixture()
def fake_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Install a `git` shim first on PATH. `behave(clone=..., ls_remote=...)` sets bash snippets for those subcommands;
    everything else execs the real git. Each call appends argv and a list of env var NAMES (never values) to calls.log."""
    bindir = tmp_path / "fakebin"
    bindir.mkdir()
    log = tmp_path / "calls.log"

    def behave(clone: str = "", ls_remote: str = "") -> Path:
        script = f"""#!/usr/bin/env bash
{{ printf 'ARGV'; printf ' %q' "$@"; printf '\\n'; printf 'ENV %s\\n' "$(env | cut -d= -f1 | sort | tr '\\n' ' ')"; }} >> {log}
for a in "$@"; do
  case "$a" in
    clone) {clone or 'exec ' + REAL_GIT + ' "$@"'} ;;
    ls-remote) {ls_remote or 'exec ' + REAL_GIT + ' "$@"'} ;;
  esac
done
exec {REAL_GIT} "$@"
"""
        g = bindir / "git"
        g.write_text(script)
        g.chmod(0o755)
        monkeypatch.setenv("PATH", f"{bindir}:{os.environ['PATH']}")
        return log

    return behave
