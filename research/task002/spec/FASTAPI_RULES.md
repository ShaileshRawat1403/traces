# FastAPI framework rules R1 to R4 (Task 002, step 6), version 2

Status: DESK SPEC v2, 2026-10-21 (IST). Owner: Traces. Lab implements in step 7.
Scope: FastAPI routing (R1), FastAPI parameter-level dependencies (R2), the hey-api generated TypeScript client join (R3), and the static persistence path through the dependency-bound session (R4), in `fastapi/full-stack-fastapi-template` at `b1125d8839482cb7bbae603ddc6d0081bf87532e`. Nothing else. Every line ref below was read from the shared clone at that SHA (read-only, `cat -n`). Lines 1-based.

Framework versions at the SHA: FastAPI 0.141.1 (`uv.lock:468-469`), `@hey-api/openapi-ts` 0.97.3 (`frontend/package.json:52`). Rules are written for these versions; another locked version makes a rule return `inconclusive` until reviewed.

## 0. Common ground

- **Validators.** Rules run on CPython 3.14.8 `ast` and the TypeScript Compiler API, `typescript@6.0.3` (DECISIONS.md "Environment facts"). Nothing else. Tree-sitter and CodeGraph are never inputs to a rule decision (D-Q1, D-002A.2).
- **Rules are validators, not originators.** A rule runs on source and produces findings. A claim (from CodeGraph, the expected-chain fixture, or the injected set) becomes `verified` only when a rule finding establishes the same relationship at the same sites (EVIDENCE_SCHEMA V3). A rule finding with no matching claim is listed in the step 11 report as a rule-only finding; it is not surfaced as a claim in Task 002.
- **What counts.** A rule establishes a relationship through syntax, binding resolution, or its documented deterministic steps (D-002A.3). A rule never treats "the referenced symbol exists" as evidence for a relationship (D-Q1).
- **Binding resolution.** Python: module scope, `import`, `from ... import`, one re-export hop, resolved to `backend/app/<x>.py` or `<x>/__init__.py`. TypeScript: `ts.createProgram` with `frontend/tsconfig.json` (path alias `@/*` to `./src/*`, `tsconfig.json:21-22`), `TypeChecker.getSymbolAtLocation` and `getAliasedSymbol`. Library packages are not installed; library symbols do not resolve and give `inconclusive`. Binding resolution under 6.0.3 has not been run on this repo yet (DECISIONS.md limit).
- **Static only.** The target app is never imported, executed or started. `openapi.json` is not generated (D-Q6, D-002A.7); doing so needs separate authorization. Environment-dependent values use the source default with flag `runtime_config_dependent`.
- **Input.** Blobs at `repo_sha` from `task002/src/fsft` (`git show <sha>:<path>`), under the isolation wrapper.
- **Result values.** `pass` (relationship established), `fail` (the rule ran fully and the relationship does not hold), `inconclusive` (a construct outside scope, or an unresolved binding). Only `fail` can reject; `inconclusive` leaves the claim `unvalidated`.

## R1. Router prefix composition to full path

### Inputs
1. App object: `backend/app/main.py:21-25` (`app = FastAPI(...)`).
2. App include: `main.py:35` `app.include_router(api_router, prefix=settings.API_V1_STR)`.
3. `APIRouter(...)` assignments: `api/main.py:6` `api_router = APIRouter()`; `api/routes/items.py:10` `router = APIRouter(prefix="/items", tags=["items"])`; `api/routes/private.py:13` `router = APIRouter(tags=["private"], prefix="/private")`.
4. Router includes and enclosing `if`: `api/main.py:7-10` (login, users, utils, items); `api/main.py:13-14` (private, under `if settings.FASTAPI_ENV == "development":`).
5. Route decorators: `items.py:61` `@router.post("/", response_model=ItemPublic)`.
6. Constants: `settings.API_V1_STR` through `from app.core.config import settings` (`main.py:9`) to `API_V1_STR: str = "/api/v1"` (`core/config.py:22`). `Settings` reads `env_file="../.env"` (`core/config.py:15-18`); the committed `.env` does not set `API_V1_STR`. Flag `runtime_config_dependent`.

### Algorithm
1. Build the include graph app to routers: `(parent, child, prefix, tags, dependencies, condition)`, every name bound by binding resolution.
2. For each decorator, walk each path from the app to its router.
3. Full path = include prefixes along the path, then the router `prefix`, then the decorator path, concatenated as strings (assumption A1). Non-literal prefix values that do not resolve to a literal default: `inconclusive`.
4. Tags = include tags, router tags, decorator tags, in that order (A2).
5. Route name = function name unless `name=` is passed (A2).
6. Conditional includes add `condition` and flag `conditional_route`.

