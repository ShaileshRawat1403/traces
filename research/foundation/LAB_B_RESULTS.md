# LAB B results: code-intelligence tools on one real repo

Detail: `lab/B/results.md` (per-tool commands, outputs, grades), `lab/B/ground-truth.md` (answer key), raw logs in `lab/B/logs/`.

## Test repo and environment

- `fastapi/full-stack-fastapi-template` @ `b1125d8839482cb7bbae603ddc6d0081bf87532e` (2026-10-15T16:04:31Z, i.e. 2026-10-15 21:34 IST). Same SHA as the lead's clone in `_src/full-stack-fastapi-template`. MIT. 1,537 commits, 252 files, Python 3.14 backend (FastAPI, SQLModel, Alembic), React/TS frontend with a generated OpenAPI client.
- Clone: `git clone https://github.com/fastapi/full-stack-fastapi-template lab/repos/fsft && git -C lab/repos/fsft checkout b1125d8839482cb7bbae603ddc6d0081bf87532e`. Tools that write files ran on throwaway copies `lab/repos/fsft-b` and `lab/repos/fsft-gn` (local clones of `fsft`, same SHA).
- Box: Debian 13, git 2.47.3, Python 3.13.5, uv 0.13.1, Node 20.19.2, npm 11.21.0, cargo 1.85.1. No Docker, no Java. No LLM keys in the environment.

## Tested vs only read

| tool | version | license | status | what I did |
|---|---|---|---|---|
| CodeBoarding | git `3a5098c31c1649fc4a16257e46ce6830c2cfac8c` | MIT | **Tested (non-LLM parts)**; LLM mode **BLOCKED** | ran `full` (fails: "LLM provider not configured"), ran `python -m health.main --local`, dumped static call graph via `lab/B/scripts/cb_dump_static.py` |
| GitDiagram | git `7a33d6ece0ec964666ed51b89895db82994b78e5` | MIT | Local run **BLOCKED** (README.md:68: "Requires Bun, Cloudflare R2, Upstash Redis, and an OpenAI or OpenRouter API key."). **Read only**: public cached diagram page (dated 2026-09-08) | fetched page with `curl`, graded claims, checked 34 cited paths |
| codeGRAPH (lemonberrylabs/codegraph) | npm `@lemonberrylabs/codegraph@0.1.0` | MIT per npm/README, no LICENSE file | **Tested** | backend and frontend call graphs |
| codeGRAPH (FalkorDB/code-graph) | not installed | MIT | **BLOCKED**: needs FalkorDB server, no Docker; chat needs Gemini key | README only |
| depvis | crates.io `0.1.0` | MIT | **Tested** | text, cycles, JSON, local-only |
| Git of Theseus | PyPI `0.3.4` (`961bda0`) | Apache-2.0 | **Tested** | analyze + 3 plots |
| GitNexus (benchmark) | npm `gitnexus@1.6.12` | PolyForm Noncommercial 1.0.0 | **Tested**, sandboxed HOME, `--index-only` | analyze, query, context, trace, impact, cypher |

Exact commands for each are in `lab/B/results.md` under each tool heading.

## Grades (Q1 purpose, Q2 components, Q3 connections, Q4 create-item trace, Q5 change over time, Q6 evidence)

G grounded and correct, P partial, W contains a wrong relationship, U ungrounded, N not answered.

| tool | Q1 | Q2 | Q3 | Q4 | Q5 | Q6 |
|---|---|---|---|---|---|---|
| CodeBoarding static + health | N | P | P | P | N | P |
| GitDiagram cached page | G | P | W | W | N | U/P |
| lemonberrylabs/codegraph | N | N | W | P | N | G |
| depvis | N | P | W | N | N | P |
| Git of Theseus | N | N | N | N | P | U |
| GitNexus | N | P | P | P | N | P |

## Top grounding failures (all checked against git at the pinned SHA)

1. GitDiagram claims items routes use the CRUD layer. `items.py` has 0 `crud.` references and writes with `session.add/commit` (`items.py:68-71`). All 34 cited paths exist, so a path-exists check would have passed it.
2. GitDiagram invents a frontend container. `compose.yml` has no frontend service; the frontend is built in `backend/Dockerfile:1-16` and served by `backend/app/main.py:36`.
3. FastAPI dependency injection is invisible: `get_current_user` (`deps.py:49`) has 0 incoming edges in CodeBoarding, codegraph and GitNexus; `gitnexus impact get_current_user` returns 0.
4. No tool links the frontend SDK call (`sdk.gen.ts:307`) to the backend route (`items.py:62`), though the operation-id join key is in `main.py:14-15`.
5. GitNexus `trace` and `cypher` lines are 0-based (492 of 500 off by one), `context` and `query` 1-based.
6. codegraph marks 4 used crud functions dead and all 230 frontend functions dead.
7. depvis silently drops `deps.py` (Python 3.14 syntax) and labels 121 local `@/` imports as external packages.
8. None of the tools answers "how did the architecture change" with commit evidence.

## What was read, not tested

GitDiagram public page; FalkorDB/code-graph and bluekap/CodeGraph READMEs; CodeBoarding README and `health/main.py` docstring (to find the non-LLM mode); GitNexus LICENSE and ARCHITECTURE.md. Requirements and licenses are in `lab/desk/tool-requirements.md`.
