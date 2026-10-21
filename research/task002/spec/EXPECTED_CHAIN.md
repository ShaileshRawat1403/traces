# Expected chain L1 to L9, injected negative controls N1 and N2 (draft for step 5), version 2

Status: DESK DRAFT v2, 2026-10-21 (IST). Owner of this draft: Traces. Lab finalizes it in step 5 as the expected-chain fixture and the injected set; Traces spot-checks every line against `git show b1125d88:<path>`.
Repo `fastapi/full-stack-fastapi-template` at `b1125d8839482cb7bbae603ddc6d0081bf87532e`. Lines read from the shared clone with `cat -n` (read-only), 1-based. Base: Lab ground truth Q3, Q4 (`lab/B/ground-truth.md`) and Lab step 1 (`task002/step1/GRADING.md`).

## How a link reaches verified

- Each link has one or more **claims**: from CodeGraph (label `inferred`, D-002A.2) where it has one, and from the expected-chain fixture (`fixture:expected-chain`, class `unverified_inference`) for every link.
- A claim becomes `verified` only through an independent check that **establishes the relationship** by syntax, binding resolution, or rule R1 to R4, with validator family `cpython-ast` or `typescript-compiler` (EVIDENCE_SCHEMA V3). Symbol existence on both ends is never enough.
- A link counts as verified when its fixture claim is `verified` and every CodeGraph claim for the same link is either `verified` or `unvalidated` with a stated reason (never silently dropped).
- Families: `ts` = TypeScript Compiler API 6.0.3; `py` = CPython 3.14.8 `ast`.

## Chain

