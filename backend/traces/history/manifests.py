"""Dependency manifest history (contract sections 6.1 and 9.6).

Manifests: package.json (dependencies, devDependencies, peerDependencies, optionalDependencies), pyproject.toml
(PEP 621 project.dependencies and optional-dependencies, PEP 735 dependency-groups, tool.poetry dependencies,
dev-dependencies and groups), Pipfile (packages, dev-packages) and requirements*.txt. Blobs are read with cat-file
and parsed with stdlib json and tomllib, or a line reader for requirements files. This is manifest data, not
source parsing, and no code from the repository is executed.

Events per non-merge commit and manifest change: dependency_added, dependency_removed and
dependency_version_changed. Lockfiles are never parsed, so lockfile-only changes produce no event. Manifests
whose path is generated (for example under dist/ or vendor/) are skipped while the generated filter is on.

Each event is a git_object_fact anchored to its commit. The independent check re-reads both manifests through
`cat-file <commit>:<path>` and `<parent>:<old path>` (tree lookup, not the ingest diff), compares the blob ids with
the cited ones, re-parses them and must find the same entry change.
"""

from __future__ import annotations

import fnmatch
import json
import re
import tomllib
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from .filters import Filters
from .ingest import ls_tree_paths, open_runner
from .lifecycle import identities
from .model import Change, Commit, HistoryLog, encode_path
from .records import RunContext, citation, ep_commit, finalize, make_record
from .shapes import HistoryResult, Record, default_context
from .verify import read_objects, resolve_blobs

NPM_SECTIONS = ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies")
MANIFEST_BASENAMES = ("package.json", "pyproject.toml", "Pipfile")
REQUIREMENTS_GLOB = "requirements*.txt"
_PEP508 = re.compile(r"^\s*([A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)\s*(\[[^\]]*\])?\s*(.*?)\s*$")

Entries = dict[tuple[str, str], str]  # (group, name) -> version specifier ("" when none)


class ManifestError(ValueError):
    pass


def manifest_kind(path: str) -> str | None:
    base = path.rsplit("/", 1)[-1]
    if base == "package.json":
        return "npm"
    if base == "pyproject.toml":
        return "pyproject"
    if base == "Pipfile":
        return "pipfile"
    if fnmatch.fnmatchcase(base, REQUIREMENTS_GLOB):
        return "requirements"
    return None


def ecosystem(kind: str) -> str:
    return "npm" if kind == "npm" else "pypi"


