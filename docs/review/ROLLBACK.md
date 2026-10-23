# Rolling back Traces v1

Applies to the integration branch `build/traces-v1`, now at `0f32d4d`. `main` is never touched. Nothing reaches `main` until Shailesh merges it.

## Rules

- History on `build/traces-v1` is never rewritten. **No force-push, no `reset --hard` on the shared branch, no rebase.**
- A rollback is a new commit on a `ws/arch-revert-*` branch, opened as a PR into `build/traces-v1`, merged with a normal merge after CI is green.
- Back up the store before deploying any build that adds a migration, and before any rollback (see "Store").

## Merge points on `build/traces-v1`

First-parent merges since the v1 review audit (`git log --first-parent --oneline build/traces-v1`):

| Merge SHA | PR | What |
| --- | --- | --- |
| `0f32d4d` | #38 | Trace UI: unresolved-call gaps (F-9) |
| `320d4c9` | #37 | Manifest rows hash the exact line sent (O-11) |
| `84d2eda` | #36 | Explain: F-11, F-8 JS, O-12 |
| `a8b73a4` | #33 | JS import check (D-030), trace completeness (D-031), F5, O-9 cleanup |
| `fc7e7b6` | #35 | Explain: format only |
| `227310c` | #34 | UI contract wiring |
| `1b10fe8` | #26 | Lab acceptance fixes F-7, F-8, G-3, O-2, O-3, O-4 |
| `b98ae5a` | #31 | Lab G-5 BYOK chat acceptance |
| `adb835e` | #32 | History lineage breaks (D-H15) |
| `0c1fa0b` | #30 | Lab G-4 Express acceptance |
| `0b9b920` | #29 | UI contract fields (D-029) |
| `b37eef2` | #27 | Isolation fails closed (D-026), security fixes, consent endpoint (D-027), **migration 0003** |
| `83fd127` | #28 | Lab checkpoint 4: fsft e2e seed, perf baseline |
| `e532644` | #25 | Lab second repo, ACCEPTANCE.md, demo script |
| `525bc1d` | #24 | Explain: co-change is a pattern |
| `01c5023` | #22 | Lab CI gaps and security suite |
| `fa78d58` | #20 | BYOK chat |
| `86e7b5a` | #23 | History aliases (opt-in) |
| `35499bc` | (direct commit) | Audited v1 review baseline |

Earlier merges: `83f5731` (#9, **migration 0002**), `80a6606` (#15), and the rest listed in [STATUS.md](../STATUS.md).

## Code rollback

Set up once (the token comes from the environment and is never printed):

```bash
git fetch origin
git switch -c ws/arch-revert-<topic> origin/build/traces-v1
```

**One PR.** Revert its merge commit against the first parent:

```bash
git revert -m 1 <merge-sha>          # e.g. git revert -m 1 0f32d4d
```

**Back to a previous merge SHA `X`.** Two normal-commit options; both keep history.

1. Revert each first-parent commit after `X`, newest first, one commit each. This is best when only a few PRs are involved, because each revert names its PR:
   ```bash
   for c in $(git rev-list --first-parent X..origin/build/traces-v1); do
     if [ "$(git rev-list --parents -n1 "$c" | wc -w)" -gt 2 ]; then git revert --no-edit -m 1 "$c"; else git revert --no-edit "$c"; fi
   done
   ```
2. Restore the tree of `X` in one commit. This is best for many PRs:
   ```bash
   git restore --source=X --staged --worktree -- :/
   git commit -m "Roll back build/traces-v1 to X (reverts PRs #a..#b)"
   git diff X HEAD --stat        # must be empty
   ```
   Checked on a scratch worktree from `0f32d4d` to `84d2eda`: the diff against `84d2eda` was empty afterwards. Nothing was pushed.

Then:

```bash
uv run --frozen ruff check backend tests && uv run --frozen mypy && uv run --frozen pytest -q
(cd web && npm ci --ignore-scripts && npm test && npm run check:api && npm run build)
git push origin ws/arch-revert-<topic>     # normal push of a new branch
```

Open a PR into `build/traces-v1`, wait for green CI (all 11 jobs), merge with a normal merge. To bring the change back later, revert the revert commit the same way.

## Store

### Migrations

The store is one SQLite file, `$TRACES_DATA_DIR/traces.sqlite3` (default `.traces-data/traces.sqlite3`), in WAL mode. Migrations are forward-only SQL files in `backend/traces/evidence/migrations/`, applied at startup and recorded in `schema_migrations`. There are no down migrations. `GET /api/v1/health` reports `store_migration`.

| Migration | Added by | Change |
| --- | --- | --- |
| `0001_init` | evidence store (before #9) | Tables `repos`, `snapshots`, `jobs`, `job_events`, `runs`, `claims` (static and history records), `claim_locations`, `components` |
| `0002_ingest` | #9, merge `83f5731` | `repos.visibility_checked_at`, `repos.external_ai_consent` |
| `0003_isolation_consent` | #27, merge `b37eef2` | `snapshots.isolation` (`unshare` / `off`), `repos.external_ai_consent_at`, `repos.external_ai_consent_text_version` |

**Older code cannot read a newer store.** API models forbid extra fields. Code at `35499bc` (migration 2), run against a copy of a migration-3 store, served health, overview, graph and history with 200, but `GET /repos` failed with 500 (`extra_forbidden` on the two 0003 repo columns). So a code rollback to before `b37eef2` needs a store backup from before migration 0003, or a fresh `TRACES_DATA_DIR` and a re-index. The same applies to rolling back before `83f5731` and migration 0002.

Newer code also changes data on startup: since #33 the API removes failed snapshot rows whose job failed with `sha_not_found` and that have no claims (D-031, O-9). Take the backup before starting a new build on an old store.

### Back up

This works while the API runs (SQLite online backup, WAL-safe). Run it from the clone root:

```bash
mkdir -p backups
uv run --frozen python - <<'PY'
import sqlite3, datetime
src = sqlite3.connect("file:.traces-data/traces.sqlite3?mode=ro", uri=True)
out = f"backups/traces-{datetime.datetime.now():%Y%m%dT%H%M}.sqlite3"
dst = sqlite3.connect(out); src.backup(dst)
print(out, dst.execute("PRAGMA integrity_check").fetchone()[0],
      dst.execute("SELECT max(version) FROM schema_migrations").fetchone()[0])
PY
```

Record the code SHA next to the backup (`git rev-parse HEAD`). Run directories under `.traces-data/runs/` hold per-run artifacts and can be copied as well. `.cache/` holds pinned checkouts and can be re-fetched.

### Restore

1. Stop the API by its PID (`ss -ltnp | grep :<api-port>`, then `kill <pid>`). Do not delete files.
2. Move the current store aside with its WAL files: `mkdir -p backups/replaced && mv .traces-data/traces.sqlite3* backups/replaced/`.
3. Copy the backup in: `cp backups/traces-<stamp>.sqlite3 .traces-data/traces.sqlite3`.
4. Check out the code SHA the backup was taken with (or a later one), then start with `./scripts/start.sh`.
5. Check `curl -s http://127.0.0.1:<api-port>/api/v1/health`. `store_migration` must match the code: 3 for any build from `b37eef2` on.
