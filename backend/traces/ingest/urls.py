"""Repository URL validation. v1 accepts public GitHub HTTPS URLs only (charter 4A, section 5)."""
from __future__ import annotations

import re
from dataclasses import dataclass

_GH = re.compile(r"^https://github\.com/(?P<owner>[A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))/(?P<name>[A-Za-z0-9._-]{1,100}?)(?:\.git)?/?$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class InvalidRepoUrl(ValueError):
    pass


@dataclass(frozen=True)
class RepoRef:
    host: str
    owner: str
    name: str

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.name}"

    @property
    def clone_url(self) -> str:
        return f"https://{self.host}/{self.owner}/{self.name}.git"

    @property
    def cache_key(self) -> str:
        return f"{self.host}__{self.owner}__{self.name}"


def parse_repo_url(url: str) -> RepoRef:
    if not isinstance(url, str) or len(url) > 300 or any(c.isspace() or ord(c) < 32 for c in url):
        raise InvalidRepoUrl("URL must be a single-line string under 300 characters")
    m = _GH.match(url)
    if not m:
        raise InvalidRepoUrl("only https://github.com/<owner>/<repo> URLs are supported in v1")
    name = m.group("name")
    if name in (".", "..") or name.startswith(".") or ".." in name:
        raise InvalidRepoUrl("invalid repository name")
    return RepoRef("github.com", m.group("owner"), name)


def require_sha(sha: str) -> str:
    if not isinstance(sha, str) or not SHA_RE.match(sha):
        raise ValueError("a full 40-character lowercase commit SHA is required")
    return sha
