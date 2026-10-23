"""Anonymous HEAD discovery for public GitHub repositories (`git ls-remote --symref <url> HEAD`).

No credentials are ever offered: credential helpers are disabled, prompts are off and askpass is /bin/false, so a
private or missing repository fails with a clean `repo_not_public` instead of asking for a login. Results are cached
per repository for `ttl_s` seconds and a per-repository minimum interval protects GitHub from rapid polling."""
from __future__ import annotations

import re
import subprocess
import tempfile
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


_NO_SUCH_COMMIT = ("not our ref", "couldn't find remote ref", "no such remote ref", "unadvertised object", "is not a commit",
                   "could not find remote ref")


def remote_commit_exists(ref: RepoRef, sha: str, timeout: float = 30.0) -> bool:
    """True when `sha` is a commit GitHub serves for this public repository. Anonymous, credential-free shallow fetch of
    that one commit object only (`--depth=1 --filter=tree:0`: no trees, no blobs) into a throwaway bare repository, so a
    well-formed but unknown SHA is refused at registration instead of failing the index job later. Network and other
    failures raise IngestError (classified as for clone); only an explicit "no such commit" answer returns False."""
    with tempfile.TemporaryDirectory(prefix="traces-shacheck-") as d:
        # a named remote, so the filtered fetch records it as the promisor (a bare URL fails the connectivity check)
        for prep in (["init", "--quiet", "--bare", d], ["-C", d, "remote", "add", "origin", ref.clone_url]):
            init = subprocess.run(["git", *SAFE_GIT_CONFIG, *prep], env=git_env(), capture_output=True, text=True,
                                  timeout=timeout, stdin=subprocess.DEVNULL)
            if init.returncode != 0:
                raise IngestError("fetch_failed", f"could not prepare the commit check for {ref.slug}",
                                  {"git": init.stderr.strip()[-400:]})
        cmd = ["git", *SAFE_GIT_CONFIG, "-C", d, "fetch", "--quiet", "--depth=1", "--filter=tree:0", "--no-tags",
               "--no-write-fetch-head", "--no-recurse-submodules", "origin", sha]
        try:
            p = subprocess.run(cmd, env=git_env(), capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            raise IngestError("fetch_timeout", f"checking commit {sha[:12]} in {ref.slug} took longer than {timeout:.0f} s") from None
    if p.returncode == 0:
        return True
    if any(m in p.stderr.lower() for m in _NO_SUCH_COMMIT):
        return False
    raise classify_git_failure(p.stderr, ref.slug)


class HeadProbe:
    """Cached, rate-limited HEAD discovery. Injected into the API (tests replace it with a fake; no network in tests)."""

    def __init__(self, ttl_s: float = 60.0, min_interval_s: float = 5.0, timeout_s: float = 20.0):
        self.ttl_s, self.min_interval_s, self.timeout_s = ttl_s, min_interval_s, timeout_s
        self._cache: dict[str, tuple[float, RemoteHead]] = {}
        self._last_call: dict[str, float] = {}
        self._known_commits: set[str] = set()
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

    def commit_exists(self, ref: RepoRef, sha: str) -> bool:
        """Whether `sha` exists in the public repository (remote_commit_exists). Positive answers are cached: a commit
        that exists does not go away for a pinned SHA."""
        key = f"{ref.cache_key}@{sha}"
        with self._lock:
            if key in self._known_commits:
                return True
        ok = remote_commit_exists(ref, sha)
        if ok:
            with self._lock:
                self._known_commits.add(key)
        return ok
