"""SQLite evidence store with versioned migrations (backend/traces/evidence/migrations/NNNN_name.sql) and JSON export.
The store holds traces-evidence/0.4 records only; older records are migrated on import."""
from __future__ import annotations

import datetime as _dt
import json
import sqlite3
import threading
import uuid
from collections import Counter
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from traces.evidence.migrate import CURRENT, to_current

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def now() -> str:
    return _dt.datetime.now(_dt.UTC).astimezone().isoformat(timespec="seconds")


def migrations(extra_dirs: Iterable[Path] = ()) -> list[tuple[int, str, Path]]:
    out = []
    for d in [MIGRATIONS_DIR, *extra_dirs]:
        for p in sorted(Path(d).glob("[0-9][0-9][0-9][0-9]_*.sql")):
            out.append((int(p.name[:4]), p.stem, p))
    nums = [n for n, _, _ in out]
    if len(nums) != len(set(nums)):
        raise RuntimeError(f"duplicate migration numbers: {sorted(n for n, c in Counter(nums).items() if c > 1)}")
    return sorted(out)


class Store:
    """One logical store, one SQLite connection per thread.

    The API serves sync endpoints from a thread pool, so a single shared connection (check_same_thread=False) let two
    threads interleave statements on one connection and fail with sqlite3.InterfaceError. Each thread now opens its own
    connection on first use (`Store.db`); file stores run in WAL mode so readers never block the writer, every connection
    has a busy_timeout so concurrent writers wait instead of failing, and `write_lock` serializes read-modify-write
    sequences inside this process (job version bumps). `:memory:` stores use a uniquely named shared-cache in-memory
    database so every thread sees the same data; an anchor connection keeps it alive for the Store's lifetime."""

    BUSY_TIMEOUT_MS = 15000

    def __init__(self, path: Path | str, extra_migration_dirs: Iterable[Path] = ()):
        self.path = str(path)
        self.memory = self.path == ":memory:"
        if self.memory:
            self._target, self._uri = f"file:traces-mem-{uuid.uuid4().hex}?mode=memory&cache=shared", True
        else:
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
            self._target, self._uri = self.path, False
        self._local = threading.local()
        self._conns: list[sqlite3.Connection] = []
        self._conns_lock = threading.Lock()
        self.write_lock = threading.RLock()
        self._anchor = self._connect()
        if not self.memory:
            self._anchor.execute("PRAGMA journal_mode = WAL")
        self._local.conn = self._anchor
        with self.write_lock:
            self.migrate(extra_migration_dirs)

    def _connect(self) -> sqlite3.Connection:
        c = sqlite3.connect(self._target, uri=self._uri, timeout=self.BUSY_TIMEOUT_MS / 1000, check_same_thread=True)
        c.row_factory = sqlite3.Row
        c.execute(f"PRAGMA busy_timeout = {self.BUSY_TIMEOUT_MS}")
        c.execute("PRAGMA foreign_keys = ON")
        if not self.memory:
            c.execute("PRAGMA synchronous = NORMAL")
        with self._conns_lock:
            self._conns.append(c)
        return c

    @property
    def db(self) -> sqlite3.Connection:
        """This thread's connection (opened on first use)."""
        c: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if c is None:
            c = self._connect()
            self._local.conn = c
        return c

    def close(self) -> None:
        """Close every connection this store opened (connections of other threads are closed from here too, so only
        call it when no request is in flight)."""
        with self._conns_lock:
            conns, self._conns = self._conns, []
        for c in conns:
            try:
                c.close()
            except sqlite3.ProgrammingError:  # created in another thread; sqlite3 refuses cross-thread close
                pass
        self._local = threading.local()

    # ---------------------------------------------------------------- migrations
    def migrate(self, extra_dirs: Iterable[Path] = ()) -> list[int]:
        self.db.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL)")
        done = {r[0] for r in self.db.execute("SELECT version FROM schema_migrations")}
        applied = []
        for num, name, p in migrations(extra_dirs):
            if num in done:
                continue
            with self.db:
                self.db.executescript(p.read_text())
                self.db.execute("INSERT INTO schema_migrations VALUES (?,?,?)", (num, name, now()))
            applied.append(num)
        return applied

    def schema_version(self) -> int:
        r = self.db.execute("SELECT max(version) FROM schema_migrations").fetchone()
        return int(r[0] or 0)

    # ---------------------------------------------------------------- repos and snapshots
    def upsert_repo(self, repo_id: str, host: str, owner: str, name: str, url: str) -> None:
        with self.write_lock, self.db:
            self.db.execute("INSERT INTO repos (id, host, owner, name, url, created_at) VALUES (?,?,?,?,?,?) ON CONFLICT(id) DO NOTHING",
                            (repo_id, host, owner, name, url, now()))

    def upsert_snapshot(self, repo_id: str, sha: str, state: str, extractor: dict[str, Any] | None = None,
                        stats: dict[str, Any] | None = None, generated_paths: list[str] | None = None) -> str:
        sid = f"{repo_id}@{sha}"
        with self.write_lock, self.db:
            self.db.execute("""INSERT INTO snapshots (id, repo_id, sha, state, evidence_schema, extractor_json, stats_json, generated_paths_json, created_at)
                               VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET state=excluded.state, extractor_json=excluded.extractor_json,
                               stats_json=excluded.stats_json, generated_paths_json=excluded.generated_paths_json""",
                            (sid, repo_id, sha, state, CURRENT, json.dumps(extractor or {}), json.dumps(stats or {}), json.dumps(generated_paths or []), now()))
        return sid

    def record_remote_head(self, repo_id: str, sha: str, default_branch: str | None, checked_at: str) -> None:
        """Store the latest anonymously discovered HEAD; a successful anonymous probe also confirms visibility=public."""
        with self.write_lock, self.db:
            self.db.execute("UPDATE repos SET latest_discovered_sha=?, latest_discovered_at=?, default_branch=coalesce(?, default_branch), "
                            "visibility_checked_at=? WHERE id=?", (sha, checked_at, default_branch, checked_at, repo_id))

    def newest_ready_snapshot(self, repo_id: str) -> dict[str, Any] | None:
        r = self.db.execute("SELECT * FROM snapshots WHERE repo_id=? AND state='ready' ORDER BY coalesce(indexed_at, created_at) DESC, created_at DESC "
                            "LIMIT 1", (repo_id,)).fetchone()
        return dict(r) if r else None

    def ensure_snapshot(self, repo_id: str, sha: str) -> str:
        """Pin a snapshot (state `pending`) unless it already exists; never downgrades an indexed snapshot."""
        sid = f"{repo_id}@{sha}"
        with self.write_lock, self.db:
            self.db.execute("INSERT INTO snapshots (id, repo_id, sha, state, evidence_schema, created_at) VALUES (?,?,?,?,?,?) "
                            "ON CONFLICT(id) DO NOTHING", (sid, repo_id, sha, "pending", CURRENT, now()))
        return sid

    def list_repos(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self.db.execute("SELECT * FROM repos ORDER BY id")]

    def get_repo(self, repo_id: str) -> dict[str, Any] | None:
        r = self.db.execute("SELECT * FROM repos WHERE id=?", (repo_id,)).fetchone()
        return dict(r) if r else None

    def list_snapshots(self, repo_id: str) -> list[dict[str, Any]]:
        return [dict(r) for r in self.db.execute("SELECT * FROM snapshots WHERE repo_id=? ORDER BY created_at", (repo_id,))]

    def get_snapshot(self, snapshot_id: str) -> dict[str, Any] | None:
        r = self.db.execute("SELECT * FROM snapshots WHERE id=?", (snapshot_id,)).fetchone()
        return dict(r) if r else None

    # ---------------------------------------------------------------- claims
    def put_claims(self, snapshot_id: str, records: Iterable[dict[str, Any]]) -> int:
        n = 0
        with self.write_lock, self.db:
            for rec in records:
                r = to_current(rec)
                fr, to = r.get("from") or {}, r.get("to") or {}
                self.db.execute("""INSERT INTO claims (snapshot_id, claim_id, run_id, schema_version, claim_kind, kind, status, label, class, evidence_scope,
                                   originator, from_symbol, from_file, to_symbol, to_file, injected, record_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                                (snapshot_id, r["claim_id"], r["run_id"], r["schema_version"], r["claim_kind"], r.get("relationship_kind") or r.get("node_kind"),
                                 r["status"], r["label"], r["class"], r["evidence_scope"], r["originator"]["name"], fr.get("symbol"), fr.get("file"),
                                 to.get("symbol"), to.get("file"), int(bool(r["injected"])), json.dumps(r, sort_keys=True, separators=(",", ":"), ensure_ascii=False)))
                for loc in r.get("locations", []):
                    self.db.execute("INSERT INTO claim_locations VALUES (?,?,?,?,?,?,?)",
                                    (snapshot_id, r["claim_id"], loc["file"], loc["start_line"], loc["end_line"], loc["role"], loc["range_kind"]))
                n += 1
        return n

    def delete_claims(self, snapshot_id: str, *, scopes: Iterable[str] | None = None) -> int:
        """Remove a snapshot's claims (all, or only the given evidence scopes) before a reindex stores fresh ones."""
        sc = list(scopes) if scopes is not None else None
        where, args = ("snapshot_id=?", [snapshot_id]) if sc is None else \
            (f"snapshot_id=? AND evidence_scope IN ({','.join('?' * len(sc))})", [snapshot_id, *sc])
        with self.write_lock, self.db:
            self.db.execute(f"DELETE FROM claim_locations WHERE (snapshot_id, claim_id) IN (SELECT snapshot_id, claim_id FROM claims WHERE {where})", args)
            n = self.db.execute(f"DELETE FROM claims WHERE {where}", args).rowcount
        return int(n)

    def set_snapshot_state(self, snapshot_id: str, state: str) -> None:
        with self.write_lock, self.db:
            self.db.execute("UPDATE snapshots SET state=? WHERE id=?", (state, snapshot_id))

    def finish_snapshot(self, snapshot_id: str, *, extractor: dict[str, Any], languages: dict[str, int], frameworks: list[str],
                        generated_paths: list[str], stats: dict[str, Any], isolation: str | None = None) -> None:
        """Mark ready. `isolation` is 'unshare' or 'off' (explicit dev override, stored so the API shows it unisolated)."""
        with self.write_lock, self.db:
            self.db.execute("UPDATE snapshots SET state='ready', extractor_json=?, languages_json=?, frameworks_json=?, generated_paths_json=?, "
                            "stats_json=?, indexed_at=?, isolation=? WHERE id=?",
                            (json.dumps(extractor, sort_keys=True), json.dumps(languages, sort_keys=True), json.dumps(frameworks),
                             json.dumps(generated_paths), json.dumps(stats, sort_keys=True), now(), isolation, snapshot_id))

    def drop_unindexed_snapshot(self, snapshot_id: str) -> bool:
        """Remove a snapshot row that never held evidence (F-6: a commit that does not exist). Jobs keep their record
        with snapshot_id NULL; a ready snapshot or one with claims is never removed. Returns True when removed."""
        with self.write_lock, self.db:
            row = self.db.execute("SELECT state FROM snapshots WHERE id=?", (snapshot_id,)).fetchone()
            if row is None or row[0] == "ready":
                return False
            if self.db.execute("SELECT 1 FROM claims WHERE snapshot_id=? LIMIT 1", (snapshot_id,)).fetchone():
                return False
            self.db.execute("UPDATE jobs SET snapshot_id=NULL WHERE snapshot_id=?", (snapshot_id,))
            for t in ("runs", "components"):
                self.db.execute(f"DELETE FROM {t} WHERE snapshot_id=?", (snapshot_id,))  # noqa: S608  fixed table names
            self.db.execute("DELETE FROM snapshots WHERE id=?", (snapshot_id,))
        return True

    def set_ai_consent(self, repo_id: str, consent: bool, text_version: str | None, at: str) -> None:
        """Record the repo-level external AI consent decision (D-027). Revoking keeps the time of the change."""
        with self.write_lock, self.db:
            self.db.execute("UPDATE repos SET external_ai_consent=?, external_ai_consent_at=?, external_ai_consent_text_version=? WHERE id=?",
                            (1 if consent else 0, at, text_version, repo_id))

    def update_snapshot_stats(self, snapshot_id: str, stats: dict[str, Any]) -> None:
        with self.write_lock, self.db:
            self.db.execute("UPDATE snapshots SET stats_json=? WHERE id=?", (json.dumps(stats, sort_keys=True), snapshot_id))

    def put_components(self, snapshot_id: str, components: Iterable[Any]) -> int:
        """Replace the snapshot's deterministic components (traces.evidence.types.ComponentDef)."""
        n = 0
        with self.write_lock, self.db:
            self.db.execute("DELETE FROM components WHERE snapshot_id=?", (snapshot_id,))
            for c in components:
                self.db.execute("INSERT INTO components (snapshot_id, component_id, name, layer, kind, paths_json, rule, record_json) "
                                "VALUES (?,?,?,?,?,?,?,?)",
                                (snapshot_id, c.id, c.name, c.layer, "directory", json.dumps(list(c.paths)), c.rule,
                                 json.dumps({"reason": getattr(c, "reason", "") or None}, sort_keys=True)))
                n += 1
        return n

    def list_components(self, snapshot_id: str) -> list[dict[str, Any]]:
        return [dict(r) for r in self.db.execute("SELECT * FROM components WHERE snapshot_id=? ORDER BY component_id", (snapshot_id,))]

    def add_run(self, run_id: str, snapshot_id: str, kind: str, run_dir: str, result: dict[str, Any], started_at: str) -> None:
        with self.write_lock, self.db:
            self.db.execute("INSERT OR REPLACE INTO runs (id, snapshot_id, kind, run_dir, result_json, started_at, finished_at) VALUES (?,?,?,?,?,?,?)",
                            (run_id, snapshot_id, kind, run_dir, json.dumps(result, sort_keys=True, default=str), started_at, now()))

    def active_job(self, snapshot_id: str) -> dict[str, Any] | None:
        r = self.db.execute("SELECT id FROM jobs WHERE snapshot_id=? AND state IN ('queued','running') ORDER BY created_at DESC LIMIT 1",
                            (snapshot_id,)).fetchone()
        return dict(r) if r else None

    def unfinished_jobs(self) -> list[str]:
        return [r[0] for r in self.db.execute("SELECT id FROM jobs WHERE state IN ('queued','running') ORDER BY created_at")]

    def get_claim(self, snapshot_id: str, claim_id: str) -> dict[str, Any] | None:
        r = self.db.execute("SELECT record_json FROM claims WHERE snapshot_id=? AND claim_id=?", (snapshot_id, claim_id)).fetchone()
        return json.loads(r[0]) if r else None

    def status_counts(self, snapshot_id: str, where: str = "", args: tuple = ()) -> dict[str, int]:
        q = f"SELECT status, count(*) FROM claims WHERE snapshot_id=? {where} GROUP BY status"
        return {s: c for s, c in self.db.execute(q, (snapshot_id, *args))}

    def iter_claims(self, snapshot_id: str) -> Iterator[dict[str, Any]]:
        for (rj,) in self.db.execute("SELECT record_json FROM claims WHERE snapshot_id=? ORDER BY claim_id", (snapshot_id,)):
            yield json.loads(rj)

    # ---------------------------------------------------------------- export
    def export_jsonl(self, snapshot_id: str, out: Path) -> dict[str, Any]:
        """Portable export: one traces-evidence/0.4 record per line (sorted by claim_id) plus a manifest beside it."""
        out = Path(out)
        n = 0
        with open(out, "w") as f:
            for r in self.iter_claims(snapshot_id):
                f.write(json.dumps(r, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")
                n += 1
        snap = self.get_snapshot(snapshot_id) or {}
        manifest = {"snapshot_id": snapshot_id, "repo_id": snap.get("repo_id"), "sha": snap.get("sha"), "schema_version": CURRENT, "records": n,
                    "by_status": self.status_counts(snapshot_id), "exported_at": now(), "store_migration": self.schema_version()}
        Path(str(out) + ".manifest.json").write_text(json.dumps(manifest, indent=1))
        return manifest


def import_pipeline_run(run_dir: Path, store: Store | None = None) -> dict[str, Any]:
    """Load a finished verification pipeline run (v1/validation/evidence.jsonl) into the store, migrated to 0.4."""
    from traces.core.config import get_settings
    from traces.ingest.urls import parse_repo_url

    run_dir = Path(run_dir)
    meta = json.loads((run_dir / "run_meta.json").read_text())
    st = store or Store(get_settings().db_path)
    ref = parse_repo_url(f"https://github.com/{meta['repo']}")
    st.upsert_repo(ref.cache_key, ref.host, ref.owner, ref.name, f"https://github.com/{ref.slug}")
    sid = st.upsert_snapshot(ref.cache_key, meta["repo_sha"], "indexing")
    with open(run_dir / "v1" / "validation" / "evidence.jsonl") as f:
        n = st.put_claims(sid, (json.loads(line) for line in f))
    st.upsert_snapshot(ref.cache_key, meta["repo_sha"], "ready", extractor={"codegraph": "1.6.2", "typescript": "6.0.3", "python": meta.get("python")},
                       stats={"records": n, "by_status": st.status_counts(sid)})
    return {"snapshot_id": sid, "records": n, "by_status": st.status_counts(sid)}


# -------------------------------------------------------------------- jobs (index job state machine, CONTRACTS s3.2)
JOB_TRANSITIONS: dict[str, set[str]] = {
    "queued": {"running", "cancelled", "failed"},
    "running": {"succeeded", "failed", "cancelled"},
    "succeeded": set(), "failed": set(), "cancelled": set(),
}
JOB_PHASES = ("queued", "fetching", "checking_out", "indexing", "adapting", "validating", "storing", "history", "done", "failed")


class JobTransitionError(ValueError):
    pass


def _job_row(st: Store, job_id: str) -> dict[str, Any] | None:
    r = st.db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    return dict(r) if r else None


def create_job(st: Store, job_id: str, repo_id: str, kind: str, snapshot_id: str | None = None) -> dict[str, Any]:
    t = now()
    with st.write_lock, st.db:
        st.db.execute("INSERT INTO jobs (id, repo_id, snapshot_id, kind, state, phase, progress, version, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                      (job_id, repo_id, snapshot_id, kind, "queued", "queued", 0.0, 1, t, t))
        st.db.execute("INSERT INTO job_events (job_id, at, phase, level, message) VALUES (?,?,?,?,?)", (job_id, t, "queued", "info", "job queued"))
    return get_job(st, job_id) or {}


def update_job(st: Store, job_id: str, *, state: str | None = None, phase: str | None = None, progress: float | None = None,
               message: str | None = None, error_code: str | None = None, error_detail: str | None = None, level: str = "info") -> dict[str, Any]:
    with st.write_lock:
        return _update_job_locked(st, job_id, state=state, phase=phase, progress=progress, message=message,
                                  error_code=error_code, error_detail=error_detail, level=level)


def _update_job_locked(st: Store, job_id: str, *, state: str | None, phase: str | None, progress: float | None,
                       message: str | None, error_code: str | None, error_detail: str | None, level: str) -> dict[str, Any]:
    cur = _job_row(st, job_id)
    if cur is None:
        raise KeyError(job_id)
    if state and state != cur["state"] and state not in JOB_TRANSITIONS[cur["state"]]:
        raise JobTransitionError(f"{cur['state']} -> {state}")
    if phase and phase not in JOB_PHASES:
        raise JobTransitionError(f"unknown phase {phase}")
    if progress is not None and not (cur["progress"] <= progress <= 1):
        raise JobTransitionError("progress must be monotonic in [0, 1]")
    t = now()
    new_state = state or cur["state"]
    fields = {"state": new_state, "phase": phase or cur["phase"], "progress": cur["progress"] if progress is None else progress,
              "message": message if message is not None else cur["message"], "error_code": error_code or cur["error_code"],
              "error_detail": error_detail or cur["error_detail"], "version": cur["version"] + 1, "updated_at": t,
              "started_at": cur["started_at"] or (t if new_state == "running" else None),
              "finished_at": t if new_state in ("succeeded", "failed", "cancelled") else None}
    with st.write_lock, st.db:
        st.db.execute("UPDATE jobs SET " + ", ".join(f"{k}=?" for k in fields) + " WHERE id=?", (*fields.values(), job_id))
        if message or phase or state:
            st.db.execute("INSERT INTO job_events (job_id, at, phase, level, message) VALUES (?,?,?,?,?)",
                          (job_id, t, fields["phase"], level, message or f"{fields['state']}/{fields['phase']}"))
    return get_job(st, job_id) or {}


def get_job(st: Store, job_id: str) -> dict[str, Any] | None:
    j = _job_row(st, job_id)
    if j is None:
        return None
    j["events"] = [dict(e) for e in st.db.execute("SELECT at, phase, level, message FROM job_events WHERE job_id=? ORDER BY id", (job_id,))]
    return j
