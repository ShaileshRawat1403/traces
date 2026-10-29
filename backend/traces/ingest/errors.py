"""Ingest failures with a stable machine code and HTTP status (CONTRACTS.md section 4 error envelope)."""
from __future__ import annotations

from typing import Any

# code -> HTTP status used by the API
CODES: dict[str, int] = {
    "invalid_repo_url": 422,
    "invalid_sha": 422,
    "repo_not_public": 422,      # not found anonymously: private, deleted or misspelled (GitHub answers the same for all three)
    "repo_empty": 422,           # no commits / no HEAD
    "sha_not_found": 422,        # the requested commit is not in the public repository
    "too_large": 413,            # clone exceeded the size cap
    "too_many_files": 413,       # checkout exceeded the file-count cap
    "fetch_timeout": 504,        # clone or ls-remote exceeded its time cap
    "upstream_unavailable": 502,  # network or GitHub failure
    "rate_limited": 429,         # HEAD discovery called too often
    "fetch_failed": 502,         # any other git failure (stderr tail in detail, never credentials)
}


class IngestError(Exception):
    def __init__(self, code: str, message: str, detail: dict[str, Any] | None = None):
        assert code in CODES, code
        super().__init__(f"{code}: {message}")
        self.code, self.message, self.detail = code, message, detail

    @property
    def http_status(self) -> int:
        return CODES[self.code]
