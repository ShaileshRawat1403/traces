"""Read-only views over a stored snapshot.

Every row comes from claims, components or Git objects already on disk. Nothing here
invents a relationship, promotes a status, or treats a history pattern as architecture.
"""
from __future__ import annotations

import heapq
import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from traces.evidence.store import Store

LAYERS = {"frontend", "api", "backend", "data", "infra", "docs", "tests", "other"}
ENTITIES = {"symbol", "file", "component", "route", "operation", "commit", "dependency", "repo"}
STATUSES = ("verified", "observed", "unvalidated", "missing_location", "rejected")
STATUS_WEIGHT = {"verified": 1, "observed": 2, "unvalidated": 5, "missing_location": 8, "rejected": 50}


def _rank_status(status: object) -> int:
    return STATUS_WEIGHT[status] if isinstance(status, str) and status in STATUS_WEIGHT else 9
STRUCTURAL = (
    "routes_to", "renders", "implements_operation", "calls", "imports", "import", "depends_on",
    "binds_handler", "uses_model", "returns_model", "persistence_path",
)
TIMELINE_KINDS = {
    "commit_adds", "commit_deletes", "commit_modifies", "commit_type_changes", "renamed_to", "copied_to",
    "dependency_added", "dependency_removed", "dependency_version_changed", "component_added",
    "reverts", "deleted_soon_after_add", "merged_as",
}
LIFECYCLE_KINDS = TIMELINE_KINDS | {"continues_as", "alias_of", "prefix_moved"}
HTTP_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS")
MAX_SOURCE_LINES = 400
MAX_TRACE_HOPS = 12


class ViewError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


INJECTED_FLAG = "injected_control"


def output_flags(rec: dict[str, Any]) -> list[str]:
    """Record flags for API output. An injected record (a Task 002 negative control fed to the validators, never a
    statement about the repository) always carries `injected_control`, so lists and graphs cannot read it as a repo fact."""
    flags = list(rec.get("flags") or [])
    if rec.get("injected") and INJECTED_FLAG not in flags:
        flags.append(INJECTED_FLAG)
    return flags


def summary(rec: dict[str, Any]) -> dict[str, Any]:
    return {
        "claim_id": rec["claim_id"],
        "claim_kind": rec["claim_kind"],
        "kind": rec.get("relationship_kind") or rec.get("node_kind"),
        "status": rec["status"],
        "label": rec["label"],
        "class": rec["class"],
        "evidence_scope": rec["evidence_scope"],
        "from_symbol": (rec.get("from") or {}).get("symbol"),
        "to_symbol": (rec.get("to") or {}).get("symbol"),
        "statement": rec["statement"],
        "qualifier": rec.get("qualifier"),
        "flags": output_flags(rec),
        "injected": bool(rec.get("injected")),
    }


def _loads(raw: str | None, fallback: Any) -> Any:
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except ValueError:
        return fallback


def load_records(st: Store, snapshot_id: str, *, scopes: set[str] | None = None, kinds: set[str] | None = None,
                 claim_kind: str | None = None) -> list[dict[str, Any]]:
    where, args = ["snapshot_id=?"], [snapshot_id]
    if scopes:
        where.append(f"evidence_scope IN ({','.join('?' * len(scopes))})")
        args.extend(sorted(scopes))
    if kinds:
        where.append(f"kind IN ({','.join('?' * len(kinds))})")
        args.extend(sorted(kinds))
    if claim_kind:
        where.append("claim_kind=?")
        args.append(claim_kind)
    q = f"SELECT record_json FROM claims WHERE {' AND '.join(where)} ORDER BY claim_id"
    return [json.loads(rj) for (rj,) in st.db.execute(q, args)]


def _allowed(status: list[str] | None, include_rejected: bool) -> set[str]:
    allowed = set(status) if status else {s for s in STATUSES if s != "rejected"}
    if include_rejected:
        allowed.add("rejected")
    else:
        allowed.discard("rejected")
    return allowed


def _page(records: list[dict[str, Any]], *, allowed: set[str], offset: int, limit: int) -> dict[str, Any]:
    hidden: Counter[str] = Counter()
    kept = []
    for rec in records:
        if rec.get("status") not in allowed:
            hidden[str(rec.get("status"))] += 1
            continue
        kept.append(rec)
    items = [summary(r) for r in kept[offset:offset + limit]]
    return {"items": items, "total": len(kept), "offset": offset, "limit": limit, "hidden_counts": dict(hidden)}


def _touches(rec: dict[str, Any], files: set[str] | None, target: str | None) -> bool:
    if files is not None:
        ends = {rec.get("from_file"), rec.get("to_file")}
        ends.discard(None)
        fr, to = rec.get("from") or {}, rec.get("to") or {}
        ends.update(x for x in (fr.get("file"), to.get("file")) if x)
        if not ends & files:
            return False
    if target:
        blob = " ".join(str(x) for x in (
            (rec.get("from") or {}).get("symbol"), (rec.get("to") or {}).get("symbol"),
            (rec.get("from") or {}).get("file"), (rec.get("to") or {}).get("file"), rec.get("statement")))
        if target not in blob:
            return False
    return True


