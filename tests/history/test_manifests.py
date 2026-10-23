"""Step 7: manifest history (contract sections 6.1, 9.6; HT14 synthetic part)."""

from __future__ import annotations

import json

import pytest

from traces.history import HistoryConfig, ingest
from traces.history.manifests import ManifestError, manifest_changes, manifest_kind, parse_manifest

from ._repo import BOT, SynthRepo
from ._schema import assert_valid
from .conftest import ref

PYPROJECT_1 = """
[project]
name = "x"
dependencies = ["FastAPI>=0.100", "sqlmodel==0.0.8", "Pydantic_Settings"]
[project.optional-dependencies]
docs = ["mkdocs"]
[dependency-groups]
dev = ["pytest>=8", {include-group = "lint"}]
lint = ["ruff"]
[tool.poetry.dependencies]
python = "^3.10"
celery = {version = "^5.3"}
redis = {git = "https://example.invalid/redis.git"}
[tool.poetry.group.test.dependencies]
coverage = "*"
"""
PYPROJECT_2 = PYPROJECT_1.replace('"sqlmodel==0.0.8"', '"sqlmodel==0.0.21"').replace(', "Pydantic_Settings"', "") \
    .replace('docs = ["mkdocs"]', 'docs = ["mkdocs", "mkdocs-material"]')


def test_parse_manifest_kinds() -> None:
    assert manifest_kind("a/package.json") == "npm" and manifest_kind("pyproject.toml") == "pyproject"
    assert manifest_kind("x/Pipfile") == "pipfile" and manifest_kind("requirements-dev.txt") == "requirements"
    assert manifest_kind("package-lock.json") is None and manifest_kind("Pipfile.lock") is None
    e, _ = parse_manifest("pyproject", PYPROJECT_1.encode())
    assert e[("project", "fastapi")] == ">=0.100"
    assert e[("project", "pydantic-settings")] == ""
    assert e[("optional:docs", "mkdocs")] == "" and e[("group:dev", "pytest")] == ">=8" and e[("group:lint", "ruff")] == ""
    assert e[("poetry", "celery")] == "^5.3" and ("poetry", "python") not in e
    assert e[("poetry", "redis")].startswith("{") and e[("poetry:test", "coverage")] == "*"
    e, notes = parse_manifest("requirements", b"# c\nrequests[socks] >= 2.0 ; python_version>'3'\n-r base.txt\nflask\n")
    assert e[("requirements", "requests")] == "[socks]>=2.0; python_version>'3'"
    assert e[("requirements", "flask")] == "" and notes
    e, _ = parse_manifest("pipfile", b'[packages]\nDjango = "*"\n[dev-packages]\npytest = {version = ">=7"}\n')
    assert e == {("packages", "django"): "*", ("dev-packages", "pytest"): ">=7"}
    for kind, bad in [("npm", b"{nope"), ("pyproject", b"[project\n"), ("npm", b"[]"), ("requirements", b"\xff\xfe")]:
        with pytest.raises(ManifestError):
            parse_manifest(kind, bad)


def _pkg(deps: dict, dev: dict | None = None) -> str:
    return json.dumps({"name": "web", "dependencies": deps, "devDependencies": dev or {}}, indent=2)


def _build(r: SynthRepo) -> dict[str, str]:
    s = {}
    r.write("frontend/package.json", _pkg({"react": "^18.0.0"}, {"vite": "^5"}))
    r.write("backend/pyproject.toml", PYPROJECT_1)
    s["init"] = r.commit("init")
    r.write("frontend/package.json", _pkg({"react": "^18.2.0", "axios": "^1"}, {}))
    s["npm"] = r.commit("npm changes")
    r.write("backend/pyproject.toml", PYPROJECT_2)
    s["py"] = r.commit("py changes")
    r.write("frontend/package-lock.json", '{"lockfileVersion": 3}')
    s["lock"] = r.commit("lockfile only")
    r.write("web/dist/package.json", _pkg({"left-pad": "1"}))
    s["dist"] = r.commit("generated manifest")
    r.write("frontend/package.json", "{broken")
    s["broken"] = r.commit("broken manifest")
    r.write("frontend/package.json", _pkg({"react": "^18.2.0", "axios": "^1.6"}, {}))
    s["fix"] = r.commit("fix manifest", BOT)
    r.mv("backend/pyproject.toml", "server/pyproject.toml")
    s["mv"] = r.commit("move manifest")
    r.write("requirements-dev.txt", "pytest==8.0\n")
    r.write("Pipfile", '[packages]\nrequests = "*"\n')
    s["req"] = r.commit("req and pipfile")
    r.rm("Pipfile")
    s["rm"] = r.commit("drop pipfile")
    return s


