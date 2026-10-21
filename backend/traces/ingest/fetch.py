"""Safe, pinned fetch of a public repository. Never runs hooks, filters, LFS smudge, submodules or any target code.
Symlinks are checked out as plain files (core.symlinks=false) so a checkout cannot point outside itself.

No credentials are offered to the remote: credential helpers are disabled, terminal prompts are off and askpass is
/bin/false, so a private or missing repository fails fast with `repo_not_public`. Clones are capped in size and time
(the clone directory is measured while `git clone` runs and the process is killed past the cap), and the checkout is
capped in file count and total blob bytes before any file is written."""
from __future__ import annotations

import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from traces.ingest.errors import IngestError
from traces.ingest.urls import RepoRef, require_sha

SAFE_GIT_CONFIG = [
    "-c", "core.hooksPath=/dev/null",
    "-c", "core.symlinks=false",
    "-c", "core.fsmonitor=false",
    "-c", "protocol.allow=never",
    "-c", "protocol.https.allow=always",
    "-c", "protocol.file.allow=always",  # local clones of an already fetched cache only
    "-c", "submodule.recurse=false",
    "-c", "advice.detachedHead=false",
    "-c", "filter.lfs.smudge=",
    "-c", "filter.lfs.process=",
    "-c", "filter.lfs.required=false",
    "-c", "credential.helper=",
    "-c", "http.followRedirects=initial",
]


def git_env() -> dict[str, str]:
    keep = {k: v for k, v in os.environ.items() if k in ("PATH", "LANG", "LC_ALL", "TMPDIR", "SSL_CERT_FILE", "SSL_CERT_DIR")}
    return {**keep, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_TERMINAL_PROMPT": "0",
            "GIT_ASKPASS": "/bin/false", "SSH_ASKPASS": "/bin/false", "GIT_LFS_SKIP_SMUDGE": "1", "GIT_OPTIONAL_LOCKS": "0",
            "HOME": "/nonexistent"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


@dataclass(frozen=True)
class FetchLimits:
    """Caps for one clone. Defaults come from the environment (docs/SETUP.md)."""
    max_clone_bytes: int = 1024 * 1024 * 1024
    clone_timeout_s: int = 900
    max_files: int = 100_000
    max_tree_bytes: int = 1024 * 1024 * 1024

    @classmethod
    def from_env(cls) -> FetchLimits:
        return cls(max_clone_bytes=_env_int("TRACES_MAX_CLONE_MB", 1024) * 1024 * 1024,
                   clone_timeout_s=_env_int("TRACES_CLONE_TIMEOUT_S", 900),
                   max_files=_env_int("TRACES_MAX_FILES", 100_000),
                   max_tree_bytes=_env_int("TRACES_MAX_TREE_MB", 1024) * 1024 * 1024)


_NOT_PUBLIC = ("could not read username", "authentication failed", "repository not found", "terminal prompts disabled",
               "invalid username or password", "returned error: 401", "returned error: 403", "returned error: 404")
_NETWORK = ("could not resolve host", "failed to connect", "connection timed out", "connection refused", "network is unreachable",
            "operation timed out", "ssl", "gnutls", "early eof", "the remote end hung up", "returned error: 5")


def classify_git_failure(stderr: str, slug: str) -> IngestError:
    low = stderr.lower()
    tail = stderr.strip()[-400:]
    if any(s in low for s in _NOT_PUBLIC):
        return IngestError("repo_not_public", f"{slug} was not found anonymously on GitHub. It may be private, renamed or deleted; "
                           "v1 indexes public repositories only and never asks for credentials.")
    if any(s in low for s in _NETWORK):
        return IngestError("upstream_unavailable", f"could not reach GitHub for {slug}", {"git": tail})
    return IngestError("fetch_failed", f"git failed for {slug}", {"git": tail})


def git(*args: str, cwd: str | Path | None = None, timeout: int = 600) -> str:
    p = subprocess.run(["git", *SAFE_GIT_CONFIG, *args], cwd=cwd, env=git_env(), capture_output=True, text=True, timeout=timeout,
                       stdin=subprocess.DEVNULL)
    if p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args[:3])} failed ({p.returncode}): {p.stderr.strip()[-500:]}")
    return p.stdout


def dir_bytes(root: Path) -> int:
    total = 0
    for dp, _dns, fns in os.walk(root):
        for f in fns:
            try:
                total += os.lstat(os.path.join(dp, f)).st_size
            except FileNotFoundError:
                continue
    return total


