"""Error codes for the history module (docs/contracts/history.md section 13). Every error is fail closed."""

from __future__ import annotations

E_SHA = "E_SHA"
E_REPO = "E_REPO"
E_SHALLOW = "E_SHALLOW"
E_MISSING_OBJECT = "E_MISSING_OBJECT"
E_GIT_VERSION = "E_GIT_VERSION"
E_GIT = "E_GIT"
E_TIMEOUT = "E_TIMEOUT"
E_LIMIT = "E_LIMIT"
E_CONFIG = "E_CONFIG"
E_COMPONENT_MAP = "E_COMPONENT_MAP"
E_EVIDENCE_SET = "E_EVIDENCE_SET"
E_REPLAY = "E_REPLAY"
E_PATH = "E_PATH"
E_COLLISION = "E_COLLISION"
E_SCHEMA = "E_SCHEMA"
E_ISOLATION = "E_ISOLATION"
E_CACHE = "E_CACHE"

CODES = frozenset({
    E_SHA, E_REPO, E_SHALLOW, E_MISSING_OBJECT, E_GIT_VERSION, E_GIT, E_TIMEOUT, E_LIMIT, E_CONFIG,
    E_COMPONENT_MAP, E_EVIDENCE_SET, E_REPLAY, E_PATH, E_COLLISION, E_SCHEMA, E_ISOLATION, E_CACHE,
})


class HistoryError(Exception):
    """A contract error. `code` is one of CODES; `detail` never contains credentials or paths outside the repo."""

    def __init__(self, code: str, detail: str, stage: str = "") -> None:
        if code not in CODES:
            raise ValueError(f"unknown history error code {code!r}")
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.stage = stage

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "detail": self.detail, "stage": self.stage}
