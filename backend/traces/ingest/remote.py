"""Anonymous HEAD discovery for public GitHub repositories (`git ls-remote --symref <url> HEAD`).

No credentials are ever offered: credential helpers are disabled, prompts are off and askpass is /bin/false, so a
private or missing repository fails with a clean `repo_not_public` instead of asking for a login. Results are cached
per repository for `ttl_s` seconds and a per-repository minimum interval protects GitHub from rapid polling."""
from __future__ import annotations

import re
import subprocess
import threading
import time
from dataclasses import dataclass

from traces.evidence.store import now
from traces.ingest.errors import IngestError
from traces.ingest.fetch import SAFE_GIT_CONFIG, classify_git_failure, git_env
from traces.ingest.urls import SHA_RE, RepoRef

_SYMREF = re.compile(r"^ref: refs/heads/(?P<branch>\S+)\tHEAD$")


@dataclass(frozen=True)
class RemoteHead:
    default_branch: str | None
    sha: str
    checked_at: str


def ls_remote_head(ref: RepoRef, timeout: float = 20.0) -> RemoteHead:
    cmd = ["git", *SAFE_GIT_CONFIG, "ls-remote", "--symref", ref.clone_url, "HEAD"]
    try:
        p = subprocess.run(cmd, env=git_env(), capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        raise IngestError("fetch_timeout", f"HEAD discovery for {ref.slug} took longer than {timeout:.0f} s") from None
    if p.returncode != 0:
        raise classify_git_failure(p.stderr, ref.slug)
    branch, sha = None, None
    for line in p.stdout.splitlines():
        m = _SYMREF.match(line)
        if m:
            branch = m.group("branch")
        elif line.endswith("\tHEAD") and SHA_RE.match(line.split("\t", 1)[0]):
            sha = line.split("\t", 1)[0]
    if sha is None:
        raise IngestError("repo_empty", f"{ref.slug} has no commits on its default branch")
    return RemoteHead(branch, sha, now())


class HeadProbe:
    """Cached, rate-limited HEAD discovery. Injected into the API (tests replace it with a fake; no network in tests)."""

    def __init__(self, ttl_s: float = 60.0, min_interval_s: float = 5.0, timeout_s: float = 20.0):
        self.ttl_s, self.min_interval_s, self.timeout_s = ttl_s, min_interval_s, timeout_s
        self._cache: dict[str, tuple[float, RemoteHead]] = {}
        self._last_call: dict[str, float] = {}
        self._lock = threading.Lock()

    def head(self, ref: RepoRef, *, max_age_s: float | None = None) -> RemoteHead:
        key = ref.cache_key
        ttl = self.ttl_s if max_age_s is None else max_age_s
        with self._lock:
            hit = self._cache.get(key)
            t = time.monotonic()
            if hit and t - hit[0] <= ttl:
                return hit[1]
            last = self._last_call.get(key)
            if last is not None and t - last < self.min_interval_s:
                if hit:
                    return hit[1]
                raise IngestError("rate_limited", f"HEAD discovery for {ref.slug} was called less than {self.min_interval_s:.0f} s ago",
                                  {"retry_after_s": round(self.min_interval_s - (t - last), 1)})
            self._last_call[key] = t
        h = ls_remote_head(ref, self.timeout_s)
        with self._lock:
            self._cache[key] = (time.monotonic(), h)
        return h
