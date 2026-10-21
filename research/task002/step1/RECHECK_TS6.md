# Step 1 recheck: TypeScript 6.0.3 vs 5.9.3

Run 2026-10-21 10:03 to 10:04 IST. All commands ran inside `tools/offline.sh` (`unshare -rn`). Python side is CPython 3.14.8, rerun in the same session. Node v20.19.2 runs the TS compiler API. The CodeGraph index was **not** regenerated: `codegraph.db` sha256 647c2feaef6010eafbe63310187c079459f3da438110b2a0c44df077a5898c10, the same file graded at 07:22 IST. Target checkout `src/fsft` at `b1125d8839482cb7bbae603ddc6d0081bf87532e`, no tracked changes before or after each run (logged in `logs/15` to `18`).

Pins: TS 5.9.3 at `tools/node_modules/typescript`, TS 6.0.3 at `tools/ts6/node_modules/typescript` (integrity in `../ENV.md`).

## Side by side

| measure | TS 5.9.3 | TS 6.0.3 | log |
|---|---|---|---|
| indexed TS/TSX files parsed | 109 | 109 | 15, 16 |
| files with parse diagnostics | 0 | 0 | 15, 16 |
| Python files parsed by 3.14.8 `ast` (same in both runs) | 43 of 43 | 43 of 43 | 15, 16 |
| declarations extracted by `ts_decls.js` | 2,817 | 2,817 | 20 |
| `ts_decls.js` output sha256 | b4e06f62...50ac4895 | b4e06f62...50ac4895 (byte-identical, `diff` exit 0) | 20 |
| start-line scope (function, method, route in `backend/app`, `frontend/src`) | 379 | 379 | 17, 18 |
| Lab `check_lines.py` `defline()` verbatim (parser-independent) | 320 / 379 | 320 / 379 | 19 |
| Lab rule plus route rule | 351 / 379 | 351 / 379 | 17, 18 |
| independent parsers (Python 3.14.8 + TS), start line confirmed | **378 / 379** | **378 / 379** | 17, 18 |
| not confirmed | `sidebar.tsx` `setOpen` at 87 | same | 17, 18 |
| end lines matching independent parser (function, method) | 341 / 348 | 341 / 348 | 17, 18 |
| containment edges recovered from AST parent-child | 1,891 / 1,893 | 1,891 / 1,893 | 17, 18 |
| edge-line classification (B), all buckets | unchanged | unchanged | 17, 18 |

No number changed. The two analysis outputs (`logs/analysis_ts5.9.3.json`, `logs/analysis_ts6.0.3.json`) are equal on every key except `parser_versions`. The 5.9.3 rerun is also equal on every key to the original 07:26 IST run (`logs/analysis.json`). Both comparisons are in `logs/20_ts_decls_diff.log`.

Why nothing moved: the checks use only the parser (`createSourceFile`, syntax kinds, node positions), not type checking. On these 109 files, 6.0.3 produces the same declarations at the same lines as 5.9.3. Type-checking differences between 5.x and 6.x were not tested and are not part of this measure.

S2 reading is unchanged: 378 / 379 = 99.7% on independent parsers; verbatim Lab script 320 / 379 = 84.4%.

## New raw logs (`step1/logs/`)

| file | content |
|---|---|
| `15_parser_coverage_ts5.9.3.log` | parse-diagnostic run, TS 5.9.3, plus Python 3.14.8 parse of 43 files |
| `16_parser_coverage_ts6.0.3.log` | same with TS 6.0.3 |
| `17_analysis_ts5.9.3.log`, `analysis_ts5.9.3.json` | full `analyze.py` with TS 5.9.3 |
| `18_analysis_ts6.0.3.log`, `analysis_ts6.0.3.json` | full `analyze.py` with TS 6.0.3 |
| `19_check_lines_verbatim_rerun.log` | Lab `defline()` unchanged |
| `20_ts_decls_diff.log`, `ts_decls_5.9.3.jsonl`, `ts_decls_6.0.3.jsonl` | raw declaration dumps, diff, analysis key comparison, index hash |

Script change: `ts_decls.js`, `ts_parse_diag.js` and `analyze.py` now take `TS_MODULE` (and `ANALYSIS_OUT` for `analyze.py`). The default is the 5.9.3 path; logic is otherwise unchanged.
