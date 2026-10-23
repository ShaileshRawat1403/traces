"""Component layer reasons and the library layer (D-029, O-3)."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from traces.evidence import components as comp


def _repo(tmp: Path, files: dict[str, str]) -> tuple[Path, str]:
    subprocess.run(["git", "init", "-q", str(tmp)], check=True)
    for k, v in files.items():
        (tmp / k).parent.mkdir(parents=True, exist_ok=True)
        (tmp / k).write_text(v)
    subprocess.run(["git", "-C", str(tmp), "add", "."], check=True)
    subprocess.run(["git", "-C", str(tmp), "-c", "user.email=t@e", "-c", "user.name=t", "commit", "-qm", "x"], check=True)
    sha = subprocess.run(["git", "-C", str(tmp), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    return tmp, sha


LIB = {"pyproject.toml": '[project]\nname = "signer"\ndependencies = []\n[project.optional-dependencies]\ntest = ["pytest"]\n',
       "src/signer/__init__.py": "", "src/signer/core.py": "def sign(): ...\n", "tests/test_core.py": "def test(): ...\n",
       "README.md": "# signer\n"}


def test_python_library_gets_library_layer_with_reason(tmp_path: Path):
    root, sha = _repo(tmp_path, LIB)
    facts = comp.snapshot_facts(root, sha)
    by = {c.name: c for c in facts.components}
    assert by["src/signer"].layer == "library"
    assert by["src/signer"].rule.endswith("+library-v1:no-app-entrypoint")
    assert "pyproject.toml" in by["src/signer"].reason and "2 of 2" in by["src/signer"].reason
    assert by["tests"].layer == "tests" and by["tests"].reason.startswith("tests: 1 of 1")
    assert facts.sources["repo_kind"]["library"] is True


def test_app_framework_or_entrypoint_keeps_backend(tmp_path: Path):
    files = dict(LIB, **{"pyproject.toml": '[project]\nname = "svc"\ndependencies = ["fastapi"]\n'})
    root, sha = _repo(tmp_path / "a", files)
    c = {c.name: c for c in comp.snapshot_facts(root, sha).components}["src/signer"]
    assert c.layer == "backend" and c.rule == comp.COMPONENT_RULE and c.reason.startswith("backend: 2 of 2")
    root, sha = _repo(tmp_path / "b", dict(LIB, **{"src/signer/main.py": "print(1)\n"}))
    kind = comp.snapshot_facts(root, sha).sources["repo_kind"]
    assert kind["library"] is False and "main.py" in kind["reason"]
    root, sha = _repo(tmp_path / "c", {k: v for k, v in LIB.items() if k != "pyproject.toml"})
    assert comp.snapshot_facts(root, sha).sources["repo_kind"]["library"] is False


def test_js_dev_dependency_does_not_make_a_library_an_app(tmp_path: Path):
    pj = {"name": "fetcher", "dependencies": {}, "devDependencies": {"express": "^4"}}
    root, sha = _repo(tmp_path, {"package.json": json.dumps(pj), "source/index.ts": "export const x = 1\n"})
    facts = comp.snapshot_facts(root, sha)
    assert "Express" in facts.frameworks  # still reported as a detected framework
    assert {c.name: c for c in facts.components}["source"].layer == "library"
    pj["private"] = True
    root, sha = _repo(tmp_path / "p", {"package.json": json.dumps(pj), "source/index.ts": "export const x = 1\n"})
    assert {c.name: c for c in comp.snapshot_facts(root, sha).components}["source"].layer == "backend"


def test_reason_is_not_part_of_the_map_digest():
    a, _ = comp.build_components(["pkg/x.py"])
    m = comp.component_map("0" * 40, a)
    b = [type(c)(id=c.id, name=c.name, layer=c.layer, paths=c.paths, rule=c.rule, reason="different") for c in a]
    assert comp.component_map("0" * 40, b).digest == m.digest
    assert a[0].layer == "backend"  # no RepoKind given: the old rule, unchanged
