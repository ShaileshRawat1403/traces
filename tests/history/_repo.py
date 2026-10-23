"""Synthetic Git repositories built at test time in tmp dirs. Uses the system git with an isolated environment so
the developer's global config never leaks in."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ALICE = ("Alice Example", "alice@example.com")
BOB = ("Bob Example", "bob@example.com")
BOT = ("dependabot[bot]", "49699333+dependabot[bot]@users.noreply.github.com")


class SynthRepo:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        self.home = self.path.parent / (self.path.name + "-home")
        self.home.mkdir(exist_ok=True)
        self.tick = 0
        self.git("init", "-q", "-b", "main")

    def env(self, author: tuple[str, str] = ALICE) -> dict[str, str]:
        self.tick += 1
        date = f"{1_700_000_000 + self.tick * 86_400} +0000"
        return {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(self.home),
                "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1", "LC_ALL": "C",
                "GIT_AUTHOR_NAME": author[0], "GIT_AUTHOR_EMAIL": author[1], "GIT_AUTHOR_DATE": date,
                "GIT_COMMITTER_NAME": author[0], "GIT_COMMITTER_EMAIL": author[1], "GIT_COMMITTER_DATE": date}

    def git(self, *args: str, author: tuple[str, str] = ALICE, input: bytes | None = None) -> bytes:
        p = subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false", *args],
                           cwd=self.path, env=self.env(author), capture_output=True, input=input, check=False)
        if p.returncode != 0:
            raise RuntimeError(f"git {args} failed: {p.stderr.decode()}")
        return p.stdout

    def write(self, rel: str | bytes, content: bytes | str) -> None:
        relb = rel.encode() if isinstance(rel, str) else rel
        full = os.path.join(os.fsencode(self.path), relb)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as f:
            f.write(content.encode() if isinstance(content, str) else content)

    def rm(self, rel: str | bytes) -> None:
        relb = rel.encode() if isinstance(rel, str) else rel
        os.remove(os.path.join(os.fsencode(self.path), relb))

    def mv(self, a: str, b: str) -> None:
        full_b = self.path / b
        full_b.parent.mkdir(parents=True, exist_ok=True)
        os.replace(self.path / a, full_b)

    def commit(self, msg: str, author: tuple[str, str] = ALICE) -> str:
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "--no-verify", "-m", msg, author=author)
        return self.head()

    def head(self) -> str:
        return self.git("rev-parse", "HEAD").decode().strip()

    def checkout(self, *args: str) -> None:
        self.git("checkout", "-q", *args)

    def merge(self, branch: str, msg: str = "merge") -> str:
        self.git("merge", "-q", "--no-ff", "--no-edit", "-m", msg, branch)
        return self.head()


def lines(n: int, tag: str = "x") -> str:
    return "".join(f"{tag} line {i}\n" for i in range(n))
