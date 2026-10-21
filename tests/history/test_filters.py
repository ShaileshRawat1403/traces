"""Step 3: filters and config (contract section 12; HT13, HT14)."""

from __future__ import annotations

import pytest

from traces.history import FilterSpec, HistoryConfig, HistoryError, Thresholds
from traces.history.filters import Filters


@pytest.mark.parametrize("path", ["web/dist/app.js", "build/out.o", "a/b/vendor/x.go", "pkg/__generated__/t.ts",
                                  "frontend/package-lock.json", "uv.lock", "x/y.min.js", "a.gen.ts", "s/generated/x.py"])
def test_generated_whole_segments(path: str) -> None:
    assert Filters(FilterSpec()).is_generated(path)


@pytest.mark.parametrize("path", ["distance/calc.py", "rebuild/run.py", "build.py", "dist.py", "vendors/x.py",
                                  "src/builder/x.ts", "mydist/x.js", "generated.py", "lock.json"])
def test_not_generated(path: str) -> None:
    assert not Filters(FilterSpec()).is_generated(path)


def test_extra_generated_paths_from_evidence() -> None:
    f = Filters(FilterSpec(extra_generated_paths=frozenset({"client/sdk.gen.ts", "openapi/"}),
                           extra_generated_source="evidence:generated_paths"))
    assert f.generated_rule("client/sdk.gen.ts") is not None
    assert "extra_generated_paths" in (f.generated_rule("openapi/x/y.ts") or "")
    assert not f.is_generated("openapix/y.ts")
    c = f.criteria()
    assert c["extra_generated_paths_count"] == 2 and c["extra_generated_source"] == "evidence:generated_paths"


@pytest.mark.parametrize(("name", "email", "bot"), [
    ("dependabot[bot]", "49699333+dependabot[bot]@users.noreply.github.com", True),
    ("github-actions", "github-actions@github.com", True),
    ("pre-commit-ci[bot]", "x@y", True),
    ("renovate[bot]", "bot@renovateapp.com", True),
    ("Alice", "alice@example.com", False),
    ("Robotics Bob", "bob@robots.org", False),
])
def test_bot_patterns(name: str, email: str, bot: bool) -> None:
    assert Filters(FilterSpec()).is_bot(name, email) is bot


def test_criteria_echo_every_field() -> None:
    c = FilterSpec().criteria()
    for k in ("bot_author_patterns", "generated_basenames", "generated_basename_globs", "generated_dir_segments",
              "exclude_bots_from_patterns", "exclude_generated_from_patterns", "bot_match", "generated_dir_rule"):
        assert k in c
    assert "dist" in c["generated_dir_segments"] and "build" in c["generated_dir_segments"]


@pytest.mark.parametrize("t", [Thresholds(min_revs=0), Thresholds(min_coupling=1.5), Thresholds(min_coupling=-0.1),
                               Thresholds(rename_threshold=0), Thresholds(rename_threshold=101),
                               Thresholds(max_changeset_size=0)])
def test_bad_thresholds(t: Thresholds) -> None:
    with pytest.raises(HistoryError) as ei:
        HistoryConfig(thresholds=t).validate()
    assert ei.value.code == "E_CONFIG"


def test_bad_config_values() -> None:
    with pytest.raises(HistoryError):
        HistoryConfig(mailmap="global").validate()
    with pytest.raises(HistoryError):
        HistoryConfig(filters=FilterSpec(bot_author_patterns=("(",))).validate()


def test_config_digest_changes_with_thresholds() -> None:
    a = HistoryConfig().digest()
    assert a == HistoryConfig().digest()
    assert a != HistoryConfig(thresholds=Thresholds(min_coupling=0.31)).digest()
    defaults = HistoryConfig().thresholds
    assert (defaults.min_revs, defaults.min_shared_revs, defaults.min_coupling, defaults.max_changeset_size) == (5, 5, 0.30, 30)