def norm_pypi(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _ws(s: str) -> str:
    return " ".join(s.split())


def _pep508(req: str) -> tuple[str, str]:
    m = _PEP508.match(req)
    if not m:
        raise ManifestError(f"not a PEP 508 requirement: {req[:60]!r}")
    extras = re.sub(r"\s+", "", m.group(2) or "")
    spec, _, marker = m.group(3).partition(";")
    out = extras + re.sub(r"\s+", "", spec)
    if marker.strip():
        out += "; " + _ws(marker)
    return norm_pypi(m.group(1)), out


def _spec_value(v: Any) -> str:
    if isinstance(v, str):
        return _ws(v)
    if isinstance(v, Mapping) and set(v) == {"version"} and isinstance(v["version"], str):
        return _ws(v["version"])
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _put(out: Entries, group: str, name: str, spec: str, dups: list[str]) -> None:
    if (group, name) in out and out[(group, name)] != spec:
        dups.append(f"{group}:{name}")
    out[(group, name)] = spec


def parse_manifest(kind: str, data: bytes) -> tuple[Entries, list[str]]:
    """Parse one manifest blob. Returns entries and notes (duplicates, skipped option lines). Raises ManifestError."""
    notes: list[str] = []
    out: Entries = {}
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise ManifestError("manifest is not UTF-8") from e
    if kind == "npm":
        try:
            doc = json.loads(text)
        except json.JSONDecodeError as e:
            raise ManifestError(f"invalid JSON: {e.msg} at line {e.lineno}") from e
        if not isinstance(doc, dict):
            raise ManifestError("package.json is not an object")
        for sec in NPM_SECTIONS:
            deps = doc.get(sec) or {}
            if not isinstance(deps, dict):
                raise ManifestError(f"{sec} is not an object")
            for name, spec in deps.items():
                _put(out, sec, str(name), _spec_value(spec), notes)
        return out, notes
    if kind == "requirements":
        skipped = 0
        for raw in text.splitlines():
            line = raw.split(" #", 1)[0].strip() if not raw.lstrip().startswith("#") else ""
            if not line:
                continue
            if line.startswith("-") or "://" in line or line.startswith((".", "/")):
                skipped += 1
                continue
            name, spec = _pep508(line)
            _put(out, "requirements", name, spec, notes)
        if skipped:
            notes.append(f"{skipped} option, URL or path lines not tracked")
        return out, notes
    try:
        doc = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise ManifestError(f"invalid TOML: {e}") from e
    if kind == "pipfile":
        for sec in ("packages", "dev-packages"):
            deps = doc.get(sec) or {}
            if not isinstance(deps, dict):
                raise ManifestError(f"{sec} is not a table")
            for name, spec in deps.items():
                _put(out, sec, norm_pypi(name), _spec_value(spec), notes)
        return out, notes
    # pyproject.toml
    proj = doc.get("project") or {}
    if not isinstance(proj, dict):
        raise ManifestError("[project] is not a table")
    for req in proj.get("dependencies") or []:
        if not isinstance(req, str):
            raise ManifestError("project.dependencies entry is not a string")
        n, s = _pep508(req)
        _put(out, "project", n, s, notes)
    for extra, reqs in sorted((proj.get("optional-dependencies") or {}).items()):
        for req in reqs or []:
            n, s = _pep508(str(req))
            _put(out, f"optional:{extra}", n, s, notes)
    for grp, reqs in sorted((doc.get("dependency-groups") or {}).items()):
        for req in reqs or []:
            if isinstance(req, dict):  # {include-group = "..."}: membership is resolved by tools, not tracked here
                continue
            n, s = _pep508(str(req))
            _put(out, f"group:{grp}", n, s, notes)
    poetry = (doc.get("tool") or {}).get("poetry") or {}
    if isinstance(poetry, dict):
        def poetry_deps(group: str, deps: Any) -> None:
            if not isinstance(deps, dict):
                return
            for name, spec in deps.items():
                if name.lower() == "python":
                    continue
                _put(out, group, norm_pypi(name), _spec_value(spec), notes)

        poetry_deps("poetry", poetry.get("dependencies"))
        poetry_deps("poetry:dev", poetry.get("dev-dependencies"))
        for g, body in sorted((poetry.get("group") or {}).items()):
            if isinstance(body, dict):
                poetry_deps(f"poetry:{g}", body.get("dependencies"))
    return out, notes


@dataclass(frozen=True)
class DepEvent:
    commit: str
    kind: str          # dependency_added | dependency_removed | dependency_version_changed
    ecosystem: str
    manifest: str      # logical manifest path (HEAD path when the manifest survives, else its path at the commit)
    path: str          # manifest path at the commit (new side)
    group: str
    name: str
    before: str | None
    after: str | None
    change: Change

    @property
    def symbol(self) -> str:
        return f"dep::{self.ecosystem}:{self.manifest}:{self.group}:{self.name}"


def diff_entries(before: Entries, after: Entries) -> list[tuple[str, str, str, str | None, str | None]]:
    out: list[tuple[str, str, str, str | None, str | None]] = []
    for key in sorted(set(before) | set(after)):
        b, a = before.get(key), after.get(key)
        if b is None and a is not None:
            out.append(("dependency_added", key[0], key[1], None, a))
        elif a is None and b is not None:
            out.append(("dependency_removed", key[0], key[1], b, None))
        elif a != b:
            out.append(("dependency_version_changed", key[0], key[1], b, a))
    return out


def _changes(log: HistoryLog, flt: Filters) -> tuple[list[tuple[Commit, Change, str]], Counter[str]]:
    skipped: Counter[str] = Counter()
    out = []
    for c in log.commits:
        if c.is_merge:
            continue
        for ch in c.changes:
            kind = manifest_kind(ch.path) or (manifest_kind(ch.old_path) if ch.old_path else None)
            if kind is None:
                if flt.generated_rule(ch.path) and ch.path.rsplit("/", 1)[-1] in flt.spec.generated_basenames:
                    skipped["lockfile_changes"] += 1
                continue
            if log.config.filters.exclude_generated_from_patterns and flt.is_generated(ch.path):
                skipped["generated_manifest_changes"] += 1
                continue
            out.append((c, ch, kind))
    return out, skipped


def manifest_events(log: HistoryLog) -> tuple[list[DepEvent], dict[str, Any]]:
    """Structured dependency events (also used by milestone selection). Returns (events, report)."""
    events, report, _ = _events(log, with_check=False)
    return events, report


def _events(log: HistoryLog, with_check: bool) -> tuple[list[DepEvent], dict[str, Any], dict[tuple[str, str, str], tuple[bool, str]]]:
    flt = Filters(log.config.filters)
    items, skipped = _changes(log, flt)
    warnings: list[dict[str, str]] = []
    notes: Counter[str] = Counter()
    events: list[DepEvent] = []
    checks: dict[tuple[str, str, str], tuple[bool, str]] = {}
    with open_runner(log.repo, log.config) as runner:
        alive = set(ls_tree_paths(runner, log.repo.sha))
        ids = identities(log, alive)
        blob_ids = [b.encode() for _, ch, _ in items for b in (ch.blob_before, ch.blob_after) if b and set(b) != {"0"}]
        blobs = read_objects(runner, blob_ids)
        tree_reads: dict[bytes, bytes | None] = {}
        tree_oids: dict[tuple[str, bytes], str | None] = {}
        if with_check:
            names = []
            for c, ch, _ in items:
                if ch.status != "D":
                    names.append(c.sha.encode() + b":" + encode_path(ch.path, ch.non_utf8))
                if c.parents and ch.status not in ("A", "C"):
                    names.append(c.parents[0].encode() + b":" + encode_path(ch.old_path or ch.path, ch.non_utf8))
            tree_reads = read_objects(runner, names)
            tree_oids = resolve_blobs(runner, [(n.split(b":", 1)[0].decode(), n.split(b":", 1)[1]) for n in names])
    parsed_cache: dict[tuple[str, bytes], Entries] = {}

    def parse(kind: str, data: bytes | None) -> Entries:
        if data is None:
            return {}
        key = (kind, data)
        if key not in parsed_cache:
            parsed_cache[key] = parse_manifest(kind, data)[0]
        return parsed_cache[key]

    for c, ch, kind in items:
        old_kind = manifest_kind(ch.old_path) if ch.old_path else kind
        new_kind = manifest_kind(ch.path)
        before_blob = ch.blob_before if ch.status not in ("A", "C") else None
        after_blob = ch.blob_after if ch.status != "D" else None
        try:
            b_data = blobs.get(before_blob.encode()) if before_blob else None
            a_data = blobs.get(after_blob.encode()) if after_blob else None
            before = parse(old_kind, b_data) if old_kind and b_data is not None else {}
            after = parse(new_kind, a_data) if new_kind and a_data is not None else {}
            if before_blob and b_data is None or after_blob and a_data is None:
                raise ManifestError("blob not readable")
            if a_data is not None and new_kind:
                for n in parse_manifest(new_kind, a_data)[1]:
                    notes["option, URL or path lines not tracked" if "lines not tracked" in n else "duplicate entry"] += 1
        except ManifestError as e:
            warnings.append({"commit": c.sha, "path": ch.path, "error": str(e)})
            continue
        hp = ids.head_path(c.sha, ch.path) if ch.status != "D" else None
        logical = hp or ch.path
        eco = ecosystem(new_kind or old_kind or kind)
        diffs = diff_entries(before, after)
        for ek, group, name, b, a in diffs:
            events.append(DepEvent(c.sha, ek, eco, logical, ch.path, group, name, b, a, ch))
        if with_check and diffs:
            ok, detail = _check(c, ch, old_kind, new_kind, tree_reads, tree_oids, diffs)
            checks[(c.sha, ch.path, "")] = (ok, detail)
    report = {"manifest_changes": len(items), "events": len(events), "unparseable": warnings,
              "skipped": dict(skipped), "notes": dict(notes),
              "events_by_kind": dict(Counter(e.kind for e in events))}
    return events, report, checks


def _check(c: Commit, ch: Change, old_kind: str | None, new_kind: str | None,
           tree: Mapping[bytes, bytes | None], oids: Mapping[tuple[str, bytes], str | None],
           diffs: Sequence[tuple[str, str, str, str | None, str | None]]) -> tuple[bool, str]:
    a_data = tree.get(c.sha.encode() + b":" + encode_path(ch.path, ch.non_utf8)) if ch.status != "D" else None
    b_data = None
    if c.parents and ch.status not in ("A", "C"):
        b_data = tree.get(c.parents[0].encode() + b":" + encode_path(ch.old_path or ch.path, ch.non_utf8))
    want_a = ch.blob_after if ch.status != "D" else None
    want_b = ch.blob_before if ch.status not in ("A", "C") else None
    got_a = oids.get((c.sha, encode_path(ch.path, ch.non_utf8))) if ch.status != "D" else None
    got_b = None
    if c.parents and ch.status not in ("A", "C"):
        got_b = oids.get((c.parents[0], encode_path(ch.old_path or ch.path, ch.non_utf8)))
    if got_a != want_a or got_b != want_b:
        return False, "tree lookup gives different manifest blobs than the cited change"
    try:
        before = parse_manifest(old_kind, b_data)[0] if old_kind and b_data is not None else {}
        after = parse_manifest(new_kind, a_data)[0] if new_kind and a_data is not None else {}
    except ManifestError as e:
        return False, f"re-parse failed: {e}"
    again = diff_entries(before, after)
    if again != list(diffs):
        return False, "re-parse of both manifests gives different entry changes"
    return True, "cat-file <commit>:<path> and <parent>:<path> re-read, blob ids match, re-parse gives the same entries"


def _statement(e: DepEvent, c: Commit) -> str:
    s = c.sha[:12]
    where = f"{e.path} ({e.group})"
    if e.kind == "dependency_added":
        return f"Commit {s} added {e.name} {e.after or ''}".rstrip() + f" to {where}."
    if e.kind == "dependency_removed":
        return f"Commit {s} removed {e.name} from {where}."
    return f"Commit {s} changed {e.name} in {where} from {e.before or '(none)'} to {e.after or '(none)'}."


def manifest_changes(log: HistoryLog, *, ctx: RunContext | None = None) -> HistoryResult:
    ctx = ctx or default_context(log.repo.repo, log.repo.sha)
    flt = Filters(log.config.filters)
    events, report, checks = _events(log, with_check=log.config.verify)
    params = {**log.ingest_parameters(), "manifests": {"basenames": list(MANIFEST_BASENAMES),
                                                       "requirements_glob": REQUIREMENTS_GLOB,
                                                       "npm_sections": list(NPM_SECTIONS),
                                                       "pyproject": ["project.dependencies", "project.optional-dependencies",
                                                                     "dependency-groups", "tool.poetry"],
                                                       "pipfile": ["packages", "dev-packages"],
                                                       "parsers": "json, tomllib, requirements line reader",
                                                       "name_normalization": "PEP 503 for pypi"},
              "generated_manifests_skipped": log.config.filters.exclude_generated_from_patterns,
              "filters": flt.criteria()}
    by = log.by_sha
    out: list[Record] = []
    for e in events:
        c = by[e.commit]
        chk = None
        if log.config.verify:
            ok, detail = checks.get((e.commit, e.path, ""), (False, "no check result"))
            chk = {"method": "git_object_check", "establishes": "presence", "result": "pass" if ok else "fail",
                   "detail": detail}
        flags = ["bot_commit"] if flt.is_bot(c.author_name, c.author_email) else []
        if flt.is_generated(e.path):
            flags.append("generated_path")
        if e.change.non_utf8:
            flags.append("non_utf8_path")
        out.append(make_record(
            ctx, claim_kind="relationship", kind=e.kind, granularity="dependency", frm=ep_commit(c.sha),
            to={"entity": "dependency", "symbol": e.symbol}, statement=_statement(e, c), cls="git_object_fact",
            provenance="history:manifest-diff",
            provenance_raw={"ecosystem": e.ecosystem, "manifest": e.manifest, "path": e.path, "group": e.group,
                            "name": e.name, "before": e.before, "after": e.after},
            origin={"kind": "git_object", "commit": c.sha, "paths": [e.path]}, qualifier="manifest entry change",
            citations=[citation(c, [e.change])], anchor={"commit": c.sha}, params=params, max_status="observed",
            flags=flags, check=chk))
    recs = finalize(out)
    report = {"stage": "manifests", "records": len(recs), **report, "parameters": params,
              "observed": sum(1 for r in recs if r["status"] == "observed")}
    return HistoryResult(recs, report)


def iter_dependency_sets(events: Iterable[DepEvent]) -> dict[str, list[DepEvent]]:
    by: dict[str, list[DepEvent]] = {}
    for e in events:
        by.setdefault(e.commit, []).append(e)
    return by


__all__ = ["DepEvent", "ManifestError", "manifest_changes", "manifest_events", "manifest_kind", "parse_manifest"]
