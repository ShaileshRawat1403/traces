# FastAPI framework rules R1, R2, R3 (Task 002, step 6)

Status: DESK SPEC, draft 1, 2026-10-21 (IST). Owner: Traces. Lab implements in step 7, after step 1a.
Scope: FastAPI routing, FastAPI parameter-level dependencies, and the hey-api generated TypeScript client, as used in `fastapi/full-stack-fastapi-template` at `b1125d8839482cb7bbae603ddc6d0081bf87532e`. Nothing else. Every line ref below was read from the shared clone at that SHA (read-only, `cat -n`). Lines 1-based.

Framework versions at the SHA: FastAPI 0.141.1 (`uv.lock:468-469`), `@hey-api/openapi-ts` 0.97.3 (`frontend/package.json:52`). Rules are written for these versions; a different locked version makes the rule return `inconclusive` until reviewed.

## 0. Common ground

- **Parsers.** Python inputs are read with CPython 3.14 `ast` (needed: `backend/app/api/deps.py:36` is `except InvalidTokenError, ValidationError:`, which 3.13 rejects). TypeScript inputs are read with the TypeScript compiler API (version: EVIDENCE_SCHEMA.md Q2).
- **Input.** Blobs at `repo_sha`, read with `git show <sha>:<path>` from the temporary checkout. The rules never read CodeGraph output.
- **Static only.** No import or execution of the app. Values that can change at runtime (environment overrides) are recorded as the source default with flag `runtime_config_dependent`.
- **Name resolution.** Within one module: module-level assignments, `def`, `class`, `import`, `from ... import`. Across modules: `from app.x import y` resolved to `backend/app/x.py` or `backend/app/x/__init__.py`; frontend `@/` resolved to `frontend/src/` (`frontend/tsconfig.json:21-22`, `frontend/vite.config.ts:14-15`). Anything else is `inconclusive`.
- **Results.** Each rule emits `statically_derived` claims with `provenance = traces:rule:R<n>` and `extractor.families` = the parsers it used, and every input location it used with role `input`. A rule result is `pass`, `fail` (the rule ran fully and the relationship does not hold) or `inconclusive` (the rule met a construct outside its scope). Only `fail` can reject; `inconclusive` leaves `unvalidated`.

## R1. Router prefix composition to full path

### Inputs
1. The app object: a module-level `Name = FastAPI(...)` call. At the SHA: `backend/app/main.py:21-25`.
2. Every `<app>.include_router(<router>, prefix=..., tags=..., dependencies=...)` call on it. At the SHA: `main.py:35` `app.include_router(api_router, prefix=settings.API_V1_STR)`.
3. Every `APIRouter(...)` assignment and its `prefix`, `tags`, `dependencies` keywords. At the SHA: `api/main.py:6` `api_router = APIRouter()`; `api/routes/items.py:10` `router = APIRouter(prefix="/items", tags=["items"])`; `api/routes/private.py:13` `router = APIRouter(tags=["private"], prefix="/private")`.
4. Every `<router>.include_router(<module>.router, ...)` call, including any enclosing `if`. At the SHA: `api/main.py:7-10` (login, users, utils, items), `api/main.py:13-14` (private, under `if settings.FASTAPI_ENV == "development":`).
5. Route decorators `@<router>.<method>(<path>, ...)` with method in `get, post, put, patch, delete, options, head`. At the SHA for L5: `items.py:61` `@router.post("/", response_model=ItemPublic)`.
6. Constant values used in prefixes. `settings.API_V1_STR` resolves through `from app.core.config import settings` (`main.py:9`) to class `Settings` field `API_V1_STR: str = "/api/v1"` (`core/config.py:22`). Settings come from `BaseSettings` with `env_file="../.env"` (`core/config.py:15-18`); the committed `.env` does not set `API_V1_STR` (read at the SHA), so the default stands. Flag `runtime_config_dependent`.

### Algorithm
1. Build the include graph from app to each router: edges `(parent, child, prefix, tags, dependencies, condition)`.
2. For each route decorator, walk every path from the app to the decorator's router. A router reachable by two paths gives two operations.
3. Full path = concatenation of, in order: each `include_router` `prefix` on the path, the router's own `APIRouter(prefix=...)`, the decorator path. Concatenate as strings, exactly as FastAPI does; do not add or strip slashes. Prefix values must resolve to string literals or to settings fields with literal defaults; anything else: `inconclusive`.
4. Tags = include tags along the path, then router tags, then decorator tags, in that order (FastAPI 0.141.1 behavior; see "Assumptions").
5. Route name = the decorated function's name unless the decorator passes `name=` (FastAPI default; see "Assumptions").
6. Conditions: if any include on the path is inside an `if`, the operation carries `condition` (source text and location) and flag `conditional_route`.
7. Emit: a `source_backed_declaration` per input declaration; one `statically_derived` claim per operation: `{method, full_path, tags, route_name, handler symbol, handler range (decorator_to_body_end)}` with all inputs as locations.