### Must reproduce at the SHA (L5)
| Item | Value | Source |
|---|---|---|
| method | `POST` | `items.py:61` |
| full path | `/api/v1/items/` = `"/api/v1"` + `""` + `"/items"` + `"/"` | `core/config.py:22` via `main.py:35`; `api/main.py:10`; `items.py:10`; `items.py:61` |
| tags | `["items"]` | `items.py:10` |
| route name | `create_item` | `items.py:62` |
| handler | `items.py:61-72` (`declaration`, decorator to body end) | |
| condition | none | `api/main.py:10` |

Control: `POST /api/v1/private/users/`, condition `settings.FASTAPI_ENV == "development"` (`api/main.py:13-14`, `private.py:13`, `private.py:23`).

### Relation to CodeGraph claims
CodeGraph's route node `POST /items` at `items.py:61` and its `references` edge to `create_item` (resolver `exact-match`, so class `unverified_inference`) become `verified` only if R1's finding has the same method, decorator line and handler. CodeGraph's router-local path (no `/api/v1`, no trailing slash) is kept in `provenance_raw`; R1 does not correct it in place.

### Out of scope, `inconclusive`
Dynamic prefixes, routers built in functions or loops, `app.mount`, `add_api_route`, `APIRoute` subclasses, unresolved include targets.

## R2. Parameter-level dependencies (Depends and Annotated aliases)

### Inputs
1. Handler `FunctionDef` from R1, all parameters including keyword-only (`items.py:63`, `*,`).
2. Parameter annotations and defaults.
3. Alias assignments `Name = Annotated[T, Depends(f)]`: `deps.py:26` (`SessionDep`, `Session`, `get_db`), `deps.py:27` (`TokenDep`, `str`, `reusable_oauth2`), `deps.py:49` (`CurrentUser`, `User`, `get_current_user`).
4. Imports into the route module: `items.py:7` `from app.api.deps import CurrentUser, SessionDep`; `private.py:6` `from app.api.deps import SessionDep`.
5. `dependencies=[Depends(...)]` on the decorator, the `APIRouter(...)`, each `include_router(...)` on the path, and `FastAPI(...)`. None for `items.py::create_item` or `private.py::create_user`; present elsewhere (`users.py:55`, `utils.py:13`).
6. Dependency callables for the transitive step: `get_db` `deps.py:21-23` (no parameters); `get_current_user` `deps.py:30-46` (`session: SessionDep, token: TokenDep`); `reusable_oauth2` `deps.py:16-18` (instance, leaf).

### Algorithm
1. For each parameter, resolve the annotation by binding resolution. `Annotated[T, ..., Depends(f), ...]` gives `depends_on(handler, f)` via the alias, `value_type = T` (resolved). Default `= Depends(f)` gives the same without alias. `Depends()` with no argument and `Security(...)`: `inconclusive`.
2. Add `dependencies=` entries at every level on every R1 path.
3. Transitive closure over the dependency callables' parameters; record depth and path.
4. Finding per direct dependency at `granularity: handler`: sites = the parameter annotation; inputs = the import, the alias binding, the callable declaration.
5. Absence: R2 states "`f` is not a dependency of handler H" only when steps 1 to 3 completed with no `inconclusive` on any of H's paths. That finding is what lets a validator return `fail` for a false `depends_on` claim.

### Must reproduce at the SHA
| Link | Finding | Source |
|---|---|---|
| L6 | `create_item` depends on `get_db` via `SessionDep` | `items.py:63`; `items.py:7`; `deps.py:26`; `deps.py:21-23` |
| L7 | `create_item` depends on `get_current_user` via `CurrentUser` | `items.py:63`; `items.py:7`; `deps.py:49`; `deps.py:30-46` |
| L7 transitive | `get_current_user` depends on `get_db` (`SessionDep`) and `reusable_oauth2` (`TokenDep`) | `deps.py:30`, `:26`, `:27`, `:16-18` |
| N2 | `private.py::create_user` closure is `{get_db}`; `CurrentUser` and `get_current_user` absent | `private.py:24` (`user_in: PrivateUserCreate, session: SessionDep`); `private.py:6`; `deps.py:26`; no `dependencies=` at `private.py:13`, `private.py:23`, `api/main.py:14`, `main.py:21-25`, `main.py:35` |

