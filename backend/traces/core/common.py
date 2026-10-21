"""Shared evidence helpers: canonical JSON, hashes, claim_id v3, EOF line semantics, read-only blob reader.
Ported from research/task002/adapter/common.py (Decision 002-B semantics unchanged). CPython 3.14 stdlib only."""
import hashlib, json, os, subprocess, datetime

# Schema written by the verification pipeline. 0.3 is the frozen Task 002 format; records are migrated to
# traces-evidence/0.4 (traces.evidence.migrate) before they reach the store or the API.
PIPELINE_SCHEMA_VERSION = "traces-evidence/0.3"
SCHEMA_VERSION = PIPELINE_SCHEMA_VERSION  # name kept for the ported pipeline code
GITENV = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}


def canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(b):
    if isinstance(b, str):
        b = b.encode()
    return hashlib.sha256(b).hexdigest()


def line_count(text):
    """Addressable source lines (Decision 002-B ruling 1): the position after a final newline is not a line.
    "" -> 0, "a" -> 1, "a\n" -> 1, "a\nb" -> 2, "a\nb\n" -> 2."""
    return text.count("\n") + (1 if text and not text.endswith("\n") else 0)


def normalize_file_range(l, text):
    """Whole-file range under Decision 002-B ruling 1. Returns a new dict; keeps the original coordinates.
    Normalized: start_line 1, end_line = last addressable line (0 for an empty blob), end_exclusive_line = end_line + 1.
    The EOF position (end_exclusive_line) is an exclusive boundary only; it is never an addressable line."""
    if l.get("range_kind") != "file" or "original" in l:
        return dict(l)
    n = line_count(text)
    d = dict(l)
    d["original"] = {"start_line": l["start_line"], "end_line": l["end_line"]}
    d["start_line"] = 1
    d["end_line"] = n
    d["end_exclusive_line"] = n + 1
    d["terminal_newline"] = text.endswith("\n") if text else None
    return d


def _range_key(e):
    if not e:
        return None
    return [e.get("file"), e.get("start_line"), e.get("end_line")]


def claim_id(repo_sha, claim_kind, kind, frm, to, granularity, extractor, anchor, target_name):
    """Decision 002-B ruling 2. claim_id = c_ + sha256(canonical JSON of the claim identity):
    relationship identity (claim_kind, kind, from/to symbol and normalized declared range, granularity),
    normalized source location (anchor: the first originator location in role order site, to_decl, from_decl, input),
    unresolved target name (reference_name, reference_kind; null otherwise), and extractor identity (name, version)."""
    ident = {"repo_sha": repo_sha, "claim_kind": claim_kind, "kind": kind, "granularity": granularity,
             "from": {"symbol": (frm or {}).get("symbol"), "range": _range_key(frm)} if frm else None,
             "to": {"symbol": (to or {}).get("symbol"), "range": _range_key(to)} if to else None,
             "location": anchor, "target_name": target_name,
             "extractor": {"name": extractor["name"], "version": extractor.get("version")}}
    return "c_" + sha256_hex(canon(ident))


ANCHOR_ORDER = {"site": 0, "to_decl": 1, "from_decl": 2, "input": 3}


def anchor_of(locations):
    """Normalized source location used in claim_id: first originator location in role order, then position."""
    L = [l for l in locations if l.get("source", "originator") == "originator" and l["role"] in ANCHOR_ORDER]
    if not L:
        return None
    l = min(L, key=lambda l: (ANCHOR_ORDER[l["role"]], l["file"], l["start_line"], l.get("start_col") if l.get("start_col") is not None else -1, l["end_line"], l.get("end_col") if l.get("end_col") is not None else -1))
    return [l["role"], l["range_kind"], l["file"], l["start_line"], l.get("start_col"), l["end_line"], l.get("end_col")]


def now_ist():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30))).isoformat(timespec="seconds")


def git(root, *args, text=True):
    return subprocess.check_output(["git", "-C", root, *args], text=text, env=GITENV)


class Blobs:
    """Blob reader at a fixed SHA (git ls-tree + git cat-file), read-only."""
    def __init__(self, root, sha):
        self.root, self.sha = root, sha
        self.tree = {}
        for line in git(root, "ls-tree", "-r", sha).splitlines():
            meta, path = line.split("\t", 1)
            self.tree[path] = meta.split()[2]
        self._cache = {}

    def exists(self, path):
        return path in self.tree

    def blob_sha(self, path):
        return self.tree.get(path)

    def bytes(self, path):
        if path not in self._cache:
            self._cache[path] = subprocess.check_output(["git", "-C", self.root, "cat-file", "blob", self.tree[path]], env=GITENV)
        return self._cache[path]

    def text(self, path):
        return self.bytes(path).decode("utf-8")

    def lines(self, path):
        return self.text(path).split("\n")


def strip_volatile(obj):
    """Remove run_id and at keys recursively (determinism hash, ADAPTER_CONTRACT 5.5)."""
    if isinstance(obj, dict):
        return {k: strip_volatile(v) for k, v in obj.items() if k not in ("run_id", "at")}
    if isinstance(obj, list):
        return [strip_volatile(v) for v in obj]
    return obj


def canonical_hash(records):
    h = hashlib.sha256()
    for r in records:
        h.update(canon(strip_volatile(r)).encode())
        h.update(b"\n")
    return h.hexdigest()
