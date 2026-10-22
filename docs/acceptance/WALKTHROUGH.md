---
title: Traces v1 walkthrough
status: review
owner: integration
version: 1
tags: [acceptance, screenshots]
---

# Walkthrough

These screens are the running app, talking to the local API and the indexed store. They are not mocks and not design comps. The previous screens of the same views are in [before/](before/).

Start at the home page. Paste a public GitHub URL. Traces indexes that commit, then the snapshot opens. The two repositories in these shots were indexed that way:

| Repository | URL | Commit |
| --- | --- | --- |
| fastapi/full-stack-fastapi-template | https://github.com/fastapi/full-stack-fastapi-template | `b1125d8839482cb7bbae603ddc6d0081bf87532e` |
| pallets/itsdangerous | https://github.com/pallets/itsdangerous | `672971d66a2ef9f85151e53283113f33d642dabd` |

The FastAPI template is the wide system. itsdangerous is the small one used to open a component, a trace, the evidence drawer, history, and ask.

Desktop shots are 1280×860. Phone shots are 390×844.

## What you see

1. **Home.** The URL field, then the repositories already indexed. [Desktop](home-desktop.png) · [Phone](home-phone.png)
2. **Overview.** Layers are bands, in a stored order. Each component is a block. The bar is how many claims were recorded for it, not a line to the next band. Grouping is a stored path rule. [Desktop](overview-desktop.png) · [Phone](overview-phone.png)
3. **Architecture graph.** Components sit in columns by layer, left to right. A line is a count of relationships on this page, drawn with the weakest status in that pair. It is not a new claim. The template page is truncated, so a missing line is not proof that nothing connects. Pan to the columns that start off-screen. [Desktop](graph-desktop.png) · [Phone](graph-phone.png)
4. **Expanded relationships.** `src/itsdangerous` at depth 1, laid out from the symbols that call each other. Names stay readable (`Serializer`, `loads`, `dumps`). Select a symbol to label its lines. List view has every relationship. [Desktop](graph-expanded-desktop.png) · [Phone](graph-expanded-phone.png)
5. **Trace.** On the FastAPI template this is a flow, not a stack of cards. A solid step is verified or observed. A dotted step is an inferred library call. A dashed step is a gap. The items page renders AddItem. The next step is a gap: no edge reaches `form.handleSubmit`. Two library steps stay inferred. The generated client matches `POST /api/v1/items/`, and `create_item` depends on `get_db`. The same symbols have a verified static persistence path (validate, stage, commit, reload). Nothing was executed, and no database was contacted. The rejected CRUD claim is not a step. Detail sits under "Recorded steps". [Desktop](trace-desktop.png) · [Phone](trace-phone.png)
6. **Evidence.** The `contains` claim from `Serializer` to `__init__`, with the pinned source lines. [Desktop](evidence-desktop.png) · [Phone](evidence-phone.png)
7. **History.** The timeline is a spine of commits, not a proof of architecture. Co-change is drawn as two paths that changed together. That is a Git pattern, not a call. Criteria stay one click away, printed as stored. [Desktop](history-desktop.png) · [Phone](history-phone.png)
8. **Ask.** "What does Serializer depend on?" with no model and no key. Grounded sentences point at the file and line of the cited record. Interpretation and unknown stay marked. The category list stays closed until you open it. [Desktop](ask-desktop.png) · [Phone](ask-phone.png)

## What this is not

- Static analysis only. No runtime behavior has been observed.
- A call into a library that cannot be checked stays inferred. It is not promoted to verified.
- The default graph is capped. The template's relationship page says it is truncated. The opening picture is components in layer columns, with counts from that page only.
- An expanded neighborhood stays zoomed so names stay readable. Pan, or use List, for the rest. That is a view limit, not a smaller graph.
- History is Git evidence for the indexed commit. It does not invent an architecture for commits that were not indexed, and co-change is not a call graph.
- Component groups come from a stored path rule. They are not a runtime boundary.
- A trace between two unrelated symbols is a gap. The gap is shown. It is not filled in.
- The create-item flow is only drawn when the snapshot has a persistence path and the library steps that reach it. A snapshot without that path says so. The path ends at the session dependency. No database was contacted.
- Ask does not call a model. There is no paid API in this path.
- Rejected claims stay in the audit trail and out of the graph and the trace until you open Review.

## Run it

```bash
make toolchain
make start
```

API on port 8000, web on port 5173. The web dev server proxies `/api` to the API. To serve the store used for these shots, start the API with `TRACES_DATA_DIR` pointed at that store.