### What it must reproduce at the SHA (L5)
| Item | Value | Source lines |
|---|---|---|
| method | `POST` | `items.py:61` |
| full path | `/api/v1/items/` = `"/api/v1"` + `""` + `"/items"` + `"/"` | `core/config.py:22` via `main.py:35`; `api/main.py:10` (no prefix); `items.py:10`; `items.py:61` |
| tags | `["items"]` | `items.py:10` (no tags at `main.py:35` or `api/main.py:10`) |
| route name | `create_item` | `items.py:62` |
| handler range | `items.py:61-72` | decorator 61, body ends 72 |
| condition | none | `api/main.py:10` is unconditional |

Control case: the private router gives `POST /api/v1/private/users/` with condition `settings.FASTAPI_ENV == "development"` (`api/main.py:13-14`, `private.py:13`, `private.py:23`).

### As an independent validator
R1 does not read CodeGraph. CodeGraph's route node for this handler is `route:backend/app/api/routes/items.py:61:POST:/`, named `POST /items` (Task 001 index, read-only), which is router-local: it lacks `/api/v1` and the trailing slash. R1 therefore validates CodeGraph's method and decorator line and supplies the full path CodeGraph does not have. Agreement on method and line 61: `framework_rule` `pass` for the CodeGraph route claim. A different method or line: `fail`.

### Failure cases
Dynamic prefixes, routers built in functions or loops, `app.mount`, `add_api_route`, `APIRoute` subclasses, `include_router` on an object R1 cannot resolve: `inconclusive`, never guessed.

## R2. Parameter-level dependencies (Depends and Annotated aliases)

### Inputs
1. The handler `FunctionDef` from R1, all parameters including keyword-only (`create_item` uses `*,` at `items.py:63`).
2. Each parameter annotation and default.
3. Module-level alias assignments of the form `Name = Annotated[T, Depends(f)]`. At the SHA: `deps.py:26` `SessionDep = Annotated[Session, Depends(get_db)]`; `deps.py:27` `TokenDep = Annotated[str, Depends(reusable_oauth2)]`; `deps.py:49` `CurrentUser = Annotated[User, Depends(get_current_user)]`.
4. Imports that bring aliases into the route module. At the SHA: `items.py:7` `from app.api.deps import CurrentUser, SessionDep`; `private.py:6` `from app.api.deps import SessionDep`.
5. Dependency-level lists: `dependencies=[Depends(...)]` on the decorator, on `APIRouter(...)`, on each `include_router(...)` on the path, and on `FastAPI(...)`. At the SHA: none for `items.py` `create_item` or `private.py` `create_user`; present elsewhere, for example `users.py:55` and `utils.py:13` use `dependencies=[Depends(get_current_active_superuser)]`.
6. The dependency callables' own signatures, for the transitive step. At the SHA: `get_db` `deps.py:21-23` (no parameters); `get_current_user` `deps.py:30-46` (`session: SessionDep, token: TokenDep`); `reusable_oauth2` `deps.py:16-18` (an `OAuth2PasswordBearer` instance, treated as a leaf).

### Algorithm
1. For each parameter: resolve the annotation name through imports to its definition. If it is `Annotated[T, ..., Depends(f), ...]`, emit `depends_on(handler, f)` via the alias, with `value_type = T`. If the default is `Depends(f)`, emit the same without alias. `Depends()` with no argument (class as dependency) and `Security(...)`: `inconclusive` in Task 002.
2. Add dependency-level lists from input 5 at every level on every R1 path to the handler.
3. Transitive closure: apply steps 1 and 2 to each dependency callable's parameters, stopping at callables with no dependency parameters or at non-function leaves. Record depth and the path.
4. Emit per direct dependency a `statically_derived` `depends_on` claim at `granularity = handler`, locations: the parameter (site), the alias line (input), the callable range (to_decl). Transitive ones are separate claims with `depth > 1`.
5. Value type (for persistence, L8): for each parameter bound through an alias, record `T` resolved through imports. `SessionDep` gives `Session` from `from sqlmodel import Session` (`deps.py:9`).
6. Persistence calls: inside the handler body, a call `p.<m>(...)` where `p` is a parameter with value type `sqlmodel.Session` and `m` in `add, add_all, delete, commit, refresh, flush, merge, exec, get, execute`: emit `persists_via(handler, Session.<m>)` at `granularity = statement`, site location at the call.
7. Absence: the rule can state that `f` is **not** a dependency of a handler only after steps 1 to 3 completed with no `inconclusive` anywhere on the handler's paths. Otherwise the answer is `inconclusive`.

