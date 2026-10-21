"""Hardened read-only Git runner (docs/contracts/history.md section 11).

Every call is a fixed argv list (no shell), runs with an environment built from scratch, a private empty HOME and
work tree, hooks off, external diff and textconv off, NUL-delimited output, a per-call timeout and an output cap.
Only read-only subcommands are allowed; network transports are refused (`protocol.allow=never`, no lazy fetch).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Sequence
from pathlib import Path

from .errors import (
    E_GIT,
    E_GIT_VERSION,
    E_LIMIT,
    E_MISSING_OBJECT,
    E_REPO,
    E_SHA,
    E_SHALLOW,
    E_TIMEOUT,
    HistoryError,
)

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
MIN_GIT_VERSION = (2, 47)
ALLOWED_SUBCOMMANDS = frozenset({"rev-parse", "cat-file", "log", "rev-list", "ls-tree", "diff-tree", "for-each-ref", "version"})
# Subcommands that produce diffs: always add --no-ext-diff --no-textconv.
DIFF_SUBCOMMANDS = frozenset({"log", "diff-tree"})

GLOBAL_CONFIG: tuple[str, ...] = (
    "core.hooksPath=/dev/null",
    "core.quotePath=false",
    "core.fsmonitor=false",
    "core.attributesFile=/dev/null",
    "core.pager=cat",
    "diff.external=",
    "log.showSignature=false",
    "log.decorate=false",
    "color.ui=false",
    "protocol.allow=never",
    "mailmap.file=",
    "i18n.logOutputEncoding=UTF-8",
)

# Messages Git prints when an object is absent; with a promisor remote we report E_MISSING_OBJECT, never fetch.
_MISSING_RE = re.compile(rb"(missing|could not read|bad object|unable to read|not a valid object|promisor)", re.I)
_SECRET_RE = re.compile(r"(gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+|//[^/\s@]+@)")


def _redact(text: str, keep: Sequence[str]) -> str:
    text = _SECRET_RE.sub("<redacted>", text)
    for k in keep:
        text = text.replace(k, "<path>")
    return text[:2000]


def validate_sha(sha: object) -> str:
    if not isinstance(sha, str) or not SHA_RE.match(sha):
        raise HistoryError(E_SHA, "SHA must be 40 lowercase hex characters; abbreviations and ref names are refused", "gitcmd")
    return sha


class GitRunner:
    """Read-only Git access to one repository. Use as a context manager so the private HOME is removed."""

    def __init__(self, repo_path: str | os.PathLike[str], *, timeout_s: float = 120.0,
                 max_output_bytes: int = 1 << 30, git_bin: str | None = None) -> None:
        self.timeout_s = timeout_s
        self.max_output_bytes = max_output_bytes
        found = git_bin or shutil.which("git")
        if not found:
            raise HistoryError(E_GIT, "git binary not found", "gitcmd")
        self.git_bin = str(Path(found).resolve())
        self._tmp = tempfile.mkdtemp(prefix="traces-history-")
        self._home = os.path.join(self._tmp, "home")
        self._worktree = os.path.join(self._tmp, "worktree")
        os.mkdir(self._home)
        os.mkdir(self._worktree)
        self.mailmap_blob: str | None = None
        self.repo_path = Path(repo_path)
        try:
            self._open()
        except BaseException:
            self.close()
            raise

    # lifecycle -------------------------------------------------------------------------------------------------
    def close(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def __enter__(self) -> GitRunner:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # environment -----------------------------------------------------------------------------------------------
    def env(self) -> dict[str, str]:
        return {
            "PATH": os.path.dirname(self.git_bin),
            "HOME": self._home,
            "XDG_CONFIG_HOME": self._home,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_ATTR_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_NO_LAZY_FETCH": "1",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_PAGER": "cat",
            "GIT_LITERAL_PATHSPECS": "1",
            "LC_ALL": "C",
        }

    def _base_argv(self) -> list[str]:
        argv = [self.git_bin, "--no-pager", f"--git-dir={self.git_dir}", f"--work-tree={self._worktree}"]
        for c in GLOBAL_CONFIG:
            argv += ["-c", c]
        if self.mailmap_blob:
            argv += ["-c", f"mailmap.blob={self.mailmap_blob}"]
        else:
            argv += ["-c", "mailmap.blob="]
        return argv

    def _exec(self, argv: list[str], stdin: bytes | None) -> subprocess.CompletedProcess[bytes]:
        try:
            p = subprocess.run(argv, input=stdin, stdin=None if stdin is not None else subprocess.DEVNULL,
                               capture_output=True, timeout=self.timeout_s, env=self.env(), cwd=self._worktree,
                               check=False)
        except subprocess.TimeoutExpired as e:
            raise HistoryError(E_TIMEOUT, f"git call exceeded {self.timeout_s}s", "gitcmd") from e
        if len(p.stdout) > self.max_output_bytes:
            raise HistoryError(E_LIMIT, f"git output exceeded {self.max_output_bytes} bytes", "gitcmd")
        return p

    # repository checks -----------------------------------------------------------------------------------------
    def _open(self) -> None:
        if not self.repo_path.exists():
            raise HistoryError(E_REPO, "repository path does not exist", "open")
        p = subprocess.run([self.git_bin, "version"], capture_output=True, env=self.env(), timeout=self.timeout_s,
                           cwd=self._worktree, stdin=subprocess.DEVNULL, check=False)
        m = re.search(rb"git version (\d+)\.(\d+)", p.stdout)
        if not m:
            raise HistoryError(E_GIT_VERSION, "cannot read git version", "open")
        self.git_version = p.stdout.decode().strip()
        if (int(m.group(1)), int(m.group(2))) < MIN_GIT_VERSION:
            raise HistoryError(E_GIT_VERSION, f"{self.git_version} is older than {MIN_GIT_VERSION}", "open")
        argv = [self.git_bin, "--no-pager", "-C", str(self.repo_path)]
        for c in GLOBAL_CONFIG:
            argv += ["-c", c]
        p = self._exec(argv + ["rev-parse", "--absolute-git-dir"], None)
        if p.returncode != 0:
            raise HistoryError(E_REPO, "not a git repository", "open")
        self.git_dir = p.stdout.decode("utf-8", "surrogateescape").strip()
        gd = Path(self.git_dir)
        shallow = self.run("rev-parse", ["--is-shallow-repository"]).strip()
        if shallow == b"true" or (gd / "shallow").exists():
            raise HistoryError(E_SHALLOW, "shallow repository: full history is required", "open")
        if (gd / "info" / "grafts").exists():
            raise HistoryError(E_SHALLOW, "repository has info/grafts", "open")
        cfg = gd / "config"
        text = cfg.read_text("utf-8", "replace").lower() if cfg.exists() else ""
        self.has_promisor = "partialclonefilter" in text or "promisor" in text

    # calls -----------------------------------------------------------------------------------------------------
    def run(self, sub: str, args: Sequence[str] = (), *, stdin: bytes | None = None, allow_fail: bool = False) -> bytes:
        """Run one allowed read-only subcommand and return stdout bytes. Nonzero exit raises E_GIT (or
        E_MISSING_OBJECT in a partial clone) unless allow_fail is set, in which case b"" is returned."""
        if sub not in ALLOWED_SUBCOMMANDS:
            raise HistoryError(E_GIT, f"git subcommand {sub!r} is not allowed", "gitcmd")
        for a in args:
            if not isinstance(a, str) or "\0" in a:
                raise HistoryError(E_GIT, "git arguments must be strings without NUL", "gitcmd")
        extra = ["--no-ext-diff", "--no-textconv"] if sub in DIFF_SUBCOMMANDS else []
        argv = self._base_argv() + [sub, *extra, *args]
        p = self._exec(argv, stdin)
        if p.returncode != 0:
            if allow_fail:
                return b""
            err = p.stderr.decode("utf-8", "replace")
            if self.has_promisor and _MISSING_RE.search(p.stderr):
                raise HistoryError(E_MISSING_OBJECT, "object absent in partial clone; lazy fetch is disabled", "gitcmd")
            raise HistoryError(E_GIT, f"git {sub} exited {p.returncode}: {_redact(err, [str(self.repo_path), self.git_dir])}", "gitcmd")
        self.last_stderr = p.stderr
        return p.stdout

    def verify_commit(self, sha: object) -> str:
        """E_SHA unless `sha` is a full SHA naming a commit present in the repository."""
        s = validate_sha(sha)
        out = self.run("rev-parse", ["--verify", "--quiet", "--end-of-options", f"{s}^{{commit}}"], allow_fail=True).strip()
        if out.decode() != s:
            raise HistoryError(E_SHA, "SHA is not a commit in this repository", "verify")
        if self.run("cat-file", ["-t", s]).strip() != b"commit":
            raise HistoryError(E_SHA, "SHA does not name a commit object", "verify")
        return s

    def set_mailmap_from(self, sha: str) -> str | None:
        """Pin mailmap to the `.mailmap` blob at `sha` (none if absent). Returns the blob id used."""
        out = self.run("ls-tree", ["-z", sha, "--", ".mailmap"])
        blob = None
        for ent in out.split(b"\0"):
            if not ent:
                continue
            meta, _, name = ent.partition(b"\t")
            parts = meta.split()
            if name == b".mailmap" and len(parts) == 3 and parts[1] == b"blob":
                blob = parts[2].decode()
        self.mailmap_blob = blob
        return blob

    def is_shallow(self) -> bool:
        return self.run("rev-parse", ["--is-shallow-repository"]).strip() == b"true"


def git_missing(text: bytes) -> bool:
    return bool(_MISSING_RE.search(text))


__all__ = ["GitRunner", "validate_sha", "SHA_RE", "ALLOWED_SUBCOMMANDS", "GLOBAL_CONFIG", "MIN_GIT_VERSION", "E_MISSING_OBJECT"]
