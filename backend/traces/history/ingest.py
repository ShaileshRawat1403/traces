"""Rename-aware history ingest (docs/contracts/history.md section 9.1).

One metadata stream (`log --no-walk=unsorted --stdin -z`, mailmapped %aN/%aE), one raw change stream
(`diff-tree --stdin -z -r --raw -M -C`) and one line-count stream (`diff-tree --stdin -z -r --numstat -M`) for all
uncached commits. Merges carry no change list; merges on the first-parent chain also get a diff against their first
parent for the lifecycle replay. Results are cached per commit, keyed by SHA plus ingest parameters.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from pathlib import Path

from .cache import CommitCache
from .config import HistoryConfig
from .errors import E_GIT, E_LIMIT, HistoryError
from .gitcmd import SHA_RE, GitRunner
from .model import Change, Commit, HistoryLog, RepoRef, decode_path

META_FIELDS = 7  # %H %P %aN %aE %at %ct %B
_RAW_HEAD = re.compile(rb"^:(\d{6}) (\d{6}) ([0-9a-f]{40}) ([0-9a-f]{40}) ([A-Z])(\d*)$")
_NULL = "0" * 40
_RENAME_LIMIT_WARN = re.compile(rb"(rename detection was skipped|only found copies from modified paths|diff\.renameLimit)")


def open_runner(repo: RepoRef, config: HistoryConfig) -> GitRunner:
    r = GitRunner(repo.path, timeout_s=config.limits.git_call_timeout_s,
                  max_output_bytes=config.limits.max_git_output_bytes)
    try:
        r.verify_commit(repo.sha)
        if config.mailmap == "pinned_blob":
            r.set_mailmap_from(repo.sha)
    except BaseException:
        r.close()
        raise
    return r


def _diff_args(config: HistoryConfig, copies: bool) -> list[str]:
    t = config.thresholds
    a = [f"-M{t.rename_threshold}%", f"-l{t.rename_limit}"]
    if copies:
        a.insert(1, f"-C{t.copy_threshold}%")
    return a


def parse_raw(tokens: list[bytes], i: int, *, stop_at_header: bool = True) -> tuple[list[Change], int]:
    """Parse raw diff entries from NUL tokens starting at i, until a non-entry token or the end."""
    out: list[Change] = []
    n = len(tokens)
    while i < n:
        t = tokens[i]
        if not t.startswith(b":"):
            break
        m = _RAW_HEAD.match(t)
        if not m:
            raise HistoryError(E_GIT, "unexpected raw diff entry", "ingest")
        mb, ma, bb, ba, st, score = m.groups()
        status = st.decode()
        if status in "RC":
            old, oflag = decode_path(tokens[i + 1])
            new, nflag = decode_path(tokens[i + 2])
            i += 3
            out.append(Change(status, new, old, int(score or 0), None if bb.decode() == _NULL else bb.decode(),
                              None if ba.decode() == _NULL else ba.decode(), mb.decode(), ma.decode(),
                              non_utf8=oflag or nflag))
        else:
            path, flag = decode_path(tokens[i + 1])
            i += 2
            out.append(Change(status, path, None, None, None if bb.decode() == _NULL else bb.decode(),
                              None if ba.decode() == _NULL else ba.decode(), mb.decode(), ma.decode(),
                              non_utf8=flag))
    return out, i


def _iter_raw_stream(out: bytes) -> Iterator[tuple[str, list[Change]]]:
    tokens = out.split(b"\0")
    i, n = 0, len(tokens)
    while i < n:
        t = tokens[i]
        if t == b"":
            i += 1
            continue
        if not SHA_RE.match(t.decode("ascii", "replace")):
            raise HistoryError(E_GIT, "unexpected token in diff-tree stream", "ingest")
        sha = t.decode()
        changes, i = parse_raw(tokens, i + 1)
        yield sha, changes


def _iter_numstat_stream(out: bytes) -> Iterator[tuple[str, dict[str, tuple[int, int, bool]]]]:
    tokens = out.split(b"\0")
    i, n = 0, len(tokens)
    while i < n:
        t = tokens[i]
        if t == b"":
            i += 1
            continue
        if b"\t" in t:
            raise HistoryError(E_GIT, "numstat entry without commit header", "ingest")
        sha = t.decode()
        i += 1
        stats: dict[str, tuple[int, int, bool]] = {}
        while i < n and b"\t" in tokens[i]:
            a, d, rest = tokens[i].split(b"\t", 2)
            binary = a == b"-"
            av = 0 if binary else int(a)
            dv = 0 if d == b"-" else int(d)
            if rest == b"":
                new, _ = decode_path(tokens[i + 2])
                i += 3
            else:
                new, _ = decode_path(rest)
                i += 1
            stats[new] = (av, dv, binary)
        yield sha, stats


def _parse_meta(out: bytes) -> dict[str, tuple[tuple[str, ...], str, str, int, int, str]]:
    tokens = out.split(b"\0")
    meta = {}
    i = 0
    while i + META_FIELDS <= len(tokens):
        h, p, an, ae, at, ct, body = tokens[i:i + META_FIELDS]
        i += META_FIELDS
        if not h:
            break
        sha = h.decode()
        parents = tuple(x for x in p.decode().split() if x)
        meta[sha] = (parents, an.decode("utf-8", "replace"), ae.decode("utf-8", "replace"), int(at), int(ct),
                     body.decode("utf-8", "replace"))
    return meta


def _commit_list(runner: GitRunner, sha: str, first_parent: bool = False) -> list[str]:
    args = ["--topo-order", "--reverse"]
    if first_parent:
        args.append("--first-parent")
    out = runner.run("rev-list", [*args, sha])
    return [x for x in out.decode().split("\n") if x]


def _fetch_commits(runner: GitRunner, shas: list[str], config: HistoryConfig) -> list[Commit]:
    if not shas:
        return []
    stdin = ("\n".join(shas) + "\n").encode()
    meta = _parse_meta(runner.run("log", ["--no-walk=unsorted", "--stdin", "-z",
                                          "--format=%H%x00%P%x00%aN%x00%aE%x00%at%x00%ct%x00%B"], stdin=stdin))
    raw = dict(_iter_raw_stream(runner.run("diff-tree", ["--stdin", "-z", "-r", "--raw", "--no-abbrev", "--root",
                                                         *_diff_args(config, copies=True)], stdin=stdin)))
    limited = bool(_RENAME_LIMIT_WARN.search(getattr(runner, "last_stderr", b"")))
    nums = dict(_iter_numstat_stream(runner.run("diff-tree", ["--stdin", "-z", "-r", "--numstat", "--root",
                                                              *_diff_args(config, copies=False)], stdin=stdin)))
    lim = config.limits.max_paths_per_commit
    out = []
    for sha in shas:
        if sha not in meta:
            raise HistoryError(E_GIT, f"no metadata for commit {sha}", "ingest")
        parents, an, ae, at, ct, body = meta[sha]
        changes = raw.get(sha, [])
        if len(parents) > 1:
            changes = []  # merges: no authored change list (D-H5)
        if len(changes) > lim:
            raise HistoryError(E_LIMIT, f"commit {sha} changes {len(changes)} paths (limit {lim})", "ingest")
        st = nums.get(sha, {})
        filled = []
        for c in changes:
            a, d, b = st.get(c.path, (None, None, False))
            filled.append(Change(c.status, c.path, c.old_path, c.similarity, c.blob_before, c.blob_after,
                                 c.mode_before, c.mode_after, a, d, b, c.non_utf8))
        filled.sort(key=lambda c: (c.path.encode("utf-8", "surrogateescape"), c.status))
        adds = sum(1 for c in filled if c.status in "AC")
        dels = sum(1 for c in filled if c.status == "D")
        rl = limited and max(adds, dels) > config.thresholds.rename_limit
        out.append(Commit(sha, parents, an, ae, at, ct, body, tuple(filled), rl))
    return out


def merge_diff(runner: GitRunner, parent: str, merge: str, config: HistoryConfig) -> tuple[Change, ...]:
    out = runner.run("diff-tree", ["-z", "-r", "--raw", "--no-abbrev", *_diff_args(config, copies=False), parent, merge])
    changes, _ = parse_raw(out.split(b"\0"), 0)
    return tuple(sorted(changes, key=lambda c: (c.path, c.status)))


def ingest(repo: RepoRef, config: HistoryConfig | None = None, *, cache_dir: Path | str | None = None) -> HistoryLog:
    """Parse all history reachable from repo.sha. Pure with respect to the repository: reads objects only."""
    config = (config or HistoryConfig()).validate()
    with open_runner(repo, config) as runner:
        shas = _commit_list(runner, repo.sha)
        if len(shas) > config.limits.max_commits:
            raise HistoryError(E_LIMIT, f"{len(shas)} commits exceeds limit {config.limits.max_commits}", "ingest")
        fp = _commit_list(runner, repo.sha, first_parent=True)
        key_params = {**config.ingest_params(), "mailmap_blob": runner.mailmap_blob, "git": runner.git_version}
        cache = CommitCache(Path(cache_dir) if cache_dir else None, key_params)
        cached: dict[str, Commit] = {}
        missing: list[str] = []
        for s in shas:
            c = cache.get(s)
            if c is None:
                missing.append(s)
            else:
                cached[s] = c
        for c in _fetch_commits(runner, missing, config):
            cached[c.sha] = c
            cache.put(c)
        commits = tuple(cached[s] for s in shas)
        merge_diffs = {}
        by = {c.sha: c for c in commits}
        for s in fp:
            c = by[s]
            if c.is_merge:
                merge_diffs[s] = merge_diff(runner, c.parents[0], s, config)
        warnings = []
        if runner.mailmap_blob is None:
            warnings.append("no .mailmap at the pinned SHA, or mailmap disabled: raw author identities used")
        limited = [c.sha for c in commits if c.rename_limited]
        if limited:
            warnings.append(f"rename detection limited in {len(limited)} commits")
        return HistoryLog(repo=repo, config=config, commits=commits, first_parent=tuple(fp),
                          merge_fp_diffs=merge_diffs, git_version=runner.git_version,
                          mailmap_blob=runner.mailmap_blob, warnings=tuple(warnings), cache_stats=cache.stats())


def ls_tree_paths(runner: GitRunner, sha: str) -> list[str]:
    out = runner.run("ls-tree", ["-r", "-z", "--full-tree", sha])
    paths = []
    for ent in out.split(b"\0"):
        if ent:
            paths.append(decode_path(ent.split(b"\t", 1)[1])[0])
    return paths


def iter_nonmerge(commits: Iterable[Commit]) -> Iterator[Commit]:
    return (c for c in commits if not c.is_merge)


__all__ = ["ingest", "open_runner", "ls_tree_paths", "merge_diff", "parse_raw", "iter_nonmerge"]