### Relation to CodeGraph claims
CodeGraph makes no handler-level dependency claim (Lab step 1: only file-level `items.py imports SessionDep` and `imports CurrentUser` at line 7, and the alias edges at `deps.py:26` and `:49`). R2 can verify those alias edges and the import edges; L6 and L7 claims come from the expected-chain fixture. CodeGraph's file-level import edges from `private.py` (`imports deps.py`, `imports SessionDep`, both at `private.py:6`) are true and are verified or left `unvalidated` on their own terms; N2's rejection does not touch them.

### Out of scope, `inconclusive`
Aliases built in functions, more than one re-export hop, `functools.partial`, class dependencies, `Security`, test dependency overrides.

## R3. Operation ID to generated SDK method join

### Inputs
Backend: `main.py:24` (`generate_unique_id_function=custom_generate_unique_id`); `main.py:14-15` (`return f"{route.tags[0]}-{route.name}"`); R1 operations.
Frontend (generated files are committed; `openapi.json` is not committed and is not generated, D-Q6): `frontend/openapi-ts.config.ts` lines 4, 5, 14 (`strategy: "byTags"`), 16 (`containerName: "{{name}}Service"`), 17 (`methodName: (name) => name.replace(/^[^-]*-/, "")`); `frontend/src/client/sdk.gen.ts` 287 (`class ItemsService`), 307 (`createItem`, `Options<itemsCreateItemData, ThrowOnError>`), 308 (`.post<`), 311 (`url: '/api/v1/items/'`), with `readItems` 293 to 297 (`.get`, same URL); `frontend/src/client/types.gen.ts` 809 (`itemsCreateItemData`), 813 (`url: '/api/v1/items/'`).

### Algorithm
1. Operation ID: evaluate the f-string symbolically; supported pieces are literals, `route.name`, `route.tags[<int>]`, `route.path`, `route.methods`. Result `items-create_item`.
2. K1 (required): `(HTTP method, full path)`. For every static method of every `*Service` class, the client call name gives the method and the `url` property literal gives the path (TS syntax). Exactly one SDK method must match R1's `(POST, /api/v1/items/)`. Zero: `fail`. More than one: `inconclusive`.
3. K2 (corroborating): naming. Type parameter `itemsCreateItemData` and method `createItem` match the generator's naming for `items-create_item`; container `ItemsService` matches the first tag (A3).
4. Cross-check: the matched `Data` type's `url` (`types.gen.ts:813`) equals the R1 path.
5. Findings: `implements_operation(ItemsService.createItem, POST /api/v1/items/ items-create_item)` (L4) and `routes_to(operation, items.py::create_item)` (L5).

`pass` needs K1 unique, K2 consistent, cross-check equal. K1 with K2 mismatch: `inconclusive`, reason `generated client may be out of date`. No K1 match: `fail`. The join is static: it says the generated client and the backend declare the same operation. It does not say an HTTP request was made.

### Relation to CodeGraph claims
CodeGraph has 0 edges across the HTTP boundary. L4 and L5 claims come from the expected-chain fixture; CodeGraph's `createItem references itemsCreateItemData` at `sdk.gen.ts:307` can be verified by binding resolution.

### Out of scope, `inconclusive`
Default FastAPI IDs, runtime-built URLs, several clients.

## R4. Static persistence path through the dependency-bound session (L8)

Separately documented write-operation rule set (D-Q4), with step types and label set by D-002A.5.

### Purpose
Establish, from source only, the ordered call path from a handler to the write calls on the session that FastAPI injects. The finding's label is **statically established persistence path**. It never states that data was persisted at runtime. The parser alone only confirms the calls are present (`observed`); R4 is what establishes the path (`verified`).

