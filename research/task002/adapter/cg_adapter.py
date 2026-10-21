"""CodeGraph 1.6.2 -> Traces evidence records (traces-evidence/0.2). Task 002 step 4.
Implements task002/spec/ADAPTER_CONTRACT.md v2. CPython 3.14 stdlib only. Reads the index with
mode=ro&immutable=1. Never sets observed or verified. Usage: cg_adapter.py --manifest <manifest.json>
Exit 0 with records.jsonl + report.json, or exit 2 with errors.json and no records (fail closed)."""
import argparse, json, os, re, sqlite3, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import canon, sha256_hex, claim_id, anchor_of, line_count, normalize_file_range, now_ist, git, Blobs, SCHEMA_VERSION, T

ADAPTER = "traces-cg-adapter"
ADAPTER_VERSION = "1.1.0"  # Decision 002-B: claim_id v3, EOF normalization, class rename, exact-duplicate consolidation
OPENED = []          # (path, mode) from the audit hook
ALLOWED_WRITE = []   # absolute prefixes


class AdapterError(Exception):
    def __init__(self, code, detail):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail = code, detail


def audit(event, args):
    if event == "open":
        path, mode = args[0], args[1]
        if isinstance(path, int):
            return
        p = os.path.abspath(os.fsdecode(path))
        m = mode if isinstance(mode, str) else ("r" if mode is None else str(mode))
        OPENED.append((p, m))
        writing = any(c in m for c in "wax+")
        if writing and ALLOWED_WRITE and not any(p.startswith(a) for a in ALLOWED_WRITE):
            raise AdapterError("E_WRITE_SCOPE", f"write attempted outside allowed scope: {p}")


RESOLVER = {  # metadata.resolvedBy -> (normalized, class)  (EVIDENCE_SCHEMA section 8)
    "import": ("codegraph:resolved-import", "statically_derived"),
    "qualified-name": ("codegraph:resolved-qualified", "statically_derived"),
    "instance-method": ("codegraph:resolved-instance", "statically_derived"),
    "function-ref": ("codegraph:resolved-function-ref", "statically_derived"),
    "framework": ("codegraph:resolved-framework", "statically_derived"),
    "exact-match": ("codegraph:name-match", "analyzer_inference"),
    "fuzzy": ("codegraph:fuzzy", "analyzer_inference"),
    "file-path": ("codegraph:resolved-file-path", "statically_derived"),
}
SYNTH = {"jsx-render": "codegraph:synthesized:jsx-render", "tanstack-link": "codegraph:synthesized:tanstack-link"}
COLUMNS = {
    "nodes": ["id", "kind", "name", "qualified_name", "file_path", "language", "start_line", "end_line", "start_column", "end_column", "decorators"],
    "edges": ["id", "source", "target", "kind", "metadata", "line", "col", "provenance"],
    "files": ["path", "content_hash", "language", "generated", "errors"],
    "unresolved_refs": ["id", "from_node_id", "reference_name", "reference_kind", "line", "col", "candidates", "file_path", "status"],
    "project_metadata": ["key", "value"],
    "schema_versions": ["version"],
}
REL_KINDS = {"contains", "imports", "calls", "references", "instantiates", "extends", "navigates"}


