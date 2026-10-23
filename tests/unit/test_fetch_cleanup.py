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
sleep 60
"""

BIG_AND_FAST = """#!/bin/bash
# fake `git clone` that writes 3 MB and exits 0 before the first size poll
dest="${@: -1}"
mkdir -p "$dest"
head -c 3000000 /dev/urandom > "$dest/pack.bin"
exit 0
"""


def _shim(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str) -> None:
    b = tmp_path / "bin"
    b.mkdir()
    (b / "git").write_text(body)
    (b / "git").chmod(0o755)
    monkeypatch.setenv("PATH", f"{b}:{os.environ['PATH']}")


def _ref() -> LocalRef:
    return LocalRef("github.com", "octo", "slow", "https://github.com/octo/slow.git")


def test_timeout_leaves_no_partial_clone(tmp_path, monkeypatch):
    _shim(tmp_path, monkeypatch, SLOW)
    dest = tmp_path / "c" / "source"
    t0 = time.monotonic()
    with pytest.raises(IngestError) as e:
        ensure_pinned_checkout(_ref(), SHA, dest, FetchLimits(clone_timeout_s=1))
    assert e.value.code == "fetch_timeout" and time.monotonic() - t0 < 10
    time.sleep(1.0)  # a surviving helper would recreate files here
    assert not (dest.parent / "source.partial").exists(), sorted(p.name for p in dest.parent.iterdir())
    assert not (dest.parent / "source.partial.stderr").exists() and not dest.exists()


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
