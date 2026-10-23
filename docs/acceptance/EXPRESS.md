# Different stack: an Express app through Traces (G-4)

Local run on the Traces Lab box, not CI. Run on 2026-10-23 at 13:11 IST, on a scratch server (API 18820, web 15180) built from `ws/lab-acceptance` @ `d492e0e`. The product code is identical to `build/traces-v1` @ `e532644`. The scratch store and cache are in `.traces-data/acceptance/express/` (gitignored). The box app was not used. The only network use was the target fetch.

Re-run after merging `build/traces-v1` @ `b37eef2` (fixes for F-1 to F-6) as `3bad896`, on a fresh store from the cached clone. Results were identical: 3,671 claims, 0 verified, and the same counts. The trace from `register` is still complete with 3 edges. The `POST /register` explain answer is unchanged. `/meta` validators are still python and typescript.

## Target

| | |
| --- | --- |
| Repository | [hagopj13/node-express-boilerplate](https://github.com/hagopj13/node-express-boilerplate) |
| Pinned SHA | `179ae84efec61b14206d0305d941daed6c6d07f9` (master HEAD, 2023-08-12) |
| License | MIT (`LICENSE`, "Copyright (c) 2019 Hagop Jamkojian") |
| Shape | Express 4 REST API: CommonJS `require`, routes, controllers, services, Mongoose models, Joi validations, Passport JWT, Jest tests. 50 JavaScript files, 241 commits (full history, not shallow) |
| Why | Real routes and data handling, meaningful history, and every pattern the FastAPI fixture lacks: JavaScript rather than Python or TypeScript, CommonJS, router mounting, a services barrel, and Mongoose rather than SQLModel |

## Run

```
POST /api/v1/repos {"url": "https://github.com/hagopj13/node-express-boilerplate"}                  -> 201
POST /api/v1/repos/github.com__hagopj13__node-express-boilerplate/index-jobs {"sha": "179ae84e..."}  -> 202, job j_bf427f28f26e4bccae05
```

The job succeeded in 5 s (13:11:47 to 13:11:52 IST) and went through every phase, history included. The adapter checks passed (`discovered=accounted=56`), and the isolation probe ran in its own network namespace.

Stored: 3,671 claims. That is 311 static nodes, 712 static relationships and 1,442 unresolved references, plus 1,206 history records. Status: 0 verified, 1,153 observed (all history), 2,176 unvalidated, 342 missing_location, 0 rejected.

## What Traces shows (API and UI)

| Screen | Result | Honest? |
| --- | --- | --- |
| Overview | Pinned SHA and the "Static analysis only" banner. Purpose is "not verified from code structure", the README heading is labelled as documentation text, and the manifests name Express and Jest. 14 components, 17 route records ("Methods marked UNKNOWN were not on the record"). Start here: "Nothing on this snapshot is verified yet." | Yes. Unknowns are stated; nothing is invented |
| Graph | The default filter (verified and observed) shows "0 nodes, 0 relationships" and "Hidden by current filters: 712 (370 inferred (unvalidated), 342 inferred (no source location))". When inferred edges are included, every edge is labelled inferred | Honest, but empty by default because of F-10 |
| Trace (default) | "No static persistence path is recorded for this snapshot, so there is no cross-layer flow to draw." | An honest unknown, but persistence detection does not know Mongoose (O-8) |
| Trace from `register` | 3 steps, 0 gaps, "Complete: every step is backed by a recorded relationship". The real flow calls `userService.createUser` and `tokenService.generateAuthTokens`; those are stored only as unresolved references and are not shown | **No**: F-9, the trace calls itself complete |
| Routes, Components | The API returns them. The UI pages are placeholders (G-3) | n/a |
| History | Timeline 241 commits. The co-change view says "not evidence of a code dependency" | Yes |
| Review | 0 rejected | Yes |
| Explain (no key) | See below | Mixed |

Explain answers:
- "Where is a user saved to the database?" and "Does it use Depends(get_db)?": "No persistence path is recorded in this snapshot." An unknown, not an invented FastAPI path.
- "Does register send an email at runtime?": "Static evidence cannot show runtime behavior", then "Not established" email-service edges.
- "What does POST /register do?": "This snapshot has no README or manifest records, so the project's stated purpose and dependencies are unknown here." The overview does show the README heading and the manifest frameworks, and the route `POST /register` is stored at `src/routes/v1/auth.route.js:9`. Neither is cited (F-11).
- "Which files changed together with src/services/user.service.js?": cites 8 patterns, none of which involve `user.service.js`. This is F-8 again on a second stack. Every pattern carries the caveat and is never stated as a fact.

## Spot-checks against Git (read-only, at the pinned SHA)

Scripts and output are in `.traces-data/acceptance/express/` (`bindcheck.py`, `spotcheck_hist.py`, `cochange_recount.py`).

| Check | Result |
| --- | --- |
| `imports`: each `require('./x')` site resolves to the target file | **107 of 107 correct**. All 107 are unvalidated with "L3 fail, not established: token 'import\|from\|export'" (F-10) |
| `calls`, `instantiates`, `references` (all 285 unvalidated): does the target match how the name is bound in the site file? | 231 correct. 7 wrong: `new User(...)` in `tests/unit/models/user.model.test.js` points at `tests/fixtures/user.fixture.js`, but the file binds `User` from `require('../../../src/models')`. 4 point at the local `require` constant for a package callee (`cors`, `helmet`, `rateLimit`). 21 could not be bound by the script and are unchecked. None is verified; all are labelled inferred |
| Routes | 15 of 15 operation routes have the right method, local path, file and line. 2 middleware mounts are recorded as UNKNOWN-method routes: `app.use('/v1/auth', authLimiter)` at `src/app.js:50`, and `router.use('/', swaggerUi.serve)` at `docs.route.js:13`. Paths are not prefixed with `/v1/auth` or `/v1/users`, because the mounts are computed by `forEach` over an array (O-7). A literal mount is composed correctly (`tests/e2e/test_express_patterns.py`) |
| History commits | 20 of 20 commit nodes have the right parents and are ancestors of the pin |
| History file changes | 30 of 30 `commit_modifies` / `commit_adds` match `git diff --name-status -M50%` |
| Co-change (file level) | 14 of 18 exact on a recount with the record's own criteria (non-merge, at most 30 files, bots excluded, renames to head paths). The 4 differences all involve `user.service.js` or `auth.service.js`. Both were deleted in `ffb47ae` and re-added in `c6c4206`, and Traces counts only from the re-add (`revs_b` 6 against 14 path commits). The sentence says "commits that touched either of these files", which does not say that (O-6) |

## Overfitting to FastAPI or Python

1. **No JavaScript validator** (F-10). `/api/v1/meta` lists validators for `python` and `typescript` only. Every JavaScript claim is unvalidated or missing_location, so nothing is verified and the default graph is empty. The TypeScript compiler API that is already pinned can read JavaScript.
2. **The import text check expects `import`, `from` or `export`** (F-10). CommonJS `require` lines fail L3, so 107 correct imports are marked not established.
3. **Persistence means a FastAPI/SQL path** (O-8). `User.create` through a Mongoose model is not recognised. Trace and explain say "No persistence path is recorded", which is honest but misses the app's main data flow.
4. Layers are reasonable for this layout: `src/controllers` and `src/routes` are api, `src/models` is data, and the rest of `src/` is backend.

## Unknowns versus invented links

The UI shows unknowns rather than invented links. Purpose, persistence and runtime are stated as unknown. All 712 static relationships are labelled inferred, and the 7 wrong CodeGraph `User` edges are never shown as verified.

The one overclaim is the trace's "Complete" label (F-9). It hides the unresolved controller-to-service calls behind a "complete" verdict.

## Automated

`tests/e2e/test_express_patterns.py` indexes a 7-file CommonJS Express app with the real worker (no network). It runs in the CI `security` job.
- Pass: CommonJS requires, and a route mounted with a literal path composed to `POST /v1/auth/register`.
- Pass: nothing is shown as verified, and the overview says so.
- xfail (strict): F-10, a true require is not verified.
- xfail (strict): F-9, a trace with stored unresolved calls is reported complete.
- With `--runxfail`, both xfails fail for the stated reason.

## BYOK chat (G-5)

Superseded: see G-5 in [../ACCEPTANCE.md](../ACCEPTANCE.md). The box app runs `b37eef2` with BYOK chat. `tests/e2e/chat_g5.cjs` passes 13 of 13 with an in-process stub provider. It ran against the box web app on 5731 (read-only), and in the CI e2e job's local run on the fsft seed. It covers:
- the consent dialog, and that Cancel and Escape send nothing
- the outbound manifest, which matches what the stub receives
- rejected claims, which are never sent
- the key, which never reaches the Traces API, its logs or its store

Live-provider chat is untested in v1 (L-2). No paid key was used.
