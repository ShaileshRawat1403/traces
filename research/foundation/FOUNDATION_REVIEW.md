# Traces Foundation Review (Task 001)

Seat: Traces (lead technical investigator). Covers Investigation A (code inspection) and Investigation D (feasibility), merged with Traces Lab's Investigation B (tool tests against a ground truth) and Investigation C (Git history prototype).
Date: 2026-10-20. Lead sections written 23:07 to 23:31 IST; Lab merge done about 23:38 to 23:55 IST.
Approval boundary: Shailesh Rawat. Reviewer: ChatGPT (product architect).

## How to read the tags

Every finding carries one tag.

- **VERIFIED-IN-CODE**: I read the cited file and lines in the cloned source.
- **TESTED**: I ran it on the box and observed the result. Logs are under `/workspace/traces-research/_tests/logs/`.
- **DOCUMENTED-CLAIM**: comes from a README or docs file only. Not checked against code or a run.
- **INFERRED**: my judgment from the evidence. Not a fact. Treat as a hypothesis for review.
- **LAB-TESTED** / **LAB-DESK** / **LAB-INFERRED**: Traces Lab's own tags carried over unchanged (Lab "tested", "read only" or desk, and "inference"). Source files are named next to each item. Where I re-checked a Lab claim myself, I add **RE-CHECKED** with what I ran.

All paths in citations are relative to `/workspace/traces-research/_src/<repo>/` unless stated. Lab paths are relative to `/workspace/traces-research/`.

---

## 0. Traces repo state (read-only)

- `ShaileshRawat1403/traces` at `63103ac4adcb62a1ff31d9a1ca9955e3d855c850` (2026-10-20 23:01 IST) has one commit, "Initial commit", with `README.md` and `.gitignore` only. README text: "Trace the decisions. Link the relationships. Understand the system." **VERIFIED-IN-CODE**
- One branch (`main`), public, created 2026-10-20 23:01 IST. **TESTED** (gh api)
- No Task 001 brief, spec, or stack decision exists in the repo. The scope I worked from is the brief relayed by the parent agent. **VERIFIED-IN-CODE**
- I did not branch, modify, or push anything. The clone is at `_src/traces`.

## 0.1 Shared test repo

- `fastapi/full-stack-fastapi-template` at **`b1125d8839482cb7bbae603ddc6d0081bf87532e`** (2026-10-15 21:34 IST). Full-history clone at `_src/full-stack-fastapi-template` (left in place for Lab, not modified). **TESTED**
- Lab pins the same SHA in `lab/README.md` and `LAB_B_RESULTS.md` ("Same SHA as the lead's clone"), and its clones `lab/repos/fsft`, `fsft-b`, `fsft-gn` are at that SHA. No reconciliation needed. **TESTED** + **LAB-TESTED**
- Lab also ran its C scripts on `ShaileshRawat1403/traces` at `63103ac` (1 commit, 2 files): exit 0, empty results. Demo only; too small to test anything (`lab/README.md`, `lab/C/logs/traces_*.log`). **LAB-TESTED**
- Profile: 252 tracked files, about 23.5k lines; 70 `.tsx`, 43 `.py`, 39 `.ts`. 1,537 commits on `master` since 2019-02-09, 1,540 with `--all`, 88 authors, 15 tags. **TESTED**
- Suitability: good choice, with these caveats a Traces design must handle. **TESTED** for the numbers, **INFERRED** for the consequences.
  1. Backend requires Python 3.14 (`backend/pyproject.toml:5`) and uses PEP 758 syntax `except InvalidTokenError, ValidationError:` (`backend/app/api/deps.py:36`). Parsers that lag the language break on it: depvis dropped the file, and Lab's own Python 3.13 `ast` parser had to fall back to regex (`lab/C/verdict.md`, gap 4).
  2. History is bot-heavy: `github-actions` 361 + `github-actions[bot]` 282 + `dependabot[bot]` 243 = 886 of 1,537 commits (58%) by author. Lab counts the same noise by message: 750 of 1,537 are release-note commits (`lab/C/verdict.md`, gap 5). Both measures say filter first.
  3. 752 of 1,537 commit subjects carry a `(#NNNN)` PR number (Lab got the same 752, and 25 of 25 fetched PRs have `merge_commit_sha` equal to the local commit). 664 rename entries exist, including bulk moves of 164, 68, 247 and 96 files (Lab `lifecycle.md`), so rename tracking matters.
  4. The frontend contains a generated API client (`frontend/src/client/*.gen.ts`). It inflates TypeScript graphs and should be labeled as generated. It is also the join point for frontend-to-route links (see 4.3).

---

## 1. Executive recommendation

**Lab's headline holds and changes how to read everything below.** In Investigation B, no tested tool explained the test repo's architecture with evidence a reviewer could check line by line (`LAB_B_RESULTS.md`, grades table). Paths were right almost everywhere; relationships were where tools failed. So the foundation question is only "which engine gives Traces the cleanest deterministic raw material". The explanation layer, the evidence checks, and the framework rules are the product, and Traces builds them. **LAB-TESTED** + **INFERRED**

**Best foundation (unchanged): compose, do not fork.** Use **CodeGraph (`colbymchenry/codegraph`, MIT)** as the deterministic extraction engine behind an adapter. Build the evidence model with line-level claim checks, framework and cross-language rules, the Git history layer, component grouping, the explanation and chat layer, and the mobile viewer in-house.

Why CodeGraph still leads after the merge:
- Local, deterministic, multi-language, file, line and column on every node and edge, no LLM, no key. 175 files to 2,076 nodes and 4,642 edges in 1.4 s; all 31 routes with handler file and line; per-edge provenance. **TESTED**
- It resolves the `crud.x()` module-attribute calls that Lab's codeGRAPH candidate (lemonberrylabs) missed: 26 incoming call edges to `crud.create_user`, `login.py:30 -> crud.authenticate` present. **TESTED**
- On FastAPI dependency injection, where Lab found 0 incoming edges to `get_current_user` in CodeBoarding, lemonberrylabs/codegraph and GitNexus, `codegraph impact get_current_user` returns 9 affected symbols reaching `items.py`, `login.py`, `users.py` and `utils.py`. That is file-level reach through the `CurrentUser` alias (`deps.py:49`), not handler-level, and it includes one false positive (`private.py` imports only `SessionDep`). Better than the rest, still not good enough. **TESTED** (follow-up run T10)
- Caveat: Lab did not run CodeGraph through its six-question ground truth. My tests and Lab's are on the same SHA, but not the same grading. That is open question 1.

**Runner-up (unchanged): CodeBoarding (MIT).** Both seats got identical static numbers (Python 95 nodes / 101 edges, TypeScript 564 / 639). Its static call graph is correct where Lab checked it, it has a non-LLM health mode Lab found (`health/main.py:3`), and its relation grounding with persisted `is_static` remains the best pattern. It stays second on weight (1.6 GB of language servers, Python 3.12 pin, LLM required for components, telemetry on by default) and because its static half misses DI edges too. **TESTED** + **LAB-TESTED**

**Git history: native git first, build in-house.** Lab C showed native git plus about 650 lines of stdlib Python covers v1 history (lifecycle, renames, co-change, hotspots, reverts, manifest and import diffs, PR-number linking) in 15.3 s and about 80 MB on 1,537 commits. Add the GitHub API for PR bodies, comments and Discussions, a semantic rename and component alias map, framework and cross-language rules, and a version-aware parser. Code Maat stays study only (GPL-3.0); Git of Theseus drops from "dependency" to "optional, reimplement if needed" because Lab's native-git layer already covers what Traces needs and Git of Theseus output carries no commit hashes. **LAB-TESTED** + **TESTED** + **INFERRED**

**Benchmark only:** GitNexus (PolyForm Noncommercial 1.0.0). Lab ran 1.6.12 as a benchmark; whether that run is acceptable for a commercial-intent evaluation is an open decision for Shailesh (6.1, 7). Its tested results were weaker than its documentation suggests (mixed 0-based and 1-based lines, DI miss, cluster labels that do not match file roles). **VERIFIED-IN-CODE** (LICENSE) + **LAB-TESTED**

**Reject as foundation:** GitDiagram (LLM-authored relationships; Lab found a wrong "items use CRUD" edge and an invented frontend container while all 34 cited paths existed), lemonberrylabs/codegraph (misses module-attribute calls, false dead code, no LICENSE file), xnuinside/codegraph, both depvis candidates.

---

## 2. Evidence-backed comparison matrix

### 2.1 Candidate identity, license, and maintenance

Maintenance numbers pulled with `gh api` on 2026-10-20 about 23:15 IST. Dates converted to IST. **TESTED**