### What it must reproduce at the SHA
| Link | Claim | Source lines |
|---|---|---|
| L6 | `create_item` depends on `get_db` via `SessionDep` | param `items.py:63`; import `items.py:7`; alias `deps.py:26`; callable `deps.py:21-23` |
| L7 | `create_item` depends on `get_current_user` via `CurrentUser` | param `items.py:63`; import `items.py:7`; alias `deps.py:49`; callable `deps.py:30-46` |
| L7 transitive | `get_current_user` depends on `get_db` (via `SessionDep`) and `reusable_oauth2` (via `TokenDep`) | `deps.py:30`, `deps.py:26`, `deps.py:27`, `deps.py:16-18` |
| L8 | `create_item` persists via `Session.add`, `Session.commit`, `Session.refresh` | `items.py:69`, `items.py:70`, `items.py:71`; value type from `deps.py:26` and `deps.py:9` |
| N2 | `private.py::create_user` has dependency closure `{get_db}` only; `get_current_user` absent | params `private.py:24` (`user_in: PrivateUserCreate, session: SessionDep`); import `private.py:6`; alias `deps.py:26`; no `dependencies=` at `private.py:13`, `private.py:23`, `api/main.py:14`, `main.py:21-25`, `main.py:35` |

### As an independent validator
- For CodeGraph claims: R2 does not read CodeGraph. CodeGraph has `CurrentUser` references `get_current_user` at `deps.py:49`, but no edge from any handler parameter to an alias (Task 001 index: `items.py` `create_item` has 0 outgoing edges). R2 supplies handler-level dependency claims CodeGraph does not make.
- For N2: R2 returns `fail` for the claim `private.py::create_user depends_on get_current_user` at `granularity = handler`, because step 7 completed with closure `{get_db}`. This is a rule `fail`, not an absence of data.
- N2 must not reject the broader result. CodeGraph's `impact get_current_user` lists `backend/app/api/routes/private.py` as `file private.py:1` (`_tests/logs/codegraph-colby-di.log:17-18`). At `granularity = file` this is true: `private.py:6` imports from `app.api.deps`, the module that defines `get_current_user`. That file-level claim stays as its own record and is not touched by N2's rejection (EVIDENCE_SCHEMA.md V6).

### Failure cases
Aliases built in functions, re-exported through several modules beyond one `from ... import` hop, `functools.partial`, class dependencies, `Security`, dependency overrides in tests: `inconclusive`.

## R3. Operation ID to generated SDK method join

### Inputs
Backend:
1. `generate_unique_id_function=` keyword on `FastAPI(...)`: `main.py:24`, naming `custom_generate_unique_id`.
2. That function's body: `main.py:14-15`, `return f"{route.tags[0]}-{route.name}"`.
3. R1 operations (method, full path, tags, route name).

Frontend (generated files are committed; no `openapi.json` is committed at the SHA, so the spec file itself cannot be read):
4. Generator config `frontend/openapi-ts.config.ts`: input `./openapi.json` (line 4), output `./src/client` (line 5), SDK plugin `strategy: "byTags"` (line 14), `containerName: "{{name}}Service"` (line 16), `methodName: (name) => name.replace(/^[^-]*-/, "")` (line 17).
5. `frontend/src/client/sdk.gen.ts`: class `ItemsService` (line 287); method `createItem` (line 307) with type parameter `Options<itemsCreateItemData, ThrowOnError>`; client call `.post<...>` (line 308); `url: '/api/v1/items/'` (line 311). Same URL with `.get` in `readItems` (lines 293-297).
6. `frontend/src/client/types.gen.ts`: `export type itemsCreateItemData` (line 809) with `url: '/api/v1/items/'` (line 813).
7. Generation script, for context only: `scripts/generate-client.sh:7` builds `openapi.json` with `FASTAPI_ENV=development`, so conditional routes such as private ones are in the generated client (`sdk.gen.ts:367` `PrivateService`).

