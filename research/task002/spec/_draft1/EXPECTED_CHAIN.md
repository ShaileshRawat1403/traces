# Expected chain L1 to L9, negative controls N1 and N2 (draft for step 5)

Status: DESK DRAFT, 2026-10-21 (IST). Owner of this draft: Traces. Lab finalizes it in step 5 as `task002/fixtures/chain_create_item.json`, and Traces spot-checks every line against `git show b1125d88:<path>`.
Repo `fastapi/full-stack-fastapi-template` at `b1125d8839482cb7bbae603ddc6d0081bf87532e`. Every line below was read from the shared clone at that SHA with `cat -n` (read-only). Lines 1-based. Base source: Lab ground truth Q3 and Q4 (`lab/B/ground-truth.md`); where this draft differs from it, the row says so.

Families: `ts` = TypeScript compiler, `py` = CPython 3.14 `ast`, `cg` = CodeGraph 1.6.2, `2p` = second parser (EVIDENCE_SCHEMA.md Q1). "Second family" means `cg` if step 1a sets `codegraph_validator_eligible = true`, else `2p`.

The "CodeGraph in Task 001" column reports what the Task 001 index holds (read-only query). It is context for step 1 and step 8, not an assumption that CodeGraph passes step 1.

## Chain

### L1. Items page renders AddItem
- Claim: `frontend/src/routes/_layout/items.tsx::Items` renders `frontend/src/components/Items/AddItem.tsx::AddItem`. `renders`, granularity `statement`, class `statically_derived`.
- Locations: site `items.tsx:65` (`<AddItem />`); input `items.tsx:8` (`import AddItem from "@/components/Items/AddItem"`); from_decl `items.tsx:57-70` (`function Items()`); to_decl `AddItem.tsx:40-141` (`const AddItem = () =>`), default export `AddItem.tsx:143`. Route registration for context: `items.tsx:20` (`createFileRoute("/_layout/items")`).
- Extractor: `ts`. Validators: L1 to L3 text checks; second family syntax check at `items.tsx:65`.
- CodeGraph in Task 001: `Items` calls `AddItem`, `heuristic`, `synthesizedBy: jsx-render`, line 57. Line 57 is the enclosing function, not the site, so this CodeGraph record starts `unvalidated` with `enclosing_scope` precision and goes through R-enclosing recovery (EVIDENCE_SCHEMA.md section 7), which should find line 65.
- Expected end: `verified`.

### L2. Form submit bound to onSubmit, which calls mutate
- Claim A: `AddItem` binds `onSubmit` to the form submit. `binds_handler`, granularity `statement`.
  Locations: site `AddItem.tsx:88` (`<form onSubmit={form.handleSubmit(onSubmit)}>`); to_decl `AddItem.tsx:68-70` (`const onSubmit = (data: FormData) => {`).
- Claim B: `onSubmit` calls `mutation.mutate`. `calls`, granularity `statement`.
  Locations: site `AddItem.tsx:69` (`mutation.mutate(data)`); input `AddItem.tsx:55-66` (`const mutation = useMutation({`).
- Extractor: `ts`. Validators: text checks; second family syntax check at 88 and 69.
- CodeGraph in Task 001: `AddItem` references `onSubmit` at line 88, `resolvedBy: function-ref`, confidence 0.95. No record found for the `mutate` call (not queried in detail; Lab checks in step 8).
- Expected end: both `verified`. L2 counts as verified only when A and B both are.

### L3. Mutation calls the generated client
- Claim: `AddItem` (inside `mutationFn`) calls `frontend/src/client/sdk.gen.ts::ItemsService.createItem`. `calls`, granularity `statement`.
- Locations: site `AddItem.tsx:56` (`mutationFn: (data: ItemCreate) => ItemsService.createItem({ body: data }),`); input `AddItem.tsx:8` (`import { type ItemCreate, ItemsService } from "@/client"`); input `frontend/src/client/index.ts:3` (re-export of `ItemsService` from `./sdk.gen`); to_decl `sdk.gen.ts:307-318`.
- Extractor: `ts`, and `cg` as a separate record.
- CodeGraph in Task 001: `AddItem` calls `createItem` at line 56, `resolvedBy: import`, confidence 0.9, target `sdk.gen.ts:307`.
- Expected end: `verified` (`ts` record validated by second family; `cg` record validated by `ts`).

### L4. Generated method implements the API operation
- Claim: `ItemsService.createItem` implements `POST /api/v1/items/`, operation ID `items-create_item`. `implements_operation`, granularity `symbol`. Extractor: R3.
- Locations: `sdk.gen.ts:287` (class), `:307` (method, `Options<itemsCreateItemData, ThrowOnError>`), `:308` (`.post<`), `:311` (`url: '/api/v1/items/'`); `types.gen.ts:809`, `:813`; `openapi-ts.config.ts:14`, `:16`, `:17`; `backend/app/main.py:14-15`, `:24`.
- Auth context, not a separate link: `sdk.gen.ts:310` (bearer security); token supplied at `frontend/src/main.tsx:17-20` (`client.setConfig`, `auth: () => localStorage.getItem("access_token")`). Lab ground truth cites `main.tsx:19` for the token; the call spans 17-20.
- Validators: R3 K1 and K2 and the `types.gen.ts` cross-check; second family syntax check on the inputs.
- CodeGraph in Task 001: 0 edges from `sdk.gen.ts` to backend files.
- Expected end: `verified`. If A3 (FASTAPI_RULES.md) stays a documented claim, K2 still checks against committed generated files; L4 passes on K1 plus K2 as observed.

