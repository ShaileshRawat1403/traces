"""Safe, pinned fetch of a public repository. Never runs hooks, filters, LFS smudge, submodules or any target code.
Symlinks are checked out as plain files (core.symlinks=false) so a checkout cannot point outside itself."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

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
]


def git_env() -> dict[str, str]:
    keep = {k: v for k, v in os.environ.items() if k in ("PATH", "LANG", "LC_ALL", "TMPDIR", "SSL_CERT_FILE", "SSL_CERT_DIR")}
    return {**keep, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_TERMINAL_PROMPT": "0",
            "GIT_LFS_SKIP_SMUDGE": "1", "GIT_OPTIONAL_LOCKS": "0", "HOME": "/nonexistent"}


def git(*args: str, cwd: str | Path | None = None, timeout: int = 600) -> str:
    p = subprocess.run(["git", *SAFE_GIT_CONFIG, *args], cwd=cwd, env=git_env(), capture_output=True, text=True, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args[:3])} failed ({p.returncode}): {p.stderr.strip()[-500:]}")
    return p.stdout


def ensure_pinned_checkout(ref: RepoRef, sha: str, dest: Path) -> Path:
    """Clone `ref` into `dest` (full history, needed for SHA~1 and history) and detach at `sha`. Idempotent:
    an existing clean checkout at `sha` is reused. Raises if the commit is missing or the tree is dirty."""
    require_sha(sha)
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
    git("clone", "--quiet", "--config", "core.symlinks=false", "--no-checkout", "--no-recurse-submodules", ref.clone_url, str(tmp), timeout=1800)
    git("-C", str(tmp), "cat-file", "-e", f"{sha}^{{commit}}")
    git("-C", str(tmp), "checkout", "--quiet", "--detach", sha)
    tmp.rename(dest)
    return dest


def local_clone(source: Path, dest: Path, rev: str) -> Path:
    """Throwaway working copy of an already pinned cache checkout (indexing writes .codegraph/ into it)."""
    git("clone", "--quiet", "--config", "core.symlinks=false", "--no-hardlinks", "--no-checkout", str(source), str(dest))
    git("-C", str(dest), "checkout", "--quiet", "--detach", rev)
    return dest
