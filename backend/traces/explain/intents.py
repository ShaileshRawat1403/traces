"""Deterministic intent routing for no-key explain (Traces UI seat, acceptance finding F-7).

A question is mapped to exactly one explicit intent by ordered patterns, with the entities the intent needs (symbol
names, a commit prefix). There is no keyword-overlap fallback: a question that matches no intent, or whose entities
cannot be read, is routed to "unsupported" and answered as unknown with suggested phrasings. Pure functions only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Runtime questions are always unknown: the evidence is static.
RUNTIME = re.compile(
    r"\b(runtime|run[- ]time|at run|in production|performance|perform|latency|throughput|memory usage|crash(es|ed)?|slow(er|est)?"
    r"|fast(er|est)?|load test|when it runs|actually happens|benchmark\w*|how long does|timeouts?)\b",
    re.I,
)

# A symbol-like token: an identifier, optionally qualified with ::, . or a path.
SYM = r"`?([A-Za-z_][\w$]*(?:(?:::|\.|/)[\w$.-]+)*)`?"
ONE = r"`?(?P<sym>[A-Za-z_][\w$]*(?:(?:::|\.|/)[\w$.-]+)*)`?"
COMMIT_SHA = re.compile(r"\b([0-9a-f]{7,40})\b", re.I)

TRACE = [
    re.compile(rf"\bfrom\s+{SYM}\s+to\s+{SYM}", re.I),
    re.compile(rf"\bhow\s+does\s+{SYM}\s+(?:reach|get\s+to|lead\s+to|connect\s+to|flow\s+to)\s+{SYM}", re.I),
    re.compile(rf"\bpath\s+between\s+{SYM}\s+and\s+{SYM}", re.I),
]
COMMIT = [
    re.compile(r"\bcommit\s+`?([0-9a-f]{7,40})`?\b", re.I),
    re.compile(r"\b(?:what|which)\s+(?:files?\s+)?changed\s+in\s+`?([0-9a-f]{7,40})`?\b", re.I),
]
DEP_VERBS = r"(?:depend\s+on|depends\s+on|call|calls|use|uses|import|imports|need|needs|render|renders|reference|references|instantiate|instantiates)"
DEPENDENCIES = [
    re.compile(rf"\bwhat\s+(?:does|do)\s+{ONE}\s+{DEP_VERBS}\b", re.I),
    re.compile(rf"\b(?:dependencies|callees|imports)\s+of\s+{ONE}", re.I),
    re.compile(rf"\bwhat\s+is\s+{ONE}\s+(?:dependent\s+on|built\s+on)\b", re.I),
]
DEPENDENTS = [
    re.compile(rf"\b(?:what|who|which\s+\w+)\s+{DEP_VERBS}\s+{ONE}\s*\??\s*$", re.I),
    re.compile(rf"\b(?:callers|users|dependents|importers)\s+of\s+{ONE}", re.I),
    re.compile(rf"\bwhere\s+is\s+{ONE}\s+(?:used|called|imported|referenced|rendered)\b", re.I),
]
DEFINITION = [
    re.compile(rf"\bwhere\s+is\s+{ONE}\s+(?:defined|declared|implemented)\b", re.I),
    re.compile(rf"^\s*(?:what\s+is|tell\s+me\s+about|explain|describe|show)\s+{ONE}\s*\??\s*$", re.I),
    re.compile(rf"^\s*{ONE}\s*\??\s*$", re.I),
]
# A route named by method and path ("POST /register"), or "route /path" / "endpoint /path".
HTTP_METHOD = r"(?:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS|USE)"
ROUTE_PATH = r"(/[\w/:{}.\-*~]*)"
ROUTE_ONE = [
    re.compile(rf"(?<![\w/])({HTTP_METHOD})\s+`?{ROUTE_PATH}`?", re.I),
    re.compile(rf"\b(?:route|endpoint|path)\s+`?{ROUTE_PATH}`?", re.I),
]
# Directory moves and renames: "When was A moved to B?", "move from A to B", "Where did A move?".
MOVE = re.compile(r"\b(mov(?:e|ed|es|ing)|renam(?:e|ed|es|ing)|relocat\w*)\b", re.I)
DIR = r"`?(?P<{}>[\w.{{}}@-]+(?:/[\w.{{}}@-]+)*/?)`?"
MOVE_PATTERNS = [
    re.compile(rf"\bfrom\s+{DIR.format('a')}\s+(?:to|into)\s+{DIR.format('b')}", re.I),
    re.compile(
        rf"\b(?:was|were|did|has|have|is)\s+(?:the\s+)?{DIR.format('a')}\s+(?:(?:get|been)\s+)?(?:directory\s+|folder\s+)?"
        rf"(?:moved|move|renamed|rename|relocated)\b(?:\s+(?:to|into|as)\s+{DIR.format('b')})?",
        re.I,
    ),
    re.compile(
        rf"\b(?:moved|move|renamed|rename)\s+(?:of\s+)?{DIR.format('a')}\s+(?:to|into|as)\s+{DIR.format('b')}", re.I
    ),
]

# A file named in a question: a path with a slash, or a name with an extension (crud.py, Alpha.tsx).
FILE_TOKEN = re.compile(r"`?((?:[\w.@-]+/)*[\w@-][\w.@-]*\.[A-Za-z][\w]{0,9}|(?:[\w.@-]+/)+[\w.@-]+)`?")
COCHANGE = re.compile(
    r"\b(co-?chang\w*|chang(?:e|es|ed|ing)\s+(?:together|along)|chang(?:e|es|ed)\s+with|coupl\w*\s+(?:with|to))\b", re.I
)
# "changed together with Alpha": a bare name after with/and, resolved later against stored paths (never guessed).
COCHANGE_NAME = re.compile(r"\b(?:with|and|to)\s+`?([A-Za-z_][\w.-]*)`?", re.I)
HISTORY = re.compile(
    r"\b(history|historical|co-?change\w*|changed together|change together|changes together|churn|hotspots?"
    r"|coupl\w*|most changed|changed most|changes most)\b",
    re.I,
)
ROUTES = re.compile(r"\b(routes?|endpoints?|urls?|api\s+paths?|pages?)\b", re.I)
PERSIST = re.compile(
    r"\b(persist\w*|database|db|saves?|saved|saving|stor(e|es|ed|age|ing)|writes?\s+to|written\s+to)\b", re.I
)
DOCS = re.compile(
    r"\b(readme|purpose|business|manifest|package\.json|pyproject|third[- ]party|what\s+(?:does|is)\s+(?:this|the)\s+"
    r"(?:app|project|repo|repository|service|codebase|library|package)(?:\s+(?:do|for|about))?)\b",
    re.I,
)
PROJECT_DEPS = re.compile(
    r"\b(?:project|package|app|repo|repository)(?:'s)?\s+dependencies\b|\bdependencies\s+(?:of|does)\s+(?:this|the)\s+"
    r"(?:project|package|app|repo|repository)\b|^\s*(?:what|which)\s+(?:are\s+the\s+)?dependencies\b",
    re.I,
)

# Words that are never a symbol even when they sit where one is expected.
NOT_SYMBOL = frozenset(
    "the a an this that it its these those they them what which who it's app project repo repository code "
    "service codebase library package page pages file files function functions".split()
)

NOT_DIR = frozenset(
    "the a an this that it its these those they them what which who directory directories folder folders files".split()
)
HISTORY_WORDS = frozenset("other others each together commits commit history time files file".split())

SUGGESTIONS = (
    "What does <symbol> depend on?",
    "What calls <symbol>?",
    "Trace from <symbol> to <symbol>",
    "Which routes are declared?",
    "What does POST /path do?",
    "When was <dir> moved to <dir>?",
    "How is data persisted?",
    "Which files changed together?",
    "Which files changed together with <path/to/file.py>?",
    "What changed in commit <sha>?",
)


@dataclass(frozen=True)
class Intent:
    name: str  # runtime | trace | commit | route | move | cochange | dependencies | dependents | definition | history | routes | persistence | docs | unsupported
    entities: tuple[str, ...] = ()
    reason: str = ""


def _clean(s: str) -> str:
    return s.strip("`'\".,?!;:()[]{}")


def _symbol_ok(s: str) -> bool:
    return bool(s) and s.lower() not in NOT_SYMBOL


def files_in(question: str) -> tuple[str, ...]:
    """Files named in the question, in order, without duplicates. Version-like or sentence tokens are not files."""
    out: list[str] = []
    for m in FILE_TOKEN.finditer(question):
        t = m.group(1).rstrip(".")
        if re.fullmatch(r"[\d.]+", t) or "." not in t and "/" not in t:
            continue
        out.append(t)
    return tuple(dict.fromkeys(out))


def _without_files(q: str) -> str:
    """The question with named files removed, so a path such as api/routes/x.py cannot trigger keyword intents."""
    return FILE_TOKEN.sub(" ", q)


def classify(question: str) -> Intent:
    q = " ".join(question.split())
    if not q:
        return Intent("unsupported", reason="The question is empty.")
    if RUNTIME.search(q):
        return Intent("runtime")
    for p in TRACE:
        if m := p.search(q):
            a, b = _clean(m.group(1)), _clean(m.group(2))
            if _symbol_ok(a) and _symbol_ok(b):
                return Intent("trace", (a, b))
            return Intent(
                "unsupported",
                reason="A trace needs two symbol names, for example 'Trace from LoginForm to login_access_token'.",
            )
    for p in COMMIT:
        if m := p.search(q):
            return Intent("commit", (m.group(1).lower(),))
    # A named route: method and path (method may be empty for "route /x").
    for p in ROUTE_ONE:
        if m := p.search(q):
            if m.lastindex == 2:
                return Intent("route", (m.group(1).upper(), m.group(2)))
            return Intent("route", ("", m.group(1)))
    # Directory moves: the named directories are the entities (none named lists the recorded moves).
    if MOVE.search(q):
        for p in MOVE_PATTERNS:
            if m := p.search(q):
                names = [_clean(x).strip("/") for x in (m.group("a"), m.groupdict().get("b")) if x]
                names = [n for n in names if n and n.lower() not in NOT_DIR]
                if names:
                    return Intent("move", tuple(dict.fromkeys(names)))
        return Intent("move")
    # Co-change: the files it names are the entities. A bare name is kept for exact resolution against stored paths.
    if COCHANGE.search(q):
        files = files_in(q)
        if not files:
            names = [
                n
                for n in (_clean(x) for x in COCHANGE_NAME.findall(_without_files(q)))
                if _symbol_ok(n) and n.lower() not in HISTORY_WORDS
            ]
            files = tuple(dict.fromkeys(names))
        return Intent("cochange", files)
    if re.search(r"\bcommit\b", q, re.I):
        return Intent(
            "unsupported",
            reason="Questions about a commit need its hash (7 to 40 hex characters), for example 'What changed in commit 1a2b3c4?'.",
        )
    if PROJECT_DEPS.search(q):
        return Intent("docs")
    for name, pats in (("dependencies", DEPENDENCIES), ("dependents", DEPENDENTS)):
        for p in pats:
            if m := p.search(q):
                sym = _clean(m.group("sym"))
                if _symbol_ok(sym):
                    return Intent(name, (sym,))
                return Intent(
                    "unsupported",
                    reason=f"'{sym}' is not a symbol name. Name a function, class or file, for example 'What does create_user depend on?'.",
                )
    if HISTORY.search(q):
        return Intent("history", files_in(q))
    bare = _without_files(q)
    if ROUTES.search(bare):
        return Intent("routes")
    if PERSIST.search(bare):
        return Intent("persistence")
    if DOCS.search(bare):
        return Intent("docs")
    for p in DEFINITION:
        if m := p.search(q):
            sym = _clean(m.group("sym"))
            if _symbol_ok(sym) and (len(q.split()) > 1 or re.search(r"[_:./]|[a-z][A-Z]", sym)):
                return Intent("definition", (sym,))
    return Intent(
        "unsupported",
        reason="This question does not match a kind of question the no-key explainer can answer from stored evidence.",
    )
