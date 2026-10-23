"""Task 002 regression fixture: the expected chain (L1 to L9, transitive L7, H1, H2) and the injected negative
controls (N1, N2a, N2b). Ported from research/task002/fixtures/build_fixture.py (EXPECTED_CHAIN.md v2).
Every cited line is spot-checked against the git blob at the pinned SHA; the build aborts on any mismatch.

Test-repository specific by design: this is a regression fixture for fastapi/full-stack-fastapi-template@b1125d8,
not product logic. The fixture is built at test time from the pinned checkout, so no target source text is committed
beyond the short single-line location anchors below (cited by path and line at b1125d8).

N1 comes from a GitDiagram page cached during Task 001 (third-party, not committed). Its sha256, the quoted line and
its offsets are recorded below. If TRACES_GITDIAGRAM_PAGE points at the cached page, the quote and hash are re-checked;
otherwise the recorded values are used and the spot check says so.
Usage: python -m traces.fixtures.task002.chain --src <checkout> --fixture-out <chain.json> [--injected-out <injected.jsonl> --run-id <id>]"""
import argparse, json, os
from traces.core.common import Blobs, canon, claim_id, anchor_of, line_count, sha256_hex, now_ist, SCHEMA_VERSION

REPO = "fastapi/full-stack-fastapi-template"
REPO_URL = "https://github.com/fastapi/full-stack-fastapi-template"
REPO_SHA = "b1125d8839482cb7bbae603ddc6d0081bf87532e"
GD_SHA256 = "79f0056822155dd8b5dc2cb9560b83ce0ceb8d2ae7d600caffdc81847bb1e0cb"
GD_OFFSETS = (38739, 57457)
IT, AT, IDX, SDK, TYP, CFG = "frontend/src/routes/_layout/items.tsx", "frontend/src/components/Items/AddItem.tsx", "frontend/src/client/index.ts", "frontend/src/client/sdk.gen.ts", "frontend/src/client/types.gen.ts", "frontend/openapi-ts.config.ts"
ITEMS, DEPS, MODELS, MAIN, APIMAIN, CONFIG, PRIV, CRUD = "backend/app/api/routes/items.py", "backend/app/api/deps.py", "backend/app/models.py", "backend/app/main.py", "backend/app/api/main.py", "backend/app/core/config.py", "backend/app/api/routes/private.py", "backend/app/crud.py"
FIXTURE_FILE = "task002/fixtures/chain_create_item.json"  # provenance label from Task 002, kept so records stay identical


def L(file, s, e, role, kind, token, rule=None):
    return {"file": file, "start_line": s, "end_line": e, "role": role, "range_kind": kind, "range_rule": rule or {"site": "expression", "declaration": "header_to_body_end", "file": "file", "body": "body_only"}[kind], "token": token}


def ep(file, qn, s, e):
    return {"symbol": f"{file}::{qn}", "file": file, "start_line": s, "end_line": e}