def _component_files(st: Store, snapshot_id: str, component: str | None) -> set[str] | None:
    if not component:
        return None
    want = component if component.startswith("component::") else f"component::{component}"
    files: set[str] = set()
    for row in st.list_components(snapshot_id):
        if row["component_id"] == want or row["name"] == component:
            files.update(_loads(row["paths_json"], []))
    return files


def _time_key(rec: dict[str, Any]) -> tuple[int, str]:
    raw = rec.get("provenance_raw") or {}
    t = raw.get("committer_time")
    when = int(t) if isinstance(t, int) else -1
    return (-when, rec["claim_id"])


def history_page(st: Store, snapshot_id: str, *, kinds: set[str], claim_kind: str | None = None,
                 path: str | None = None, component: str | None = None, target: str | None = None,
                 granularity: str | None = None, include_rejected: bool = False,
                 offset: int = 0, limit: int = 100, by_time: bool = False) -> dict[str, Any]:
    files = _component_files(st, snapshot_id, component)
    if path:
        files = {path} if files is None else (files & {path})
    recs = load_records(st, snapshot_id, kinds=kinds, claim_kind=claim_kind)
    if granularity:
        recs = [r for r in recs if r.get("granularity") == granularity]
    recs = [r for r in recs if _touches(r, files, target)]
    recs.sort(key=_time_key if by_time else (lambda r: r["claim_id"]))
    return _page(recs, allowed=_allowed(None, include_rejected), offset=offset, limit=limit)


def components_view(st: Store, snapshot_id: str) -> list[dict[str, Any]]:
    rows = st.list_components(snapshot_id)
    file_of: dict[str, str] = {}
    out = []
    for row in rows:
        paths = [p for p in _loads(row["paths_json"], []) if isinstance(p, str)]
        for p in paths:
            file_of[p] = row["component_id"]
        layer = row["layer"] if row["layer"] in LAYERS else "other"
        out.append({"id": row["component_id"], "name": row["name"], "layer": layer, "kind": row["kind"] or "directory",
                    "paths": paths, "rule": row["rule"], "claim_counts": {}})
    by_id = {c["id"]: c for c in out}
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for (ff, tf, status) in st.db.execute("SELECT from_file, to_file, status FROM claims WHERE snapshot_id=?", (snapshot_id,)):
        seen = set()
        for f in (ff, tf):
            cid = file_of.get(f) if f else None
            if cid and cid not in seen:
                counts[cid][status] += 1
                seen.add(cid)
    for cid, c in counts.items():
        by_id[cid]["claim_counts"] = dict(c)
    return out


def _method_and_path(rec: dict[str, Any]) -> tuple[str, str]:
    raw = rec.get("provenance_raw") or {}
    row = raw.get("row") if isinstance(raw.get("row"), dict) else {}
    text = " ".join(str(x) for x in (
        raw.get("route_local_path"), row.get("name") if isinstance(row, dict) else None,
        (rec.get("from") or {}).get("symbol"), rec.get("statement")) if x)
    method = "UNKNOWN"
    for m in HTTP_METHODS:
        if f"{m} " in text or text.startswith(m + " ") or f"@{m.lower()}(" in text.lower() or f".{m.lower()}(" in text.lower():
            method = m
            break
    path = raw.get("route_local_path") or (row.get("name") if isinstance(row, dict) else None) or ""
    if not isinstance(path, str) or not path.startswith("/"):
        for token in text.replace("'", " ").replace('"', " ").split():
            if token.startswith("/") and not token.startswith("//"):
                path = token.rstrip(".,)")
                break
        else:
            path = path if isinstance(path, str) and path else "(path not recorded)"
    if path == method or path.startswith(method + " "):
        rest = path.split(" ", 1)
        path = rest[1] if len(rest) == 2 else "(path not recorded)"
    return method, path


def _line_of(rec: dict[str, Any]) -> tuple[str, int]:
    fr = rec.get("from") or {}
    locs = rec.get("locations") or []
    file = fr.get("file") or (locs[0].get("file") if locs else "") or ""
    line = fr.get("start_line") or (locs[0].get("start_line") if locs else 1) or 1
    try:
        line = int(line)
    except (TypeError, ValueError):
        line = 1
    return str(file), max(1, line)