| Candidate | Repo inspected | SHA inspected | License (from LICENSE file) | Stack | Last commit (IST) | Stars | Contributors | Open issues / PRs |
|---|---|---|---|---|---|---|---|---|
| CodeBoarding | CodeBoarding/CodeBoarding | 3a5098c | MIT | Python 3.12, LangChain/LangGraph, tree-sitter, LSP clients | 2026-10-15 08:18 | 2,602 | 28 | 28 / 22 |
| GitDiagram | ahmedkhaleel2004/gitdiagram | 7a33d6e | MIT | Next.js 16, React 19, TS, Mermaid 12, OpenAI SDK, Cloudflare Workers | 2026-10-20 10:17 | 18,344 | 5 | 30 / 23 |
| codeGRAPH (chosen reading) | colbymchenry/codegraph | 505c355 | MIT | TypeScript on Node 20 to 24, web-tree-sitter WASM, Rust kernel, SQLite, Svelte + @xyflow viewer | 2026-10-20 23:08 | 74,521 | 51 | 189 / 412 |
| codeGRAPH (alternate) | xnuinside/codegraph | effefc7 | MIT | Python, click, D3 via CDN | 2026-04-07 14:26 | 509 | 3 | 1 / 2 |
| depvis (chosen reading) | mfinean/depvis | dcdff8d | MIT | Rust, rustpython-parser, D3 web viewer | 2025-12-26 16:27 | 3 | 1 | 1 / 0 |
| depvis (alternate) | nealwp/depvis | 6b846c9 | MIT (copyright Robert Kieffer, npmgraph lineage) | React, Graphviz WASM, D3 | 2026-08-26 01:11 | 0 | 1 | 0 / 0 |
| GitNexus | abhigyanpatwari/GitNexus | 7090ac8 | **PolyForm Noncommercial 1.0.0** | TypeScript, tree-sitter (native), LadybugDB, graphology + sigma, transformers.js embeddings | 2026-10-20 22:14 | 47,971 | 212 | 232 / 52 |
| Git of Theseus | erikbern/git-of-theseus | 961bda0 | Apache-2.0 | Python, GitPython, matplotlib | 2023-11-25 22:34 | 2,971 | 19 | 18 / 6 |
| Code Maat | adamtornhill/code-maat | 50537ab | **GPL-3.0** (no LICENSE file; stated in `README.md:30`, `project.clj:3-9`, and every source header) | Clojure on the JVM, Incanter | 2025-07-03 17:21 | 2,641 | 23 | 11 / 0 |
| codeGRAPH (Lab's reading) | lemonberrylabs/codegraph | not cloned by me; Lab used npm `@lemonberrylabs/codegraph@0.1.0` | **No LICENSE file in the repo** (`gh api` license null); MIT claimed only in README and npm metadata | TypeScript CLI, call graphs for TS, Go, Python | last push 2026-02-20 04:50 IST | 3 | not pulled | 0 open (issues + PRs) |
| codeGRAPH (fourth reading) | FalkorDB/code-graph | not cloned | MIT per `gh api` | FalkorDB graph DB, GraphRAG chat (Gemini default) | last push 2026-10-19 08:24 IST | 349 | not pulled | not pulled |

**Name ambiguity.**
- "codeGRAPH": at least six live repos use the name. The two seats picked different ones, so the matrix covers three that were actually run:
  - `colbymchenry/codegraph` (74.5k stars, multi-language knowledge graph, MIT). My pick and the recommended engine. Run by me only. **TESTED**
  - `xnuinside/codegraph` (509 stars, Python dependency graph with HTML viz, MIT). Run by me only. **TESTED**
  - `lemonberrylabs/codegraph` (3 stars, local call-graph CLI, no LICENSE file). Lab's pick. Run by Lab only. **LAB-TESTED**
  - Not run by either seat: `FalkorDB/code-graph` (349 stars, MIT, needs a FalkorDB server, chat needs a Gemini key; Lab marked it BLOCKED, no Docker on the box), `bluekap/CodeGraph` (Lab: search summary only), `CodeGraphContext/CodeGraphContext` (4.3k, MIT, MCP + graph DB) and `Jakedismo/codegraph-rust` (902, no license). **TESTED** (gh search) + **LAB-DESK**
  - Which one ChatGPT meant is still open (section 7, question 2). The recommendation does not depend on the answer: none of the others beat colbymchenry/codegraph on the evidence we have.
- "depvis": no well-known repo exists. Both seats ran `mfinean/depvis` 0.1.0 (I built source `dcdff8d`, Lab installed the crates.io release). `nealwp/depvis` is an npmgraph adaptation that reads the npm registry (`src/ModuleCache.ts:3`, README line 229), so it is not a repo analyzer. `accso/java9-jigsaw-depvis` is Java 9 modules only. **TESTED** + **VERIFIED-IN-CODE** + **LAB-TESTED**

### 2.2 How each one works (Investigation A)

#### CodeBoarding
- Entry points: `codeboarding`, `codeboarding-setup`, `codeboarding-render` (`pyproject.toml` `[project.scripts]`). CLI in `codeboarding_cli/main.py:37-130`; full run calls `codeboarding_workflows/analysis.py:58-82` which calls `DiagramGenerator.generate_analysis` (`diagram_analysis/diagram_generator.py` around 1389-1418). **VERIFIED-IN-CODE**
- Extraction: language servers driven over stdio by its own LSP client (`static_analyzer/engine/lsp_client.py:92`, process spawn at 186). Servers installed by `codeboarding-setup`: pyright 1.1.400, typescript-language-server 4.3.4, intelephense 1.16.5, gopls, rust-analyzer, JDTLS 1.59.0, kotlin-lsp, csharp-ls (`infra/tool_registry/registry.py:29-36`, `~/.codeboarding/servers/installed.json`). Tree-sitter grammars are also pinned (`pyproject.toml:56-65`). Output is a call graph, references, class hierarchy, and package dependencies per language (`static_analyzer/analysis_result.py:214-252`). **VERIFIED-IN-CODE** + **TESTED**
- Deterministic vs LLM: static analysis is deterministic. Component names, descriptions, and relation phrases come from LLM agents (`agents/planner_agent.py`, `agents/scope_analysis_agent.py`). LLM-proposed relations are matched to static edges in `diagram_analysis/scope_assembly.py:270-293` and flagged `is_static=bool(static_edges)`. Relations with no resolvable key edges and no evidence text are dropped (`diagram_analysis/reference_resolver.py:307-315`). Semantic relations without static backing are kept with a logged warning (`scope_assembly.py:270-276`). **VERIFIED-IN-CODE**
- Note: the LLM is told to give line numbers "only if you are absolutely sure" (`agents/agent_responses.py:38-45`). Line numbers in the final `methods_index` come from static analysis (`diagram_analysis/analysis_json.py:247-252`). **VERIFIED-IN-CODE**
- Graph format: one `analysis.json` with `metadata`, `files`, `methods_index` (keyed `file|qualified_name`, with start and end line and content hash), nested `components`, `components_relations` with `key_edges` carrying call-site line and column, and `is_static` (`analysis_json.py:39`, `:317`). The `is_static` field is excluded from the LLM response schema (`agent_responses.py:185`) but persisted to JSON. **VERIFIED-IN-CODE** + **TESTED** (in its own committed `.codeboarding/analysis.json`, 68 of 68 relations carry `is_static`, all true)
- Visualization: renders Markdown, HTML, MDX, RST (`output_generators/rendering.py:63-68`). HTML uses Cytoscape 3.23 + dagre from unpkg CDN (`output_generators/html_template.py:376-378`), with a viewport meta tag (`:373`). **VERIFIED-IN-CODE** + **TESTED** (render produced 6 HTML pages, 0.8 s)
- LLM/chat: provider list in `agents/llm_config.py:136-310` (OpenAI, Vercel, Anthropic, Google, Bedrock, Cerebras, Ollama, DeepSeek, GLM, Kimi, OpenRouter, OrcaRouter, Requesty, LiteLLM). OpenAI supports `OPENAI_BASE_URL` (`:139-144`), so any OpenAI-compatible endpoint works. No chat feature. **VERIFIED-IN-CODE**
- Git history: incremental mode diffs against a prior run (`infra/repo_utils/change_detector.py:73`, `codeboarding_workflows/fingerprint_diff.py`). No history mining. **VERIFIED-IN-CODE**
- Traceability: node to file and line yes, edge to call-site line yes, node to commit only through `source_sha` metadata. **VERIFIED-IN-CODE**
- Telemetry: PostHog, on by default, sends repo owner account name; opt out with `CODEBOARDING_TELEMETRY=false` (`TELEMETRY.md:5`, `:17-25`, `:149`). **DOCUMENTED-CLAIM**
- Third-party code safety: installs target repo JS dependencies only when `CODEBOARDING_INSTALL_DEPENDENCIES` is set, always with `--ignore-scripts` (`static_analyzer/workspace_dependencies.py:18-38`), but notes that `.npmrc` and `.pnpmfile.cjs` in the target still run (`:3`). **VERIFIED-IN-CODE**
- Tests: 128 `test_*.py` files under `tests/`. **VERIFIED-IN-CODE**

#### GitDiagram
- Stack and deploy: Next.js 16 route handlers on Cloudflare Workers via OpenNext, R2 storage, Upstash Redis, PostHog, OpenAI or OpenRouter (`docs/architecture.md:5-14`). Also contains explainer-video, payments, and admin features (`src/server/explainer/payments.ts`, `src/app/admin/`). **DOCUMENTED-CLAIM** + **VERIFIED-IN-CODE** (files exist)
- Ingestion: GitHub REST API only, recursive tree (`src/server/generate/github.ts:367`) and README (`:495`). No clone, no parser. Source excerpts capped at 12 files, 48,000 characters, plus 28 reference-only files (`src/server/generate/repository-context.ts:4-13`). **VERIFIED-IN-CODE**
- Deterministic vs LLM: the LLM writes the graph (groups, nodes, edges, labels, paths). The server validates the graph and strips unknown paths (`src/server/generate/graph.ts:91`, `:199`). A deterministic import/name scan of each read file (`src/server/generate/source-references.ts:1-8`) backs edge citations: an `evidencePath` must be a file the model was actually shown, otherwise it is stripped or filled from the reference list (`src/server/generate/edge-evidence.ts:17-26`). Edge schema has `evidencePath` (`src/features/diagram/graph.ts:88`). Nodes carry an optional repo `path`, no line. **VERIFIED-IN-CODE**
- Visualization: deterministic compiler to Mermaid, browser renders SVG with click links restricted to github.com (`src/features/diagram/mermaid-security.ts:2`, `docs/architecture.md:41-42`). Pan and zoom hook in `src/hooks/use-mermaid-viewport.ts` (703 lines, has touch handling). **VERIFIED-IN-CODE**
- LLM: `OPENROUTER_API_KEY` or `OPENAI_API_KEY` (`src/server/generate/openai.ts:27-30`), OpenRouter base URL at `:53`. Also exposes an MCP server at gitdiagram.com/mcp (`README.md:64`). **VERIFIED-IN-CODE** + **DOCUMENTED-CLAIM**
- Git history: none. **VERIFIED-IN-CODE** (no history code in `src/server/generate/`)
- Requires Node 22.x and bun 1.3.14+ (`package.json:143-146`). **VERIFIED-IN-CODE**

#### CodeGraph (colbymchenry/codegraph)
- Entry point: `codegraph` bin (`package.json` `bin`), commander CLI in `src/bin/codegraph.ts` with `init` (790), `index` (865), `sync` (995), `query` (1302), `explore` (1390), `context` (1431), `ui` (2047), `impact` (2440), `affected` (2557). **VERIFIED-IN-CODE**
- Extraction: web-tree-sitter WASM grammars (`package.json:44-55`) plus a Rust kernel (`codegraph-kernel/`). 31 files in `src/extraction/languages/` (about 28 languages plus helpers), plus Vue, Svelte, Astro, Razor, Liquid, MyBatis extractors in `src/extraction/`. **VERIFIED-IN-CODE**
- Graph model: SQLite. `nodes` table has kind, qualified name, file path, language, start and end line and column, docstring, signature (`src/db/schema.sql:20-32`). `edges` has kind, line, column, `provenance` (`:45-56`). Edge kinds: contains, calls, imports, exports, extends, implements, references, type_of, returns, instantiates, overrides, decorates, navigates (`src/types.ts:57-71`). Provenance values `tree-sitter | scip | heuristic` (`src/types.ts:227`). Unresolved references kept in their own table (`schema.sql:88-100`). **VERIFIED-IN-CODE**
- External integration detection: regex classifier for network, SDK, and queue call patterns, including `requests`, `httpx`, `boto3`, `openai`, `anthropic` (`src/ui-server/api/effects.ts:189-192`). Heuristic by design. **VERIFIED-IN-CODE**
- LLM: none. It is a context engine for coding agents via MCP (`src/mcp/`). Provider names appear only in the effect regex and MCP metadata. **VERIFIED-IN-CODE**
- Viewer: Svelte + `@xyflow/svelte` (`ui/package.json:48`), served locally with JSON endpoints `/api/stats`, `/api/routes`, `/api/map`, `/api/flow`, `/api/source` and more (`src/ui-server/api/index.ts:176-235`). Gated behind `CODEGRAPH_UI=1` because it is pre-release and "exercised on Expo apps, not on API ... projects" (`src/bin/viewer-gate.ts:1-11`). **VERIFIED-IN-CODE**
- Git: uses git for hooks and file listing (`src/sync/git-hooks.ts:56-106`, `src/sync/watcher.ts:33`). No history mining. **VERIFIED-IN-CODE**
- Telemetry: anonymous, default on, opt out with `codegraph telemetry off`, `CODEGRAPH_TELEMETRY=0`, or `DO_NOT_TRACK=1` (`TELEMETRY.md:11-28`); endpoint `telemetry.getcodegraph.com` (`src/telemetry/index.ts:30`). **VERIFIED-IN-CODE**
- Commercial direction: README advertises a hosted "CodeGraph platform" waitlist. **DOCUMENTED-CLAIM**. Open-core drift risk is **INFERRED**.

#### xnuinside/codegraph
- Python only. Parses with the `tokenize` module (`codegraph/parser.py:3`, `:99`). Links usage by substring checks on source lines (`codegraph/core.py:363-375`). Output: D3 force HTML (D3 from `d3js.org` CDN) or CSV, optional matplotlib. **VERIFIED-IN-CODE** + **TESTED**

#### depvis (mfinean)
- Rust CLI (`src/main.rs:356`). Python via `rustpython-parser 0.4` (`Cargo.toml:21`, `src/analyzers/python.rs:5`). JS/TS via line-by-line string scanning (`src/analyzers/javascript.rs:31-60`). C++ includes via regex (`src/analyzers/cpp.rs:31`). Edges carry a `reason` string, no file line (`src/graph.rs:53-57`). Outputs text, JSON, DOT, PNG/SVG via Graphviz, D3 web viewer from CDN (`web/index.html:8`). **VERIFIED-IN-CODE**

#### depvis (nealwp)
- Browser app that fetches package metadata from `https://registry.npmjs.org` (`src/ModuleCache.ts:3`); README line 229 says it was forked from npmgraph. Not a repo analyzer. **VERIFIED-IN-CODE**

#### GitNexus (benchmark only)
- Monorepo: CLI + MCP + HTTP API in `gitnexus/`, React web client in `gitnexus-web/` (`ARCHITECTURE.md:5-15`). 19-phase ingestion pipeline (`ARCHITECTURE.md:17`, `gitnexus/src/core/ingestion/pipeline.ts`), native tree-sitter grammars (`gitnexus/package.json:99-109`), LadybugDB graph store (`:71`), graphology (`:83-85`), local embeddings via `@huggingface/transformers` (`:113`). **VERIFIED-IN-CODE** (files and deps); the pipeline behavior is **DOCUMENTED-CLAIM**.
- MCP tools include `query`, `cypher`, `context`, `impact`, `detect_changes`, `api_impact`, `trace`, `route_map`, `shape_check`, `pdg_query` (`ARCHITECTURE.md` MCP table). Git staleness classification in `gitnexus/src/core/git-staleness.ts`. **DOCUMENTED-CLAIM**
- Web chat supports openai, azure-openai, gemini, anthropic, ollama, openrouter (`gitnexus-web/src/core/llm/types.ts:13-18`). Viewer uses sigma (`gitnexus-web/package.json:27-35`). **VERIFIED-IN-CODE**
- License: PolyForm Noncommercial 1.0.0 (`LICENSE:1-3`). Permitted: noncommercial purposes (`:31-33`) and personal research "without any anticipated commercial application" (`:35-37`). README offers commercial licensing via akonlabs.com (`README.md:1178-1191`). **VERIFIED-IN-CODE**

#### Git of Theseus
- `git-of-theseus-analyze` (`setup.py:19-25`) walks `repo.iter_commits(branch)` (`git_of_theseus/analyze.py:300`), samples one commit per interval (default 7 days, `:241`, `:321`), runs `git blame` per file in worker processes (`:88-91`), and buckets surviving lines by cohort year, author, extension, top dir, and email domain (`:104-107`). Writes `cohorts.json`, `exts.json`, `authors.json`, `dirs.json`, `domains.json`, `survival.json` (`:532-543`). Plots are matplotlib PNGs. Fully deterministic, no network. **VERIFIED-IN-CODE**

#### Code Maat (study only, GPL-3.0)
- Input is a pre-made `git log` dump; the preferred format is `git log --all --numstat --date=short --pretty=format:'--%h--%ad--%aN' --no-renames` (`README.md:83`). **VERIFIED-IN-CODE**
- Analyses registered in `src/code_maat/app/app.clj:56-73`: authors, revisions, coupling, soc (sum of coupling), summary, abs-churn, author-churn, entity-churn, entity-ownership, main-dev, refactoring-main-dev, entity-effort, main-dev-by-revs, fragmentation, communication, messages, age. **VERIFIED-IN-CODE**
- Technique I studied (described in my words, no code carried over): logical coupling counts how often two files change in the same commit, divides shared revisions by the average revision count of the pair, and reports it as a percentage (`src/code_maat/analysis/logical_coupling.clj:24-46`). Noise controls: minimum revisions 5, minimum shared revisions 5, minimum coupling 30%, maximum coupling 100%, and changesets larger than 30 files are ignored (`src/code_maat/cmd_line.clj:23-33`, filter at `coupling_algos.clj:76-87`). A temporal-period option merges commits within a window into one logical changeset (`cmd_line.clj:35-36`). **VERIFIED-IN-CODE**

### 2.3 Scores (rubric from the approved brief), revised after Lab B and C

1 = poor, 5 = strong. Scores are **INFERRED** judgments from section 2.2, my tests (section 3), and Lab's graded results (3.9). Changes from the pre-merge version are marked with the old value and a reason.

| Candidate | Architecture analysis | Graph interaction | Conversational integration | Historical analysis | Integration effort (5 = easy) | Commercial reuse | Total /30 |
|---|---|---|---|---|---|---|---|
| CodeGraph (colbymchenry) | 4 | 3 | 3 | 2 | 4 | 4 | **20** (unchanged) |
| GitNexus (benchmark) | **4** (was 5) | 4 | 4 | **2** (was 3) | 2 | 1 | 17 (was 19; not eligible) |
| CodeBoarding | **3** (was 4) | 3 | 2 | 2 | 2 | 4 | **16** (was 17) |
| Git of Theseus | 1 | 1 | 1 | 3 | 4 | 5 | 15 (history only, unchanged) |
| xnuinside/codegraph | 2 | 2 | 1 | 1 | 4 | 5 | 15 (unchanged) |
| GitDiagram | 2 | 2 | 2 | 1 | 2 | 4 | 13 (unchanged) |
| depvis (mfinean) | 1 | 2 | 1 | 1 | 3 | 4 | 12 (unchanged) |
| Code Maat | 1 | 1 | 1 | 5 | 2 | 1 | 11 (study only, unchanged) |
| lemonberrylabs/codegraph (new, from Lab) | 2 | 1 | 1 | 1 | 4 | 2 | 11 |
| depvis (nealwp) | 1 | 2 | 1 | 1 | 2 | 4 | 11 (not a repo analyzer) |

Totals are a reading aid, not the decision. The decision weighs evidence fidelity and commercial reuse above the rest. Best and runner-up do not change.

**Score changes and why**

- **CodeBoarding architecture 4 to 3.** My 4 credited the component layer, which neither seat could run (no LLM key). Lab graded the part that does run (static + health) against ground truth: N on purpose, P on components, connections and the create-item trace. It also gives `deps.get_current_user` 0 incoming edges (`LAB_B_RESULTS.md`, failure 3). A score should reflect what was tested, so 3. **LAB-TESTED**
- **GitNexus architecture 5 to 4.** My 5 rested mostly on its documentation. Lab's run found DI invisible (`impact get_current_user` returns 0), no path across HTTP (`trace Login authenticate` returns `no_path`), cluster labels that do not match file roles (`crud.create_user` in module "Routes"), and `trace`/`cypher` start lines 0-based in 492 of 500 Function nodes while `context`/`query` are 1-based (`lab/B/logs/line_check.txt`). Still the richest analysis tested, so 4, not lower. **LAB-TESTED**
- **GitNexus historical 3 to 2.** Lab: no history mining, only `detect-changes` on a diff; Q5 graded N. My 3 came from documented staleness and change detection, which are diff features, not history. **LAB-TESTED**
- **lemonberrylabs/codegraph (new row).** Scored from Lab's evidence only; I did not inspect its code. Architecture 2: function start lines exact (61 of 61 Python, 207 of 230 TS confirmed), but it misses `crud.x()` module-attribute calls (0 route-to-crud edges where ground truth has at least 11), flags 4 used crud functions dead, and marks all 230 frontend functions dead because entry globs matched 0 nodes. Graph interaction 1: Lab used JSON output; no viewer was assessed. Conversational 1, historical 1: none. Integration effort 4: npm install, 0.29 s backend run. Commercial reuse 2: no LICENSE file in the repo, so the MIT claim rests on README and npm metadata, which is weak for reuse. **LAB-TESTED** + **LAB-DESK**

**Scores kept, with Lab evidence noted**

- **CodeGraph, all unchanged.** Lab's systematic gaps (DI, HTTP boundary) apply: my follow-up T10 shows file-level DI reach with one false positive and 0 frontend-to-backend edges. That was already priced into architecture 4 ("no cross-language link", route prefix not composed). Not raised either, because Lab has not graded it. **TESTED**
- **GitDiagram architecture stays 2.** Lab confirms the reason for not scoring it higher: Q3 and Q4 contain a wrong relationship and Q2 adds a container that does not exist. Not lowered to 1 because Q1 (purpose and entry points) was correct, which depvis and lemonberrylabs cannot do at all. Rejected either way. **LAB-TESTED**
- **Git of Theseus historical stays 3.** Lab graded Q5 P and Q6 U: it shows when big shifts happened but carries no commit hashes. That matches my 3 ("one technique done well, no PR linking"). **LAB-TESTED**
- **depvis stays 1 on architecture.** Lab adds a second failure: 121 local `@/...` imports labeled as external packages. **LAB-TESTED**

**Reasons per score (pre-merge reasoning, still valid unless changed above)**

CodeGraph
- Architecture 4: symbols, calls, imports, inheritance, and HTTP routes with file, line, and column across Python and TypeScript, with provenance per edge. Loses a point: no component grouping, no cross-language link from the frontend client to backend routes, DI only at file level, and the `/api/v1` prefix was not composed into route paths.
- Graph interaction 3: real viewer with map, flow, routes, and source views plus JSON APIs, but it is pre-release, gated, and tuned for Expo apps per its own gate comment.
- Conversational 3: no chat, but MCP tools (`query`, `explore`, `context`, `impact`) are the right shape for a grounded chat backend. Traces must build the chat.
- Historical 2: `affected` maps changed files to tests; no commit history analysis.
- Integration effort 4: npm install in 10 s, 288 MB `node_modules`, SQLite output readable from any language. Loses a point for API churn risk (412 open PRs, version 1.6.2 moving fast).
- Commercial reuse 4: MIT. Loses a point for default-on telemetry and an announced hosted platform that could pull features out of the OSS line (**INFERRED**).

CodeBoarding
- Architecture 3: see change above.
- Graph interaction 3: Cytoscape HTML with nested component pages. Static docs, not an explorer.
- Conversational 2: no chat. LLM used only to generate the analysis.
- Historical 2: incremental re-analysis on diffs, nothing on history.
- Integration effort 2: Python 3.12 only (`pyproject.toml:11`), 414 MB venv, 1.6 GB of language servers (kotlin-lsp alone 1.2 GB), LLM key required for the main output. Lab measured the language-server download at 33.9 s.
- Commercial reuse 4: MIT. Loses a point for default-on PostHog telemetry including repo owner, and because setup downloads Intelephense, which ships under a proprietary licence with paid premium features (`~/.codeboarding/servers/node_modules/intelephense/LICENSE.txt`).

GitNexus
- Architecture 4 and historical 2: see changes above. Graph 4 and conversational 4 remain **DOCUMENTED-CLAIM** plus dependency evidence; Lab ran it `--index-only` and did not test the web UI or chat. Commercial reuse 1: PolyForm Noncommercial. Integration effort 2: native tree-sitter builds, embedded graph DB, local embedding model download, and by default `analyze` writes `AGENTS.md`, `CLAUDE.md`, skills and Claude Code hooks into the repo (`lab/desk/tool-requirements.md`).

GitDiagram
- Architecture 2: the graph is LLM-authored from at most 12 excerpted files; validation stops invented paths but cannot prove a relationship exists, and Lab's graded page shows exactly that failure.
- Graph interaction 2: Mermaid SVG with pan, zoom, and GitHub links. No progressive disclosure or search.
- Conversational 2: streamed overview and an MCP endpoint, no chat in the app.
- Historical 1: none.
- Integration effort 2: Cloudflare Workers, R2, Upstash, PostHog, payments, Node 22. Lifting it means untangling hosting.
- Commercial reuse 4: MIT, with brand and hosted-service entanglement to strip.

Git of Theseus
- Historical 3: one technique (line survival by cohort, author, dir) done well and deterministically. No coupling, no commit hashes, no PR linking.
- Integration effort 4: pip install, 9.8 s on 1,537 commits (Lab: 5.1 s). Last commit 2023-11-25, so Traces would own maintenance.
- Commercial reuse 5: Apache-2.0, no NOTICE file present.

Code Maat
- Historical 5: the richest technique catalogue here (coupling, sum of coupling, churn, ownership, fragmentation, communication, age).
- Integration effort 2: JVM, CSV only, and GPL means it can only run as a separate program or be reimplemented clean-room.
- Commercial reuse 1: GPL-3.0. No code reuse in a product Shailesh may sell under other terms.

xnuinside/codegraph
- Architecture 2: Python only; substring matching (`core.py:363-375`) is open to name collisions. Graph 2: D3 force HTML. Integration 4 and reuse 5: tiny and MIT, but little to reuse.

depvis (mfinean)
- Architecture 1: dropped the test repo's Python 3.14 file, mislabeled 121 local imports as packages (Lab), and with `--local-only` produced 198 nodes and 1 edge (both seats). Graph 2: D3 force viewer with path finding. Reuse 4: MIT, but one maintainer and 3 stars.

depvis (nealwp)
- Not a source analyzer. Scored for completeness only.

---

## 3. Test results and limits

### 3.0 Exact tests I ran (separate from desk research)

All runs on the box: 8 vCPU, 15 GB RAM, Python 3.13.5 system (3.12 venvs via uv 0.13.1), Node 20.19.2, cargo 1.85.1. Timing and peak RSS from a `getrusage` wrapper (`_tests/measure.py`). Telemetry disabled for every tool (`DO_NOT_TRACK=1`, `CODEGRAPH_TELEMETRY=0`, `CODEBOARDING_TELEMETRY=false`). No LLM keys present in the environment; GitHub tokens unset for the CodeBoarding run. Tools that write into the repo ran on copies under `_work/`, never on `_src/full-stack-fastapi-template`.

| # | Tool and version | Command (short form) | Result | Wall time / peak RSS | Artifacts |
|---|---|---|---|---|---|
| T1 | Git of Theseus 0.3.4 (from source 961bda0) | `uv pip install` then `git-of-theseus-analyze --procs 4 .` then stack and survival plots | Success | install 1.7 s; analyze 9.8 s / 87 MB; plots 3.2 s | `_tests/out/got/*.json`, `cohorts.png`, `dirs.png`, `survival.png` |
| T2 | xnuinside/codegraph 1.2.0 | `codegraph app --output backend.html` and `--csv` in `backend/` | Success | 1.1 s / 55 MB | `_tests/out/xnu/backend.html` (99 KB), `backend.csv` (118 rows) |
| T3 | depvis 0.1.0 (mfinean, built from source) | `cargo build --release --features serve`; then `--format json`, `--summary --analyze --cycles --local-only`, `--format dot` | Build success; analysis partial | build 47.9 s / 571 MB; runs under 0.1 s | `_tests/out/depvis/graph.json` (680 nodes, 985 edges), `graph.dot`. PNG/SVG skipped: Graphviz not installed |
| T4 | CodeGraph 1.6.2 (npm `@colbymchenry/codegraph`) | `npm install`; `codegraph init -y .`; `status`; `query create_user`; `impact create_user`; `affected backend/app/crud.py`; `CODEGRAPH_UI=1 codegraph ui --read-only --no-open`; curl `/api/stats`, `/api/routes`, `/api/map`, `/api/entrypoints`; direct SQLite queries | Success | install 9.9 s, 288 MB; index 1.4 s / 378 MB; 5.0 MB DB | `_work/fastapi-codegraph/.codegraph/codegraph.db`, `_tests/out/codegraph-api/*.json`, `_tests/logs/codegraph-colby-*.log` |
| T5 | CodeGraph 1.6.2, scale | `codegraph init -y .` on a copy of the GitNexus repo (7,194 files, about 4.5M lines incl. fixtures). Parsing only; GitNexus code was not executed | Success, 1 file with parse errors | 88.7 s / **4.1 GB**; 67,910 nodes, 221,498 edges; 294 MB DB (deleted after) | `_tests/logs/codegraph-scale.log` |
| T6 | CodeBoarding 0.15.1 (from source 3a5098c) | `uv pip install`; `codeboarding-setup`; static analysis only via `static_analyzer.get_static_analysis` (`_tests/cb_static.py`); `codeboarding full --local` with no key; `codeboarding-render` on its own committed `analysis.json` | Install and static success; full run **stopped at missing LLM key** as expected; render success | venv 414 MB; static 10.4 s / 354 MB; no-key run 6.0 s | `_tests/logs/codeboarding-*.log`, `_tests/out/cb-render/*.html` |
| T7 | GitDiagram 7a33d6e | `npm install` (failed: EOVERRIDE on dompurify); `bun install --frozen-lockfile` (failed: lockfile drift); `bun install --ignore-scripts` (success); `npx vitest run` on 4 server test files | 2 test files passed (13 tests: edge-evidence, source-references); 2 failed to load on Node 20 (`webidl.util.markAsUncloneable`, needs Node 22). Generation not attempted: needs OpenAI or OpenRouter key plus R2 and Upstash | install 1.8 s (warm cache), 1.5 GB `node_modules`; tests 1.4 s | `_tests/logs/gitdiagram-*.log` |
| T8 | Code Maat 1.0.4 standalone jar (official release), portable Temurin JRE 17 via `install-jdk` | `git log --all --numstat ... --no-renames` dump, then `-c git2 -a summary|coupling|revisions|entity-churn|main-dev|age`. Run as a separate process; no Code Maat code read into or copied into anything | Success | about 2.3 s / 300 to 370 MB per analysis; 174 MB JRE + jar | `_tests/out/codemaat/*.csv`, `git2.log` |
| T9 | Test repo history probes | `git log` counts for PR refs, bot authors, renames, tags | Success | under 1 s | numbers in 0.1 |
| T10 | CodeGraph 1.6.2, follow-up after Lab B (run about 23:45 IST) | `codegraph impact get_current_user`; SQLite queries for edges into `deps.py` symbols, outgoing edges of `items.create_item`, and frontend-to-backend edges | Success. DI reach is file-level only, with 1 false positive; 0 frontend-to-backend edges; `items.create_item` has 0 outgoing call edges | under 1 s | `_tests/logs/codegraph-colby-di.log` |

Not run: **GitNexus** (license, see 3.8), **nealwp/depvis** (not a repo analyzer), **CodeBoarding full analysis and GitDiagram generation** (need paid LLM keys, stopped by rule).

### 3.1 CodeGraph on the test repo (TESTED)
- 175 files indexed (70 tsx, 43 python, 39 typescript, 23 yaml), 2,076 nodes, 4,642 edges. Edge mix: contains 1,893, imports 1,222, calls 884, references 576, instantiates 47, navigates 14, extends 6. Provenance: 4,351 unset (default extraction), 291 `heuristic`.
- Python 3.14 `except A, B:` syntax in `deps.py` parsed fine; all 8 symbols in that file were extracted.
- 31 routes found, each with method, path, handler, file, and line. Spot check: `POST /users` at `backend/app/api/routes/users.py:54` (decorator line) with handler at `:57`. Correct.
- `crud.create_user` (`backend/app/crud.py:10`) has 26 incoming call edges, including `routes/users.py:68`, `register_user` at `:158`, and `core/db.py:33`. Spot-checked lines are correct.
- Limits seen: route paths are `/users`, not `/api/v1/users`; the prefix set in `backend/app/main.py:35` from `config.py:22` was not composed. No edges from frontend code to backend routes, so the HTTP boundary between React and FastAPI is invisible. 3,314 unresolved references (all `failed`), mostly third-party imports and Playwright calls; they are kept, not silently dropped.
- Heuristic edges are mostly JSX component usage (e.g. `EditUser.tsx:59 -> DialogFooter`). Correct in the samples I checked, but they are labeled heuristic, which is what Traces needs.

### 3.2 CodeBoarding on the test repo (TESTED)
- Static analysis without an LLM: Python 27 source files, 95 call-graph nodes, 101 edges, 8 package deps; TypeScript 94 files, 564 nodes, 639 edges, 21 package deps. 10.4 s.
- Python coverage was 27 of 43 `.py` files. I did not trace why 16 were excluded (likely tests or alembic config). **INFERRED**
- `codeboarding full` stops at "LLM provider not configured" and lists 20 accepted env vars. So no component view without a paid or self-hosted LLM.
- `~/.codeboarding` already existed when I ran setup (created 23:10 IST, before my install at 23:14). Lab's B results confirm it was Lab's install (`python -m infra.install`, 33.9 s, `lab/B/logs/codeboarding_install.log`). **LAB-TESTED** Footprint 1.6 GB (`bin/kotlin-lsp` 1.2 GB, `node_modules` 217 MB). The config file has every provider key commented out; no secrets present.

### 3.3 GitDiagram (TESTED, partial)
- The two evidence modules that matter for Traces pass their own tests on Node 20. Full generation is out of reach without an LLM key and Cloudflare-style services. Its install failed under npm and under a frozen bun lockfile, a sign that the repo is tuned for its own deploy, not for embedding. **TESTED** + **INFERRED**

### 3.4 xnuinside/codegraph (TESTED)
- Ran on `backend/app` in 1.1 s. CSV gives name, type, parent module, path, links in and out, and line count, but no line numbers. `crud.create_user` shows 5 incoming links while CodeGraph found 3 non-test callers in `app/`. With substring matching (`core.py:363-375`) the extra 2 are likely false positives. **TESTED** for the counts, **INFERRED** for the cause.

### 3.5 depvis, mfinean (TESTED)
- Python parse failed on `backend/app/api/deps.py` (PEP 758 syntax) because `rustpython-parser 0.4` predates Python 3.14.
- Full graph: 680 nodes, 985 edges (505 python_import, 383 js_import, 28 js_type_import, npm and python dependency edges). With `--local-only`: 198 nodes, 1 edge, 196 orphans. Imports resolve to module names, not to files, so the local file graph is empty.

### 3.6 Git of Theseus (TESTED)
- 98 weekly samples from 2019-02-10 to 2026-10-15. Surviving lines at HEAD by cohort year: 2019: 522, 2020: 255, 2023: 271, 2024: 2,913, 2025: 6,640, 2026: 4,400. By top dir: `frontend/` 11,279, `backend/` 2,936, `packages/` 388, `scripts/` 254.
- Reads as: most of today's code was written in 2024 to 2026; the 2019 to 2020 code is mostly gone. That is a real architectural-evolution signal for a non-developer, but the PNG output is not interactive or mobile-friendly.

### 3.7 Code Maat (TESTED as an external program)
- Summary: 1,540 commits, 1,221 entities, 5,590 entity changes, 88 authors.
- Top coupling pairs (degree %, average revs): `deploy-production.yml` and `deploy-staging.yml` 100% / 21; `AddItem.tsx` and `EditItem.tsx` 94% / 9; `AddUser.tsx` and `AddItem.tsx` 94% / 9; `package-lock.json` and `package.json` 82% / 135. These are genuine "change together" facts. Whether they mean shared design or copy-paste is a hypothesis, not a finding.
- Top revisions: `release-notes.md` 670 (bot-driven), `frontend/package.json` 161, `README.md` 153. Confirms bot filtering is required.
- `--no-renames` splits history for moved paths (old `{{cookiecutter.project_slug}}/...` entries show up as separate files). A Traces implementation should follow renames.

### 3.8 GitNexus: not run by me; run by Lab as a benchmark

- The PolyForm Noncommercial licence permits personal research "without any anticipated commercial application" (`LICENSE:35-37`). Evaluating it as a foundation for a product Shailesh may sell is arguably an anticipated commercial application, so I did not install or run it. **INFERRED** (not legal advice)
- Lab ran `gitnexus@1.6.12` in a throwaway clone with a sandboxed `HOME`, `DO_NOT_TRACK=1` and `--index-only` so it could not inject `AGENTS.md`, `CLAUDE.md` or editor hooks (`lab/B/results.md`, GitNexus section). Its results are merged in 3.9 and used in 2.3. Whether that run was acceptable is an open decision for Shailesh (6.1, 7). **LAB-TESTED**

### 3.9 Investigation B (Traces Lab), merged

Source: `LAB_B_RESULTS.md`, `lab/B/results.md`, `lab/B/ground-truth.md`, `lab/B/logs/`. Author: Traces Lab. Lab's tags kept. Box and SHA identical to mine.

**Method.** Lab wrote a git-verified ground truth for six questions (Q1 purpose, Q2 components, Q3 connections, Q4 create-item trace, Q5 change over time, Q6 evidence quality) and graded each tool G (grounded and correct), P (partial), W (contains a wrong relationship), U (ungrounded), N (not answered). This is a stronger test than mine, which measured install, run cost, and spot-checked counts and lines. **LAB-TESTED**

**What Lab ran.** CodeBoarding `3a5098c` static + health (LLM mode BLOCKED, no key); GitDiagram public cached page only (local run BLOCKED: Bun, R2, Upstash, OpenAI or OpenRouter key; `README.md:68`); `@lemonberrylabs/codegraph@0.1.0`; depvis 0.1.0 from crates.io; Git of Theseus 0.3.4; GitNexus 1.6.12 (benchmark). FalkorDB/code-graph BLOCKED (needs a FalkorDB server, no Docker). **LAB-TESTED** / **LAB-DESK**

**Lab grades** (copied from `LAB_B_RESULTS.md`):

| tool | Q1 | Q2 | Q3 | Q4 | Q5 | Q6 |
|---|---|---|---|---|---|---|
| CodeBoarding static + health | N | P | P | P | N | P |
| GitDiagram cached page | G | P | W | W | N | U/P |
| lemonberrylabs/codegraph | N | N | W | P | N | G |
| depvis | N | P | W | N | N | P |
| Git of Theseus | N | N | N | N | P | U |
| GitNexus | N | P | P | P | N | P |

CodeGraph (colbymchenry) and xnuinside/codegraph were not graded by Lab.

**Lab's top grounding failures**, with my re-checks where I ran one:

1. GitDiagram says items routes use the CRUD layer. `items.py` has 0 `crud.` references and writes with `session.add/commit` at `items.py:68-71`; all 34 cited paths exist (`lab/B/logs/gitdiagram_path_check.txt`). **LAB-TESTED**. **RE-CHECKED**: `grep -c 'crud\.'` on `backend/app/api/routes/items.py` returns 0; lines 68-71 are `Item.model_validate`, `session.add`, `session.commit`, `session.refresh`.
2. GitDiagram invents a frontend container. `compose.yml` services are proxy, db, adminer, backend; the frontend is built in `backend/Dockerfile:1-16` and served by `backend/app/main.py:36`; `frontend/Dockerfile` was deleted in `e80d924` (#2393). **LAB-TESTED**. **RE-CHECKED**: `compose.yml` top-level services at lines 3, 20, 34, 49 are exactly those four; only `frontend/Dockerfile.playwright` exists.
3. FastAPI DI is invisible: `get_current_user` has 0 incoming edges in CodeBoarding, lemonberrylabs/codegraph and GitNexus; `gitnexus impact get_current_user` returns 0. **LAB-TESTED**. **RE-CHECKED on CodeGraph (not in Lab's set)**: 9 affected symbols, file-level (T10).
4. No tool links the SDK call `ItemsService.createItem` (`sdk.gen.ts:307`) to the route `items.create_item` (`items.py:62`), though the join key is the operation id built at `main.py:14-15`. **LAB-TESTED**. **RE-CHECKED**: `main.py:14-15` returns `f"{route.tags[0]}-{route.name}"`; `sdk.gen.ts:307` declares `createItem` with `itemsCreateItemData`; CodeGraph has 0 frontend-to-backend edges.
5. GitNexus `trace` and `cypher` start lines are 0-based (492 of 500 Function nodes off by one), `context` and `query` 1-based. **LAB-TESTED** (`lab/B/logs/line_check.txt`)
6. lemonberrylabs/codegraph marks 4 used crud functions dead and all 230 frontend functions dead. **LAB-TESTED**
7. depvis drops `deps.py` (Python 3.14 syntax) with only a stderr warning, and labels 121 local `@/` imports as external packages. **LAB-TESTED**
8. No tool answers "how did the architecture change" with commit evidence. **LAB-TESTED**

**Where Lab and I agree**

| Topic | Lab | Me | Verdict |
|---|---|---|---|
| Test repo SHA | `b1125d8` | `b1125d8` | Same |
| CodeBoarding static counts | Py 95 nodes / 101 edges, TS 564 / 639 | identical | Agree exactly |
| CodeBoarding LLM mode | BLOCKED, "LLM provider not configured" | same error | Agree |
| CodeBoarding install footprint | 1.6 GB into `~/.codeboarding`, 33.9 s | 1.6 GB; my setup took 2.4 s because Lab's download was already there | Agree. Resolves my 3.2 inference: the 23:10 IST install was Lab's (`lab/B/logs/codeboarding_install.log`) |
| depvis Python 3.14 failure | `deps.py` dropped | same, error at byte 996 (`except A, B:`) | Agree |
| depvis `--local-only` | 198 nodes, 1 edge | 198 nodes, 1 edge | Agree exactly |
| Git of Theseus cohorts | 522 / 255 / 271 / 2,913 / 6,640 / 4,400; "counting 320 commits" | identical | Agree exactly |
| HTTP boundary | no tool crosses it | CodeGraph doesn't either | Agree, now covers 7 tools |
| Python 3.14 parser drift | Lab's own `ast` fell back to regex | depvis and rustpython fail; CodeGraph's tree-sitter parsed it | Agree on the risk; tree-sitter is the fix |

**Where we differ, and why**

| Topic | Lab | Me | Reading |
|---|---|---|---|
| codeGRAPH candidate | lemonberrylabs/codegraph | colbymchenry/codegraph, xnuinside/codegraph | Different repos, no overlap. Contrast, not conflict: lemonberrylabs misses `crud.x()` calls, colbymchenry finds 26 callers of `crud.create_user`. Open question 1 and 2 |
| "No tool handles DI" | true for all 3 tools Lab ran | CodeGraph gives file-level reach through `CurrentUser` (9 symbols, 1 false positive) | Lab's statement holds at handler level for every tool, including CodeGraph. CodeGraph is better at file level. **TESTED** |
| depvis node count | 619 nodes, 985 edges (text output) | 680 nodes, 985 edges (JSON, `--no-cache`) | Same edges, different node counts. Not resolved; likely output mode or cache. **INFERRED** |
| Git of Theseus wall time | 5.1 s | 9.8 s | My run shared the box with 3 other jobs. **INFERRED** |
| GitDiagram evidence | graded the public page dated 2026-09-08: relationships carry no evidence | read code: edges have `evidencePath` and a deterministic check | Both true. `src/server/generate/edge-evidence.ts` first landed in `539c996` on 2026-09-30 02:27 IST, after the page date (`gh api` commits). The page reflects the older pipeline. Even the newer check is file-level: an `items -> CRUD` edge citing `items.py` (a file the model was shown, on one side of the edge) would likely survive it. **TESTED** (date) + **INFERRED** (survival) |
| GitNexus | ran it | did not run it | License posture differs. Decision pending with Shailesh |

**Lab inference carried over** (**LAB-INFERRED**): "path citations are cheap and all tools got paths right; relationship claims are where they fail. A Traces answer should cite the line where the relationship happens (call site, `Depends(...)`, `include_router`, operation id), not just the files involved." Both systematic gaps (DI, OpenAPI boundary) are solvable with deterministic rules on this stack. I agree; it drives 4.3.

## 4. Reuse vs build custom

### 4.1 Fork one project vs compose parts

Recommendation: **compose.** **INFERRED**

- No single candidate covers more than two of the seven product capabilities with evidence-first behavior. Forking CodeBoarding gets components but inherits an LLM-first docs generator and 1.6 GB of servers. Forking GitDiagram inherits a hosted business. Forking CodeGraph inherits a fast-moving codebase with 412 open PRs that Shailesh would then need to keep merging.
- Composition keeps each upstream behind an adapter that writes into a Traces-owned evidence schema. If an upstream changes license or direction, Traces swaps the adapter, not the product.

### 4.2 Role of each piece

| Layer | Use | How | Tag |
|---|---|---|---|
| Symbol, call, import, route extraction | CodeGraph | npm dependency, run as a CLI or library, read its SQLite. Pin a version. Telemetry off by default in Traces | TESTED |
| LSP-precision call graph (optional, per language) | CodeBoarding `static_analyzer` | Optional second engine for deeper Python and TS call resolution when needed; skip its LLM layer | TESTED |
| Edge evidence validation pattern | GitDiagram ideas | Reimplement the rule "an LLM citation must point at a file the model was shown, else strip it" (`edge-evidence.ts:17-26`). MIT allows lifting the module with attribution. Revised after Lab B: this check is file-level only and would pass a wrong relationship, so Traces adds line-level checks on top (4.3.1) | VERIFIED-IN-CODE + LAB-TESTED |
| LLM relation grounding pattern | CodeBoarding ideas | Same idea at relation level: every LLM-proposed relation is matched to static edges and flagged `is_static`; unbacked ones are labeled, not hidden | VERIFIED-IN-CODE |
| Line survival by cohort | Build in-house (Git of Theseus as reference) | Reimplement blame sampling keyed by commit SHA; Git of Theseus (Apache-2.0) output has no commit hashes (Lab Q6 U). Revised after Lab C | TESTED + LAB-TESTED |
| History ingest, lifecycle, coupling, churn, ownership, age, reverts | Build in-house on native git | Start from Lab's stdlib prototype (`lab/C/scripts/`, 15.3 s on this repo); techniques clean-room from published descriptions, never from Code Maat source | TESTED (Code Maat as external tool) + LAB-TESTED |
| Decision evidence | Build in-house on the GitHub API | PR bodies, review comments, linked Discussions keyed by `(#N)` | LAB-TESTED |
| Framework and cross-language edges | Build in-house | `Depends`, router prefixes, OpenAPI operation-id join, per framework (4.3) | TESTED (absence) + LAB-TESTED |
| Evidence schema, component grouping, PR and doc linking, chat, mobile viewer, privacy controls | Build in-house | Nothing reviewed does these to Traces' standard | INFERRED |

### 4.3 What to build in-house and why

1. **Evidence schema.** Every node and edge carries source (`file`, `line`, `col`, pinned `commit` SHA), extractor and version, provenance (`parsed`, `framework-rule`, `heuristic`, `history`, `llm-proposed`), and confidence. UI shows the tag. This is the core product differentiator and must not depend on any upstream. Lab's four evidence classes in `lab/C/evolution.md` (structure, statistics, documented decisions, inference) map onto the same field and should be adopted as the top-level split. **INFERRED** + **LAB-INFERRED**
2. **Line-level claim verification (lesson from Lab B).** See 4.3.1.
3. **Component grouping without an LLM first.** Group by directory, package manifest, and graph communities, then let the LLM name groups. CodeBoarding shows naming needs an LLM; grouping does not. GitNexus's mislabeled clusters (Lab: `crud.create_user` in "Routes") show that naming must be checked against file roles. **INFERRED** + **LAB-TESTED**
4. **Framework and cross-boundary rules.** No tool in either seat's tests handled these on the test repo, so they are in-house work. First rules for the FastAPI + generated-client stack: **TESTED** (absence) + **LAB-TESTED** + **INFERRED** (rules)
   - `Depends(x)` and `Annotated[..., Depends(x)]` become a `depends_on` edge from the handler to `x`, anchored at the parameter line, and alias variables such as `CurrentUser = Annotated[User, Depends(get_current_user)]` (`deps.py:49`) are resolved through.
   - `include_router(..., prefix=...)` and `APIRouter(prefix=...)` compose into full route paths (CodeGraph showed `/users`, real path `/api/v1/users`).
   - SDK method to route via the OpenAPI operation id (`main.py:14-15` builds `"{tag}-{name}"`; `sdk.gen.ts:307` `createItem` uses `itemsCreateItemData`).
   - Env vars and config to integrations (SMTP, Sentry, DB URL).
   - Rules are per framework and versioned, so each edge says which rule produced it.
5. **Chat over the evidence graph.** Retrieval from the Traces store; answers cite node and edge IDs that resolve to file, line and commit. Every sentence that states a relationship must cite an edge that passed 4.3.1. CodeGraph's MCP tool shapes are a good model. **INFERRED**
6. **Mobile viewer.** See 4.4.

#### 4.3.1 Evidence-checking lesson: path checks are not enough

The GitDiagram page Lab graded cited 34 paths and all 34 exist, yet it claimed `items routes -> CRUD layer: uses` while `items.py` writes to the DB directly at lines 68-71 and never references `crud.` (**LAB-TESTED**, **RE-CHECKED**). A file-exists check, and even GitDiagram's newer "the model was shown this file" check, would pass the claim (3.9). GitNexus shows a second failure mode: the same symbol reported at two line numbers depending on the command (0-based vs 1-based). **LAB-TESTED**

What Traces' evidence model needs as a result (**INFERRED**):

| Level | Check | Passes the GitDiagram crud claim? |
|---|---|---|
| L0 path exists | file exists at the pinned SHA | Yes (34 of 34) |
| L1 file shown | file was in the context the model saw | Yes |
| L2 line exists | cited line exists in that file at that SHA | Would pass if a line is cited |
| **L3 line supports the claim** | the cited line contains the relationship token for the edge type: a call or attribute access to the target symbol, an import of it, a `Depends(target)`, an `include_router(target)`, or an operation-id match | **No**: no line in `items.py` references `crud` |
| L4 deterministic edge exists | a parser or framework rule produced the same edge independently | **No** |

Rules that follow:
- Any relationship shown as fact must reach L3, and L4 where an extractor covers the edge type. Below L3 it is shown as "proposed, unverified".
- Absence must be tested too: "A uses B" fails if A's file has zero references to B, which is exactly the GitDiagram case.
- Cite the pinned commit SHA, not `blob/master` (the GitDiagram page links to a moving branch).
- Normalize every line number to 1-based on ingest, store the extractor's original value, and add a regression test per extractor (GitNexus off-by-one).
- Keep absence explicit: GitNexus prints "An absent flow does NOT mean the code path does not exist". Traces should say the same whenever an impact answer is empty, since DI and HTTP edges are known gaps.
- Run the checks automatically before any LLM-written sentence reaches the user, and keep the failed claims in a reviewer view so ChatGPT or Shailesh can audit what was dropped.

### 4.4 Multi-language, scale, navigation, mobile

- **Multi-language:** CodeGraph ships about 28 language extractors and handled Python 3.14 syntax; CodeBoarding covers 9 languages via LSPs but csharp needs dotnet; depvis failed on new Python syntax. **TESTED** + **VERIFIED-IN-CODE**
- **Large repos:** CodeGraph indexed about 4.5M lines in 88.7 s with 4.1 GB peak RSS on 8 cores. That is fine for a worker job, too heavy for a phone or a small serverless function. CodeBoarding lets LSPs use up to three quarters of RAM, capped at 12 GB (`README.md:194`). Traces should index server-side, store per-commit snapshots, and stream subgraphs to the client. **TESTED** + **DOCUMENTED-CLAIM** + **INFERRED**
- **Progressive disclosure for non-developers:** CodeBoarding's nested components (component, then sub-component, then methods) is the best model seen. CodeGraph's `/api/map`, `/api/routes`, `/api/entrypoints` give the raw material for a "start from what the system does" view (routes and screens first, code later). **TESTED** + **INFERRED**
- **Mobile, Android browser:** none of the viewers is designed for phones. GitDiagram's Mermaid viewport has touch handling; CodeBoarding's HTML has a viewport meta tag; xnuinside and mfinean ship D3 force graphs from CDNs with no touch code (D3 zoom does handle touch natively, **INFERRED**). For Traces: default to list and card views of capabilities and routes, open a small focused graph (one node plus neighbors) on demand, and use a canvas or WebGL renderer for large graphs. Candidates to evaluate: Cytoscape.js (MIT), sigma.js (MIT), React Flow / xyflow (MIT). **INFERRED**, needs a real Android test in a later task.

---

## 5. Git history integration recommendation

### 5.1 Lab's Investigation C, merged

Source: `LAB_C_RESULTS.md`, `lab/C/verdict.md`, `lab/C/evolution.md`, `lab/C/out/`, `lab/C/logs/`, `lab/desk/code-maat-techniques.md`. Author: Traces Lab. Lab's tags kept.

**Setup.** git 2.47.3, Python 3.13.5 stdlib only, `gh` GET calls only. Nine scripts, 650 lines total, Lab's own code (`lab/C/scripts/`). Runs on the test repo and on Traces `63103ac` (empty results, exit 0). **LAB-TESTED** (I confirmed the 650-line total with `wc -l`.)

**What native git covered** (**LAB-TESTED**, `lab/C/verdict.md` table):
- Architectural snapshots: 7, with stack markers (Vue, Celery, Couchbase, SQLModel, uv, Bun, Copier).
- Lifecycle: 27 directory events, 9 bulk moves (for example `src` to root, 247 renames in `8558cf0`), replayed file set equals `git ls-tree` at HEAD (252 = 252). `items.py` followed back 5 renames to 2019.
- Co-change with a > 30-path changeset filter: `AddUser.tsx`/`EditUser.tsx` support 18, degree 0.95.
- Hotspots, age, authors, effort: 135 code files; `users.py` 43 revisions, equal to `git log --follow`.
- Reverts: 4 detected, 3 real, 1 false positive from a Dependabot body quoting an upstream changelog.
- Manifest dependency history: 50 events; SQLModel added in #558 before #559 adopted it.
- Import-graph diffs at 13 milestones: in 2019 `app.api.api_v1` imported `app.crud` 21 times; at HEAD only `login.py:8` and `users.py:7` import it.
- PR linking: 752 of 1,537 subjects carry `(#N)`; 25 of 25 fetched PRs match local merge commits.

**Cost.** Full suite 15.3 s wall on 1,537 commits; history parse 1.76 s; peak RSS about 80 MB; 25 PR fetches in 57.1 s (rate limit 4,964 to 4,939). Large repos not measured. **LAB-TESTED**

**Gaps Lab found** (**LAB-TESTED**):
1. Rationale lives outside git: 18 of 25 key PRs add under 40 characters beyond the title. Reasons sit in a few PR bodies (#694, #2393), in comments (13 on #694), and in Discussions (#1862 links #1555, not returned by the PR API).
2. Semantic renames: `crud/` (3 files) became `crud.py` in `2d0f774` (#622). Git sees delete plus add, and `git log --follow backend/app/crud.py` stops there. Component renames (#629) break import diffs without an alias map.
3. Framework edges (DI, OpenAPI operation id) are invisible to git. Backend-API-to-client co-change confidence is only 0.14 (client to API 0.30). Lab's own inference: low co-change does not mean a loose boundary, because client regenerations often land in separate commits (`3676734`, #1281). **LAB-INFERRED**
4. Parser version drift: Python 3.13 `ast` cannot parse `deps.py`.
5. Bot noise: a false revert from a Dependabot body; 750 release-note commits.
6. Decisions with no structural footprint: #612 (Add Copier) and #2097 (npm to Bun) touch few directories, and the structural ranker did not select #612.
7. Rename double counting, found and fixed in Lab's own code: `--numstat --no-renames` counted `users.py` as 48 revisions and 2,974 churn instead of 43 and 1,188. Fixed with `--numstat -M -z`.

**Lab's verdict** (**LAB-INFERRED**): native git is enough for the v1 history layer. It is not enough for rationale (needs PR bodies, comments and Discussions through the API), semantic renames and refactor lineage, framework and cross-language edges, and new-syntax parsing (needs tree-sitter or the repo's Python version).

**Lab's documented-decisions output** is the best example in either seat of evidence-first history. `lab/C/evolution.md` section 3 quotes PR bodies with commit and PR for each, for example #694: "When choosing Celery I evaluated RQ, Dramatiq, and a couple of other options..." and #2393: "This simplifies the logic, deployment, debugging, virtually removes all potential CORS issues." Section 4 holds interpretations, each labeled "Inference". **LAB-TESTED**

### 5.2 Combined recommendation (Lab C + my Git of Theseus and Code Maat study)

**Agree with Lab: native git is the system of record for v1 history.** One cached, rename-aware log parse per repo, incremental on new commits. Neither Git of Theseus nor Code Maat is needed at runtime. **LAB-TESTED** + **INFERRED**

How the two seats' evidence fits together:

| Point | Lab C | My study | Combined call |
|---|---|---|---|
| Code Maat access | read README only; did not open, copy or run its source | read the source to verify the formula; ran the official 1.0.4 jar as a separate process (T8); copied nothing | Both stay clean-room. Nothing from Code Maat goes into Traces |
| Coupling formula | degree = support / mean(revs); Lab noted it had not checked whether Code Maat computes it the same way | `logical_coupling.clj:24-46`: shared revisions divided by the average revisions of the pair, as a percentage | **Same formula.** Lab's open item is resolved. **VERIFIED-IN-CODE** |
| Coupling results | AddUser/EditUser 0.95 (support 18), AddUser/EditItem 0.94 (rename-normalized, min support 4) | Code Maat: AddUser/EditUser 90% (avg revs 10), AddItem/EditItem 94%, AddUser/EditItem 88% (`--no-renames`, min shared 5) | Same pairs on top, a few points apart. The difference is rename handling and thresholds. **TESTED** + **LAB-TESTED** |
| Renames | `--no-renames` double counted in Lab's own code until fixed | Code Maat's recommended log format uses `--no-renames` (`README.md:83`), which splits the `{{cookiecutter.project_slug}}/` paths from today's | Agree: rename-aware parsing is a hard requirement, with a regression test using Lab's `users.py` 43 / 1,188 numbers |
| Thresholds | min revs 5, min support 4, max changeset 30 | Code Maat defaults: 5, 5, 30%, 30 (`cmd_line.clj:23-33`) | Start with Code Maat's published defaults, expose them, record which were used on every coupling claim |
| Temporal period | not implemented | Code Maat supports it (`cmd_line.clj:35-36`) | Add for repos that do not squash-merge; this repo does, so it can wait |
| Sum of coupling, communication, fragmentation | not implemented | listed in `app.clj:56-73` | v2. Communication needs a team map, which consultants may not have |
| Line survival | not in Lab's scripts; Lab graded Git of Theseus Q5 P, Q6 U (no hashes) | Git of Theseus: identical cohort numbers in both seats, 9.8 s | Reimplement survival in-house from blame sampling, keyed by commit SHA so every cohort links to commits. Keep Git of Theseus (Apache-2.0) only as a reference implementation |
| Hotspots | revisions x indentation complexity (attributed to Tornhill's books, not verified against a primary source) | not run | Adopt with the formula and inputs shown to the user; mark the complexity proxy as a proxy |
| Bot filtering | 750 release-note commits; Dependabot false revert | 886 bot-authored commits | Filter by author and by message pattern, both on by default, visible toggle |

**v1 history layer** (**INFERRED** unless tagged):
1. Rename-aware ingest (`--name-status -M -C`, `--numstat -M -z`, `.mailmap`), cached per commit. **LAB-TESTED** that this is fast and correct on this repo.
2. Bot and generated-file filters on by default.
3. Lifecycle, snapshots, co-change, hotspots, age, ownership, reverts, manifest diffs: port the ideas from Lab's prototype into Traces' codebase with tests. Lab's scripts are Lab's own code, so they are a valid starting point; Code Maat's are not.
4. Semantic rename and component alias map: detect delete-plus-add where content moves (for example `crud/crud_user.py` into `crud.py` in #622) using content similarity across files, and let a reviewer confirm aliases. Treat it as `history-inferred` evidence until confirmed.
5. Decisions: GitHub API for PR bodies, review comments and linked Discussions (GraphQL), keyed by `(#N)`, cached and rate-limited. Rank PRs by structural signals plus manifest and keyword signals so footprint-light decisions like #612 are not missed.
6. Structure over time: rebuild the CodeGraph index at sampled commits and diff component edges. 1.4 s per index here (**TESTED**); use tags or monthly samples on large repos.
7. Change impact: union of CodeGraph `impact`, the framework rules in 4.3, and co-change partners, each labeled by source. An empty answer always says which edge types are known gaps.
8. Output: Lab's four evidence classes as separate fields. Motives appear only as quotes with a link; anything else is labeled inference.

---

## 6. Licensing and security risks

### 6.1 Licensing

Not legal advice. Confirm with counsel before commercial launch. **INFERRED** unless tagged.

| Item | License | What it means for a commercial Traces |
|---|---|---|
| CodeGraph | MIT (**VERIFIED-IN-CODE**) | Use, modify, sell. Keep the copyright and license text in distributions. Check its transitive deps (tree-sitter grammars are mostly MIT) before shipping. |
| CodeBoarding | MIT (**VERIFIED-IN-CODE**) | Same as MIT above. Runtime downloads are separate: Intelephense is under a proprietary licence (**VERIFIED-IN-CODE**, its `LICENSE.txt`), JDTLS is EPL (**INFERRED**), and the kotlin-lsp server "is distributed under its own terms" per CodeBoarding's installer output (**LAB-TESTED**, `lab/B/logs/codeboarding_install.log`). Do not bundle these without review. |
| GitDiagram | MIT (**VERIFIED-IN-CODE**) | Code reusable with attribution. Name and logo are not covered. |
| Git of Theseus | Apache-2.0 (**VERIFIED-IN-CODE**) | Use, modify, sell. Keep LICENSE, state changes to modified files, keep any NOTICE (none present). Includes a patent grant. |
| lemonberrylabs/codegraph | **No LICENSE file**; MIT stated only in README and npm metadata (**LAB-DESK**, confirmed by my `gh api` call: license null) | Without a license file in the repo, reuse rights rest on the README and package metadata. Weak footing; do not depend on it without the author adding a LICENSE. |
| GitNexus | PolyForm Noncommercial 1.0.0 (**VERIFIED-IN-CODE**) | No commercial use, no derivative work for commercial use. Commercial licence offered by the vendor. Benchmark only. Keep any comparison at the level of observable behavior; no GitNexus code or design copied into Traces. See the pending decision below. |
| Code Maat | GPL-3.0 (**VERIFIED-IN-CODE**: `README.md:30`, `project.clj:3-9`) | See 6.2. |
| xnuinside/codegraph, both depvis | MIT (**VERIFIED-IN-CODE**) | Reusable, little worth reusing. |
| Lab's C scripts (`lab/C/scripts/`, 650 lines) | Lab's own code, written for this project; Lab states nothing from Code Maat was opened or copied (`lab/desk/code-maat-techniques.md`) | Usable as a starting point for Traces. Shailesh should confirm ownership terms for seat-written code before it enters a commercial repo. |

**Open decision for Shailesh: Lab's GitNexus run.** Traces Lab installed and ran `gitnexus@1.6.12` (`analyze`, `query`, `context`, `trace`, `impact`, `cypher`) on the test repo as a benchmark, sandboxed and `--index-only` (`lab/B/results.md`). The PolyForm Noncommercial licence allows personal research "without any anticipated commercial application" (`LICENSE:35-37`). This evaluation feeds a product Shailesh may commercialize, so whether the run falls inside the licence is unclear. Status: **pending Shailesh's decision**. Options: (a) accept it as benchmark use and keep the results as they are; (b) treat the run as out of scope, remove GitNexus run artifacts from `lab/`, and keep only documentation-level comparison; (c) ask the vendor (akonlabs.com, `README.md:1178-1191`) for written permission or an evaluation licence. Until decided, nothing derived from GitNexus behavior should become a Traces design requirement beyond "benchmark target". **INFERRED** (not legal advice) *Partly closed by addendum: record kept, outputs quarantined from implementation decisions, no re-run without permission or a license. Licensing clarification stays open.*

### 6.2 Code Maat GPL-3.0 obligations, spelled out

If any Code Maat code, or a work based on it, were included in software that is conveyed (distributed) to others, GPL-3.0 would require:
1. Licensing the whole combined work under GPL-3.0, so a proprietary Traces build could not include it.
2. Providing complete corresponding source to every recipient, including build scripts.
3. Keeping copyright notices and the licence text intact, and marking modifications with dates.
4. Not adding restrictions (no extra licence terms, no DRM that blocks the recipient's GPL rights), and passing on the patent licence the GPL grants.
5. For user products, providing installation information in some cases (GPL-3.0 section 6).

What does not trigger these: reading the code, running the unmodified jar as a separate program (as I did in T8), and reimplementing the analysis ideas from published descriptions without copying expression. GPL-3.0 (unlike AGPL) is not triggered by running it on a server for users who never receive a copy, but shipping it inside a desktop or self-hosted Traces build would be conveying.

Rule for Traces: no Code Maat code, translated code, or line-by-line ports in any Traces repo. Implement coupling, churn, and ownership from the formulas in section 5.2. **INFERRED**

### 6.3 Security and privacy

- **What leaves the machine:**
  - CodeGraph: nothing except telemetry (default on, opt-out) and a daily version check (`TELEMETRY.md:11-38`). **VERIFIED-IN-CODE**
  - CodeBoarding: code context goes to the configured LLM provider; telemetry goes to PostHog US by default and includes repo owner (`TELEMETRY.md:5-11`, `:149`). **DOCUMENTED-CLAIM**
  - GitDiagram (hosted pattern): repo tree, README, and up to 12 file excerpts go to OpenAI or OpenRouter; artifacts persist in R2. **VERIFIED-IN-CODE** + **DOCUMENTED-CLAIM**
  - GitNexus: web chat sends to the user's chosen provider. **VERIFIED-IN-CODE**
- **Traces policy proposal:** deterministic extraction runs only in Traces infrastructure; the LLM receives only the snippets needed for one answer, each tagged with file and line; a per-repo "sent to provider" log is visible to the user; private repos need an explicit opt-in before any LLM call; telemetry of all embedded tools forced off. **INFERRED**
- **Untrusted repo contents:** never run target repo install scripts or builds. CodeBoarding's opt-in install uses `--ignore-scripts` but still honors the repo's `.npmrc` and `.pnpmfile.cjs` (`workspace_dependencies.py:3`), which can point at hostile registries. Treat repo text as untrusted input to the LLM too: a README or code comment can contain prompt-injection text. Run indexers in a sandbox with no credentials and no network beyond git fetch. **VERIFIED-IN-CODE** + **INFERRED**
- **CDN scripts in generated HTML:** CodeBoarding (unpkg), xnuinside (d3js.org), depvis (d3js.org) load viewer libraries from CDNs at view time. A Traces viewer should self-host pinned assets. **VERIFIED-IN-CODE**
- **Resource exhaustion:** 4.1 GB RSS for a 4.5M-line repo (T5). A hostile or huge repo needs file count, byte, and time caps. **TESTED** + **INFERRED**
- **Tools that write into the repo or editor config:** GitNexus `analyze` by default writes `AGENTS.md`, `CLAUDE.md`, skills and Claude Code hooks; Lab avoided it with `--index-only` and a sandboxed `HOME` (`lab/desk/tool-requirements.md`). CodeGraph and CodeBoarding write `.codegraph/` and `.codeboarding/` into the target. Traces must run indexers on throwaway copies or with output directories outside the repo, and must never install agent hooks on a user's machine. **LAB-DESK** + **TESTED** + **INFERRED**
- **GitHub API use for history:** Lab used the box's existing `GH_TOKEN` for GET calls only (25 + 7 PRs, about 25 core requests). A Traces deployment needs its own GitHub App with read-only scopes per repo, cached responses, and rate-limit handling; a user's token must never be stored in plain text. **LAB-TESTED** + **INFERRED**
- **Wrong-but-cited claims are a trust risk, not only a quality issue.** A consultant who repeats GitDiagram's "items use CRUD" to a client is misinformed by a claim that looked sourced. The L3 check in 4.3.1 is a safety control. **INFERRED** *Closed by addendum (conditions B and C): provenance, extractor, validation status and source location on every relationship; L3 is the minimum.*

### 6.4 AI provider independence and data portability

- CodeGraph needs no LLM, so the extraction layer is provider-neutral by construction. **VERIFIED-IN-CODE**
- CodeBoarding reaches any OpenAI-compatible endpoint through `OPENAI_BASE_URL` (`llm_config.py:139-144`). xAI exposes an OpenAI-compatible API, so a future Grok provider fits the same seam. **VERIFIED-IN-CODE** + **INFERRED** for Grok compatibility.
- Recommendation: Traces owns a thin provider interface (chat, structured output, embeddings optional) with adapters per vendor; prompts and evidence formats are Traces-owned; no vendor-specific features in the core path. **INFERRED**
- Portability: store the Traces evidence graph in an open format (SQLite or Postgres tables plus JSON export, with optional GraphML or JSON Graph export). CodeGraph's SQLite and CodeBoarding's `analysis.json` are both easy to convert. Avoid formats tied to a single licensed engine (LadybugDB inside GitNexus is fine in itself, but the GitNexus licence is not). **TESTED** (formats read) + **INFERRED**

---

## 7. Open questions for ChatGPT's review

1. **Grade CodeGraph against Lab's ground truth.** The recommended engine was tested by me (counts, spot-checks, DI follow-up) but not graded by Lab on the six questions. Should Lab run `colbymchenry/codegraph` through `lab/B/ground-truth.md` before Task 002 commits to it? *Converted to condition A by the addendum; it is step 1 of `TASK_002_PLAN.md`.*
2. **codeGRAPH identity.** The two seats tested three different repos: `colbymchenry/codegraph` (my pick, recommended), `xnuinside/codegraph` (mine), `lemonberrylabs/codegraph` (Lab's). `FalkorDB/code-graph`, `CodeGraphContext/CodeGraphContext` and `bluekap/CodeGraph` were not run. Which did the brief mean? If it was FalkorDB or CodeGraphContext, it needs its own pass (FalkorDB needs Docker or a cloud signup). *Closed by addendum: the conversational one is UX reference only; CodeGraph (colbymchenry) stays the engine.*
3. **depvis identity.** Neither depvis found is credible as a foundation. Was a different project meant? *Closed by addendum: depvis means `mfinean/depvis`; no more investigation.*
4. **Dependency on a fast-moving MIT engine.** CodeGraph has 412 open PRs and an announced hosted platform. Is pinning plus an adapter enough, or should Traces plan to own a tree-sitter extractor within a year? *Closed by addendum: pin the version, wrap in a Traces-owned adapter with contract tests, no replacement extractor.*
5. **Component layer.** Adopt CodeBoarding's static-grounded LLM component approach (and pay the LSP weight), or build deterministic grouping first and add LLM naming later? *Closed by addendum: deterministic grouping first, AI naming and explanations later.*
6. **GitNexus benchmark use (decision for Shailesh, pending).** Lab ran GitNexus 1.6.12. Accept as benchmark use, remove the run artifacts and stay at docs-level comparison, or ask the vendor for permission? See 6.1. *Partly closed by addendum: keep the factual record, quarantine outputs, no re-run without permission or a license. Licensing clarification itself stays open.*
7. **Framework rules scope.** Lab and I agree DI and OpenAPI-client links are solvable with deterministic rules for FastAPI. Which frameworks come next (Django, Express, Spring, Next.js), and is the per-framework rule cost acceptable for v1? *Closed by addendum: FastAPI dependencies, routing, and generated-client relationships first.*
8. **Evidence level for display.** Is L3 (cited line contains the relationship token) the right bar for showing a relationship as fact, with L4 (independent extractor edge) required only for impact answers? Or L4 everywhere? *Closed by addendum (condition C): L3 is the minimum, not sufficient; four evidence classes; "verified" needs independent validation; unsupported claims stay visible.*
9. **Semantic rename confirmation.** Should component aliases (for example `crud/` to `crud.py` in #622) be auto-applied above a similarity threshold, or always reviewer-confirmed? *Closed by addendum: suggest automatically, confirm when identity is ambiguous.*
10. **Discussions and rationale.** GitHub Discussions need GraphQL and add API cost. In v1 or later? Rationale exists for only 7 of 25 key PRs on this repo.
11. **Hosting model.** Server-side indexing (needed for 4 GB jobs) vs local or desktop indexing (better privacy). Which comes first for consultants handling client repos? *Closed by addendum: server-side sandboxed indexing, local-first stays possible.*
12. **History presentation.** How should coupling and survival be shown to non-developers without implying causation? Proposed wording: "changed together in N of M commits". Lab's 0.14 backend-to-client co-change shows a low number can still hide a tight boundary.
13. **Private repos and LLM providers.** Is a per-repo opt-in plus a "sent to provider" log enough, or does Traces need a no-LLM mode as a first-class product tier? *Partly closed by addendum: no-LLM mode must work on its own. The opt-in and disclosure design stays open.*
14. **Grok.** Confirm the target is an OpenAI-compatible endpoint, so a generic provider adapter covers it.
15. **Seat-written code.** Can Lab's 650-line C prototype be ported into the Traces repo as-is, or rewritten?

---

## 8. Sources, code paths, tested versions

### 8.1 Upstream sources and SHAs inspected

| Repo | URL | SHA | Local path |
|---|---|---|---|
| Traces | https://github.com/ShaileshRawat1403/traces | 63103ac4adcb62a1ff31d9a1ca9955e3d855c850 | `_src/traces` |
| Test repo | https://github.com/fastapi/full-stack-fastapi-template | b1125d8839482cb7bbae603ddc6d0081bf87532e | `_src/full-stack-fastapi-template` (full history) |
| CodeBoarding | https://github.com/CodeBoarding/CodeBoarding | 3a5098c31c1649fc4a16257e46ce6830c2cfac8c | `_src/CodeBoarding` |
| GitDiagram | https://github.com/ahmedkhaleel2004/gitdiagram | 7a33d6ece0ec964666ed51b89895db82994b78e5 | `_src/gitdiagram` |
| CodeGraph | https://github.com/colbymchenry/codegraph | 505c355be39213db3347cc14f628196365d9a2ae | `_src/colbymchenry_codegraph` |
| codegraph (alt) | https://github.com/xnuinside/codegraph | effefc709e73e1eedbbfcb850146ed603ce257ec | `_src/xnuinside_codegraph` |
| depvis | https://github.com/mfinean/depvis | dcdff8dfa2431cc753557d987459ed3b4dcf97c9 | `_src/mfinean_depvis` |
| depvis (alt) | https://github.com/nealwp/depvis | 6b846c9ce537a0e1e24d7f37b6068f5a5162cc5c | `_src/nealwp_depvis` |
| GitNexus | https://github.com/abhigyanpatwari/GitNexus | 7090ac80f72590be7d7edd7e8cf8152de1f3d31f | `_src/abhigyanpatwari_GitNexus` |
| Git of Theseus | https://github.com/erikbern/git-of-theseus | 961bda027ffa9fcd8bbe99d5b8809cc0eaa86464 | `_src/git-of-theseus` (shallow), `_src/git-of-theseus-fullhist` (full) |
| Code Maat | https://github.com/adamtornhill/code-maat | 50537abb8dffa1b1ba4e91a605ee5c558c01b224 | `_src/code-maat` |
| lemonberrylabs/codegraph (Lab) | https://github.com/lemonberrylabs/codegraph | npm `@lemonberrylabs/codegraph@0.1.0` (CLI reports 1.0.0) | Lab's `lab/tools/` |
| GitNexus (Lab run) | npm `gitnexus` | 1.6.12 | Lab's `lab/tools/gitnexus/` |

All upstream clones are `--depth 1` except the test repo and `git-of-theseus-fullhist`. Maintenance data came from the GitHub API, so shallow clones did not limit it.

### 8.2 Tested package versions

CodeGraph npm `@colbymchenry/codegraph` 1.6.2; CodeBoarding 0.15.1 (source); Git of Theseus 0.3.4 (source) with GitPython 3.2.1 and matplotlib 3.11.2; xnuinside codegraph 1.2.0 (source); depvis 0.1.0 (source build); Code Maat 1.0.4 standalone jar with Temurin JRE 17.0.20.1; GitDiagram at 7a33d6e with bun 1.4.3. LSPs used by CodeBoarding: pyright 1.1.400, typescript-language-server 4.3.4, typescript 5.7.3.

### 8.3 Key code paths cited (quick index)

- CodeBoarding: `agents/agent_responses.py:26-46,163-190`; `diagram_analysis/scope_assembly.py:270-293`; `diagram_analysis/reference_resolver.py:307-315`; `diagram_analysis/analysis_json.py:39,247-252,317`; `agents/llm_config.py:136-310`; `static_analyzer/engine/lsp_client.py:92,186`; `static_analyzer/workspace_dependencies.py:3,18-38`; `output_generators/html_template.py:373-378`; `TELEMETRY.md:5,17-25,149`.
- GitDiagram: `src/server/generate/github.ts:367,495`; `src/server/generate/repository-context.ts:4-13`; `src/server/generate/edge-evidence.ts:17-26`; `src/server/generate/source-references.ts:1-8`; `src/features/diagram/graph.ts:55-91`; `src/features/diagram/mermaid-security.ts:2`; `src/server/generate/openai.ts:27-53`; `docs/architecture.md:5-14,37-42`; `package.json:143-146`.
- CodeGraph: `src/db/schema.sql:20-56,88-100`; `src/types.ts:57-71,227`; `src/bin/codegraph.ts:790-2557`; `src/bin/viewer-gate.ts:1-11`; `src/ui-server/api/index.ts:176-235`; `src/ui-server/api/effects.ts:189-192`; `src/telemetry/index.ts:30`; `TELEMETRY.md:11-28`; `package.json:44-65`; `ui/package.json:48`.
- GitNexus: `LICENSE:1-3,31-37,69`; `ARCHITECTURE.md:5-17`; `gitnexus/package.json:71-113`; `gitnexus-web/src/core/llm/types.ts:13-18`; `README.md:1178-1191`.
- Git of Theseus: `git_of_theseus/analyze.py:88-107,238-321,532-543`; `setup.py:11-25`.
- Code Maat: `README.md:30,79-83`; `project.clj:3-9`; `src/code_maat/app/app.clj:56-73`; `src/code_maat/analysis/logical_coupling.clj:24-46`; `src/code_maat/analysis/coupling_algos.clj:47-87`; `src/code_maat/cmd_line.clj:23-36`.
- xnuinside: `codegraph/parser.py:3,99`; `codegraph/core.py:363-375`.
- depvis (mfinean): `Cargo.toml:21`; `src/analyzers/python.rs:5`; `src/analyzers/javascript.rs:31-60`; `src/graph.rs:46-57`; `web/index.html:8`.
- Test repo: `backend/pyproject.toml:5`; `backend/app/api/deps.py:36`; `backend/app/main.py:35`; `backend/app/core/config.py:22`; `backend/app/crud.py:10`; `backend/app/api/routes/users.py:54-68`.

### 8.4 Artifacts on the box

- Logs: `/workspace/traces-research/_tests/logs/`
- Outputs: `/workspace/traces-research/_tests/out/` (`got/`, `xnu/`, `depvis/`, `codegraph-api/`, `cb-render/`, `cb-static-cache/`, `codemaat/`)
- Working copies that tools wrote into: `/workspace/traces-research/_work/`
- Lab outputs merged here: `/workspace/traces-research/LAB_B_RESULTS.md`, `LAB_C_RESULTS.md`, `lab/README.md`, `lab/B/results.md`, `lab/B/ground-truth.md`, `lab/B/logs/`, `lab/C/verdict.md`, `lab/C/evolution.md`, `lab/C/out/`, `lab/C/logs/`, `lab/desk/`. I read them and did not modify them.
- My follow-up check after the merge: `_tests/logs/codegraph-colby-di.log` (T10).
- Nothing was pushed, published, or sent anywhere. No secrets were written.

---

## Addendum: Task 001 review decisions (2026-10-21)

Source: ChatGPT review of Task 001, verdict APPROVED WITH CONDITIONS, relayed by Shailesh via Architect1. Recorded here as given. Sections above are not rewritten; items these decisions close carry a short "Closed by addendum" note in sections 6 and 7.

### Conditions

**A.** CodeGraph stays provisional until graded against Lab's six-question ground truth.

**B.** Every relationship imported into Traces must carry normalized provenance, extractor identity, validation status and source location. 4,351 of 4,642 CodeGraph edges (about 94%) have unset provenance, so they cannot be treated as verified.

- Check against my own run: **matches.** Section 3.1 (T5 fastapi run) records "4,642 edges ... Provenance: 4,351 unset (default extraction), 291 `heuristic`". Re-read on 2026-10-21 with a read-only SQLite open of the existing index (`_work/fastapi-codegraph/.codegraph/codegraph.db`, no tool run): `provenance NULL` 4,351, `heuristic` 291, total 4,642. 4,351 / 4,642 = 93.7%. **TESTED** (re-read of an existing artifact).
- Related fact from the same read: 1,981 edges have no line number (1,893 `contains`, 88 `references`). An edge with no line cannot pass an L3 check and must be labeled accordingly. **TESTED**

**C.** An L3 line check is the minimum, not sufficient alone. Keep four classes separate: source-backed declarations, statically derived relationships, unverified inferences, runtime-observed behavior. A claim labeled verified needs independent parser or framework-rule validation where applicable. Unsupported claims stay visible to reviewers.

### Decisions closed

| Decision | Recorded as | Note from Traces |
|---|---|---|
| codeGRAPH (the conversational one) | UX reference only, not the engine. | In our matrix the only codeGRAPH candidate with a chat feature is **`FalkorDB/code-graph`** (GraphRAG chat over a FalkorDB graph, `/api/chat` with Gemini by default, per `lab/desk/tool-requirements.md:10` and matrix row at section 2). Lab's own B table also labels it "codeGRAPH (FalkorDB/code-graph)" (`LAB_B_RESULTS.md:18`). Neither seat cloned or ran it (Lab: BLOCKED, needs a FalkorDB server), so this identification is **INFERRED** from README-level facts, medium to high confidence. It cannot mean `colbymchenry/codegraph` (no chat, and the decision below keeps it as the engine), `lemonberrylabs/codegraph` (CLI and MCP, no chat), or `xnuinside/codegraph` (static D3 viz). If ChatGPT meant another repo, that repo is not in our matrix. |
| depvis | `mfinean/depvis`. No more investigation. | Matches the matrix choice. `nealwp/depvis` stays rejected and is not looked at again. |
| GitNexus | Keep a factual record of the run, quarantine its outputs from implementation decisions until licensing is clarified, do not run again without permission or a license. | The record stays in sections 3 and 6.1 as written. GitNexus results must not feed Task 002 fixtures, ground truth, or design choices. |
| CodeGraph | Pin the version, wrap in a Traces-owned adapter with contract tests. No replacement extractor. | Tested version is `@colbymchenry/codegraph` 1.6.2, index schema version 11. Adapter and contract tests are specified in `TASK_002_PLAN.md`. |
| Component grouping | Deterministic first, AI naming and explanations later. | |
| Framework scope | FastAPI dependencies, routing, and generated-client relationships first. | |
| Semantic renames | Suggest automatically, confirm when identity is ambiguous. | |
| Hosting | Server-side sandboxed indexing, local-first stays possible, no-LLM mode must work on its own. | |

### What stays open

Open questions 10 (Discussions), 12 (history presentation), 14 (Grok endpoint), 15 (seat-written code), the provider opt-in part of 13, and the licensing clarification part of 6 are not closed by this review.

### Next

Task 002 plan: `/workspace/traces-research/TASK_002_PLAN.md`. Task 002 does not start until Shailesh approves.