### Algorithm
1. Operation ID. Evaluate the function body from input 2 symbolically. Supported pieces only: string literals, `route.name`, `route.tags[<int>]`, `route.path`, `route.methods`. Anything else: `inconclusive`. With R1 values: `"items" + "-" + "create_item"` = `items-create_item`.
2. Key K1 (primary): `(HTTP method, full path)`. From the frontend, read every static method in every `*Service` class in `sdk.gen.ts`: method from the client call name (`.get`, `.post`, `.put`, `.patch`, `.delete`), path from the `url` property literal. Match R1's `(POST, /api/v1/items/)`. Exactly one SDK method must match; zero or several: `fail` (zero) or `inconclusive` (several). At the SHA: `ItemsService.createItem` only (`readItems` has the same URL but `.get`).
3. Key K2 (corroborating): naming. The type parameter of the matched method, `itemsCreateItemData`, must equal the generator's type name for operation ID `items-create_item` plus `Data`. The method name must equal `methodName("items-create_item")` = `create_item`, transformed by the generator's method-name casing into `createItem`. The container must be `{{name}}Service` for the first tag: `ItemsService`. The `-` removal, the casing of `itemsCreateItem`, and `create_item` to `createItem` are generator behavior of `@hey-api/openapi-ts` 0.97.3, not visible in repo source; see "Assumptions".
4. Cross-check: the `url` in `types.gen.ts` for the matched `Data` type equals the R1 full path.
5. Emit `implements_operation(sdk method, operation)` (L4) and `routes_to(operation, handler)` (L5), each `statically_derived`, with every input above as a location.

Result: `pass` needs K1 unique match, K2 consistent, and the cross-check equal. K1 match with K2 mismatch: `inconclusive`, reason `generated client may be out of date with the backend`. No K1 match: `fail`.

### What it must reproduce at the SHA
| Link | Value | Source lines |
|---|---|---|
| L4 | `ItemsService.createItem` implements `POST /api/v1/items/`, operation ID `items-create_item` | `sdk.gen.ts:287`, `:307`, `:308`, `:311`; `types.gen.ts:809`, `:813`; `openapi-ts.config.ts:14-17`; `main.py:14-15`, `:24` |
| L5 | operation `items-create_item` is served by `items.py::create_item` | R1 outputs (`items.py:61-72`, `items.py:10`, `api/main.py:10`, `main.py:35`, `core/config.py:22`) |

### As an independent validator
R3 joins two parser families (CPython `ast` for the backend, TypeScript compiler for the frontend) and reads no CodeGraph output. In the Task 001 index CodeGraph has 0 edges from `sdk.gen.ts` to backend files (`_tests/logs/codegraph-colby-di.log:28`), so R3 is the only source of L4 and L5 links across the HTTP boundary. Because R3 is also their extractor, L4 and L5 still need a check from a family outside `{cpython-ast, typescript-compiler}` on their input locations to reach `verified` (EVIDENCE_SCHEMA.md section 6): CodeGraph syntax-level confirmation if eligible, otherwise the second parser (EVIDENCE_SCHEMA.md Q1).

### Failure cases
No `generate_unique_id_function` (FastAPI default IDs): out of scope, `inconclusive`. URLs built at runtime, path parameters in different syntax, several clients: `inconclusive`.

## Assumptions about framework behavior (not in repo source)

| Id | Assumption | Used by | How it is checked in Task 002 |
|---|---|---|---|
| A1 | FastAPI concatenates include prefix, router prefix and route path as strings | R1 | K1 in R3: the generated client, built from the real app's OpenAPI output, has `url: '/api/v1/items/'` (`sdk.gen.ts:311`), which matches R1's string concatenation |
| A2 | route tags order: include, router, decorator; `route.name` defaults to the function name | R1, R3 | K2 in R3: `itemsCreateItemData` encodes `items` and `CreateItem`, matching tag `items` and name `create_item` |
| A3 | hey-api 0.97.3 casing turns `items-create_item` into `itemsCreateItem` and `create_item` into `createItem` | R3 K2 | observed in the committed generated files only; documented as **DOCUMENTED-CLAIM** until the generator source is read (no install in Task 002) |

Each check above uses generated artifacts that came from running the real app at generation time, which makes them evidence about real framework behavior, but only for the version and commit that generated them. If the generated client is older than the backend, A1 and A2 checks report `inconclusive`, not `pass`.

## Open questions

- **Q5 (Architect1).** Persistence detection (R2 step 6) lists Session method names. Is that inside "FastAPI dependencies" scope, or should L8 be validated by the parser alone (call sites at `items.py:68-71`) with no rule?
- **Q6 (Architect1).** Generating `openapi.json` by importing the app (as `scripts/generate-client.sh:7` does) would give runtime-observed operation IDs and settle A1 to A3. It needs backend dependencies installed and executes target code. Proposal: not in Task 002; listed for later with its own approval.