def routes_view(st: Store, snapshot_id: str) -> list[dict[str, Any]]:
    """Route inventory from stored route nodes and routes_to claims. No source scan, so a missing method stays UNKNOWN."""
    items = []
    seen: set[tuple[str, str, str]] = set()
    nodes = load_records(st, snapshot_id, kinds={"route"}, claim_kind="node")
    edges = load_records(st, snapshot_id, kinds={"routes_to"}, claim_kind="relationship")
    for rec in nodes + edges:
        if rec.get("status") == "rejected":
            continue
        method, path = _method_and_path(rec)
        file, line = _line_of(rec)
        handler = (rec.get("to") or {}).get("symbol") if rec.get("relationship_kind") == "routes_to" else (rec.get("from") or {}).get("symbol")
        key = (method, path, handler or "")
        if key in seen:
            continue
        seen.add(key)
        flags = list(rec.get("flags") or [])
        row = (rec.get("provenance_raw") or {}).get("row") or {}
        if method == "UNKNOWN" and isinstance(row, dict) and str(row.get("name") or "").startswith("USE "):
            method = "USE"  # O-7: an app.use()/router.use() mount as recorded, not an HTTP operation with an unknown method
            flags.append("mount")
        if method == "UNKNOWN" and "method_not_recorded" not in flags:
            flags.append("method_not_recorded")
        items.append({
            "method": method, "path": path, "handler_symbol": handler, "operation_id": None,
            "file": file or "(file not recorded)", "line": line, "status": rec["status"],
            "claim_id": rec["claim_id"], "flags": flags,
        })
    items.sort(key=lambda r: (r["path"], r["method"], r["claim_id"]))
    return items


def _fact(text: str, kind: str, claim_ids: list[str] | None = None) -> dict[str, Any]:
    return {"text": text, "kind": kind, "claim_ids": claim_ids or []}


def _readme_heading(checkout: Path | None, sha: str) -> tuple[str, str] | None:
    """Return ('heading', text) for the first Markdown heading, else ('line', text) for the first
    prose line. HTML banners are not headings. The text is a quote, not a verified capability."""
    if checkout is None or not checkout.exists():
        return None
    if not (checkout / ".git").exists() and not (checkout / "HEAD").exists():
        return None
    for name in ("README.md", "readme.md", "README.rst", "README"):
        try:
            text = _git_blob(checkout, sha, name)
        except ViewError:
            continue
        fallback: str | None = None
        for line in text.splitlines():
            raw = line.strip()
            if not raw or raw.startswith("<"):
                continue
            if raw.startswith("#"):
                heading = raw.lstrip("#").strip()
                if heading:
                    return ("heading", heading[:240])
            if fallback is None:
                fallback = raw[:240]
        if fallback:
            return ("line", fallback)
    return None


def overview_view(st: Store, snap: dict[str, Any], *, repo_name: str, checkout: Path | None = None) -> dict[str, Any]:
    languages = _loads(snap.get("languages_json"), {})
    frameworks = _loads(snap.get("frameworks_json"), [])
    stats = _loads(snap.get("stats_json"), {})
    by_status = st.status_counts(snap["id"])
    comps = components_view(st, snap["id"])
    routes = routes_view(st, snap["id"])
    sha = snap["sha"]
    business = [
        _fact("What this software is for is not verified from code structure. File names and frameworks are not a business description.", "unknown"),
    ]
    heading = _readme_heading(checkout, sha)
    if heading:
        kind, text = heading
        label = "README heading" if kind == "heading" else "First README line"
        business.append(_fact(f'{label} at this commit: "{text}". That is documentation text, not a verified capability.', "interpretation"))
    else:
        business.append(_fact("No README heading was read for this snapshot (no local checkout, or the file is absent).", "unknown"))

    architecture = [
        _fact(f"Snapshot {sha} of {repo_name} is pinned. Counts below are from stored evidence and the deterministic component rules, not from running the software.", "fact"),
    ]
    if comps:
        layers = Counter(c["layer"] for c in comps)
        layer_txt = ", ".join(f"{n} {layer}" for layer, n in sorted(layers.items()))
        architecture.append(_fact(f"{len(comps)} components from rule dir-v1 ({layer_txt}).", "fact"))
    else:
        architecture.append(_fact("No components are stored for this snapshot. It may not have been indexed.", "unknown"))
    if frameworks:
        architecture.append(_fact("Dependency manifests name: " + ", ".join(str(f) for f in frameworks) + ". A named library is not a verified architecture edge.", "fact"))
    else:
        architecture.append(_fact("No framework was read from a dependency manifest for this snapshot.", "unknown"))

    impl = []
    if languages:
        lang_txt = ", ".join(f"{n} {name}" for name, n in sorted(languages.items(), key=lambda kv: (-kv[1], kv[0])))
        impl.append(_fact(f"Files by language: {lang_txt}.", "fact"))
    else:
        impl.append(_fact("No language counts are stored for this snapshot.", "unknown"))
    if by_status:
        bits = ", ".join(f"{by_status[s]} {s}" for s in STATUSES if by_status.get(s))
        impl.append(_fact(f"Stored evidence by status: {bits}. Rejected claims stay in the store and are hidden from the default graph.", "fact"))
    else:
        impl.append(_fact("No evidence records are stored for this snapshot.", "unknown"))
    hist = stats.get("history") if isinstance(stats, dict) else None
    if isinstance(hist, dict) and hist.get("state"):
        impl.append(_fact(f"History step state: {hist.get('state')}. A skipped or failed history step does not remove the static evidence.", "fact"))

    entry = []
    if routes:
        entry.append(_fact(f"{len(routes)} route or operation records are stored. Methods marked UNKNOWN were not on the record.", "fact",
                           [r["claim_id"] for r in routes[:8] if r.get("claim_id")]))
    else:
        entry.append(_fact("No route nodes or routes_to claims are stored. That is an absence of records, not proof the software has no HTTP routes.", "unknown"))

    verified = by_status.get("verified", 0)
    start = [_fact(
        "Start with the graph filtered to verified and observed. A verified edge passed an independent check. "
        "Unvalidated, missing-location and library-contract steps are not established architecture. "
        "Co-change and hotspots are history patterns, not code dependencies and not causes.",
        "interpretation")]
    if verified:
        start.append(_fact(f"{verified} claims are verified on this snapshot.", "fact"))
    else:
        start.append(_fact("Nothing on this snapshot is verified yet.", "unknown"))

    counts = {"claims": sum(by_status.values()), "components": len(comps), "routes": len(routes), **{s: by_status.get(s, 0) for s in STATUSES}}
    files = stats.get("files") if isinstance(stats, dict) else None
    if isinstance(files, int):
        counts["files"] = files
    return {
        "snapshot_id": snap["id"],
        "business": business,
        "architecture": architecture,
        "implementation": impl,
        "entry_points": entry,
        "start_here": start,
        "languages": {str(k): int(v) for k, v in languages.items() if isinstance(v, int)},
        "counts": counts,
    }