OP = ep(ITEMS, "operation POST /api/v1/items/ (items-create_item)", 61, 61)
CLAIMS = [
    {"id": "L1", "kind": "renders", "gran": "statement", "from": ep(IT, "Items", 57, 70), "to": ep(AT, "AddItem", 40, 141),
     "statement": "items.tsx::Items renders AddItem.tsx::AddItem (JSX element <AddItem /> at items.tsx:65).",
     "locs": [L(IT, 65, 65, "site", "site", "<AddItem />"), L(IT, 8, 8, "input", "site", 'import AddItem from "@/components/Items/AddItem"'), L(IT, 57, 70, "from_decl", "declaration", "function Items()"),
              L(AT, 40, 141, "to_decl", "declaration", "const AddItem = () => {", "binding_statement"), L(AT, 143, 143, "input", "declaration", "export default AddItem", "binding_statement")],
     "context": [L(IT, 20, 20, "input", "site", 'createFileRoute("/_layout/items")')]},
    {"id": "L2A", "kind": "binds_handler", "gran": "statement", "from": ep(AT, "AddItem", 40, 141), "to": ep(AT, "AddItem::onSubmit", 68, 70),
     "statement": "AddItem binds_handler onSubmit: identifier onSubmit is passed as the argument of form.handleSubmit(...) in the onSubmit attribute of <form> (AddItem.tsx:88).",
     "locs": [L(AT, 88, 88, "site", "site", "form.handleSubmit(onSubmit)"), L(AT, 68, 70, "to_decl", "declaration", "const onSubmit = (data: FormData) => {", "binding_statement")]},
    {"id": "L2B", "kind": "calls", "gran": "statement", "from": ep(AT, "AddItem::onSubmit", 68, 70), "to": ep(AT, "AddItem::mutation.mutate", 69, 69),
     "statement": "onSubmit calls mutation.mutate (AddItem.tsx:69), where mutation is the const bound at AddItem.tsx:55-66.",
     "locs": [L(AT, 69, 69, "site", "site", "mutation.mutate(data)"), L(AT, 55, 66, "input", "declaration", "const mutation = useMutation({", "binding_statement"), L(AT, 68, 70, "from_decl", "declaration", "const onSubmit", "binding_statement")]},
    {"id": "L3", "kind": "calls", "gran": "statement", "from": ep(AT, "AddItem::mutationFn", 56, 56), "to": ep(SDK, "ItemsService::createItem", 307, 318),
     "statement": "The mutationFn arrow inside AddItem calls ItemsService.createItem (AddItem.tsx:56).",
     "locs": [L(AT, 56, 56, "site", "site", "ItemsService.createItem({ body: data })"), L(AT, 8, 8, "input", "site", 'import { type ItemCreate, ItemsService } from "@/client"'),
              L(IDX, 3, 3, "input", "site", "ItemsService"), L(SDK, 287, 287, "input", "declaration", "export class ItemsService", "header_to_body_end"), L(SDK, 307, 318, "to_decl", "declaration", "public static createItem")]},
    {"id": "L4", "kind": "implements_operation", "gran": "symbol", "from": ep(SDK, "ItemsService::createItem", 307, 318), "to": OP,
     "statement": "ItemsService.createItem implements_operation POST /api/v1/items/, operation ID items-create_item.",
     "locs": [L(SDK, 307, 307, "site", "site", "createItem"), L(SDK, 287, 287, "input", "declaration", "class ItemsService"), L(SDK, 308, 308, "input", "site", ".post<"), L(SDK, 311, 311, "input", "site", "url: '/api/v1/items/'"),
              L(TYP, 809, 809, "input", "declaration", "export type itemsCreateItemData"), L(TYP, 813, 813, "input", "site", "url: '/api/v1/items/'"),
              L(CFG, 14, 14, "input", "site", 'strategy: "byTags"'), L(CFG, 16, 16, "input", "site", 'containerName: "{{name}}Service"'), L(CFG, 17, 17, "input", "site", 'methodName: (name: string): string => name.replace(/^[^-]*-/, "")'),
              L(MAIN, 14, 15, "input", "declaration", "custom_generate_unique_id"), L(MAIN, 24, 24, "input", "site", "generate_unique_id_function=custom_generate_unique_id")],
     "context": [L(SDK, 310, 310, "input", "site", "security: [{ scheme: 'bearer', type: 'http' }]"), L("frontend/src/main.tsx", 17, 20, "input", "site", "client.setConfig({")]},
    {"id": "L5", "kind": "routes_to", "gran": "handler", "from": OP, "to": ep(ITEMS, "create_item", 61, 72),
     "statement": "Operation POST /api/v1/items/ (items-create_item) routes_to backend/app/api/routes/items.py::create_item.",
     "locs": [L(ITEMS, 61, 61, "site", "site", '@router.post("/", response_model=ItemPublic)'), L(CONFIG, 22, 22, "input", "declaration", 'API_V1_STR: str = "/api/v1"', "binding_statement"),
              L(MAIN, 9, 9, "input", "site", "from app.core.config import settings"), L(MAIN, 35, 35, "input", "site", "app.include_router(api_router, prefix=settings.API_V1_STR)"),
              L(APIMAIN, 3, 3, "input", "site", "from app.api.routes import items"), L(APIMAIN, 6, 6, "input", "declaration", "api_router = APIRouter()", "binding_statement"), L(APIMAIN, 10, 10, "input", "site", "api_router.include_router(items.router)"),
              L(ITEMS, 10, 10, "input", "declaration", 'router = APIRouter(prefix="/items", tags=["items"])', "binding_statement"), L(ITEMS, 61, 72, "to_decl", "declaration", "def create_item(", "decorator_to_body_end"),
              L(ITEMS, 62, 72, "to_decl", "declaration", "def create_item(", "header_to_body_end")]},
    {"id": "L6", "kind": "depends_on", "gran": "handler", "from": ep(ITEMS, "create_item", 61, 72), "to": ep(DEPS, "get_db", 21, 23),
     "statement": "create_item depends_on deps.py::get_db via SessionDep (parameter session at items.py:63).",
     "locs": [L(ITEMS, 63, 63, "site", "site", "session: SessionDep"), L(ITEMS, 7, 7, "input", "site", "from app.api.deps import CurrentUser, SessionDep"), L(DEPS, 26, 26, "input", "declaration", "SessionDep = Annotated[Session, Depends(get_db)]", "binding_statement"),
              L(DEPS, 21, 23, "to_decl", "declaration", "def get_db()")]},
    {"id": "L7", "kind": "depends_on", "gran": "handler", "from": ep(ITEMS, "create_item", 61, 72), "to": ep(DEPS, "get_current_user", 30, 46),
     "statement": "create_item depends_on deps.py::get_current_user via CurrentUser (parameter current_user at items.py:63).",
     "locs": [L(ITEMS, 63, 63, "site", "site", "current_user: CurrentUser"), L(ITEMS, 7, 7, "input", "site", "from app.api.deps import CurrentUser, SessionDep"), L(DEPS, 49, 49, "input", "declaration", "CurrentUser = Annotated[User, Depends(get_current_user)]", "binding_statement"),
              L(DEPS, 30, 46, "to_decl", "declaration", "def get_current_user(session: SessionDep, token: TokenDep) -> User:")]},
    {"id": "L7T1", "kind": "depends_on", "gran": "symbol", "transitive": True, "from": ep(DEPS, "get_current_user", 30, 46), "to": ep(DEPS, "get_db", 21, 23),
     "statement": "Transitive (depth 2): get_current_user depends_on get_db via SessionDep (deps.py:30, :26).",
     "locs": [L(DEPS, 30, 30, "site", "site", "session: SessionDep"), L(DEPS, 26, 26, "input", "declaration", "SessionDep = Annotated[Session, Depends(get_db)]", "binding_statement"), L(DEPS, 21, 23, "to_decl", "declaration", "def get_db()")]},
    {"id": "L7T2", "kind": "depends_on", "gran": "symbol", "transitive": True, "from": ep(DEPS, "get_current_user", 30, 46), "to": ep(DEPS, "reusable_oauth2", 16, 18),
     "statement": "Transitive (depth 2): get_current_user depends_on reusable_oauth2 via TokenDep (deps.py:30, :27, :16-18).",
     "locs": [L(DEPS, 30, 30, "site", "site", "token: TokenDep"), L(DEPS, 27, 27, "input", "declaration", "TokenDep = Annotated[str, Depends(reusable_oauth2)]", "binding_statement"), L(DEPS, 16, 18, "to_decl", "declaration", "reusable_oauth2 = OAuth2PasswordBearer(", "binding_statement")]},
    {"id": "L8", "kind": "persistence_path", "gran": "path", "qualifier": "statically established persistence path", "from": ep(ITEMS, "create_item", 61, 72), "to": ep(DEPS, "get_db", 21, 23),
     "statement": "persistence_path(create_item): model_validation (items.py:68), session_stage (69), session_commit (70), session_reload (71) on receiver session bound to SessionDep.",
     "locs": [L(ITEMS, 68, 68, "site", "site", "Item.model_validate("), L(ITEMS, 69, 69, "site", "site", "session.add(item)"), L(ITEMS, 70, 70, "site", "site", "session.commit()"), L(ITEMS, 71, 71, "site", "site", "session.refresh(item)"),
              L(ITEMS, 63, 63, "input", "site", "session: SessionDep"), L(ITEMS, 7, 7, "input", "site", "SessionDep"), L(ITEMS, 8, 8, "input", "site", "Item"), L(DEPS, 26, 26, "input", "declaration", "SessionDep = Annotated[Session, Depends(get_db)]", "binding_statement"),
              L(DEPS, 9, 9, "input", "site", "from sqlmodel import Session"), L(DEPS, 21, 23, "input", "declaration", "def get_db()"), L(MODELS, 87, 87, "input", "declaration", "class Item(ItemBase, table=True):")]},
    {"id": "L9A", "kind": "uses_model", "gran": "handler", "from": ep(ITEMS, "create_item", 61, 72), "to": ep(MODELS, "Item", 87, 93),
     "statement": "create_item uses_model models.py::Item (Item.model_validate at items.py:68; class Item(ItemBase, table=True) at models.py:87).",
     "locs": [L(ITEMS, 68, 68, "site", "site", "Item.model_validate"), L(ITEMS, 8, 8, "input", "site", "from app.models import Item"), L(MODELS, 87, 93, "to_decl", "declaration", "class Item(ItemBase, table=True):")]},
    {"id": "L9B", "kind": "returns_model", "gran": "handler", "from": ep(ITEMS, "create_item", 61, 72), "to": ep(MODELS, "ItemPublic", 97, 100),
     "statement": "create_item returns_model models.py::ItemPublic (response_model=ItemPublic at items.py:61).",
     "locs": [L(ITEMS, 61, 61, "site", "site", "response_model=ItemPublic"), L(ITEMS, 8, 8, "input", "site", "ItemPublic"), L(MODELS, 97, 100, "to_decl", "declaration", "class ItemPublic(ItemBase):")]},
    {"id": "H1", "kind": "library_contract", "gran": "statement", "library": True, "from": ep(AT, "AddItem::form.handleSubmit", 88, 88), "to": ep(AT, "AddItem::onSubmit", 68, 70),
     "statement": "react-hook-form form.handleSubmit(onSubmit) calls onSubmit on submit (AddItem.tsx:88). Library behavior.",
     "locs": [L(AT, 88, 88, "site", "site", "form.handleSubmit(onSubmit)")]},
    {"id": "H2", "kind": "library_contract", "gran": "statement", "library": True, "from": ep(AT, "AddItem::mutation.mutate", 69, 69), "to": ep(AT, "AddItem::mutationFn", 56, 56),
     "statement": "TanStack Query mutation.mutate(data) calls the mutationFn given to useMutation (AddItem.tsx:69 to :56). Library behavior.",
     "locs": [L(AT, 69, 69, "site", "site", "mutation.mutate(data)"), L(AT, 56, 56, "input", "site", "mutationFn: (data: ItemCreate) => ItemsService.createItem")]},
]
EXPECT = {"L1": "verified", "L2A": "verified", "L2B": "verified", "L3": "verified", "L4": "verified", "L5": "verified", "L6": "verified", "L7": "verified", "L7T1": "verified (reported separately)", "L7T2": "verified (reported separately)",
          "L8": "verified, qualifier statically established persistence path", "L9A": "verified", "L9B": "verified", "H1": "inferred (library_contract, unvalidated)", "H2": "inferred (library_contract, unvalidated)",
          "N1": "rejected", "N2a": "rejected", "N2b": "rejected"}