def map_edge(row, md):
    """Return (normalized provenance, class, relationship_kind). Raises E_PROVENANCE_UNKNOWN."""
    prov, kind = row["provenance"], row["kind"]
    if kind not in REL_KINDS:
        raise AdapterError("E_PROVENANCE_UNKNOWN", f"edges:{row['id']} unknown edge kind {kind!r}")
    keys = set(md)
    if prov is None:
        if kind == "contains":
            if md:
                raise AdapterError("E_PROVENANCE_UNKNOWN", f"edges:{row['id']} contains edge with metadata {md}")
            return "codegraph:structural", "statically_derived", "contains"
        if md.get("valueRef") is True and "resolvedBy" not in md:
            return "codegraph:value-ref", "statically_derived", kind
        if "synthesizedBy" in keys:
            raise AdapterError("E_PROVENANCE_UNKNOWN", f"edges:{row['id']} synthesizedBy without heuristic provenance")
        rb = md.get("resolvedBy")
        if rb not in RESOLVER:
            raise AdapterError("E_PROVENANCE_UNKNOWN", f"edges:{row['id']} unmapped resolvedBy {rb!r}")
        n, c = RESOLVER[rb]
        return n, c, kind
    if prov == "heuristic":
        sb = md.get("synthesizedBy")
        if sb not in SYNTH:
            raise AdapterError("E_PROVENANCE_UNKNOWN", f"edges:{row['id']} unmapped synthesizedBy {sb!r}")
        rk = "renders" if (sb == "jsx-render" and kind == "calls") else kind
        return SYNTH[sb], "analyzer_inference", rk
    if prov in ("tree-sitter", "scip"):
        rb = md.get("resolvedBy")
        if rb not in RESOLVER:
            raise AdapterError("E_PROVENANCE_UNKNOWN", f"edges:{row['id']} unmapped resolvedBy {rb!r} under provenance {prov}")
        return f"codegraph:{prov}", RESOLVER[rb][1], kind
    raise AdapterError("E_PROVENANCE_UNKNOWN", f"edges:{row['id']} unmapped provenance {prov!r}")


def bad_path(p):
    return (not isinstance(p, str)) or p == "" or p.startswith("/") or p.startswith("../") or "/../" in p or p == ".." or p.endswith("/..") or "\\" in p


