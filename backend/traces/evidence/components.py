"""Deterministic snapshot facts for INDEX (D-007): components and layers, languages, frameworks and generated paths.

Everything here is computed from Git objects at the pinned SHA with fixed rules; nothing is executed and no LLM is
involved. Each component records the rule that produced it."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from traces.evidence.types import ComponentDef, ComponentMap

COMPONENT_RULE = "dir-v1:container-strip"
LAYER_RULE = "layer-v1:path-and-extension"
CONTAINERS = {"src", "app", "apps", "lib", "libs", "packages", "backend", "frontend", "server", "web", "pkg", "internal", "cmd"}
LAYER_ORDER = ("api", "frontend", "data", "backend", "infra", "tests", "docs", "other")

EXT_LANG = {".py": "Python", ".pyi": "Python", ".ts": "TypeScript", ".tsx": "TypeScript", ".mts": "TypeScript", ".cts": "TypeScript",
            ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript", ".go": "Go", ".rs": "Rust",
            ".java": "Java", ".kt": "Kotlin", ".rb": "Ruby", ".php": "PHP", ".cs": "C#", ".c": "C", ".h": "C", ".cpp": "C++",
            ".hpp": "C++", ".swift": "Swift", ".vue": "Vue", ".svelte": "Svelte", ".css": "CSS", ".scss": "CSS", ".html": "HTML",
            ".sql": "SQL", ".sh": "Shell", ".md": "Markdown", ".mdx": "Markdown", ".yml": "YAML", ".yaml": "YAML", ".toml": "TOML",
            ".json": "JSON"}
FRONTEND_EXT = {".tsx", ".jsx", ".vue", ".svelte", ".css", ".scss", ".html"}
CODE_EXT = {".py", ".ts", ".mts", ".cts", ".js", ".mjs", ".cjs", ".go", ".rs", ".java", ".kt", ".rb", ".php", ".cs", ".c", ".cpp", ".swift"}
JS_FRAMEWORKS = {"react": "React", "vue": "Vue", "svelte": "Svelte", "next": "Next.js", "@angular/core": "Angular", "vite": "Vite",
                 "express": "Express", "fastify": "Fastify", "@nestjs/core": "NestJS", "@tanstack/react-query": "TanStack Query",
                 "@tanstack/react-router": "TanStack Router", "react-router-dom": "React Router", "@hey-api/openapi-ts": "openapi-ts",
                 "axios": "axios", "react-hook-form": "react-hook-form", "@playwright/test": "Playwright", "jest": "Jest", "vitest": "Vitest"}
PY_FRAMEWORKS = {"fastapi": "FastAPI", "django": "Django", "flask": "Flask", "starlette": "Starlette", "sqlmodel": "SQLModel",
                 "sqlalchemy": "SQLAlchemy", "pydantic": "Pydantic", "alembic": "Alembic", "celery": "Celery", "pytest": "pytest",
                 "click": "Click", "typer": "Typer", "httpx": "HTTPX", "requests": "Requests", "aiohttp": "aiohttp"}


def _git(root: Path, *args: str) -> str:
    env = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null", "HOME": "/nonexistent", "GIT_OPTIONAL_LOCKS": "0", "PATH": "/usr/bin:/bin"}
    return subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "-C", str(root), *args], env=env, capture_output=True, text=True,
                          check=True, timeout=300).stdout


@dataclass(frozen=True)
class SnapshotFacts:
    files: tuple[str, ...]
    languages: dict[str, int]
    frameworks: list[str]
    generated_paths: list[str]
    components: list[ComponentDef]
    layer_of: dict[str, str]
    sources: dict[str, Any]     # where each framework / generated path was read from (file at the SHA)


def tree_files(root: Path, sha: str) -> list[str]:
    out = _git(root, "ls-tree", "-r", "-z", "--name-only", "--full-tree", sha)
    return sorted(p for p in out.split("\0") if p)


def blob(root: Path, sha: str, path: str, max_bytes: int = 2_000_000) -> str | None:
    try:
        size = int(_git(root, "cat-file", "-s", f"{sha}:{path}").strip())
        if size > max_bytes:
            return None
        return _git(root, "cat-file", "blob", f"{sha}:{path}")
    except (subprocess.CalledProcessError, ValueError, UnicodeDecodeError):
        return None


def layer_of(path: str) -> str:
    p = PurePosixPath(path)
    parts = [s.lower() for s in p.parts]
    name, ext = p.name.lower(), p.suffix.lower()
    dirs = parts[:-1]
    if any(d in ("tests", "test", "__tests__", "e2e", "spec", "specs", "testing") for d in dirs) or name.startswith("test_") \
            or name.endswith(("_test.py", "_test.go")) or re.search(r"\.(test|spec)\.[jt]sx?$", name):
        return "tests"
    if ext in (".md", ".mdx", ".rst", ".txt") or any(d in ("docs", "doc") for d in dirs):
        return "docs"
    if any(d in (".github", ".gitlab", "deploy", "deployment", "k8s", "helm", "terraform", "infra", "docker", "scripts", ".devcontainer") for d in dirs) \
            or name.startswith(("dockerfile", "docker-compose", "compose.")) or name in ("makefile", ".gitlab-ci.yml", "procfile"):
        return "infra"
    if any(d in ("api", "routes", "routers", "endpoints", "controllers", "handlers") for d in dirs) and ext in CODE_EXT:
        return "api"
    if any(d in ("models", "migrations", "alembic", "db", "database", "schemas", "repositories") for d in dirs) \
            or name in ("models.py", "crud.py", "schemas.py", "schema.py", "db.py", "database.py") or ext == ".sql":
        return "data"
    if ext in FRONTEND_EXT or (dirs and dirs[0] in ("frontend", "web", "client", "ui")) and ext in CODE_EXT | FRONTEND_EXT:
        return "frontend"
    if ext in CODE_EXT:
        return "backend"
    return "other"


def component_key(path: str) -> str:
    parts = PurePosixPath(path).parts
    if len(parts) == 1:
        return "(root)"
    prefix: list[str] = []
    for seg in parts[:-1]:
        prefix.append(seg)
        if seg.lower() not in CONTAINERS:
            break
    return "/".join(prefix)


LIBRARY_RULE = "library-v1:no-app-entrypoint"
APP_FRAMEWORKS = {"FastAPI", "Django", "Flask", "Starlette", "Express", "Fastify", "NestJS", "Next.js", "React", "Vue", "Svelte",
                  "Angular", "Vite"}
ENTRYPOINT_NAMES = {"manage.py", "wsgi.py", "asgi.py", "app.py", "main.py", "server.py", "index.html", "server.js", "server.ts",
                    "procfile"}
NON_PRODUCT_DIRS = {"tests", "test", "docs", "doc", "examples", "example", "benchmarks", "scripts", ".github", "e2e"}
LAYER_WHY = {"api": "under an api/routes/endpoints/controllers/handlers directory", "frontend": "UI files or a frontend/web/client/ui tree",
             "data": "models, schemas, migrations, db or SQL", "backend": "code outside api, data and UI paths",
             "infra": "CI, deploy, docker or scripts", "tests": "test files or test directories", "docs": "documentation files",
             "other": "no code, docs or infra files"}


@dataclass(frozen=True)
class RepoKind:
    """Whether the snapshot looks like an importable library rather than an application, and why (D-029)."""
    library: bool
    reason: str


def repo_kind(files: Iterable[str], frameworks: Iterable[str], package_decl: str | None) -> RepoKind:
    """A library: a package is declared (pyproject/setup or a non-private package.json), no application framework is
    a dependency, and no application entrypoint file exists outside tests, docs and examples. Deterministic, from Git
    objects only; nothing is run."""
    app_fw = sorted(set(frameworks) & APP_FRAMEWORKS)
    entry = sorted(f for f in files if PurePosixPath(f).name.lower() in ENTRYPOINT_NAMES
                   and not any(d.lower() in NON_PRODUCT_DIRS for d in PurePosixPath(f).parts[:-1]))
    if package_decl is None:
        return RepoKind(False, "no package declaration (pyproject.toml [project], setup.py/setup.cfg or a public package.json)")
    if app_fw:
        return RepoKind(False, f"application framework dependency: {', '.join(app_fw)}")  # runtime deps for package.json
    if entry:
        return RepoKind(False, f"application entrypoint file(s): {', '.join(entry[:3])}")
    return RepoKind(True, f"package declared in {package_decl}, no application framework dependency and no application "
                          "entrypoint outside tests, docs and examples")


def build_components(files: Iterable[str], kind: RepoKind | None = None) -> tuple[list[ComponentDef], dict[str, str]]:
    groups: dict[str, list[str]] = defaultdict(list)
    lay: dict[str, str] = {}
    for f in files:
        groups[component_key(f)].append(f)
        lay[f] = layer_of(f)
    comps = []
    for key in sorted(groups):
        members = sorted(groups[key])
        counts = Counter(lay[m] for m in members if lay[m] not in ("other",)) or Counter(lay[m] for m in members)
        top = max(counts.values())
        layer = next(l for l in LAYER_ORDER if counts.get(l) == top)
        reason = f"{layer}: {top} of {len(members)} file(s) are {LAYER_WHY[layer]} ({LAYER_RULE})"
        rule = COMPONENT_RULE
        if layer == "backend" and kind is not None and kind.library:
            layer, rule = "library", f"{COMPONENT_RULE}+{LIBRARY_RULE}"
            reason = (f"library: {top} of {len(members)} file(s) are code outside api, data and UI paths, and the repository "
                      f"looks like a library ({kind.reason}), so 'backend' would overstate it ({LIBRARY_RULE})")
        comps.append(ComponentDef(id=f"component::{key}", name=key, layer=layer, paths=tuple(members), rule=rule, reason=reason))
    return comps, lay


def package_declaration(root: Path, sha: str, files: Iterable[str]) -> str | None:
    """Top-level package declaration file, if any: pyproject.toml with [project] or [tool.poetry], setup.py, setup.cfg,
    or a package.json with a name that is not private."""
    top = {f for f in files if "/" not in f}
    if "pyproject.toml" in top and re.search(r"^\[(project|tool\.poetry)\]", blob(root, sha, "pyproject.toml") or "", re.M):
        return "pyproject.toml"
    for f in ("setup.py", "setup.cfg"):
        if f in top:
            return f
    if "package.json" in top:
        try:
            pj = json.loads(blob(root, sha, "package.json") or "{}")
        except ValueError:
            pj = {}
        if isinstance(pj, dict) and pj.get("name") and pj.get("private") is not True:
            return "package.json"
    return None


def component_map(sha: str, comps: Iterable[ComponentDef]) -> ComponentMap:
    cs = {c.id: c for c in comps}
    canon = json.dumps([[c.id, c.layer, c.rule, list(c.paths)] for c in sorted(cs.values(), key=lambda c: c.id)], separators=(",", ":"))
    index = {p: c.id for c in cs.values() for p in c.paths}
    return ComponentMap(sha=sha, components=cs, digest="sha256:" + hashlib.sha256(canon.encode()).hexdigest(), _index=index)


def _js_frameworks(text: str, keys: tuple[str, ...] = ("dependencies", "devDependencies", "peerDependencies")) -> set[str]:
    try:
        pj = json.loads(text)
    except ValueError:
        return set()
    if not isinstance(pj, dict):
        return set()
    deps: dict[str, Any] = {}
    for k in keys:
        if isinstance(pj.get(k), Mapping):
            deps.update(pj[k])
    return {v for k, v in JS_FRAMEWORKS.items() if k in deps}


def _py_frameworks(text: str) -> set[str]:
    names = set(re.findall(r"""(?im)^[\s"'\[]*([A-Za-z0-9_.-]+)\s*(?:\[[^\]]*\])?\s*(?:[<>=!~;,"']|$)""", text))
    names |= set(re.findall(r"""["']([A-Za-z0-9_.-]+)\s*(?:\[[^\]]*\])?\s*(?:[<>=!~;][^"']*)?["']""", text))
    low = {n.lower().replace("_", "-") for n in names}
    return {v for k, v in PY_FRAMEWORKS.items() if k in low}


def generated_paths(root: Path, sha: str, files: list[str]) -> tuple[list[str], dict[str, str]]:
    """Generator-config output dirs (D-H8): openapi-ts `output`, plus `linguist-generated` patterns in .gitattributes."""
    out: dict[str, str] = {}
    for f in files:
        name = PurePosixPath(f).name
        if re.match(r"openapi-ts\.config\.[cm]?[jt]s$", name):
            text = blob(root, sha, f) or ""
            m = re.search(r"""output\s*:\s*(?:\{[^}]*?path\s*:\s*)?["']([^"']+)["']""", text)
            if m:
                joined = (PurePosixPath(f).parent / m.group(1)).as_posix().removeprefix("./")
                out[re.sub(r"/+$", "", str(PurePosixPath(joined)))] = f
        elif name == ".gitattributes":
            for line in (blob(root, sha, f) or "").splitlines():
                parts = line.split()
                if len(parts) > 1 and any(a in ("linguist-generated", "linguist-generated=true") for a in parts[1:]):
                    parent = str(PurePosixPath(f).parent)
                    out[(parts[0] if parent == "." else f"{parent}/{parts[0]}").removeprefix("/")] = f
    return sorted(out), out


def snapshot_facts(root: Path, sha: str) -> SnapshotFacts:
    files = tree_files(root, sha)
    langs = Counter(EXT_LANG[PurePosixPath(f).suffix.lower()] for f in files if PurePosixPath(f).suffix.lower() in EXT_LANG)
    fw: dict[str, list[str]] = defaultdict(list)
    runtime_fw: set[str] = set()  # JS devDependencies (test servers, bundlers) do not make a library an application
    for f in files:
        name = PurePosixPath(f).name
        if "node_modules/" in f:
            continue
        if name == "package.json":
            text = blob(root, sha, f) or ""
            for x in _js_frameworks(text):
                fw[x].append(f)
            runtime_fw |= _js_frameworks(text, ("dependencies", "peerDependencies"))
        elif name in ("pyproject.toml", "requirements.txt", "setup.cfg", "Pipfile") or re.match(r"requirements[-_.].*\.txt$", name):
            for x in _py_frameworks(blob(root, sha, f) or ""):
                fw[x].append(f)
                runtime_fw.add(x)
    gen, gen_src = generated_paths(root, sha, files)
    kind = repo_kind(files, runtime_fw, package_declaration(root, sha, files))
    comps, lay = build_components(files, kind)
    return SnapshotFacts(files=tuple(files), languages=dict(sorted(langs.items())), frameworks=sorted(fw), generated_paths=gen,
                         components=comps, layer_of=lay, sources={"frameworks": {k: sorted(v) for k, v in sorted(fw.items())},
                                                                  "generated_paths": gen_src, "component_rule": COMPONENT_RULE,
                                                                  "layer_rule": LAYER_RULE,
                                                                  "repo_kind": {"library": kind.library, "reason": kind.reason,
                                                                                "rule": LIBRARY_RULE}})