### L5. API operation routed to the backend handler
- Claim: operation `POST /api/v1/items/` (`items-create_item`) is served by `backend/app/api/routes/items.py::create_item`. `routes_to`, granularity `handler`. Extractor: R1 and R3.
- Locations: `core/config.py:22` (`API_V1_STR: str = "/api/v1"`); `main.py:9` (settings import); `main.py:35` (`app.include_router(api_router, prefix=settings.API_V1_STR)`); `api/main.py:3`, `:6`, `:10`; `items.py:10` (`router = APIRouter(prefix="/items", tags=["items"])`); handler `items.py:61-72` (decorator `@router.post("/", response_model=ItemPublic)` at 61, `def create_item(` at 62).
- Lab ground truth gives `items.py:61-72` in Q4 and `items.py:62` in its failure list; both are right under different range rules (decorator vs `def`).
- CodeGraph in Task 001: route node `POST /items` at line 61 references `create_item` (`resolvedBy: exact-match`, confidence 0.7). Router-local path, no `/api/v1`.
- Expected end: `verified`.

### L6. Handler depends on the DB session
- Claim: `create_item` depends on `deps.py::get_db` via alias `SessionDep`. `depends_on`, granularity `handler`. Extractor: R2.
- Locations: site `items.py:63` (`*, session: SessionDep, current_user: CurrentUser, item_in: ItemCreate`); input `items.py:7` (`from app.api.deps import CurrentUser, SessionDep`); input `deps.py:26` (`SessionDep = Annotated[Session, Depends(get_db)]`); to_decl `deps.py:21-23`.
- Lab ground truth cites `deps.py:21-26` (function plus alias). Split here into function 21-23 and alias 26.
- CodeGraph in Task 001: no edge from `create_item` to `SessionDep` or `get_db`.
- Expected end: `verified`.

### L7. Handler depends on the current user
- Claim: `create_item` depends on `deps.py::get_current_user` via alias `CurrentUser`. `depends_on`, granularity `handler`. Extractor: R2.
- Locations: site `items.py:63`; input `items.py:7`; input `deps.py:49` (`CurrentUser = Annotated[User, Depends(get_current_user)]`); to_decl `deps.py:30-46`.
- Transitive claims (separate records, depth 2): `get_current_user` depends on `get_db` via `SessionDep` (`deps.py:30`, `:26`) and on `reusable_oauth2` via `TokenDep` (`deps.py:30`, `:27`, `:16-18`). Behavior inside, for the statement only: JWT decode with `settings.SECRET_KEY` (`deps.py:32-34`), user load `session.get(User, token_data.sub)` (`deps.py:41`).
- CodeGraph in Task 001: `CurrentUser` references `get_current_user` at `deps.py:49`; nothing at handler level.
- Expected end: `verified` for the direct claim; transitive claims `verified` or `unvalidated` reported separately (not part of the 9 targets).

### L8. Handler persists directly through the session
- Claim: `create_item` builds the row and persists through `sqlmodel.Session`: `Item.model_validate` (68), `session.add` (69), `session.commit` (70), `session.refresh` (71). `persists_via`, granularity `statement`, one record per call; L8 counts as verified only when all four are. Extractor: `py` with R2 value type.
- Locations: sites `items.py:68`, `:69`, `:70`, `:71`; input `deps.py:26` and `deps.py:9` (`from sqlmodel import Session`) for the value type.
- CodeGraph in Task 001: 0 outgoing edges from `create_item`; 5 unresolved references at lines 68 to 71 (`Item.model_validate`, `current_user.id`, `session.add`, `session.commit`, `session.refresh`), status `failed`. They show CodeGraph saw the call sites.
- Expected end: `verified`. Depends on FASTAPI_RULES.md Q5.

### L9. Table model and response model
- Claim A: `create_item` uses table model `backend/app/models.py::Item`. `declares_model`, granularity `statement`.
  Locations: site `items.py:68`; input `items.py:8` (`from app.models import Item, ItemCreate, ItemPublic, ItemsPublic, ItemUpdate, Message`); to_decl `models.py:87-93` (`class Item(ItemBase, table=True):`, `owner_id` foreign key `user.id` with `ondelete="CASCADE"` at 90-92).
- Claim B: `create_item` returns `ItemPublic`. `returns_model`, granularity `handler`.
  Locations: site `items.py:61` (`response_model=ItemPublic`); to_decl `models.py:97-100`.
- Request model for context: `item_in: ItemCreate` at `items.py:63`, `models.py:76-77`.
- Extractor: `py`.
- Expected end: both `verified`.

Browser follow-up for context, not a chain link: `AddItem.tsx:63-65` (`onSettled` invalidates the `["items"]` query). Lab ground truth cites line 64.