def _layer_of_files(comps: list[dict[str, Any]]) -> dict[str, str]:
    out = {}
    for c in comps:
        for p in c["paths"]:
            out[p] = c["layer"]
    return out


def _component_of_files(comps: list[dict[str, Any]]) -> dict[str, str]:
    out = {}
    for c in comps:
        for p in c["paths"]:
            out[p] = c["id"]
    return out


def _entity(ep: dict[str, Any] | None) -> str:
    e = (ep or {}).get("entity") or "symbol"
    return e if e in ENTITIES else "symbol"


def _node(nid: str, ep: dict[str, Any], layer: str | None) -> dict[str, Any]:
    short = nid.split("::")[-1] or nid
    return {"id": nid, "label": short[:160], "entity": _entity(ep), "layer": layer, "file": ep.get("file"), "degree": 0}


def graph_view(st: Store, snapshot_id: str, *, focus: str | None = None, depth: int = 1, layer: list[str] | None = None,
               rel: list[str] | None = None, status: list[str] | None = None, q: str | None = None,
               include_rejected: bool = False, limit: int = 300) -> dict[str, Any]:
    """Architecture graph: static relationships only. History patterns are a different view."""
    allowed = _allowed(status, include_rejected)
    comps = components_view(st, snapshot_id)
    file_layer = _layer_of_files(comps)
    file_comp = _component_of_files(comps)
    want_layer = set(layer or [])
    want_rel = set(rel or [])
    needle = (q or "").strip().lower()
    # Filters first, then the status split, so hidden_counts describe what this request would otherwise have shown.
    hidden_recs: list[dict[str, Any]] = []
    edges_all = []
    for rec in load_records(st, snapshot_id, scopes={"static"}, claim_kind="relationship"):
        src = (rec.get("from") or {}).get("symbol")
        dst = (rec.get("to") or {}).get("symbol")
        if not src or not dst:
            continue
        kind = rec.get("relationship_kind") or ""
        if want_rel and kind not in want_rel:
            continue
        files = [(rec.get("from") or {}).get("file"), (rec.get("to") or {}).get("file")]
        layers = {file_layer.get(f) for f in files if f}
        if want_layer and not (layers & want_layer):
            continue
        if needle:
            blob = " ".join(str(x) for x in (rec.get("statement"), kind, src, dst, *files)).lower()
            if needle not in blob:
                continue
        if rec.get("status") not in allowed:
            hidden_recs.append(rec)
            continue
        edges_all.append(rec)

    by_src: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_dst: dict[str, list[dict[str, Any]]] = defaultdict(list)
    nodes_eps: dict[str, dict[str, Any]] = {}
    for rec in edges_all:
        src_ep, dst_ep = rec.get("from") or {}, rec.get("to") or {}
        src, dst = src_ep["symbol"], dst_ep["symbol"]
        by_src[src].append(rec)
        by_dst[dst].append(rec)
        nodes_eps.setdefault(src, src_ep)
        nodes_eps.setdefault(dst, dst_ep)

    by_comp = {c["id"]: c for c in comps}
    chosen = edges_all
    focus_id: str | None = None
    focus_ep: dict[str, Any] | None = None
    focus_scope: set[str] | None = None  # symbols whose hidden edges count toward hidden_counts when focused
    neighbourhood_rule = False  # symbol focus: a hidden edge counts only with both ends in scope, as shown edges do
    if focus:
        focus_id = _resolve(focus, set(nodes_eps))
        comp_focus = by_comp.get(focus) if focus_id is None else None
        if focus_id is None and comp_focus is None:
            chosen = []
        elif comp_focus is not None:
            members = {
                sym
                for sym, ep in nodes_eps.items()
                if isinstance(raw_file := ep.get("file"), str) and file_comp.get(raw_file) == comp_focus["id"]
            }
            chosen = [
                r for r in edges_all
                if (r.get("from") or {}).get("symbol") in members or (r.get("to") or {}).get("symbol") in members
            ]
            focus_scope = members | {
                sym for r in hidden_recs for ep in (r.get("from") or {}, r.get("to") or {})
                if isinstance(sym := ep.get("symbol"), str) and isinstance(f := ep.get("file"), str)
                and file_comp.get(f) == comp_focus["id"]
            }
            focus_id = None
        else:
            assert focus_id is not None
            focus_ep = nodes_eps.get(focus_id)
            depth = max(0, min(4, depth))
            seen = _neighbourhood(focus_id, depth, by_src, by_dst)
            if depth == 0:
                chosen = []
                focus_scope = {focus_id}
                neighbourhood_rule = True  # depth 0 shows no edges, so none counts as hidden either
            else:
                chosen = [r for r in edges_all if (r.get("from") or {}).get("symbol") in seen and (r.get("to") or {}).get("symbol") in seen]
                # F5 consistency: a hidden edge counts when it is exactly an edge that showing its status would add, i.e.
                # both ends in the neighbourhood computed with the hidden edges included (the same rule as the shown edges)
                h_src, h_dst = defaultdict(list, {k: list(v) for k, v in by_src.items()}), defaultdict(list, {k: list(v) for k, v in by_dst.items()})
                for rec in hidden_recs:
                    a, b = (rec.get("from") or {}).get("symbol"), (rec.get("to") or {}).get("symbol")
                    if a and b:
                        h_src[a].append(rec)
                        h_dst[b].append(rec)
                focus_scope = _neighbourhood(focus_id, depth, h_src, h_dst)
                neighbourhood_rule = True

    # hidden_counts are scoped like the edges: the whole (filtered) snapshot when unfocused, otherwise only hidden
    # edges that touch the focused neighbourhood or component (F5).
    def ends(rec: dict[str, Any]) -> tuple[str | None, str | None]:
        return (rec.get("from") or {}).get("symbol"), (rec.get("to") or {}).get("symbol")

    if not focus:
        scope_hidden = hidden_recs
    elif focus_scope is None:
        scope_hidden = []
    else:
        scope_hidden = [r for r in hidden_recs if (all if neighbourhood_rule else any)(e in focus_scope for e in ends(r))]
    hidden: Counter[str] = Counter(str(r.get("status")) for r in scope_hidden)

    def rank(rec: dict[str, Any]) -> tuple[int, int, str]:
        kind = rec.get("relationship_kind") or ""
        structural = STRUCTURAL.index(kind) if kind in STRUCTURAL else len(STRUCTURAL)
        return (_rank_status(rec.get("status")), structural, rec["claim_id"])

    chosen.sort(key=rank)
    truncated = len(chosen) > limit
    # edges cut by the limit are counted by status, so e.g. rejected edges sorted last are never silently lost (F4)
    truncated_counts: Counter[str] = Counter(str(r.get("status")) for r in chosen[limit:])
    chosen = chosen[:limit]

    deg: Counter[str] = Counter()
    edges = []
    keep_nodes: dict[str, dict[str, Any]] = {}
    if focus_id and focus_ep:
        keep_nodes[focus_id] = focus_ep
    for rec in chosen:
        src_ep, dst_ep = rec.get("from") or {}, rec.get("to") or {}
        src, dst = src_ep["symbol"], dst_ep["symbol"]
        deg[src] += 1
        deg[dst] += 1
        keep_nodes.setdefault(src, src_ep)
        keep_nodes.setdefault(dst, dst_ep)
        edges.append({
            "id": rec["claim_id"], "source": src, "target": dst, "kind": rec.get("relationship_kind") or "",
            "status": rec["status"], "label": rec["label"], "qualifier": rec.get("qualifier"),
            "flags": output_flags(rec), "injected": bool(rec.get("injected")),
        })

    nodes: list[dict[str, Any]] = []
    comp_ids: set[str] = set()
    for nid, ep in sorted(keep_nodes.items()):
        f = ep.get("file")
        layer_name = file_layer.get(f) if f else None
        nodes.append(_node(nid, ep, layer_name))
        cid = file_comp.get(f) if f else None
        if cid:
            comp_ids.add(cid)
    by_comp = {c["id"]: c for c in comps}
    for cid in sorted(comp_ids):
        c = by_comp[cid]
        nodes.append({"id": c["id"], "label": c["name"], "entity": "component", "layer": c["layer"], "file": None, "degree": 0})
    for node in nodes:
        node["degree"] = int(deg.get(str(node["id"]), 0))
    return {"snapshot_id": snapshot_id, "nodes": nodes, "edges": edges, "hidden_counts": dict(hidden),
            "truncated": truncated, "truncated_counts": dict(truncated_counts), "limit": limit}


