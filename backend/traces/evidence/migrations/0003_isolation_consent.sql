-- Traces store, migration 0003 (D-026, D-027). Snapshot isolation and repo-level AI consent details.
-- snapshots.isolation: how the analysis workers ran for the stored evidence. 'unshare' (network namespace shown by the
-- per-run probe) or 'off' (explicit TRACES_ISOLATION=off dev override: unisolated, never acceptance evidence).
-- NULL for snapshots written before 0003 or never indexed.
ALTER TABLE snapshots ADD COLUMN isolation TEXT CHECK (isolation IS NULL OR isolation IN ('unshare', 'off'));
-- repos.external_ai_consent (0002) gains when it was last set and which consent text the user saw (PUT /repos/{id}/ai-consent).
ALTER TABLE repos ADD COLUMN external_ai_consent_at TEXT;
ALTER TABLE repos ADD COLUMN external_ai_consent_text_version TEXT;
