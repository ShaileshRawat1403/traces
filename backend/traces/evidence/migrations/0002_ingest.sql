-- Traces store, migration 0002 (INGEST, D-021). Visibility and consent bookkeeping for registered repositories.
-- visibility stays 'public' only (0001 CHECK); visibility_checked_at records when an anonymous ls-remote last confirmed it.
-- external_ai_consent is the repo-level consent to send source snippets to an external AI provider; it defaults to 0 and
-- v1 exposes no endpoint that sets it, so explain bundles still need per-request consent in the browser.
ALTER TABLE repos ADD COLUMN visibility_checked_at TEXT;
ALTER TABLE repos ADD COLUMN external_ai_consent INTEGER NOT NULL DEFAULT 0 CHECK (external_ai_consent IN (0, 1));