def _resolve(query: str, nodes: set[str]) -> str | None:
    if query in nodes:
        return query
    exact = [n for n in nodes if n.endswith(f"::{query}") or n == f"file::{query}"]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        return sorted(exact, key=lambda n: (len(n), n))[0]
    loose = [n for n in nodes if query in n]
    if len(loose) == 1:
        return loose[0]
    return None


def _hop(i: int, rec: dict[str, Any] | None, frm: str, to: str, *, gap: str | None = None) -> dict[str, Any]:
    if gap is not None or rec is None:
        return {"index": i, "type": "gap", "claim_id": None, "from_symbol": frm, "to_symbol": to, "kind": "gap",
                "status": "unvalidated", "label": "inferred", "reason": gap or "no recorded static relationship",
                "qualifier": None, "evidence_scope": "static"}
    flags = list(rec.get("flags") or [])
    kind = rec.get("relationship_kind") or ""
    library = kind == "library_contract" or "library_contract" in flags
    reason = None
    if library:
        reason = rec.get("qualifier") or rec.get("status_reason") or "Library behavior. Not independently verified as a source-level call."
    return {"index": i, "type": "library_contract" if library else "edge", "claim_id": rec["claim_id"],
            "from_symbol": (rec.get("from") or {}).get("symbol") or frm, "to_symbol": (rec.get("to") or {}).get("symbol") or to,
            "kind": kind, "status": rec["status"], "label": rec["label"], "reason": reason,
            "qualifier": rec.get("qualifier"), "evidence_scope": "static", "injected": bool(rec.get("injected"))}


