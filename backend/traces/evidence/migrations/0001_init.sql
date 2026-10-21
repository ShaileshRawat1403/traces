-- Traces store, migration 0001. SQLite. Evidence is stored as the full traces-evidence/0.4 record (record_json) plus
-- indexed columns for queries. Migration number ranges: 0001-0099 evidence/ingest/API (Traces seat),
-- 0100-0199 history (Traces History seat), 0200-0299 explain (Traces UI seat). See docs/CONTRACTS.md section 3.
CREATE TABLE repos (
  id TEXT PRIMARY KEY,                 -- "<host>__<owner>__<name>"
  host TEXT NOT NULL, owner TEXT NOT NULL, name TEXT NOT NULL,
  url TEXT NOT NULL,
  visibility TEXT NOT NULL DEFAULT 'public' CHECK (visibility IN ('public')),
  created_at TEXT NOT NULL,
  latest_discovered_sha TEXT, latest_discovered_at TEXT, default_branch TEXT
);
CREATE TABLE snapshots (
  id TEXT PRIMARY KEY,                 -- "<repo_id>@<sha>"
  repo_id TEXT NOT NULL REFERENCES repos(id),
  sha TEXT NOT NULL CHECK (length(sha) = 40),
  state TEXT NOT NULL CHECK (state IN ('pending','indexing','ready','failed')),
  evidence_schema TEXT NOT NULL,
  extractor_json TEXT NOT NULL DEFAULT '{}',   -- pins: CodeGraph, TypeScript, Python
  languages_json TEXT NOT NULL DEFAULT '{}',
  frameworks_json TEXT NOT NULL DEFAULT '[]',
  generated_paths_json TEXT NOT NULL DEFAULT '[]', -- generator-config-detected paths (history's generated filter)
  stats_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL, indexed_at TEXT,
  UNIQUE (repo_id, sha)
);
CREATE TABLE jobs (
  id TEXT PRIMARY KEY,
  repo_id TEXT NOT NULL REFERENCES repos(id),
  snapshot_id TEXT REFERENCES snapshots(id),
  kind TEXT NOT NULL CHECK (kind IN ('index','reindex','history','baseline')),
  state TEXT NOT NULL CHECK (state IN ('queued','running','succeeded','failed','cancelled')),
  phase TEXT NOT NULL,
  progress REAL NOT NULL DEFAULT 0 CHECK (progress >= 0 AND progress <= 1),
  message TEXT,
  error_code TEXT, error_detail TEXT,
  version INTEGER NOT NULL DEFAULT 1,  -- bumped on every change; the API ETag
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, started_at TEXT, finished_at TEXT
);
CREATE TABLE job_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id TEXT NOT NULL REFERENCES jobs(id),
  at TEXT NOT NULL, phase TEXT NOT NULL, level TEXT NOT NULL CHECK (level IN ('info','warning','error')), message TEXT NOT NULL
);
CREATE TABLE runs (
  id TEXT PRIMARY KEY,
  snapshot_id TEXT NOT NULL REFERENCES snapshots(id),
  kind TEXT NOT NULL,                  -- 'evidence' | 'history' | 'baseline'
  run_dir TEXT,                        -- relative to the data dir
  result_json TEXT NOT NULL DEFAULT '{}',
  started_at TEXT, finished_at TEXT
);
CREATE TABLE claims (
  snapshot_id TEXT NOT NULL REFERENCES snapshots(id),
  claim_id TEXT NOT NULL,
  run_id TEXT NOT NULL,
  schema_version TEXT NOT NULL,
  claim_kind TEXT NOT NULL,
  kind TEXT,                           -- relationship_kind or node_kind
  status TEXT NOT NULL, label TEXT NOT NULL, class TEXT NOT NULL, evidence_scope TEXT NOT NULL,
  originator TEXT NOT NULL,
  from_symbol TEXT, from_file TEXT, to_symbol TEXT, to_file TEXT,
  injected INTEGER NOT NULL DEFAULT 0,
  record_json TEXT NOT NULL,
  PRIMARY KEY (snapshot_id, claim_id)
);
CREATE INDEX claims_status ON claims(snapshot_id, status);
CREATE INDEX claims_from ON claims(snapshot_id, from_symbol);
CREATE INDEX claims_to ON claims(snapshot_id, to_symbol);
CREATE INDEX claims_kind ON claims(snapshot_id, claim_kind, kind);
CREATE TABLE claim_locations (
  snapshot_id TEXT NOT NULL, claim_id TEXT NOT NULL,
  file TEXT NOT NULL, start_line INTEGER NOT NULL, end_line INTEGER NOT NULL, role TEXT NOT NULL, range_kind TEXT NOT NULL,
  FOREIGN KEY (snapshot_id, claim_id) REFERENCES claims(snapshot_id, claim_id)
);
CREATE INDEX claim_locations_file ON claim_locations(snapshot_id, file, start_line);
CREATE TABLE components (            -- deterministic output of the evidence/indexing side (D-007)
  snapshot_id TEXT NOT NULL REFERENCES snapshots(id),
  component_id TEXT NOT NULL, name TEXT NOT NULL, layer TEXT NOT NULL, kind TEXT NOT NULL,
  paths_json TEXT NOT NULL, rule TEXT NOT NULL, record_json TEXT NOT NULL DEFAULT '{}',
  PRIMARY KEY (snapshot_id, component_id)
);
