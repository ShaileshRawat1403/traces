# line_checker_v1

Frozen start-line checker for Task 002 (Decision 002-A, 2026-10-21). VERSION `line_checker_v1.0.0`, in both files. Hashes are in `SHA256SUMS`; check with `cd checker && sha256sum -c SHA256SUMS`.

| file | role |
|---|---|
| `line_checker_v1.py` | main checker, CPython 3.14 stdlib only |
| `ts_decls_v1.js` | TypeScript declaration helper, called by the main checker with Node; loads the TypeScript package given by `TS_MODULE` |

It measures whether CodeGraph's reported **start line** for a node is that node's declaration line in the source at the pinned commit. It is a measurement tool for the extractor. It does not validate relationships and never marks anything verified.

## What it counts

- Node kinds: `function`, `method`, `route` from the CodeGraph `nodes` table.
- Files: `file_path` under `backend/app/` or `frontend/src/`. On fsft @ `b1125d88` that is 379 nodes (312 function, 36 method, 31 route).
- Measured field: `start_line` only. End lines are not scored. Step 1 found 341/348 end lines agree; that came from `step1/analyze.py`, not from this checker.
- Line numbers: 1-based on both sides.

## Declaration line, by language (mode `parser`)

- **Python** (CPython 3.14 `ast`, source from `git show <sha>:<path>`): the `def` line (`FunctionDef.lineno` / `AsyncFunctionDef.lineno`).
  - Matching is by name within the same file.
  - A start line on the first decorator is recorded as `py_decorator_line` and counted **not exact**. The decorator line belongs to the route node, not the function node. Example: `items.py` route at 61 (`@router.post`), `create_item` function at 62 (`def`).
- **TypeScript/TSX** (TypeScript compiler API, parser only, `createSourceFile`): exact if CodeGraph's start line equals either the declaration's first-token line or its name line. Declaration nodes are:
  - function declarations, class, interface, type alias, enum and method declarations (first token is the line holding `public static` etc.);
  - `const`/`let`/`var` declarations. For `const X = () => ...` or `const X = function ...` the declaration line is the `const` statement line;
  - property assignments and signatures (this covers optional method signatures such as `onRequest?: (...) => ...`).
  - Generic methods (`createItem<ThrowOnError ...>(`) are handled by the parser, unlike the Lab regex.

## Route rule (both modes)

- **Backend FastAPI route** (node id `route:<file>:<line>:<METHOD>:<path>`): exact if the reported line starts with `@` and the decorator call contains `.<method>("<path>"` or `'<path>'`. The call is read from the reported line through the first line containing `)`, at most 6 lines, so multi-line decorators such as `users.py:32` count.
- **Frontend TanStack route** (id without METHOD): exact if the reported line contains `createFileRoute` and the route path without its trailing slash.

## Modes

| mode | function/method rule | route rule | result on fsft @ b1125d88 | status |
|---|---|---|---|---|
| `parser` (default) | independent parsers above | route rule | **378 / 379 (99.74%)** | accepted S2 measure (Decision 002-A) |
| `lab_route` | Lab Task 001 regex `defline`, copied unchanged from `lab/B/scripts/check_lines.py:7-15` | route rule | 351 / 379 (92.61%) | audit variant |
| (not in this checker) | unmodified `lab/B/scripts/check_lines.py` `defline` for all three kinds, no route rule | none | 320 / 379 (84.4%) | audit record; run via `step1/verbatim_check_lines.py` |

## Inputs

```
python line_checker_v1.py --db <path to .codegraph/codegraph.db> --src <git checkout root> --sha <commit> \
    --ts-module <dir of the typescript npm package> [--mode parser|lab_route] [--out <result.json>]
```

- The checker refuses to run if `git rev-parse HEAD` in `--src` differs from `--sha`.
- The DB is opened read-only, `mode=ro&immutable=1`, so no WAL or SHM writes.
- Accepted pins: Python 3.14.8 (`tools/py314`), TypeScript 6.0.3 (`tools/ts6/node_modules/typescript`), Node 20.19.2 for the helper. Run under `tools/offline.sh`.

## Outputs

- **stdout:** JSON with `version`, `mode`, `sha`, `db`, `parsers` (python, typescript, count of TS files with parse diagnostics), `scope`, `total`, `exact`, `share`, `by_kind_basis`, and `not_exact` (one entry per miss with `basis`).
- **`--out`:** the same JSON plus `nodes`, the per-node record `{kind, file, name, start_line, exact, basis}`.
- **Basis codes:** `py_def_line`, `py_decorator_line`, `py_no_decl`, `py_mismatch`, `ts_decl_line`, `ts_no_decl`, `ts_mismatch:<kind>@<line>,...`, `route_rule`, `lab_defline:<result>`.

## Reproduction run

`logs/checker/run_v1_20261021T100725.log`, offline via `tools/offline.sh`:
- `parser` 378/379, `lab_route` 351/379, and the original Lab `defline` rerun 320/379.
- Target checkout unchanged and `codegraph.db` sha256 unchanged (647c2fea...5898c10).
- `lab/B/scripts/check_lines.py` sha256 0421b5b8a340b94f92e89da88a97c90c5e8c8a3d7bf34abc3a93ddcde6136856, mtime 2026-10-20 23:16:03 IST (Task 001; not modified).

## The one miss on record: `setOpen`

`frontend/src/components/ui/sidebar.tsx`:
- line 86: `const setOpen = React.useCallback(` is the **declaration line** (binding statement; the statement ends at 99);
- line 87: `(value: boolean | ((value: boolean) => boolean)) => {` is the **body/arrow line**, the arrow function passed to `useCallback` (arrow ends at 97).

CodeGraph reports `setOpen` at 87-97, the arrow function, not the declaration. The checker records it as `ts_mismatch:PropertySignature@36,Variable@86`. Line 36 is an unrelated `setOpen` property signature in the context type. It counts as not exact. CodeGraph's location is right for the function body and wrong for the declaration.

## Known limits

- Matching is by short name within a file. Two declarations with the same name in one file both count as candidates (for example `createUser` twice in `sdk.gen.ts`, at 119 and 373, which are different classes). A start line matching either counts as exact. Parent class is not checked.
- Only start lines are scored. End-line conventions differ (CodeGraph includes trailing comments inside Alembic functions; `ast.end_lineno` does not).
- TS check is syntax only. No type checking, no module resolution.
- A `const` whose initializer is a call (such as `React.useCallback(...)`) is a `Variable`, not a function, so a node pointing at the inner arrow fails. This is intended and is the `setOpen` case.
- The route rule checks the decorator or `createFileRoute` line and path literal. It does not compose prefixes (`/api/v1`, router prefix). That is a framework rule (R1), not a line check.
- Scope prefixes and node kinds are fixed in the code (`SCOPE_KINDS`, `SCOPE_PREFIXES`). Other repos need a new version.
- Python parsing needs 3.14 for this repo (`deps.py:36`). Older interpreters fail with SyntaxError rather than silently skipping.
