"""No network, no writes to the target (contract section 9.1, HT21, HT22)."""

from __future__ import annotations

import ast
import os
import shutil
import socket
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from traces.history import HistoryConfig, HistoryError, churn, cochange, commit_facts, hotspots, ingest, lifecycle

from ._repo import SynthRepo, lines
from .conftest import ref

PKG = Path(__file__).resolve().parents[2] / "backend" / "traces" / "history"
FORBIDDEN = {"socket", "ssl", "urllib", "http", "requests", "httpx", "aiohttp", "ftplib", "smtplib", "telnetlib",
             "xmlrpc", "websocket", "websockets", "paramiko", "github", "asyncio"}


def test_no_network_imports_and_one_subprocess_site() -> None:
    files = sorted(PKG.glob("*.py"))
    assert files
    for f in files:
        tree = ast.parse(f.read_text(), str(f))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = [node.module]
            for n in names:
                assert n.split(".")[0] not in FORBIDDEN, f"{f.name} imports {n}"
                if n == "subprocess":
                    assert f.name == "gitcmd.py", f"{f.name} imports subprocess; only gitcmd may run git"


def _small(r: SynthRepo) -> None:
    for i in range(3):
        r.write("a.py", lines(5 + i))
        r.write("b.py", lines(3 + i))
        r.commit(f"c{i}")


def _all(log) -> int:  # type: ignore[no-untyped-def]
    n = 0
    for fn in (commit_facts, lifecycle, churn, hotspots, cochange):
        n += len(fn(log).records)
    return n


def test_full_pipeline_with_sockets_blocked(synth: SynthRepo, monkeypatch: pytest.MonkeyPatch) -> None:
    _small(synth)

    def boom(*a, **k):  # type: ignore[no-untyped-def]
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket.socket, "connect", boom)
    monkeypatch.setattr(socket, "create_connection", boom)
    monkeypatch.setattr(socket, "getaddrinfo", boom)
    assert _all(ingest(ref(synth), HistoryConfig())) > 0


def test_partial_clone_missing_object_no_fetch(synth: SynthRepo, tmp_path: Path) -> None:
    synth.write("a.py", lines(40))
    synth.commit("one")
    synth.write("a.py", lines(41))
    synth.mv("a.py", "b.py")
    synth.commit("two")
    synth.git("config", "uploadpack.allowFilter", "true")
    dst = tmp_path / "partial"
    env = {**synth.env(), "GIT_CONFIG_GLOBAL": "/dev/null"}
    subprocess.run(["git", "clone", "-q", "--bare", "--filter=blob:none", f"file://{synth.path}", str(dst)],
                   check=True, env=env, capture_output=True)

    def objects() -> str:
        return subprocess.run(["git", "--git-dir", str(dst), "count-objects", "-v"], env=env, capture_output=True,
                              check=True).stdout.decode()

    before = objects()
    with pytest.raises(HistoryError) as ei:
        ingest(ref(SynthRepoView(dst), synth.head()), HistoryConfig())
    assert ei.value.code == "E_MISSING_OBJECT"
    assert objects() == before


class SynthRepoView:
    """Minimal stand-in so conftest.ref() works for a bare clone path."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def head(self) -> str:  # pragma: no cover - sha is always passed explicitly
        raise NotImplementedError


def test_runs_inside_network_namespace(synth: SynthRepo) -> None:
    unshare = shutil.which("unshare")
    if unshare is None:
        pytest.skip("unshare not available")
    probe = subprocess.run([unshare, "-rn", "true"], capture_output=True)
    if probe.returncode != 0:
        pytest.skip(f"unprivileged network namespace not permitted here: {probe.stderr.decode().strip()[:120]}")
    _small(synth)
    code = textwrap.dedent(f"""
        import socket, sys
        from pathlib import Path
        from traces.history import HistoryConfig, RepoRef, cochange, churn, commit_facts, ingest, lifecycle
        try:
            socket.create_connection(("1.1.1.1", 443), timeout=2)
            sys.exit("network reachable inside the namespace; test is not meaningful")
        except OSError:
            pass
        log = ingest(RepoRef(Path({str(synth.path)!r}), "synthetic/repo", {synth.head()!r}), HistoryConfig())
        n = sum(len(f(log).records) for f in (commit_facts, lifecycle, churn, cochange))
        print(n)
    """)
    env = {**os.environ, "PYTHONPATH": str(PKG.parents[1])}
    p = subprocess.run([unshare, "-rn", sys.executable, "-c", code], capture_output=True, env=env, timeout=120)
    assert p.returncode == 0, p.stderr.decode()[-500:]
    assert int(p.stdout.decode().strip()) > 0