N1_REASON = "items.py has no import of app.crud and no crud reference; create_item writes through the SessionDep-bound session at items.py:68-71 (statically established persistence path)"
N2_REASON = "private.py create_user takes only user_in and session: SessionDep; dependency closure is {get_db}; no CurrentUser or get_current_user binding; no dependencies= on decorator, router, includes or app"


def spot_check(blobs, locs, log):
    bad = 0
    for l in locs:
        lines = blobs.lines(l["file"])
        seg = "\n".join(lines[l["start_line"] - 1: l["end_line"]])
        ok = l["token"] in seg if l["token"] else True
        log.append(f"{'OK ' if ok else 'BAD'} {l['file']}:{l['start_line']}{'-' + str(l['end_line']) if l['end_line'] != l['start_line'] else ''} token {l['token']!r} | first line: {lines[l['start_line'] - 1].strip()[:90]!r}")
        bad += 0 if ok else 1
    return bad


def record(c, blobs, run_id, at, originator, prov, origin, injected, status_reason):
    locs = []
    for l in c["locs"]:
        d = {k: v for k, v in l.items() if k != "token"}
        d.update(line_base=1, col_base=0, blob_sha=blobs.blob_sha(l["file"]), source="originator", recovered_by=None)
        locs.append(d)
    raw = {"fixture_entry": {k: v for k, v in c.items()}}
    cid = claim_id(REPO_SHA, "relationship", c["kind"], c["from"], c["to"], c["gran"], originator, anchor_of(locs), None)  # Decision 002-B ruling 2
    r = {"schema_version": SCHEMA_VERSION, "claim_id": cid, "run_id": run_id, "repo": REPO, "repo_sha": REPO_SHA, "claim_kind": "relationship", "relationship_kind": c["kind"],
         "granularity": c["gran"], "from": c["from"], "to": c["to"], "statement": c["statement"], "class": "analyzer_inference", "originator": originator, "provenance_raw": raw,
         "provenance": prov, "origin": origin, "injected": injected, "evidence_scope": "static", "qualifier": c.get("qualifier"), "locations": locs, "checks": [],
         "status": "unvalidated", "label": "inferred", "status_reason": status_reason,
         "status_history": [{"from": None, "to": "unvalidated", "at": at, "run_id": run_id, "check_ids": [], "by": "traces-fixture-builder 1.0.0"}],
         "supersedes": None, "visible_to_reviewer": True, "flags": (["library_contract"] if c.get("library") else []) + (["generated_file"] if any(l["file"] in (SDK, TYP) for l in c["locs"] if l["role"] == "site") else [])}
    return r


