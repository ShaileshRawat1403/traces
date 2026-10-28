---
title: Traces v1 walkthrough
status: review
owner: integration
version: 1
tags: [acceptance, screenshots]
---

# Walkthrough

These screens are the running app, talking to the local API and the indexed store. They are not mocks and not design comps. The previous screens of the same views are in [before/](before/).

Start at the home page. Paste a public GitHub URL. That opens the repository. Index the commit, then open the ready snapshot. The two repositories in these shots were indexed that way:

| Repository | URL | Commit |
| --- | --- | --- |
| fastapi/full-stack-fastapi-template | https://github.com/fastapi/full-stack-fastapi-template | `b1125d8839482cb7bbae603ddc6d0081bf87532e` |
| pallets/itsdangerous | https://github.com/pallets/itsdangerous | `672971d66a2ef9f85151e53283113f33d642dabd` |

The FastAPI template is the wide system. itsdangerous is the small one used to open a component, a trace, the evidence drawer, history, and ask.

Desktop shots are 1280×860. Phone shots are 390×844.

## What you see

1. **Home.** The URL field, then the repositories already indexed. [Desktop](home-desktop.png) · [Phone](home-phone.png)
2. **Overview.** The first thing on the page is the architecture, with the strongest recorded links beside it. Find, in the snapshot header, searches stored components, routes, files, and handlers. A match opens on the map, in source, or as a question the explainer can route. Components sit in columns by stored layer. A column title names the layer. A line between neighboring columns is a count of relationships on this page, drawn with the weakest status in that pair. Longer links are not drawn across other columns until you select a component, or choose All recorded lines. They are not new claims. Select a component to see what it connects to, then open it on the graph, follow a flow, or look at history. On a wide repository the first picture is the code layers (frontend, api, backend, library, data). All layers is one click away. On a phone the map opens one layer at a time, as a list you can tap. Grouping is a stored path rule. [Desktop](overview-desktop.png) · [Phone](overview-phone.png)
3. **Architecture graph.** The same columns, scaled so the components in this view stay inside the frame. Neighboring lines are drawn. Select one component to dim the rest and to draw the longer links that touch it. Enter expands it. On a phone the map opens one layer at a time, as a list. [Desktop](graph-desktop.png) · [Phone](graph-phone.png)
4. **Expanded relationships.** A component with more than a handful of symbols opens as its files, with the recorded lines between those files. Select a file to emphasize its lines. Those lines are counts, not new claims. Enter opens the symbols in that file. List view still has every relationship. [Desktop](graph-expanded-desktop.png) · [Phone](graph-expanded-phone.png)
5. **Trace.** On a wide screen the FastAPI template path is one horizontal flow, and the selected step opens underneath it. On a phone the same steps stack. A solid step is verified or observed. A dotted step is an inferred library call. A dashed step is a gap. The selected step is the panel: the items page renders AddItem, a gap stays where no edge reaches `form.handleSubmit`, two library steps stay inferred, the generated client matches `POST /api/v1/items/`, and `create_item` depends on `get_db`. The same symbols have a verified static persistence path (validate, stage, commit, reload). Nothing was executed, and no database was contacted. The rejected CRUD claim is not a step. [Desktop](trace-desktop.png) · [Phone](trace-phone.png)
6. **Evidence.** The `contains` claim from `Serializer` to `__init__`, with the pinned source lines. [Desktop](evidence-desktop.png) · [Phone](evidence-phone.png)
7. **History.** The timeline is a spine of commits, not a stack of cards and not a proof of architecture. Co-change is drawn as two paths that changed together. That is a Git pattern, not a call. Criteria stay one click away, printed as stored. [Desktop](history-desktop.png) · [Phone](history-phone.png)
8. **Ask.** The page lists questions this snapshot can answer, including one stored route when the inventory has one. You can still type your own. "What does Serializer depend on?" needs no model and no key. The answer comes first. Each grounded sentence points at the file, and those files open on the graph. Interpretation and unknown stay marked. The category list stays closed until you open it. [Desktop](ask-desktop.png) · [Phone](ask-phone.png)

## What this is not

- Static analysis only. No runtime behavior has been observed.
- A call into a library that cannot be checked stays inferred. It is not promoted to verified.
- The default graph is capped. The template's relationship page says it is truncated. The opening picture is every stored component, in layer columns, with counts from that page only. A phone opens one layer so the names stay readable.
- An expanded component with many symbols opens as files. Select a file to see the lines recorded from it, then open the file to see the symbols. List still has every relationship. That is a view limit, not a smaller graph.
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
