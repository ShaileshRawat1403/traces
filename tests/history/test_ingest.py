"""Step 2: ingest and cache (contract sections 8, 9.2, 9.3; HT6 to HT12, HT18)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from traces.history import HistoryConfig, HistoryError, ingest
from traces.history.config import Limits, Thresholds

from ._repo import ALICE, BOB, SynthRepo, lines
from .conftest import NO_FILTERS, ref


def _changes(log, sha):  # type: ignore[no-untyped-def]
    return {(c.status, c.old_path, c.path) for c in log.by_sha[sha].changes}


def test_add_modify_delete_and_numstat(synth: SynthRepo) -> None:
    synth.write("a.py", lines(10))
    c1 = synth.commit("add")
    synth.write("a.py", lines(12))
    c2 = synth.commit("modify")
    synth.rm("a.py")
    synth.write("b.py", "x\n")
    c3 = synth.commit("delete")
    log = ingest(ref(synth), NO_FILTERS)
    assert [c.sha for c in log.commits] == [c1, c2, c3]
    assert log.first_parent == (c1, c2, c3)
    (a,) = log.by_sha[c1].changes
    assert (a.status, a.path, a.added, a.deleted) == ("A", "a.py", 10, 0)
    (m,) = log.by_sha[c2].changes
    assert (m.status, m.added, m.deleted) == ("M", 2, 0)
    assert _changes(log, c3) == {("D", None, "a.py"), ("A", None, "b.py")}
    d = next(c for c in log.by_sha[c3].changes if c.status == "D")
    assert (d.added, d.deleted) == (0, 12)


def test_exact_and_similarity_rename(synth: SynthRepo) -> None:
    synth.write("src/a.py", lines(20))
    synth.write("src/b.py", lines(20, "b"))
    synth.commit("add")
    synth.mv("src/a.py", "lib/a.py")
    synth.mv("src/b.py", "lib/b2.py")
    synth.write("lib/b2.py", lines(18, "b") + "new\n")
    c2 = synth.commit("move")
    log = ingest(ref(synth), NO_FILTERS)
    by = {c.path: c for c in log.by_sha[c2].changes}
    assert by["lib/a.py"].status == "R" and by["lib/a.py"].old_path == "src/a.py" and by["lib/a.py"].similarity == 100
    b = by["lib/b2.py"]
    assert b.status == "R" and b.old_path == "src/b.py" and 50 <= b.similarity < 100
    assert (b.added, b.deleted) == (1, 2)


def test_copy_detected(synth: SynthRepo) -> None:
    synth.write("a.py", lines(30))
    synth.commit("add")
    synth.write("a.py", lines(30) + "more\n")
    synth.write("a_copy.py", lines(30))
    c2 = synth.commit("copy")
    log = ingest(ref(synth), NO_FILTERS)
    cp = next(c for c in log.by_sha[c2].changes if c.path == "a_copy.py")
    assert cp.status == "C" and cp.old_path == "a.py"


def test_merge_commits_have_no_changes_and_first_parent_diff(synth: SynthRepo) -> None:
    synth.write("a.py", "a\n")
    synth.commit("base")
    synth.checkout("-b", "feat")
    synth.write("f.py", "f\n")
    cf = synth.commit("feat")
    synth.checkout("main")
    synth.write("m.py", "m\n")
    synth.commit("main")
    mg = synth.merge("feat")
    log = ingest(ref(synth), NO_FILTERS)
    assert log.by_sha[mg].is_merge and log.by_sha[mg].changes == ()
    assert cf in log.by_sha and cf not in log.first_parent
    assert {(c.status, c.path) for c in log.merge_fp_diffs[mg]} == {("A", "f.py")}


ODD = ["sp ace.py", "tab\there.py", "new\nline.py", "-leading.py", "quo\"te.py", "back\\slash.py", "ünïcødé.py",
       "*glob?.py", ":colon.py", "dir with space/x y.py"]


def test_odd_paths_round_trip(synth: SynthRepo) -> None:
    for i, p in enumerate(ODD):
        synth.write(p, f"{i}\n")
    synth.write(b"bad-\xff\xfe.py", "nonutf8\n")
    c1 = synth.commit("odd")
    synth.mv("tab\there.py", "moved\ttab.py")
    c2 = synth.commit("rename odd")
    log = ingest(ref(synth), NO_FILTERS)
    paths = {c.path for c in log.by_sha[c1].changes}
    assert set(ODD) <= paths
    bad = [c for c in log.by_sha[c1].changes if c.non_utf8]
    assert len(bad) == 1 and bad[0].path == "bad-%FF%FE.py"
    assert all(c.added == 1 for c in log.by_sha[c1].changes)
    (r,) = log.by_sha[c2].changes
    assert (r.status, r.old_path, r.path) == ("R", "tab\there.py", "moved\ttab.py")


def test_mailmap_pinned_and_later_change_ignored(synth: SynthRepo) -> None:
    synth.write(".mailmap", "Alice Canonical <alice@canonical.org> Alice Example <alice@example.com>\n")
    synth.write("a.py", "1\n")
    c1 = synth.commit("one", ALICE)
    log = ingest(ref(synth), NO_FILTERS)
    assert log.mailmap_blob is not None
    assert (log.by_sha[c1].author_name, log.by_sha[c1].author_email) == ("Alice Canonical", "alice@canonical.org")
    synth.write(".mailmap", "Other <o@x.org> Alice Example <alice@example.com>\n")
    synth.commit("change mailmap", BOB)
    # pinned at the old SHA: the later .mailmap is not consulted, and the working tree is never read
    log_old = ingest(ref(synth, c1), NO_FILTERS)
    assert log_old.by_sha[c1].author_name == "Alice Canonical"
    log_new = ingest(ref(synth), NO_FILTERS)
    assert log_new.by_sha[c1].author_name == "Other"
    raw = ingest(ref(synth), HistoryConfig(mailmap="none"))
    assert raw.by_sha[c1].author_name == "Alice Example" and raw.mailmap_blob is None
    assert any("mailmap" in w for w in raw.warnings)


def test_pinned_sha_ignores_later_commits(synth: SynthRepo) -> None:
    synth.write("a.py", "1\n")
    c1 = synth.commit("one")
    synth.write("a.py", "2\n")
    synth.commit("two")
    log = ingest(ref(synth, c1), NO_FILTERS)
    assert [c.sha for c in log.commits] == [c1]


def test_cache_incremental_and_identical(synth: SynthRepo, tmp_path: Path) -> None:
    synth.write("a.py", "1\n")
    synth.commit("one")
    synth.write("a.py", "2\n")
    c2 = synth.commit("two")
    cache = tmp_path / "cache"
    cold = ingest(ref(synth), NO_FILTERS, cache_dir=cache)
    assert cold.cache_stats["misses"] == 2
    warm = ingest(ref(synth), NO_FILTERS, cache_dir=cache)
    assert warm.cache_stats["hits"] == 2 and warm.commits == cold.commits
    synth.write("a.py", "3\n")
    synth.commit("three")
    inc = ingest(ref(synth), NO_FILTERS, cache_dir=cache)
    assert (inc.cache_stats["hits"], inc.cache_stats["misses"]) == (2, 1)
    assert inc.commits[:2] == cold.commits
    # a different rename threshold must not reuse entries
    other = ingest(ref(synth, c2), HistoryConfig(thresholds=Thresholds(rename_threshold=60)), cache_dir=cache)
    assert other.cache_stats["hits"] == 0


def test_cache_corrupt_entry_discarded(synth: SynthRepo, tmp_path: Path) -> None:
    synth.write("a.py", "1\n")
    c1 = synth.commit("one")
    cache = tmp_path / "cache"
    good = ingest(ref(synth), NO_FILTERS, cache_dir=cache)
    (entry,) = list(cache.rglob(f"{c1}.json"))
    d = json.loads(entry.read_text())
    d["commit"]["author_name"] = "Mallory"
    entry.write_text(json.dumps(d))
    again = ingest(ref(synth), NO_FILTERS, cache_dir=cache)
    assert again.commits == good.commits
    assert again.cache_stats["discarded"] == 1
    entry.write_text("{not json")
    assert ingest(ref(synth), NO_FILTERS, cache_dir=cache).commits == good.commits


def test_limits(synth: SynthRepo) -> None:
    for i in range(5):
        synth.write(f"f{i}.py", f"{i}\n")
    synth.commit("many")
    with pytest.raises(HistoryError) as ei:
        ingest(ref(synth), HistoryConfig(limits=Limits(max_paths_per_commit=3)))
    assert ei.value.code == "E_LIMIT"
    with pytest.raises(HistoryError) as ei:
        ingest(ref(synth), HistoryConfig(limits=Limits(max_commits=0)))
    assert ei.value.code == "E_LIMIT"


def test_binary_and_mode_change(synth: SynthRepo) -> None:
    synth.write("img.bin", bytes(range(256)) * 4)
    synth.write("run.sh", "echo hi\n")
    synth.commit("add")
    (synth.path / "run.sh").chmod(0o755)
    synth.write("img.bin", bytes(range(255, -1, -1)) * 4)
    c2 = synth.commit("mode and binary")
    log = ingest(ref(synth), NO_FILTERS)
    by = {c.path: c for c in log.by_sha[c2].changes}
    assert by["img.bin"].binary and by["img.bin"].added == 0
    assert by["run.sh"].mode_after == "100755" and by["run.sh"].status == "M"


def test_empty_commit_and_message(synth: SynthRepo) -> None:
    synth.write("a.py", "1\n")
    synth.commit("one")
    c2 = synth.commit("empty\n\nbody with\x01 odd bytes")
    log = ingest(ref(synth), NO_FILTERS)
    assert log.by_sha[c2].changes == ()
    assert log.by_sha[c2].subject == "empty"