class Adapter:
    def __init__(self, manifest_path):
        self.manifest_path = os.path.abspath(manifest_path)
        self.m = json.load(open(self.manifest_path))
        self.run_id = self.m["run_id"]
        self.out = os.path.abspath(self.m["adapter_out"])
        self.at = now_ist()
        self.warnings = []
        self.checks_done = []

    # ---------- preflight and pin checks (section 4) ----------
    def preflight(self):
        env = os.environ
        if env.get("CODEGRAPH_TELEMETRY") != "0" or env.get("DO_NOT_TRACK") != "1":
            raise AdapterError("E_TELEMETRY", f"CODEGRAPH_TELEMETRY={env.get('CODEGRAPH_TELEMETRY')!r} DO_NOT_TRACK={env.get('DO_NOT_TRACK')!r}")
        self.checks_done.append("telemetry env: CODEGRAPH_TELEMETRY=0 DO_NOT_TRACK=1")

    def c41(self):
        cg = self.m["codegraph"]
        pkg = json.load(open(os.path.join(self.m["package_dir"], "package.json")))
        if pkg.get("name") != cg["package"] or pkg.get("version") != cg["version"]:
            raise AdapterError("E_VERSION", f"installed package {pkg.get('name')}@{pkg.get('version')} != {cg['package']}@{cg['version']}")
        lock = json.load(open(self.m["lockfile"]))
        ent = lock["packages"].get("node_modules/" + cg["package"], {})
        if ent.get("version") != cg["version"] or ent.get("integrity") != cg["npm_integrity"]:
            raise AdapterError("E_VERSION", f"lockfile entry {ent.get('version')} {ent.get('integrity')} != manifest {cg['version']} {cg['npm_integrity']}")
        reg = open(self.m["registry_record_log"]).read()
        mm = re.search(r'npm view ' + re.escape(cg["package"]) + r'@' + re.escape(cg["version"]) + r'[^\n]*\n(\{.*?\n\})', reg, re.S)
        if not mm:
            raise AdapterError("E_VERSION", "registry record for the pinned package not found in registry_record_log")
        rec = json.loads(mm.group(1))
        if rec.get("dist.integrity") != cg["npm_integrity"] or rec.get("dist.shasum") != cg["npm_shasum"] or rec.get("version") != cg["version"]:
            raise AdapterError("E_VERSION", f"registry record integrity/shasum {rec.get('dist.integrity')} {rec.get('dist.shasum')} != manifest")
        self.checks_done.append("4.1 package version, lockfile integrity, registry integrity and shasum")

    def open_db(self):
        p = self.m["index_path"]
        if not os.path.exists(p):
            raise AdapterError("E_SCHEMA", f"index not found: {p}")
        self.db = sqlite3.connect(f"file:{p}?mode=ro&immutable=1", uri=True)
        self.db.row_factory = sqlite3.Row

    def meta(self, key):
        try:
            r = self.db.execute("select value from project_metadata where key=?", (key,)).fetchone()
        except sqlite3.OperationalError as e:
            raise AdapterError("E_SCHEMA", f"project_metadata: {e}")
        return None if r is None else r[0]

    def c42(self):
        v = self.meta("indexed_with_version")
        if v != self.m["codegraph"]["version"]:
            raise AdapterError("E_VERSION", f"project_metadata.indexed_with_version={v!r} != {self.m['codegraph']['version']}")
        self.checks_done.append("4.2 indexed_with_version")

    def c43(self):
        try:
            mx = self.db.execute("select max(version) from schema_versions").fetchone()[0]
        except sqlite3.OperationalError as e:
            raise AdapterError("E_SCHEMA", f"schema_versions: {e}")
        if mx != self.m["codegraph"]["schema_version_max"]:
            raise AdapterError("E_VERSION", f"max(schema_versions.version)={mx} != {self.m['codegraph']['schema_version_max']}")
        ev = self.meta("indexed_with_extraction_version")
        if ev != self.m["codegraph"]["extraction_version"]:
            raise AdapterError("E_VERSION", f"indexed_with_extraction_version={ev!r} != {self.m['codegraph']['extraction_version']}")
        self.checks_done.append("4.3 schema max and extraction version")

    def c44(self):
        sha = self.m["repo_sha"]; root = self.m["checkout_path"]
        iac = self.meta("indexed_at_commit")
        if iac != sha:
            raise AdapterError("E_SHA", f"indexed_at_commit={iac} != manifest repo_sha={sha}")
        dp = json.loads(self.meta("indexed_dirty_paths") or "{}")
        if dp.get("paths"):
            raise AdapterError("E_SHA", f"indexed_dirty_paths not empty: {dp.get('paths')[:5]}")
        head = git(root, "rev-parse", "HEAD").strip()
        if head != sha:
            raise AdapterError("E_SHA", f"git rev-parse HEAD={head} != manifest repo_sha={sha}")
        st = git(root, "status", "--porcelain")
        lines = [l for l in st.splitlines() if l.strip()]
        if any(l != "?? .codegraph/" for l in lines):
            raise AdapterError("E_SHA", f"worktree not clean: {lines[:5]}")
        self.checks_done.append("4.4 indexed_at_commit, dirty paths, HEAD, git status")

    def c45(self):
        st = self.meta("index_state"); d = self.meta("index_files_discovered"); a = self.meta("index_files_accounted")
        if st != "complete" or d is None or d != a:
            raise AdapterError("E_INDEX_INCOMPLETE", f"index_state={st} discovered={d} accounted={a}")
        self.checks_done.append(f"4.5 index_state complete, discovered=accounted={d}")

    def c46(self):
        for t, cols in COLUMNS.items():
            info = self.db.execute(f"pragma table_info({t})").fetchall()
            if not info:
                raise AdapterError("E_SCHEMA", f"missing table {t}")
            have = {r[1] for r in info}
            for c in cols:
                if c not in have:
                    raise AdapterError("E_SCHEMA", f"missing column {t}.{c}")
        self.checks_done.append("4.6 tables and columns")

    def c47(self):
        p = self.m["env"]["netprobe_log"]
        if not os.path.exists(p):
            raise AdapterError("E_ISOLATION", f"no per-run probe log at {p}")
        txt = open(p).read()
        m = re.search(r"^PROBE_SUMMARY (.*)$", txt, re.M)
        if not m:
            raise AdapterError("E_ISOLATION", "probe log has no PROBE_SUMMARY line")
        kv = dict(x.split("=", 1) for x in m.group(1).split())
        for k in ("a", "b", "c", "d"):
            if kv.get(k) != "pass":
                raise AdapterError("E_ISOLATION", f"probe ({k}) = {kv.get(k)}")
        me = os.readlink("/proc/self/ns/net")
        if me != kv.get("wrapper_ns") or me == kv.get("outer_ns"):
            raise AdapterError("E_ISOLATION", f"adapter netns {me} not the probed wrapper netns {kv.get('wrapper_ns')} (outer {kv.get('outer_ns')})")
        self.adapter_ns = me
        self.checks_done.append(f"4.7 probe log (a)-(d) pass; adapter netns {me} = wrapper netns, outer {kv.get('outer_ns')}")

    # ---------- mapping ----------
    def run(self):
        os.makedirs(self.out, exist_ok=True)
        self.preflight()
        self.c41(); self.open_db(); self.c42(); self.c43(); self.c44(); self.c45(); self.c46(); self.c47()
        self.blobs = Blobs(self.m["checkout_path"], self.m["repo_sha"])
        q = lambda t: [dict(r) for r in self.db.execute(f"select {', '.join(COLUMNS[t])} from {t} order by rowid")]
        files, nodes, edges, unres = q("files"), q("nodes"), q("edges"), q("unresolved_refs")
        # E_INJECTED on input: no injected marker anywhere in the index rows
        for t, rows in (("nodes", nodes), ("edges", edges), ("unresolved_refs", unres), ("files", files)):
            for r in rows:
                s = canon(r)
                if '"injected"' in s or "validator_inputs" in s:
                    raise AdapterError("E_INJECTED", f"{t} row carries an injected marker: {s[:200]}")
        fmeta = {}
        for f in files:
            if bad_path(f["path"]) or not self.blobs.exists(f["path"]):
                raise AdapterError("E_PATH", f"files.path {f['path']!r} absolute, contains '..', or absent at {self.m['repo_sha']}")
            h = sha256_hex(self.blobs.bytes(f["path"]))
            if h != f["content_hash"]:
                raise AdapterError("E_HASH", f"files.content_hash {f['content_hash']} != sha256(blob {f['path']}) {h}")
            errs = json.loads(f["errors"]) if f["errors"] else []
            fmeta[f["path"]] = {"generated": f["generated"] == 1, "errors": errs}
        self.file_errors = {p: v["errors"] for p, v in fmeta.items() if v["errors"]}
        self.fmeta = fmeta
        by_id = {}
        for n in nodes:
            if bad_path(n["file_path"]) or not self.blobs.exists(n["file_path"]):
                raise AdapterError("E_PATH", f"nodes.file_path {n['file_path']!r} for {n['id']}")
            by_id[n["id"]] = n
        for u in unres:
            if bad_path(u["file_path"]) or not self.blobs.exists(u["file_path"]):
                raise AdapterError("E_PATH", f"unresolved_refs.file_path {u['file_path']!r} for id {u['id']}")
            if u["from_node_id"] not in by_id:
                raise AdapterError("E_DANGLING", f"unresolved_refs:{u['id']} from_node_id {u['from_node_id']} has no node")
        for e in edges:
            for end in ("source", "target"):
                if e[end] not in by_id:
                    raise AdapterError("E_DANGLING", f"edges:{e['id']} {end} {e[end]} has no node")
        recs = []
        for n in nodes:
            recs.append(self.node_record(n))
        for e in edges:
            recs.append(self.edge_record(e, by_id))
        for u in unres:
            recs.append(self.unres_record(u, by_id))
        for r in recs:
            if r["injected"]:
                raise AdapterError("E_INJECTED", f"output record {r['claim_id']} injected")
        recs = self.consolidate(recs)
        recs.sort(key=lambda r: (r["claim_id"], r["origin"]["row_ref"]))
        self.write(recs, files, nodes, edges, unres)
        return recs

    # ---------- record builders ----------
    def endpoint(self, n):
        ep = {"symbol": f"{n['file_path']}::{n['qualified_name']}", "file": n["file_path"], "start_line": n["start_line"], "end_line": n["end_line"]}
        if n["kind"] == "file":  # Decision 002-B ruling 1: normalized end = last addressable line; original kept
            ep["start_line"] = 1
            ep["end_line"] = line_count(self.blobs.text(n["file_path"]))
            ep["original_end_line"] = n["end_line"]
        return ep

    def flags_for(self, path):
        fl = []
        fm = self.fmeta.get(path)
        if fm and fm["generated"]:
            fl.append("generated_file")
        if fm and fm["errors"]:
            fl.append("extractor_file_errors")
        return fl

    def decl_loc(self, n, role):
        if n["kind"] == "file":
            raw = {"file": n["file_path"], "start_line": n["start_line"], "end_line": n["end_line"], "line_base": 1, "col_base": 0,
                   "range_kind": "file", "range_rule": "file", "role": role, "blob_sha": self.blobs.blob_sha(n["file_path"]), "source": "originator", "recovered_by": None}
            return normalize_file_range(raw, self.blobs.text(n["file_path"]))
        if n["kind"] == "route" and n["language"] == "python":
            rule = "decorator_to_body_end"
        elif n["kind"] in ("function", "method", "class", "interface", "component"):
            rule = "header_to_body_end"
        else:
            rule = "binding_statement"
        return {"file": n["file_path"], "start_line": n["start_line"], "end_line": n["end_line"], "start_col": n["start_column"], "end_col": n["end_column"],
                "line_base": 1, "col_base": 0, "range_kind": "declaration", "range_rule": rule, "role": role,
                "blob_sha": self.blobs.blob_sha(n["file_path"]), "source": "originator", "recovered_by": None}

    def base(self, claim_kind, kind_field, kind_value, frm, to, gran, statement, cls, prov, raw, row_ref, locs, status, reason, flags):
        tn = [raw["row"]["reference_name"], raw["row"]["reference_kind"]] if claim_kind == "unresolved_reference" else None
        cid = claim_id(self.m["repo_sha"], claim_kind, kind_value, frm, to, gran, {"name": "codegraph", "version": self.m["codegraph"]["version"]}, anchor_of(locs), tn)
        r = {"schema_version": SCHEMA_VERSION, "claim_id": cid, "run_id": self.run_id, "repo": self.m["repo"], "repo_sha": self.m["repo_sha"],
             "claim_kind": claim_kind, kind_field: kind_value, "granularity": gran, "statement": statement, "class": cls,
             "originator": {"name": "codegraph", "version": self.m["codegraph"]["version"], "role": "extractor"},
             "provenance_raw": raw, "provenance": prov,
             "origin": {"kind": "tool_output", "artifact": os.path.relpath(self.m["index_path"], self.m["checkout_path"]), "row_ref": row_ref},
             "injected": False, "evidence_scope": "static", "qualifier": None, "locations": locs, "checks": [],
             "status": status, "label": "inferred", "status_reason": reason,
             "status_history": [{"from": None, "to": status, "at": self.at, "run_id": self.run_id, "check_ids": [], "by": f"{ADAPTER} {ADAPTER_VERSION}"}],
             "supersedes": None, "visible_to_reviewer": True, "flags": flags}
        if frm:
            r["from"] = frm
        if to:
            r["to"] = to
        return r

    def node_record(self, n):
        ep = self.endpoint(n)
        raw = {"table": "nodes", "row": n}
        if n["kind"] == "route":
            raw["route_local_path"] = n["name"]
        gran = "file" if n["kind"] == "file" else "symbol"
        st = f"CodeGraph reports a {n['kind']} node '{n['name']}' at {n['file_path']}:{n['start_line']}-{n['end_line']}."
        return self.base("node", "node_kind", n["kind"], ep, None, gran, st, "source_backed_declaration", "codegraph:declaration", raw,
                         f"nodes:{n['id']}", [self.decl_loc(n, "from_decl")], "unvalidated", "CodeGraph node; no independent parser_presence check yet", self.flags_for(n["file_path"]))

    def edge_record(self, e, by_id):
        s, t = by_id[e["source"]], by_id[e["target"]]
        md = json.loads(e["metadata"]) if e["metadata"] else {}
        prov, cls, rk = map_edge(e, md)
        raw = {"table": "edges", "row": e, "endpoint_rows": {"source": s, "target": t}}
        frm, to = self.endpoint(s), self.endpoint(t)
        gran = "file" if s["kind"] == "file" else "symbol"
        locs, status, reason = [], "unvalidated", "CodeGraph edge; no independent relationship check yet"
        if e["line"] is None:
            status, reason = "missing_location", "CodeGraph edge has no line (contains or valueRef); node ranges kept in provenance_raw.endpoint_rows for recovery"
        else:
            enclosing = "synthesizedBy" in md or (s["kind"] == "route" and s["language"] in ("tsx", "typescript") and e["line"] == s["start_line"])
            site = {"file": s["file_path"], "start_line": e["line"], "end_line": e["line"], "line_base": 1, "col_base": 0,
                    "range_kind": "enclosing_scope" if enclosing else "site", "range_rule": "expression", "role": "site",
                    "blob_sha": self.blobs.blob_sha(s["file_path"]), "source": "originator", "recovered_by": None}
            if e["col"] is not None:
                site["start_col"] = e["col"]
            locs = [site, self.decl_loc(s, "from_decl"), self.decl_loc(t, "to_decl")]
            if enclosing:
                reason = "CodeGraph edge with enclosing_scope location only; needs a site location (R-enclosing) and an independent relationship check"
        where = f" at {s['file_path']}:{e['line']}" if e["line"] is not None else " (no line)"
        raw_kind = f" (raw kind {e['kind']}, {md.get('synthesizedBy')})" if rk != e["kind"] else ""
        st = f"CodeGraph reports '{s['qualified_name']}' {rk} '{t['qualified_name']}'{where}{raw_kind}."
        return self.base("relationship", "relationship_kind", rk, frm, to, gran, st, cls, prov, raw, f"edges:{e['id']}", locs, status, reason, self.flags_for(s["file_path"]))

    def unres_record(self, u, by_id):
        s = by_id[u["from_node_id"]]
        frm = self.endpoint(s)
        raw = {"table": "unresolved_refs", "row": u}
        site = {"file": u["file_path"], "start_line": u["line"], "end_line": u["line"], "start_col": u["col"], "line_base": 1, "col_base": 0,
                "range_kind": "site", "range_rule": "expression", "role": "site", "blob_sha": self.blobs.blob_sha(u["file_path"]), "source": "originator", "recovered_by": None}
        st = f"CodeGraph reports an unresolved {u['reference_kind']} reference '{u['reference_name']}' from '{s['qualified_name']}' at {u['file_path']}:{u['line']} (status {u['status']})."
        rec = self.base("unresolved_reference", "node_kind", u["reference_kind"], frm, None, "statement", st, "source_backed_declaration", "codegraph:unresolved", raw,
                        f"unresolved_refs:{u['id']}", [site], "unvalidated", "CodeGraph unresolved reference; no independent parser_presence check yet", self.flags_for(u["file_path"]))
        return rec

    # ---------- Decision 002-B ruling 2: exact duplicates consolidate, distinct claims never share an id ----------
    @staticmethod
    def _row_id_free(o):
        if isinstance(o, dict):
            return {k: Adapter._row_id_free(v) for k, v in o.items() if k not in ("id", "row_ref")}
        if isinstance(o, list):
            return [Adapter._row_id_free(v) for v in o]
        return o

    def _claim_content(self, r):
        keep = {k: v for k, v in r.items() if k not in ("origin", "provenance_raw", "status_history", "run_id")}
        return canon([keep, self._row_id_free(r["provenance_raw"]), {k: v for k, v in r["origin"].items() if k != "row_ref"}])

    def consolidate(self, recs):
        groups = {}
        for r in recs:
            groups.setdefault(r["claim_id"], []).append(r)
        out = []
        self.consolidated = []
        def rowkey(r):
            t, _, i = r["origin"]["row_ref"].partition(":")
            return (t, int(i) if i.isdigit() else 0, i)
        for cid, g in groups.items():
            if len(g) == 1:
                out.append(g[0]); continue
            contents = {self._claim_content(r) for r in g}
            if len(contents) != 1:
                raise AdapterError("E_COLLISION", f"{len(g)} distinct claims share {cid}: rows {[r['origin']['row_ref'] for r in g]}")
            g = sorted(g, key=rowkey)
            keep = g[0]
            keep["consolidation"] = {"rule": "exact duplicate: identical claim content and identical originator rows except the row id (Decision 002-B ruling 2)",
                                     "count": len(g),
                                     "members": [{"row_ref": r["origin"]["row_ref"], "provenance_raw": r["provenance_raw"], "status_history": r["status_history"]} for r in g]}
            self.consolidated.append({"claim_id": cid, "row_refs": [r["origin"]["row_ref"] for r in g]})
            out.append(keep)
        return out

    def write(self, recs, files, nodes, edges, unres):
        with open(os.path.join(self.out, "records.jsonl"), "w") as f:
            for r in recs:
                f.write(canon(r) + "\n")
        from collections import Counter
        cnt = lambda key: dict(sorted(((("(none)" if k is None else k), v) for k, v in Counter(key(r) for r in recs).items())))
        dup = Counter(r["claim_id"] for r in recs)
        dups = {k: v for k, v in dup.items() if v > 1}
        rep = {"adapter": ADAPTER, "adapter_version": ADAPTER_VERSION, "run_id": self.run_id, "at": self.at, "manifest": self.manifest_path,
               "index_path": self.m["index_path"], "checkout_path": self.m["checkout_path"], "repo_sha": self.m["repo_sha"],
               "checks_passed": self.checks_done,
               "input_rows": {"files": len(files), "nodes": len(nodes), "edges": len(edges), "unresolved_refs": len(unres)},
               "records": len(recs), "by_claim_kind": cnt(lambda r: r["claim_kind"]), "by_provenance": cnt(lambda r: r["provenance"]),
               "by_class": cnt(lambda r: r["class"]), "by_status": cnt(lambda r: r["status"]), "by_label": cnt(lambda r: r["label"]),
               "by_relationship_kind": cnt(lambda r: r.get("relationship_kind")), "generated_files": sorted(p for p, v in self.fmeta.items() if v["generated"]),
               "file_errors": self.file_errors,
               "duplicate_claim_ids": {"groups": len(dups), "records": sum(dups.values()),
                                       "note": "claim_id v3 (Decision 002-B): distinct claims never share an id; exact duplicates are consolidated into one record that keeps every contributing row"},
               "consolidated": {"records": len(self.consolidated), "rows": sum(len(c["row_refs"]) for c in self.consolidated), "groups": self.consolidated},
               "eof_normalized_file_ranges": sum(1 for r in recs for l in r["locations"] if l.get("original") and l["original"]["end_line"] != l["end_line"]),
               "warnings": self.warnings}
        json.dump(rep, open(os.path.join(self.out, "report.json"), "w"), indent=1, sort_keys=True)
        json.dump(sorted({p for p, _ in OPENED}), open(os.path.join(self.out, "opened_files.json"), "w"), indent=0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    a = ap.parse_args()
    ad = Adapter(a.manifest)
    run_dir = os.path.dirname(os.path.abspath(a.manifest))
    ALLOWED_WRITE.extend([run_dir + "/", os.path.abspath(ad.m["checkout_path"]) + "/.codegraph/"])
    if not ad.out.startswith(run_dir + "/"):
        raise SystemExit("adapter_out must be under the run dir")
    sys.addaudithook(audit)
    try:
        recs = ad.run()
        print(f"OK records={len(recs)} out={ad.out}")
        return 0
    except AdapterError as e:
        os.makedirs(ad.out, exist_ok=True)
        for fn in ("records.jsonl", "report.json"):
            p = os.path.join(ad.out, fn)
            if os.path.exists(p):
                os.rename(p, p + ".discarded")
        json.dump({"code": e.code, "detail": e.detail, "run_id": ad.run_id, "at": now_ist(), "checks_passed": ad.checks_done}, open(os.path.join(ad.out, "errors.json"), "w"), indent=1)
        json.dump(sorted({p for p, _ in OPENED}), open(os.path.join(ad.out, "opened_files.json"), "w"), indent=0)
        print(f"FAIL {e.code}: {e.detail}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
