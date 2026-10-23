"""INGEST cleanup (D-021, acceptance audit): a capped clone never leaves `source.partial` behind, even when git's helper
processes keep writing after the cap fires, and the clone size is checked once more after git exits. A `git` shim on
PATH stands in for a slow or oversized clone; no network is used."""
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from tests.unit.test_ingest import LocalRef
from traces.ingest.errors import IngestError
from traces.ingest.fetch import FetchLimits, ensure_pinned_checkout

SHA = "1" * 40

SLOW = """#!/bin/bash
# fake `git clone` that behaves like a slow fetch: a helper (think git-remote-https + index-pack) keeps writing pack
# temp files, recreating its directory, until it is killed; killing only the parent leaves it running
dest="${@: -1}"
( for i in $(seq 1 200); do mkdir -p "$dest/objects/pack"; head -c 50000 /dev/urandom > "$dest/objects/pack/tmp_pack_$i"; sleep 0.1; done ) &
echo "$! $$" >> "$(dirname "$0")/../shim.pids"
sleep 600 &
echo "$!" >> "$(dirname "$0")/../shim.pids"
wait
"""

BIG_AND_FAST = """#!/bin/bash
# fake `git clone` that writes 3 MB and exits 0 before the first size poll
dest="${@: -1}"
mkdir -p "$dest"
head -c 3000000 /dev/urandom > "$dest/pack.bin"
exit 0
"""


def _shim(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str) -> Path:
    b = tmp_path / "bin"
    b.mkdir()
    (b / "git").write_text(body)
    (b / "git").chmod(0o755)
    monkeypatch.setenv("PATH", f"{b}:{os.environ['PATH']}")
    pids = tmp_path / "shim.pids"
    return pids


def _alive(pid: int) -> bool:
    """True if `pid` is a live process (a zombie that is only waiting to be reaped does not count)."""
    try:
        with open(f"/proc/{pid}/stat") as f:
            return f.read().rsplit(")", 1)[1].split()[0] != "Z"
    except (FileNotFoundError, ProcessLookupError, IndexError):
        return False


def _assert_no_survivors(pids_file: Path) -> None:
    pids = [int(x) for x in pids_file.read_text().split()] if pids_file.exists() else []
    assert pids, "the shim did not record its processes"
    deadline = time.monotonic() + 3
    while any(_alive(p) for p in pids) and time.monotonic() < deadline:
        time.sleep(0.05)
    alive = [p for p in pids if _alive(p)]
    for p in alive:  # do not leave them behind even when the assertion fails
        os.kill(p, 9)
    assert not alive, f"processes from the git shim survived the timeout: {alive}"


def _ref() -> LocalRef:
    return LocalRef("github.com", "octo", "slow", "https://github.com/octo/slow.git")


def test_timeout_leaves_no_partial_clone(tmp_path, monkeypatch):
    pids = _shim(tmp_path, monkeypatch, SLOW)
    dest = tmp_path / "c" / "source"
    t0 = time.monotonic()
    with pytest.raises(IngestError) as e:
        ensure_pinned_checkout(_ref(), SHA, dest, FetchLimits(clone_timeout_s=1))
    assert e.value.code == "fetch_timeout" and time.monotonic() - t0 < 10
    time.sleep(1.0)  # a surviving helper would recreate files here
    assert not (dest.parent / "source.partial").exists(), sorted(p.name for p in dest.parent.iterdir())
    assert not (dest.parent / "source.partial.stderr").exists() and not dest.exists()
    _assert_no_survivors(pids)  # git, its helper loop and its long sleep: the whole process group is gone


def test_interrupt_during_clone_kills_the_group(tmp_path, monkeypatch):
    pids = _shim(tmp_path, monkeypatch, SLOW)
    import traces.ingest.fetch as fetch

    real_sleep, calls = time.sleep, []

    def interrupt_after_two_polls(s: float) -> None:
        calls.append(s)
        if len(calls) > 2:
            raise KeyboardInterrupt
        real_sleep(s)

    monkeypatch.setattr(fetch.time, "sleep", interrupt_after_two_polls)
    dest = tmp_path / "c" / "source"
    with pytest.raises(KeyboardInterrupt):
        ensure_pinned_checkout(_ref(), SHA, dest, FetchLimits(clone_timeout_s=600))
    monkeypatch.setattr(fetch.time, "sleep", real_sleep)
    _assert_no_survivors(pids)
    assert not (dest.parent / "source.partial").exists()


def test_git_helper_timeout_kills_the_group(tmp_path, monkeypatch):
    """Every other git call in the fetch path (`git()`: cat-file, ls-tree, checkout) is group-killed on timeout too."""
    import subprocess

    pids = _shim(tmp_path, monkeypatch, SLOW)
    import traces.ingest.fetch as fetch

    t0 = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        fetch.git("status", cwd=tmp_path, timeout=1)
    assert time.monotonic() - t0 < 10
    _assert_no_survivors(pids)


def test_size_is_checked_after_git_exits(tmp_path, monkeypatch):
    _shim(tmp_path, monkeypatch, BIG_AND_FAST)
    dest = tmp_path / "c" / "source"
    with pytest.raises(IngestError) as e:
        ensure_pinned_checkout(_ref(), SHA, dest, FetchLimits(max_clone_bytes=1024 * 1024))
    assert e.value.code == "too_large" and e.value.detail == {"max_clone_bytes": 1024 * 1024}
    assert list(dest.parent.iterdir()) == []


def test_interrupt_leaves_no_partial_clone(tmp_path, monkeypatch):
    _shim(tmp_path, monkeypatch, BIG_AND_FAST)
    import traces.ingest.fetch as fetch

    def boom(*a, **k):
        raise KeyboardInterrupt

    monkeypatch.setattr(fetch, "_check_tree", boom)
    monkeypatch.setattr(fetch, "git", lambda *a, **k: "")
    dest = tmp_path / "c" / "source"
    with pytest.raises(KeyboardInterrupt):
        ensure_pinned_checkout(_ref(), SHA, dest, FetchLimits())
    assert list(dest.parent.iterdir()) == []