def injected_claims(blobs, log=None):
    quote = '<li><strong>Auth, users, and items</strong><span aria-label="to"> → </span><strong>CRUD layer</strong>: <!-- -->uses</li>'
    quote2 = 'node_api_routes --\\u003e|\\"uses\\"| node_crud'
    gd = os.environ.get("TRACES_GITDIAGRAM_PAGE")
    if gd and os.path.exists(gd):
        page = open(gd, "rb").read(); sha = sha256_hex(page); txt = page.decode("utf-8")
        off = txt.find(quote); assert off >= 0, "N1 quote not found in the GitDiagram page"
        off2 = txt.find(quote2); assert off2 >= 0
        assert sha == GD_SHA256 and (off, off2) == GD_OFFSETS, f"GitDiagram page differs from the Task 002 record: {sha} {off} {off2}"
        (log if log is not None else []).append(f"N1 GitDiagram page re-read: sha256 {sha}, quote offsets {off}, {off2}")
    else:
        sha, (off, off2) = GD_SHA256, GD_OFFSETS
        (log if log is not None else []).append(f"N1 GitDiagram page not available; using the Task 002 record: sha256 {sha}, quote offsets {off}, {off2}")
    n1 = {"id": "N1", "kind": "uses_crud", "gran": "handler", "from": ep(ITEMS, "create_item", 61, 72), "to": ep(CRUD, CRUD, 1, line_count(blobs.text(CRUD))),  # Decision 002-B ruling 1: last addressable line, not the EOF position
          "statement": "Auth, users, and items → CRUD layer: uses",
          "locs": [L(ITEMS, 61, 72, "site", "declaration", "crud.", "decorator_to_body_end"), L(ITEMS, 1, 8, "input", "declaration", "from app.models import", "binding_statement"), L(CRUD, 63, 68, "input", "declaration", "def create_item(", "header_to_body_end"),
                   L("backend/tests/utils/item.py", 16, 16, "input", "site", "crud.create_item(")],
          "interpretation": "items.py handlers, including create_item, uses_crud (call functions in backend/app/crud.py)", "page_offsets": [off, off2]}
    n2a = {"id": "N2a", "kind": "depends_on", "gran": "handler", "from": ep(PRIV, "create_user", 23, 38), "to": ep(DEPS, "CurrentUser", 49, 49),
           "statement": "private.py:create_user depends on CurrentUser", "locs": [L(PRIV, 24, 24, "site", "site", "def create_user(user_in: PrivateUserCreate, session: SessionDep)"), L(PRIV, 6, 6, "input", "site", "from app.api.deps import SessionDep"),
           L(PRIV, 23, 38, "from_decl", "declaration", '@router.post("/users/"', "decorator_to_body_end"), L(DEPS, 49, 49, "to_decl", "declaration", "CurrentUser = Annotated", "binding_statement")]}
    n2b = {"id": "N2b", "kind": "depends_on", "gran": "handler", "from": ep(PRIV, "create_user", 23, 38), "to": ep(DEPS, "get_current_user", 30, 46),
           "statement": "private.py:create_user depends on get_current_user", "locs": [L(PRIV, 24, 24, "site", "site", "def create_user(user_in: PrivateUserCreate, session: SessionDep)"), L(PRIV, 6, 6, "input", "site", "from app.api.deps import SessionDep"),
           L(PRIV, 23, 38, "from_decl", "declaration", '@router.post("/users/"', "decorator_to_body_end"), L(DEPS, 30, 46, "to_decl", "declaration", "def get_current_user(")]}
    return [n1, n2a, n2b], sha, quote, off


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--src", required=True); ap.add_argument("--fixture-out", required=True); ap.add_argument("--injected-out"); ap.add_argument("--run-id", default="fixture-build"); ap.add_argument("--spotcheck-out")
    a = ap.parse_args()
    blobs = Blobs(a.src, REPO_SHA); at = now_ist(); log = []
    bad = 0
    for c in CLAIMS:
        log.append(f"## {c['id']}")
        bad += spot_check(blobs, c["locs"] + c.get("context", []), log)
    inj, gsha, quote, off = injected_claims(blobs, log)
    for c in inj:
        log.append(f"## {c['id']} (injected)")
        bad += spot_check(blobs, [l for l in c["locs"] if l["token"] != "crud."], log)
        if c["id"] == "N1":
            seg = "\n".join(blobs.lines(ITEMS)[60:72]); log.append(f"N1 evidence: 'crud.' occurrences in items.py:61-72 = {seg.count('crud.')}; 'crud' in items.py = {blobs.text(ITEMS).count('crud')}")
    if bad:
        print("\n".join(log)); raise SystemExit(f"spot check failed on {bad} location(s)")
    orig = {"name": "traces-lab-fixture", "version": "chain_create_item 1.0.0", "role": "fixture"}
    recs = []
    for c in CLAIMS:
        recs.append(record(c, blobs, a.run_id, at, orig, "fixture:expected-chain",
                           {"kind": "fixture", "fixture_id": c["id"], "fixture_file": FIXTURE_FILE, "derived_from": [f"task002/spec/EXPECTED_CHAIN.md {c['id'][:2]}", "lab/B/ground-truth.md Q3/Q4"]},
                           False, "fixture hypothesis; not yet checked by an independent validator"))
    fixture = {"fixture": "chain_create_item", "version": "1.0.0", "repo": REPO, "repo_sha": REPO_SHA, "spec": "task002/spec/EXPECTED_CHAIN.md v2", "built_at": at,
               "claims": recs, "expected": EXPECT, "negative_controls": {"N1": {"expected_status": "rejected", "expected_status_reason": N1_REASON}, "N2": {"expected_status": "rejected", "expected_status_reason": N2_REASON}},
               "injected_set_location": "task002/work/<run_id>/validator_inputs/injected.jsonl (written per run; never in this file)", "spot_check": log,
               "note": "Lab spot check only (token on the cited line, from git show at repo_sha). Traces' own spot check (TASK_002_PLAN step 5) is pending."}
    json.dump(fixture, open(a.fixture_out, "w"), indent=1, sort_keys=True, ensure_ascii=False)
    if a.spotcheck_out:
        open(a.spotcheck_out, "w").write("\n".join(log) + "\n")
    if a.injected_out:
        os.makedirs(os.path.dirname(a.injected_out), exist_ok=True)
        with open(a.injected_out, "w") as f:
            n1, n2a, n2b = inj
            f.write(canon(record(n1, blobs, a.run_id, at, {"name": "gitdiagram", "version": f"public cached page sha256 {gsha}", "role": "external"}, "external:gitdiagram-page",
                                 {"kind": "external_document", "artifact": "lab/B/logs/gitdiagram_page.html", "sha256": gsha, "quote": quote}, True, "injected negative control; not yet checked")) + "\n")
            for n in (n2a, n2b):
                f.write(canon(record(n, blobs, a.run_id, at, {"name": "traces-negative-control", "version": "N2 1.0.0", "role": "fixture"}, "fixture:negative-control",
                                     {"kind": "fixture", "fixture_id": n["id"], "fixture_file": "validator_inputs/injected.jsonl", "derived_from": ["task002/spec/EXPECTED_CHAIN.md N2", "DECISIONS.md D-Q8, D-002A.8"]}, True, "injected negative control; not yet checked")) + "\n")
    print(f"fixture claims {len(recs)}; spot-checked locations {sum(1 for x in log if x.startswith('OK'))}, bad {bad}; injected {'written' if a.injected_out else 'not written'}")


if __name__ == "__main__":
    main()