def _ev(res, sha):  # type: ignore[no-untyped-def]
    return sorted((r["relationship_kind"], r["provenance_raw"]["group"], r["provenance_raw"]["name"],
                   r["provenance_raw"]["before"], r["provenance_raw"]["after"])
                  for r in res.records if r["from"]["symbol"] == f"commit::{sha}")


def test_manifest_events(synth: SynthRepo) -> None:
    s = _build(synth)
    res = manifest_changes(ingest(ref(synth), HistoryConfig()))
    assert_valid(res.records)
    assert all(r["status"] == "observed" and r["class"] == "git_object_fact" for r in res.records)
    assert all(r["qualifier"] == "manifest entry change" and r["checks"][0]["method"] == "git_object_check"
               for r in res.records)
    assert _ev(res, s["npm"]) == [
        ("dependency_added", "dependencies", "axios", None, "^1"),
        ("dependency_removed", "devDependencies", "vite", "^5", None),
        ("dependency_version_changed", "dependencies", "react", "^18.0.0", "^18.2.0")]
    assert _ev(res, s["py"]) == [
        ("dependency_added", "optional:docs", "mkdocs-material", None, ""),
        ("dependency_removed", "project", "pydantic-settings", "", None),
        ("dependency_version_changed", "project", "sqlmodel", "==0.0.8", "==0.0.21")]
    assert _ev(res, s["lock"]) == [] and _ev(res, s["dist"]) == [] and _ev(res, s["broken"]) == []
    assert res.report["skipped"] == {"lockfile_changes": 1, "generated_manifest_changes": 1}
    # an unparseable blob on either side: warning with commit and path, no event for that commit (section 9.6)
    assert [(w["commit"], w["path"]) for w in res.report["unparseable"]] == [
        (s["broken"], "frontend/package.json"), (s["fix"], "frontend/package.json")]
    assert _ev(res, s["fix"]) == []
    assert _ev(res, s["mv"]) == []  # exact rename of a manifest: no entry change
    assert _ev(res, s["req"]) == [("dependency_added", "packages", "requests", None, "*"),
                                  ("dependency_added", "requirements", "pytest", None, "==8.0")]
    assert _ev(res, s["rm"]) == [("dependency_removed", "packages", "requests", "*", None)]
    # logical manifest identity follows the rename to server/pyproject.toml
    sql = [r for r in res.records if r["provenance_raw"]["name"] == "sqlmodel"]
    assert {r["to"]["symbol"] for r in sql} == {"dep::pypi:server/pyproject.toml:project:sqlmodel"}
    assert sql[0]["citations"][0]["paths"][0]["path"] == "backend/pyproject.toml"


def test_generated_manifest_kept_when_filter_off(synth: SynthRepo) -> None:
    from traces.history import FilterSpec

    s = _build(synth)
    res = manifest_changes(ingest(ref(synth), HistoryConfig(filters=FilterSpec(exclude_generated_from_patterns=False))))
    d = [r for r in res.records if r["from"]["symbol"] == f"commit::{s['dist']}"]
    assert len(d) == 1 and "generated_path" in d[0]["flags"]


def test_bot_manifest_change_flagged(synth: SynthRepo) -> None:
    synth.write("package.json", _pkg({"a": "1"}))
    synth.commit("init")
    synth.write("package.json", _pkg({"a": "2"}))
    c = synth.commit("bump", BOT)
    (r,) = [x for x in manifest_changes(ingest(ref(synth), HistoryConfig())).records if c in x["from"]["symbol"]]
    assert "bot_commit" in r["flags"] and r["status"] == "observed"