### Inputs
1. Handler and its R2 findings (which parameter is bound to which alias, and the alias's `value_type`).
2. The alias and type binding chain: `items.py:63` parameter `session: SessionDep`; `items.py:7` import; `deps.py:26` `SessionDep = Annotated[Session, Depends(get_db)]`; `deps.py:9` `from sqlmodel import Session`; `deps.py:21-23` `get_db` yields `Session(engine)` (`deps.py:22-23`).
3. The handler body statements.
4. Step-type table (fixed for Task 002, sqlmodel `Session` API names):

| Step type | Calls on the bound receiver | Meaning in the label |
|---|---|---|
| `model_validation` | `<Model>.model_validate(...)` where `<Model>` resolves to a class in `app.models` | builds and validates an instance; not a write |
| `session_stage` | `add`, `add_all`, `delete` | stages a change in the session |
| `session_commit` | `commit` | commit attempt |
| `session_reload` | `refresh` | reloads from the database; not a write |

Reads (`get`, `exec`, `execute`) and `flush`, `merge` are recorded as `observed` calls only in Task 002; they are not part of a persistence path finding.

### Algorithm
1. **Receiver check.** For each call `r.m(...)` in the handler body: `r` must be a `Name` bound to a handler parameter (binding resolution, no reassignment of `r` before the call in the same body; any reassignment or `del`: `inconclusive`). The parameter must be R2-bound to an alias whose resolved `value_type` is `sqlmodel.Session` and whose dependency callable is `get_db`. Method name alone never qualifies a call (D-002A.5).
2. **Model check** for `model_validation`: the class name resolves through `items.py:8` to `backend/app/models.py`, and the class declaration has keyword `table=True` (`models.py:87`) to count as a table model.
3. **Static call path.** Record the ordered steps by source position. Depth 0 (calls directly in the handler) is required for L8. Depth up to 2 through repo functions that receive the bound session as an argument (for example `crud.create_user(session=session, ...)`) is allowed for other handlers, with each hop resolved by binding resolution; anything else: `inconclusive`.
4. **Path condition.** A `persistence_path` finding needs at least one `session_stage` followed by a `session_commit` on the same receiver, both on the straight-line body with no branch (`if`, `try`, loop) between them; a branch makes the finding `inconclusive` in Task 002.
5. **Finding.** `persistence_path(handler)` with ordered steps, each with its `site` location and step type, the receiver binding chain as `input` locations, and `qualifier: statically established persistence path`.

### Must reproduce at the SHA (L8)
| Order | Site | Step type | Receiver check |
|---|---|---|---|
| 1 | `items.py:68` `Item.model_validate(item_in, update={"owner_id": current_user.id})` | `model_validation` | `Item` resolves via `items.py:8` to `models.py:87` (`table=True`) |
| 2 | `items.py:69` `session.add(item)` | `session_stage` | `session` = parameter at `items.py:63`, `SessionDep` (`deps.py:26`), `Session` (`deps.py:9`), `get_db` (`deps.py:21-23`) |
| 3 | `items.py:70` `session.commit()` | `session_commit` | same |
| 4 | `items.py:71` `session.refresh(item)` | `session_reload` | same |

Expected label: "statically established persistence path: `create_item` stages `Item` via `session.add` (69) and commits via `session.commit` (70) on the `SessionDep`-bound `Session`; model built at 68; reloaded at 71". No `crud` call on the path. This is also the evidence that rejects N1.

### Relation to CodeGraph claims
CodeGraph has 0 outgoing edges from `create_item` and 5 unresolved references at 68 to 71 (`failed`). Those references can reach `observed` (the call text is there); R4 does not use them. The L8 claim comes from the expected-chain fixture.

### Out of scope, `inconclusive`
Sessions not obtained through an R2-resolved alias, context-managed sessions inside the handler, async sessions, raw SQL, ORM events, background tasks, transactions spanning helpers beyond depth 2.

## Assumptions about framework behavior (not in repo source)

| Id | Assumption | Used by | Check in Task 002 |
|---|---|---|---|
| A1 | FastAPI concatenates include prefix, router prefix and route path as strings | R1 | R3 K1: the committed generated client, built from the real app's OpenAPI at generation time, has `url: '/api/v1/items/'` (`sdk.gen.ts:311`) |
| A2 | tag order include, router, decorator; `route.name` defaults to the function name | R1, R3 | R3 K2: `itemsCreateItemData` encodes `items` and `CreateItem` |
| A3 | hey-api 0.97.3 casing turns `items-create_item` into `itemsCreateItem` and `create_item` into `createItem` | R3 K2 | pinned to `@hey-api/openapi-ts` 0.97.3 (`frontend/package.json:52`) and its config (`openapi-ts.config.ts`), corroborated by the committed generated output; the version pin alone is not independent proof of the naming behavior (D-002B.4) |
| A4 | `Session.add` stages and `Session.commit` attempts a commit (sqlmodel on SQLAlchemy) | R4 | not checked; library semantics. This is why the R4 label says "statically established persistence path" and nothing about runtime |

Decision 002-B ruling 4 (2026-10-21): A1 to A3 approved with qualification. A1 and A2 are source-backed framework rules. A3 is pinned to hey-api 0.97.3 and its config, with the generated output corroborating; the version pin alone is not independent proof of naming behavior. A4 is unchanged.

Generated artifacts are evidence about the real framework behavior only for the version and commit that generated them. If the generated client is older than the backend, A1 and A2 checks are `inconclusive`. Generating `openapi.json` would settle A1 to A3 with runtime evidence; it is deferred and needs separate authorization (D-Q6, D-002A.7).