def _neighbourhood(start: str, depth: int, by_src: dict[str, list[dict[str, Any]]], by_dst: dict[str, list[dict[str, Any]]]) -> set[str]:
    seen = {start}
    frontier = {start}
    for _ in range(depth):
        nxt: set[str] = set()
        for cur in frontier:
            for rec in by_src.get(cur, []) + by_dst.get(cur, []):
                for ep in (rec.get("from") or {}, rec.get("to") or {}):
                    sym = ep.get("symbol")
                    if sym and sym not in seen:
                        nxt.add(sym)
        seen |= nxt
        frontier = nxt
        if not frontier:
            break
    return seen


def trace_view(st: Store, snapshot_id: str, *, frm: str, to: str | None, include_rejected: bool = False) -> dict[str, Any]:
    """Shortest static path. Rejected claims are not bridges. Library-contract hops stay labeled as such."""
    allowed = _allowed(None, include_rejected)
    hidden: Counter[str] = Counter()
    outgoing: dict[str, list[tuple[int, str, dict[str, Any]]]] = defaultdict(list)
    nodes: set[str] = set()
    for rec in load_records(st, snapshot_id, scopes={"static"}, claim_kind="relationship"):
        if rec.get("status") not in allowed:
            hidden[str(rec.get("status"))] += 1
            continue
        src = (rec.get("from") or {}).get("symbol")
        dst = (rec.get("to") or {}).get("symbol")
        if not src or not dst or src == dst:
            continue
        nodes.add(src)
        nodes.add(dst)
        w = _rank_status(rec.get("status"))
        heap_id = rec["claim_id"]
        prev = outgoing[src]
        # keep the strongest edge between the same pair
        weaker = [i for i, (_w, d, old) in enumerate(prev) if d == dst and (_w, old["claim_id"]) >= (w, heap_id)]
        if any(d == dst and (_w, old["claim_id"]) <= (w, heap_id) for _w, d, old in prev):
            continue
        for i in reversed(weaker):
            prev.pop(i)
        prev.append((w, dst, rec))

    start = _resolve(frm, nodes)
    goal = _resolve(to, nodes) if to else None
    hops: list[dict[str, Any]] = []
    if start is None:
        hops = [_hop(0, None, frm, to or frm, gap=f"No stored static symbol matches {frm!r}.")]
    elif to and goal is None:
        hops = [_hop(0, None, start, to, gap=f"No stored static symbol matches {to!r}.")]
    elif to and goal is not None:
        found = _shortest(outgoing, start, goal)
        hops = found if found is not None else [_hop(
            0, None, start, goal,
            gap="No recorded static relationship connects these symbols. Absence is not proof they are unrelated.")]
    else:
        recs = sorted((rec for _w, _d, rec in outgoing.get(start, [])), key=lambda r: (_rank_status(r.get("status")), r["claim_id"]))
        hops = [_hop(i, rec, start, (rec.get("to") or {}).get("symbol") or start) for i, rec in enumerate(recs[:MAX_TRACE_HOPS])]
        if not hops:
            hops = [_hop(0, None, start, start, gap="This symbol has no outgoing static relationship in the store.")]
    # F-9: a step whose outgoing calls are stored only as unresolved references is not fully traced. Each such step gets
    # a gap that names them, and an edge hop that is not verified or observed also keeps the trace from being complete.
    steps = [start] if start is not None and not to else []
    steps += [h["from_symbol"] for h in hops if h["type"] != "gap"]
    unresolved = _unresolved_calls(st, snapshot_id, set(steps), include_rejected) if steps else {}
    for sym in dict.fromkeys(steps):
        names = unresolved.get(sym)
        if names:
            shown = ", ".join(names[:MAX_UNRESOLVED_NAMES]) + (f", and {len(names) - MAX_UNRESOLVED_NAMES} more" if len(names) > MAX_UNRESOLVED_NAMES else "")
            g = _hop(len(hops), None, sym, "(unresolved)", gap=(
                f"{len(names)} outgoing call(s) from this step are recorded only as unresolved references ({shown}): the "
                "extractor did not resolve them to a declaration, so the trace cannot follow them. They may lead to other code."))
            g["unresolved_calls"] = names
            hops.append(g)
    weak = [h for h in hops if h["type"] == "edge" and h["status"] not in ("verified", "observed")]
    incomplete: list[str] = []
    if any(h["type"] == "gap" for h in hops):
        incomplete.append("gaps: " + str(sum(1 for h in hops if h["type"] == "gap")))
    if weak:
        incomplete.append(f"{len(weak)} step(s) rest on relationships that are not verified or observed")
    for i, h in enumerate(hops):
        h["index"] = i
    return {"snapshot_id": snapshot_id, "from_symbol": start or frm, "to_symbol": goal or to, "hops": hops,
            "hidden_counts": dict(hidden), "complete": not incomplete, "incomplete_reasons": incomplete}