def _clone_capped(url: str, dest: Path, slug: str, limits: FetchLimits) -> None:
    """`git clone --no-checkout` with a wall-clock cap and a size cap measured while it runs."""
    cmd = ["git", *SAFE_GIT_CONFIG, "clone", "--quiet", "--config", "core.symlinks=false", "--no-checkout",
           "--no-recurse-submodules", url, str(dest)]
    err_path = dest.with_name(dest.name + ".stderr")
    with open(err_path, "w+") as err:
        p = subprocess.Popen(cmd, env=git_env(), stdout=subprocess.DEVNULL, stderr=err, stdin=subprocess.DEVNULL)
        t0, killed = time.monotonic(), None
        while p.poll() is None:
            time.sleep(0.5)
            if time.monotonic() - t0 > limits.clone_timeout_s:
                killed = "timeout"
            elif dest.exists() and dir_bytes(dest) > limits.max_clone_bytes:
                killed = "size"
            if killed:
                p.kill()
                p.wait()
                break
        err.seek(0)
        stderr = err.read()
    err_path.unlink(missing_ok=True)
    if killed == "timeout":
        raise IngestError("fetch_timeout", f"cloning {slug} took longer than {limits.clone_timeout_s} s")
    if killed == "size":
        raise IngestError("too_large", f"{slug} is larger than the {limits.max_clone_bytes // (1024 * 1024)} MiB clone cap",
                          {"max_clone_bytes": limits.max_clone_bytes})
    if p.returncode != 0:
        raise classify_git_failure(stderr, slug)


def _check_tree(repo: Path, sha: str, slug: str, limits: FetchLimits) -> dict[str, int]:
    """Count files and blob bytes of the pinned tree from Git objects before anything is checked out."""
    n, size = 0, 0
    for line in git("-C", str(repo), "ls-tree", "-r", "-l", "--full-tree", sha).splitlines():
        meta, _path = line.split("\t", 1)
        parts = meta.split()
        if parts[1] != "blob":
            continue
        n += 1
        size += int(parts[3]) if parts[3].isdigit() else 0
    if n > limits.max_files:
        raise IngestError("too_many_files", f"{slug}@{sha[:12]} has {n} files (cap {limits.max_files})", {"files": n})
    if size > limits.max_tree_bytes:
        raise IngestError("too_large", f"{slug}@{sha[:12]} checkout would be {size // (1024 * 1024)} MiB "
                          f"(cap {limits.max_tree_bytes // (1024 * 1024)} MiB)", {"tree_bytes": size})
    return {"files": n, "tree_bytes": size}


def ensure_pinned_checkout(ref: RepoRef, sha: str, dest: Path, limits: FetchLimits | None = None) -> Path:
    """Clone `ref` into `dest` (full history, needed for SHA~1 and history) and detach at `sha`. Idempotent:
    an existing clean checkout at `sha` is reused. Raises IngestError on a private/missing repo, a missing commit,
    a cap violation or a network failure; a partial clone is always removed."""
    require_sha(sha)
    limits = limits or FetchLimits.from_env()
    dest = Path(dest)
    if (dest / ".git").exists():
        head = git("-C", str(dest), "rev-parse", "HEAD").strip()
        dirty = git("-C", str(dest), "status", "--porcelain", "--untracked-files=all").strip()
        if head == sha and not dirty:
            return dest
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".partial")
    if tmp.exists():
        shutil.rmtree(tmp)
    try:
        _clone_capped(ref.clone_url, tmp, ref.slug, limits)
        try:
            git("-C", str(tmp), "cat-file", "-e", f"{sha}^{{commit}}")
        except RuntimeError:
            raise IngestError("sha_not_found", f"commit {sha} is not in {ref.slug}") from None
        _check_tree(tmp, sha, ref.slug, limits)
        git("-C", str(tmp), "checkout", "--quiet", "--detach", sha)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    tmp.rename(dest)
    return dest


def local_clone(source: Path, dest: Path, rev: str) -> Path:
    """Throwaway working copy of an already pinned cache checkout (indexing writes .codegraph/ into it)."""
    git("clone", "--quiet", "--config", "core.symlinks=false", "--no-hardlinks", "--no-checkout", str(source), str(dest))
    git("-C", str(dest), "checkout", "--quiet", "--detach", rev)
    return dest