## Negative controls

### N1. "items routes use crud" (GitDiagram)
- Original claim, kept verbatim in `statement` and `origin.quote` once Lab extracts the exact wording and its location from `lab/B/logs/gitdiagram_page.html` (sha256 recorded). Class `unverified_inference`, provenance `external:gitdiagram-page`, extractor `{name: gitdiagram-public-page, version: cached 2026 page, families: [none]}`.
- Claim as tested: `backend/app/api/routes/items.py` handlers, including `create_item`, call functions in `backend/app/crud.py`. `uses_crud`, granularity `handler`.
- Evidence against, at the SHA:
  - `items.py:1-8` imports: `uuid`, `typing.Any`, `fastapi`, `sqlmodel`, `app.api.deps`, `app.models`. No `app.crud`, no `crud` name.
  - `items.py` contains 0 occurrences of `crud` (`grep -c crud` = 0).
  - `create_item` body `items.py:68-71` calls `Item.model_validate`, `session.add`, `session.commit`, `session.refresh`.
  - `crud.py::create_item` (`crud.py:63-68`) exists and does the same work, which is why the claim looks plausible. Its only caller at the SHA is `backend/tests/utils/item.py:16`.
- Checks: L1 and L2 pass (the file exists); L3 fail (token `crud.` absent in `items.py:61-72`, and in the whole file); `parser_independent` by `py` fail (no `Call` with a callee resolving to `app.crud`; no import binding `crud`); second family `fail` on the same question.
- Expected end: `rejected`, `status_reason`: "items.py has no import of app.crud and no crud reference; create_item writes through session at items.py:68-71". Original claim stays visible.

### N2. private.py handler depends on get_current_user
- Origin: CodeGraph `impact get_current_user` lists `backend/app/api/routes/private.py` (`_tests/logs/codegraph-colby-di.log:17-18`) at file level. The negative control narrows it to the handler, the way a reader would misread it: "`private.py::create_user` requires the current user (depends on `get_current_user`)". Class `unverified_inference`, provenance `fixture:negative-control`, `origin.derived_from` = the impact output.
- Claim as tested: `depends_on(private.py::create_user, deps.py::get_current_user)`, granularity `handler`.
- Evidence against, at the SHA:
  - Handler `private.py:23-38`: decorator `@router.post("/users/", response_model=UserPublic)` at 23, `def create_user(user_in: PrivateUserCreate, session: SessionDep) -> Any:` at 24.
  - Only dependency import: `private.py:6` `from app.api.deps import SessionDep`.
  - `SessionDep` resolves to `get_db` (`deps.py:26`, `deps.py:21-23`); `get_db` has no parameters, so the closure is `{get_db}`.
  - No `dependencies=` at any level: `private.py:13`, `private.py:23`, `api/main.py:14`, `main.py:21-25`, `main.py:35`.
- Checks: R2 `framework_rule` fail (closure complete, `get_current_user` absent); second family `parser_independent` fail (no `CurrentUser` or `get_current_user` name in `private.py`).
- Expected end: `rejected`, `status_reason`: "private.py create_user takes only user_in and session: SessionDep; dependency closure is {get_db}; no dependencies= on decorator, router, includes or app".
- What N2 must not do: reject the file-level record "`private.py` imports from the module that defines `get_current_user`" (`private.py:6`). That record is a different claim (granularity `file`) and keeps its own status. N2 tests handler precision only.

## Target summary

| Id | Expected status | Main evidence |
|---|---|---|
| L1 | verified | `items.tsx:65`, `items.tsx:8` |
| L2 | verified | `AddItem.tsx:88`, `:68-70`, `:69` |
| L3 | verified | `AddItem.tsx:56`, `sdk.gen.ts:307-318` |
| L4 | verified | `sdk.gen.ts:307`, `:308`, `:311`; `types.gen.ts:809`, `:813`; `main.py:14-15` |
| L5 | verified | `core/config.py:22`, `main.py:35`, `api/main.py:10`, `items.py:10`, `items.py:61-72` |
| L6 | verified | `items.py:63`, `deps.py:26`, `deps.py:21-23` |
| L7 | verified | `items.py:63`, `deps.py:49`, `deps.py:30-46` |
| L8 | verified | `items.py:68-71`, `deps.py:26`, `deps.py:9` |
| L9 | verified | `items.py:68`, `items.py:61`, `models.py:87-93`, `models.py:97-100` |
| N1 | rejected | `items.py:1-8`, `items.py:68-71`, `crud.py:63-68`, `tests/utils/item.py:16` |
| N2 | rejected | `private.py:6`, `private.py:23-24`, `deps.py:26` |

## Differences from Lab ground truth to settle in step 5

1. L5 handler start: Q4 uses 61-72, the failure list uses 62. Both kept, with range rules.
2. L6 and L7: Q4 cites `deps.py:21-26` and `deps.py:30-49`. Split into function and alias lines here.
3. L4 token line: Q4 cites `main.tsx:19`; the `client.setConfig` call spans 17-20.
4. Browser refetch: Q4 cites `AddItem.tsx:64`; the `onSettled` block is 63-65.
