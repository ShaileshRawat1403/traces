---
title: Traces v1 walkthrough
status: review
owner: integration
version: 1
tags: [acceptance, screenshots]
---

# Walkthrough

These screens are the running app, talking to the local API and the indexed store. They are not mocks and not design comps.

Start at the home page. Paste a public GitHub URL. Traces indexes that commit, then the snapshot opens. The two repositories in these shots were indexed that way:

| Repository | URL | Commit |
| --- | --- | --- |
| fastapi/full-stack-fastapi-template | https://github.com/fastapi/full-stack-fastapi-template | `b1125d8839482cb7bbae603ddc6d0081bf87532e` |
| pallets/itsdangerous | https://github.com/pallets/itsdangerous | `672971d66a2ef9f85151e53283113f33d642dabd` |

The FastAPI template is the wide system. itsdangerous is the small one used to open a component, a trace, the evidence drawer, history, and ask.

Desktop shots are 1280×860. Phone shots are 390×844.

## What you see

1. **Home.** The URL field, then the repositories already indexed. [Desktop](home-desktop.png) · [Phone](home-phone.png)
2. **Overview.** Components by layer come first. Each chip opens that component in the graph. The language bar and the three readings (Business, Architecture, Implementation) sit under the map. Evidence counts are at the bottom, including the rejected claims that stay out of the graph. [Desktop](overview-desktop.png) · [Phone](overview-phone.png)
3. **Architecture graph.** The opening map is the components, colored by layer. The relationship page behind it is larger and, for the template, truncated. [Desktop](graph-desktop.png) · [Phone](graph-phone.png)
4. **Expanded relationships.** `src/itsdangerous` at depth 1. The map stays zoomed in so names stay readable (`Serializer`, `loads`, `dumps`, and the methods around them). Drag to pan. The side panel is a symbol you moved to, with its relationships and an evidence button, not a component that claims zero edges. [Desktop](graph-expanded-desktop.png) · [Phone](graph-expanded-phone.png)
5. **Trace.** Outgoing verified steps from `Serializer`, drawn as a path. Each step can open evidence. [Desktop](trace-desktop.png) · [Phone](trace-phone.png)
6. **Evidence.** The `contains` claim from `Serializer` to `__init__`, with the pinned source lines. [Desktop](evidence-desktop.png) · [Phone](evidence-phone.png)
7. **History.** The timeline leads. The criteria that produced the page are one click away, printed as stored. [Desktop](history-desktop.png) · [Phone](history-phone.png)
8. **Ask.** "What does Serializer depend on?" answered with no model and no key. Grounded sentences cite claims. The category breakdown stays closed until you open it. [Desktop](ask-desktop.png) · [Phone](ask-phone.png)

## What this is not

- Static analysis only. No runtime behavior has been observed.
- A call into a library that cannot be checked stays inferred. It is not promoted to verified.
- The default graph is capped. The template's relationship page says it is truncated. The opening picture is the component map, not every symbol.
- An expanded component with many symbols is zoomed to a readable neighborhood. List view has the rest. That is a view limit, not a smaller graph.
- History is Git evidence for the indexed commit. It does not invent an architecture for commits that were not indexed, and co-change is not a call graph.
- Component groups come from a stored path rule. They are not a runtime boundary.
- A trace between two unrelated symbols is a gap. The gap is shown. It is not filled in.
- Ask does not call a model. There is no paid API in this path.
- Rejected claims stay in the audit trail and out of the graph and the trace until you open Review.

## Run it

```bash
make toolchain
make start
```

API on port 8000, web on port 5173. The web dev server proxies `/api` to the API. To serve the store used for these shots, start the API with `TRACES_DATA_DIR` pointed at that store.
