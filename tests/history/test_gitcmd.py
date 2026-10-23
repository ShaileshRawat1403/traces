"""Step 1: hardened gitcmd (contract sections 9.1 and 13; HT17, HT20, HT21)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from traces.history import GitRunner, HistoryConfig, HistoryError, ingest
from traces.history.errors import CODES
from traces.history.gitcmd import ALLOWED_SUBCOMMANDS, validate_sha

from ._repo import SynthRepo
from .conftest import ref


def _basic(r: SynthRepo) -> str:
    r.write("a.py", "print(1)\n")
    return r.commit("one")


def test_allowed_subcommands_are_read_only() -> None:
    assert ALLOWED_SUBCOMMANDS == {"rev-parse", "cat-file", "log", "rev-list", "ls-tree", "diff-tree",
                                   "for-each-ref", "version"}


@pytest.mark.parametrize("sub", ["fetch", "clone", "checkout", "config", "gc", "remote", "submodule", "push", "!sh"])
def test_disallowed_subcommand_refused(synth: SynthRepo, sub: str) -> None:
    _basic(synth)
    with GitRunner(synth.path) as g:
        with pytest.raises(HistoryError) as ei:
            g.run(sub)
    assert ei.value.code == "E_GIT"


def test_error_codes_complete() -> None:
    assert {"E_REPO", "E_SHA", "E_SHALLOW", "E_MISSING_OBJECT", "E_GIT", "E_GIT_VERSION", "E_TIMEOUT", "E_LIMIT",
            "E_CONFIG", "E_COMPONENT_MAP", "E_CACHE", "E_REPLAY", "E_COLLISION", "E_SCHEMA", "E_PATH"} <= set(CODES)


@pytest.mark.parametrize("bad", ["HEAD", "main", "abc1234", "b1125d8", "", None, 12, "g" * 40, "A" * 40 + "\n",
                                 "--output=/tmp/x", "a" * 64])
def test_sha_must_be_full_hex(bad: object) -> None:
    with pytest.raises(HistoryError) as ei:
        validate_sha(bad)
    assert ei.value.code == "E_SHA"


def test_sha_must_name_a_commit(synth: SynthRepo) -> None:
    sha = _basic(synth)
    tree = synth.git("rev-parse", "HEAD^{tree}").decode().strip()
    blob = synth.git("rev-parse", "HEAD:a.py").decode().strip()
    with GitRunner(synth.path) as g:
        assert g.verify_commit(sha) == sha
        for bad in (tree, blob, "0" * 40, "1234567890" * 4):
            with pytest.raises(HistoryError) as ei:
                g.verify_commit(bad)
            assert ei.value.code == "E_SHA"


def test_not_a_repo(tmp_path: Path) -> None:
    with pytest.raises(HistoryError) as ei:
        GitRunner(tmp_path / "missing")
    assert ei.value.code == "E_REPO"
    (tmp_path / "plain").mkdir()
    with pytest.raises(HistoryError) as ei:
        GitRunner(tmp_path / "plain")
    assert ei.value.code == "E_REPO"


def test_shallow_clone_refused(synth: SynthRepo, tmp_path: Path) -> None:
    _basic(synth)
    synth.write("b.py", "x = 2\n")
    synth.commit("two")
    dst = tmp_path / "shallow"
    subprocess.run(["git", "clone", "-q", "--depth", "1", f"file://{synth.path}", str(dst)], check=True,
                   env={**synth.env(), "GIT_CONFIG_GLOBAL": "/dev/null"}, capture_output=True)
    with pytest.raises(HistoryError) as ei:
        GitRunner(dst)
    assert ei.value.code == "E_SHALLOW"


def test_grafts_refused(synth: SynthRepo) -> None:
    _basic(synth)
    (synth.path / ".git" / "info").mkdir(exist_ok=True)
    (synth.path / ".git" / "info" / "grafts").write_text("")
    with pytest.raises(HistoryError) as ei:
        GitRunner(synth.path)
    assert ei.value.code == "E_SHALLOW"


def test_repo_config_cannot_run_programs(synth: SynthRepo, tmp_path: Path) -> None:
    """Hooks, textconv, external diff, fsmonitor and pager settings in the target repo must never execute."""
    sentinel = tmp_path / "sentinel"
    script = tmp_path / "evil.sh"
    script.write_text(f"#!/bin/sh\ntouch {sentinel}\ncat \"$1\" 2>/dev/null\n")
    script.chmod(0o755)
    synth.write(".gitattributes", "*.py diff=evil\n")
    synth.write("a.py", "one\n")
    synth.commit("one")
    synth.write("a.py", "two\n")
    synth.mv("a.py", "b.py")
    synth.commit("two")
    for key, val in [("diff.evil.textconv", str(script)), ("diff.evil.command", str(script)),
                     ("diff.external", str(script)), ("core.fsmonitor", str(script)), ("core.pager", str(script)),
                     ("core.hooksPath", str(tmp_path)), ("core.sshCommand", str(script))]:
        synth.git("config", key, val)
    for hook in ("post-checkout", "pre-commit", "reference-transaction", "post-index-change"):
        (tmp_path / hook).write_text(f"#!/bin/sh\ntouch {sentinel}\n")
        (tmp_path / hook).chmod(0o755)
    log = ingest(ref(synth), HistoryConfig())
    assert len(log.commits) == 2
    assert not sentinel.exists()


def test_env_isolated_from_user_config(synth: SynthRepo, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _basic(synth)
    gc = tmp_path / "gitconfig"
    gc.write_text("[diff]\n\trenames = false\n[log]\n\tshowSignature = true\n[core]\n\tquotepath = true\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(gc))
    monkeypatch.setenv("GIT_DIR", "/nonexistent")
    monkeypatch.setenv("GIT_EXEC_PATH_EXTRA", "x")
    with GitRunner(synth.path) as g:
        env = g.env()
        assert env["GIT_CONFIG_GLOBAL"] == "/dev/null"
        assert env["GIT_CONFIG_NOSYSTEM"] == "1"
        assert env.get("GIT_NO_LAZY_FETCH") == "1"
        assert "GIT_DIR" not in env and "GIT_EXEC_PATH_EXTRA" not in env
        assert env["HOME"] != os.environ.get("HOME")


def test_git_error_redacts_paths(synth: SynthRepo) -> None:
    _basic(synth)
    with GitRunner(synth.path) as g:
        with pytest.raises(HistoryError) as ei:
            g.run("cat-file", ["-p", "0" * 40])
    assert ei.value.code == "E_GIT"
    assert str(synth.path) not in ei.value.detail


def test_output_limit(synth: SynthRepo) -> None:
    sha = _basic(synth)
    with GitRunner(synth.path) as g:
        g.max_output_bytes = 10
        with pytest.raises(HistoryError) as ei:
            g.run("cat-file", ["-p", sha])
    assert ei.value.code == "E_LIMIT"