MAX_UNRESOLVED_NAMES = 5


def _unresolved_calls(st: Store, snapshot_id: str, symbols: set[str], include_rejected: bool) -> dict[str, list[str]]:
    """Unresolved call references stored for these source symbols, by symbol (sorted, unique names)."""
    out: dict[str, set[str]] = defaultdict(set)
    for rec in load_records(st, snapshot_id, scopes={"static"}, claim_kind="unresolved_reference"):
        sym = (rec.get("from") or {}).get("symbol")
        if sym not in symbols or (rec.get("status") == "rejected" and not include_rejected):
            continue
        row = (rec.get("provenance_raw") or {}).get("row") or {}
        if row.get("reference_kind") not in ("calls", "instantiates"):
            continue
        name = row.get("reference_name")
        if isinstance(name, str) and name and name != "require":  # require() is the module import, checked as `imports`
            out[sym].add(name[:200])
    return {k: sorted(v) for k, v in out.items()}


def _shortest(outgoing: dict[str, list[tuple[int, str, dict[str, Any]]]], start: str, goal: str) -> list[dict[str, Any]] | None:
    if start == goal:
        return []
    # (weight, hops, claim_id tiebreak, node, path)
    pq: list[tuple[int, int, str, str, tuple[dict[str, Any], ...]]] = [(0, 0, "", start, ())]
    best: dict[str, tuple[int, int]] = {start: (0, 0)}
    while pq:
        weight, hops, _tie, node, path = heapq.heappop(pq)
        if best.get(node, (weight, hops)) < (weight, hops):
            continue
        if node == goal and path:
            return [_hop(i, rec, (rec.get("from") or {}).get("symbol") or start, (rec.get("to") or {}).get("symbol") or goal) for i, rec in enumerate(path)]
        if hops >= MAX_TRACE_HOPS:
            continue
        for w, dst, rec in outgoing.get(node, []):
            nw, nh = weight + w, hops + 1
            prev = best.get(dst)
            if prev is not None and prev <= (nw, nh):
                continue
            best[dst] = (nw, nh)
            heapq.heappush(pq, (nw, nh, rec["claim_id"], dst, path + (rec,)))
    return None


def safe_repo_path(path: str) -> str:
    """Validate a repository-relative path from a request. Refuses what could escape the tree or confuse Git (NUL,
    newlines, backslashes, absolute or home-relative paths, `..` components) with a message naming the actual problem.
    A leading `-` is a legal file name (`-rf.py`): paths only ever reach Git inside a `<sha>:<path>` revision argument
    after `--end-of-options`, so they cannot be read as options (security finding F-2)."""
    if not path:
        raise ViewError(422, "invalid_request", "path is required")
    if "\x00" in path or "\n" in path or "\r" in path:
        raise ViewError(422, "invalid_request", "path must not contain NUL or line-break characters")
    if "\\" in path:
        raise ViewError(422, "invalid_request", "path must use forward slashes, not backslashes")
    if path.startswith("/") or path.startswith("~"):
        raise ViewError(422, "invalid_request", "path must be relative to the repository root, not absolute or home-relative")
    parts = [p for p in Path(path).parts if p != "."]
    if any(p == ".." for p in parts):
        raise ViewError(422, "invalid_request", "path must not contain '..' components")
    if not parts:
        raise ViewError(422, "invalid_request", "path must name a file inside the repository")
    return "/".join(parts)