### L1. Items page renders AddItem
- Fixture claim: `items.tsx::Items` `renders` `AddItem.tsx::AddItem`, granularity `statement`.
- Sites and inputs: site `frontend/src/routes/_layout/items.tsx:65` (`<AddItem />`); input `items.tsx:8` (`import AddItem from "@/components/Items/AddItem"`); from_decl `items.tsx:57-70`; to_decl `frontend/src/components/Items/AddItem.tsx:40-141`, default export `AddItem.tsx:143`. Route registration for context: `items.tsx:20`.
- Establishing checks (`ts`): `syntax_structure` (the JSX element at 65 lies inside `Items`' body) and `binding_resolution` (tag `AddItem` resolves through the import at 8 to the default export at 143, declared at 40).
- CodeGraph claim: `Items` to `AddItem`, raw `calls` with `synthesizedBy: jsx-render`, mapped to `renders`, `enclosing_scope` at 57. R-enclosing must add the `site` at 65 first (V6); then the same checks apply.
- Expected: both `verified`.

### L2. Form submit wiring
- Claim A (fixture): `AddItem` `binds_handler` `onSubmit`: identifier `onSubmit` is passed as the argument of `form.handleSubmit(...)` in the `onSubmit` attribute of `<form>`. Site `AddItem.tsx:88`; to_decl `AddItem.tsx:68-70`. Establishing: `syntax_structure` (argument position inside the JSX attribute) and `binding_resolution` (`onSubmit` at 88 resolves to the `const` at 68).
- Claim B (fixture): `onSubmit` `calls` `mutation.mutate`. Site `AddItem.tsx:69`; input `AddItem.tsx:55-66` (`const mutation = useMutation({...})`). Establishing: `syntax_structure` (call inside `onSubmit` body) and `binding_resolution` (`mutation` at 69 resolves to the `const` at 55).
- CodeGraph: `AddItem` references `onSubmit` at 88 (`function-ref`, statically_derived). No claim for `mutate` (failed unresolved reference at 69, which can reach `observed`).
- Expected: A and B `verified`. The claims are written to say only what syntax and bindings show. What the libraries do at submit time is not part of L2 (see "Library hops").

### L3. Mutation function calls the generated client
- Fixture claim: the `mutationFn` arrow inside `AddItem` `calls` `ItemsService.createItem`. Site `AddItem.tsx:56`; inputs `AddItem.tsx:8` (`import { type ItemCreate, ItemsService } from "@/client"`), `frontend/src/client/index.ts:3` (re-export from `./sdk.gen`); to_decl `frontend/src/client/sdk.gen.ts:307-318`.
- Establishing (`ts`): `binding_resolution` of `ItemsService` through the import and the re-export to `sdk.gen.ts:287`, and member `createItem` to 307; `syntax_structure` for the call inside the `mutationFn` property of the object passed to `useMutation`.
- CodeGraph: `AddItem` calls `ItemsService::createItem` at 56 (`import`, confidence 0.9).
- Expected: both `verified`.

### L4. Generated method implements the API operation
- Fixture claim: `ItemsService.createItem` `implements_operation` `POST /api/v1/items/`, operation ID `items-create_item`.
- Inputs: `sdk.gen.ts:287`, `:307`, `:308`, `:311`; `types.gen.ts:809`, `:813`; `openapi-ts.config.ts:14`, `:16`, `:17`; `backend/app/main.py:14-15`, `:24`. Auth context only: `sdk.gen.ts:310`, `frontend/src/main.tsx:17-20`.
- Establishing: R3 (`ts` and `py`).
- CodeGraph: `createItem references itemsCreateItemData` at 307 only; nothing for the operation.
- Expected: `verified` on K1 plus K2 and the `types.gen.ts` cross-check. A3 is pinned to hey-api 0.97.3 and its config, with the generated output corroborating; the version pin alone is not independent proof of naming behavior (D-002B.4). It is recorded on the finding.

### L5. Operation routed to the backend handler
- Fixture claim: operation `POST /api/v1/items/` (`items-create_item`) `routes_to` `backend/app/api/routes/items.py::create_item`, granularity `handler`.
- Inputs: `core/config.py:22`; `main.py:9`, `:35`; `api/main.py:3`, `:6`, `:10`; `items.py:10`; handler `items.py:61-72` (`declaration`, decorator 61, `def` 62).
- Establishing: R1 and R3 (`py`, `ts`).
- CodeGraph: route `POST /items` at 61 references `create_item` (`exact-match`, so `unverified_inference`); router-local path. Verified only if R1's finding matches method, line 61 and handler.
- Expected: fixture claim `verified`; CodeGraph claim `verified` on method, line and handler, with its incomplete path kept in `provenance_raw`.

### L6. Handler depends on the DB session
- Fixture claim: `create_item` `depends_on` `deps.py::get_db` via `SessionDep`, granularity `handler`.
- Sites and inputs: site `items.py:63` (`session: SessionDep`); inputs `items.py:7`, `deps.py:26`; to_decl `deps.py:21-23`.
- Establishing: R2 (`py`).
- CodeGraph: only file-level `items.py imports SessionDep` at 7 and the alias edge at `deps.py:26`; both can be verified separately; neither is a handler claim.
- Expected: `verified`.

### L7. Handler depends on the current user
- Fixture claim: `create_item` `depends_on` `deps.py::get_current_user` via `CurrentUser`, granularity `handler`.
- Sites and inputs: site `items.py:63` (`current_user: CurrentUser`); inputs `items.py:7`, `deps.py:49`; to_decl `deps.py:30-46`.
- Transitive (separate fixture claims, depth 2, not counted in the nine): `get_current_user` depends on `get_db` via `SessionDep` (`deps.py:30`, `:26`) and on `reusable_oauth2` via `TokenDep` (`deps.py:30`, `:27`, `:16-18`).
- Establishing: R2.
- Expected: direct claim `verified`; transitive claims reported separately.

### L8. Statically established persistence path
- Fixture claim: `persistence_path(create_item)` with steps `model_validation` (68), `session_stage` (69), `session_commit` (70), `session_reload` (71), receiver `session` bound to `SessionDep`. `qualifier: statically established persistence path`.
- Sites and inputs: `items.py:68`, `:69`, `:70`, `:71`; `items.py:63`, `:7`, `:8`; `deps.py:26`, `deps.py:9`, `deps.py:21-23`; `models.py:87`.
- Establishing: R4 (`py`), which includes the receiver check. The parser alone only makes the four call sites `observed`.
- CodeGraph: 5 unresolved references at 68 to 71 (can reach `observed`); no edges.
- Expected: `verified` with the qualifier. Never described as runtime persistence.

### L9. Table model and response model
- Claim A (fixture): `create_item` `uses_model` `models.py::Item`. Site `items.py:68`; input `items.py:8`; to_decl `models.py:87-93` (`class Item(ItemBase, table=True):`, foreign key at 90-92). Establishing (`py`): `binding_resolution` of `Item` through the import at 8, `syntax_structure` for the `table=True` keyword. Shared with R4 step 1.
- Claim B (fixture): `create_item` `returns_model` `models.py::ItemPublic`. Site `items.py:61` (`response_model=ItemPublic`); to_decl `models.py:97-100`. Establishing: `syntax_structure` (keyword on the route decorator) and `binding_resolution` (`ItemPublic` through `items.py:8`).
- CodeGraph: class nodes exact; no edge for `response_model` at 61.
- Expected: A and B `verified`.

## Library hops (not part of L1 to L9, stay inferred)

Two hops in the frontend runtime story connect L2 to L3 but are library behavior, not repo source:
- H1: react-hook-form `form.handleSubmit(onSubmit)` calls `onSubmit` on submit (`AddItem.tsx:88`).
- H2: TanStack Query `mutation.mutate(data)` calls the `mutationFn` given to `useMutation` (`AddItem.tsx:69` to `:56`).

Neither can be established by syntax, binding resolution or a documented rule without the library source, which is not installed and not in scope. They are written as `library_contract` claims, class `unverified_inference`, flag `library_contract`, and the JSON Schema forbids `verified` for that kind. They stay visible and labeled `inferred`. The step 11 report states that the end-to-end story contains these two inferred hops even though L1 to L9 are each verified.

## Injected negative controls (D-002A.8)

Both are false claims placed only in the validator test inputs (`task002/work/<run_id>/validator_inputs/injected.jsonl`), never in the target checkout, never in CodeGraph's index or the adapter output. Each has `injected: true`, class `unverified_inference`, label `inferred`, and must end `rejected` with an explanation, visible to reviewers.

### N1. "items routes use crud" (GitDiagram, injected)
- Origin: GitDiagram public cached page, `lab/B/logs/gitdiagram_page.html` (Lab records sha256 and the exact quote in step 5). Provenance `external:gitdiagram-page`.
- Claim: `backend/app/api/routes/items.py` handlers, including `create_item`, `uses_crud` (call functions in `backend/app/crud.py`), granularity `handler`.
- Evidence against at the SHA:
  - `items.py:1-8` imports `uuid`, `typing.Any`, `fastapi`, `sqlmodel`, `app.api.deps`, `app.models`; no binding for `crud` or `app.crud`.
  - `items.py` has 0 occurrences of `crud`.
  - R4 finding for `create_item`: the path runs through `session` (`items.py:68-71`), not `crud`.
  - `crud.py::create_item` (`crud.py:63-68`) exists and has one caller, `backend/tests/utils/item.py:16`. This is why the claim looks plausible.
- Checks: L1, L2 pass; L3 `fail` (no `crud.` in `items.py:61-72`); `binding_resolution` `fail` (`py`: no call in any `items.py` handler resolves into `app.crud`; the module has no such import).
- Expected: `rejected`. `status_reason`: "items.py has no import of app.crud and no crud reference; create_item writes through the SessionDep-bound session at items.py:68-71 (statically established persistence path)".

### N2. "`private.py:create_user` depends on `CurrentUser`/`get_current_user`" (planted)
- Origin: planted fixture (`fixture:negative-control`). Not attributed to CodeGraph: Lab step 1 found CodeGraph makes no such handler-level claim; its only `private.py` to `deps.py` edges are `imports deps.py` and `imports SessionDep` at `private.py:6`, both true.
- Claims (two injected records, one per target): `private.py::create_user` `depends_on` `deps.py::CurrentUser` (alias), and `depends_on` `deps.py::get_current_user`, granularity `handler`.
- Evidence against at the SHA:
  - Handler `private.py:23-38`: decorator at 23, `def create_user(user_in: PrivateUserCreate, session: SessionDep) -> Any:` at 24.
  - Only dependency import: `private.py:6` `from app.api.deps import SessionDep`.
  - `SessionDep` resolves to `get_db` (`deps.py:26`, `:21-23`), which has no parameters: closure `{get_db}`.
  - No `dependencies=` at `private.py:13`, `private.py:23`, `api/main.py:14`, `main.py:21-25`, `main.py:35`.
- Checks: R2 `fail` (complete closure, target absent); `binding_resolution` `fail` (no `CurrentUser` or `get_current_user` binding in `private.py`).
- Expected: both `rejected`. `status_reason`: "private.py create_user takes only user_in and session: SessionDep; dependency closure is {get_db}; no CurrentUser or get_current_user binding; no dependencies= on decorator, router, includes or app".
- Not affected: CodeGraph's two `private.py:6` import records keep their own status (expected `verified` by `binding_resolution` of the import), and are never rejected because of N2.

## Target summary

| Id | Expected status, label | Establishing method | Main evidence |
|---|---|---|---|
| L1 | verified | ts syntax + binding | `items.tsx:65`, `:8`; `AddItem.tsx:143` |
| L2 | verified (A and B) | ts syntax + binding | `AddItem.tsx:88`, `:68-70`, `:69`, `:55` |
| L3 | verified | ts binding + syntax | `AddItem.tsx:56`, `:8`; `client/index.ts:3`; `sdk.gen.ts:307` |
| L4 | verified | R3 | `sdk.gen.ts:307`, `:308`, `:311`; `types.gen.ts:809`, `:813`; `main.py:14-15` |
| L5 | verified | R1, R3 | `core/config.py:22`, `main.py:35`, `api/main.py:10`, `items.py:10`, `items.py:61-72` |
| L6 | verified | R2 | `items.py:63`, `deps.py:26`, `deps.py:21-23` |
| L7 | verified | R2 | `items.py:63`, `deps.py:49`, `deps.py:30-46` |
| L8 | verified, qualifier "statically established persistence path" | R4 | `items.py:68-71`, `deps.py:26`, `deps.py:9` |
| L9 | verified (A and B) | py binding + syntax | `items.py:68`, `:61`, `:8`; `models.py:87-93`, `:97-100` |
| H1, H2 | inferred (`library_contract`), unvalidated library-contract assumptions (D-002B.3); library source is not downloaded | none available | `AddItem.tsx:88`, `:69`, `:56` |
| N1 | rejected, visible | L3 + py binding | `items.py:1-8`, `:68-71`; `crud.py:63-68`; `tests/utils/item.py:16` |
| N2 | rejected, visible (2 records) | R2 + py binding | `private.py:6`, `:23-24`; `deps.py:26` |

If any target fails, the step 11 report states it as failed with the reason. No target is relaxed.

## Differences from Lab ground truth to settle in step 5

1. L5 handler start: Q4 uses 61-72, the failure list uses 62. Both kept as `declaration` (61) and `header_to_body_end` (62).
2. L6 and L7: Q4 cites `deps.py:21-26` and `30-49`; split into function and alias lines here.
3. L4 token line: Q4 cites `main.tsx:19`; the `client.setConfig` call spans 17-20.
4. Browser refetch: Q4 cites `AddItem.tsx:64`; the `onSettled` block is 63-65 (context only).

## Step 11 review package (D-002A.10)

Traces' step 11 report contains, then stops for architectural approval:
1. Updated verification results: counts by status, label, class and provenance for all records; recovery results against 1,891 of 1,893; the 616 name-only matches by final label.
2. L1 to L9 evidence classifications: per link, each claim's originator, class, final status and label, establishing checks, and site locations at `b1125d8`.
3. N1 and N2 rejection evidence: the original claims, the failing checks, and the reasons, as shown to reviewers.
4. Remaining limitations: H1 and H2 library hops; assumptions A1 to A4; parse-only TS 6.0.3 recheck versus binding resolution in step 7; the `setOpen` body location; anything that did not meet its target.