def _git_blob(checkout: Path, sha: str, path: str) -> str:
    if not checkout.exists():
        raise ViewError(404, "not_found", "the pinned checkout is not on this machine; index the snapshot here to read source")
    spec = f"{sha}:{path}"
    try:
        p = subprocess.run(["git", "-C", str(checkout), "cat-file", "blob", "--end-of-options", spec], capture_output=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise ViewError(404, "not_found", f"could not read {path} from the pinned checkout") from e
    if p.returncode != 0:
        raise ViewError(404, "not_found", f"{path} is not in the tree at {sha[:12]}")
    return p.stdout.decode("utf-8", errors="replace")


def _blob_sha(checkout: Path, sha: str, path: str) -> str:
    p = subprocess.run(["git", "-C", str(checkout), "rev-parse", "--verify", "--quiet", "--end-of-options", f"{sha}:{path}"], capture_output=True, text=True, timeout=30, check=False)
    if p.returncode != 0:
        raise ViewError(404, "not_found", f"{path} is not in the tree at {sha[:12]}")
    return p.stdout.strip()


def source_view(st: Store, snap: dict[str, Any], *, path: str, start: int, end: int | None, checkout: Path | None) -> dict[str, Any]:
    rel = safe_repo_path(path)
    if checkout is None:
        raise ViewError(404, "not_found", "the pinned checkout is not on this machine; index the snapshot here to read source")
    text = _git_blob(checkout, snap["sha"], rel)
    lines = text.splitlines()
    total = len(lines)
    if start > max(total, 1):
        raise ViewError(422, "invalid_request", f"start {start} is past the end of {rel} ({total} lines)")
    last = total if end is None else end
    if last < start:
        raise ViewError(422, "invalid_request", "end is before start")
    if last - start + 1 > MAX_SOURCE_LINES:
        raise ViewError(422, "invalid_request", f"source ranges are limited to {MAX_SOURCE_LINES} lines")
    last = min(last, total)
    generated_paths = _loads(snap.get("generated_paths_json"), [])
    generated = rel in generated_paths or any(rel == g or rel.startswith(g.rstrip("/") + "/") for g in generated_paths if isinstance(g, str))
    rows = st.db.execute(
        "SELECT DISTINCT claim_id FROM claim_locations WHERE snapshot_id=? AND file=? AND start_line<=? AND end_line>=? ORDER BY claim_id",
        (snap["id"], rel, last, start)).fetchall()
    return {
        "snapshot_id": snap["id"], "sha": snap["sha"], "path": rel, "blob_sha": _blob_sha(checkout, snap["sha"], rel),
        "start_line": start, "end_line": last if total else start, "total_lines": total,
        "lines": lines[start - 1:last] if total else [], "generated": bool(generated),
        "claim_ids": [r[0] for r in rows],
    }


def _static_identity(rec: dict[str, Any]) -> tuple[Any, ...]:
    return (rec.get("claim_kind"), rec.get("relationship_kind") or rec.get("node_kind"), rec.get("granularity"),
            (rec.get("from") or {}).get("symbol"), (rec.get("to") or {}).get("symbol"))


def compare_view(st: Store, *, base_id: str, head_id: str, limit: int = 200) -> dict[str, Any]:
    """Identity diff of stored static claims. This is not a rename-aware snapshot_diff and it does not write records.

    Items keep the underlying claim id and kind, so they are evidence that already exists. They are not
    snapshot_added or snapshot_removed records (those are produced only when history is given two evidence sets).
    """
    def present(sid: str) -> tuple[dict[tuple[Any, ...], dict[str, Any]], int]:
        out: dict[tuple[Any, ...], dict[str, Any]] = {}
        hidden = 0
        for rec in load_records(st, sid, scopes={"static"}):
            if rec.get("status") == "rejected":
                hidden += 1
                continue
            out.setdefault(_static_identity(rec), rec)
        return out, hidden

    base, base_rej = present(base_id)
    head, head_rej = present(head_id)
    removed = [base[k] for k in sorted(set(base) - set(head), key=repr)]
    added = [head[k] for k in sorted(set(head) - set(base), key=repr)]
    ordered = sorted(added, key=lambda r: (_rank_status(r.get("status")), r["claim_id"]))
    ordered += sorted(removed, key=lambda r: (_rank_status(r.get("status")), r["claim_id"]))
    return {"items": [summary(r) for r in ordered[:limit]], "total": len(ordered), "offset": 0, "limit": limit,
            "hidden_counts": {"rejected": base_rej + head_rej} if (base_rej or head_rej) else {}}
