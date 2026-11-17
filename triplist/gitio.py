"""Small git helpers. All calls are read-only."""

from __future__ import annotations

import os
import re
import subprocess
from typing import List, Optional

DIFF_ARGS = [
    "diff", "--no-color", "--no-ext-diff", "--no-textconv", "--no-relative",
    "--src-prefix=a/", "--dst-prefix=b/", "-M", "-U0",
]
TRAILER = re.compile(r"^Checked:[ \t]*([A-Za-z0-9][A-Za-z0-9._-]*)", re.M | re.I)
SCISSORS = "# ------------------------ >8 ------------------------"
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


class GitError(Exception):
    pass


def git(args: List[str], cwd: Optional[str] = None) -> str:
    try:
        out = subprocess.run(
            ["git", "-c", "core.quotepath=off"] + args,
            cwd=cwd, capture_output=True, check=False,
        )
    except FileNotFoundError:
        raise GitError("git is not installed")
    if out.returncode != 0:
        msg = out.stderr.decode("utf-8", "replace").strip() or "git failed"
        raise GitError(f"git {' '.join(args)}: {msg}")
    return out.stdout.decode("utf-8", "replace")


def toplevel(cwd: Optional[str] = None) -> str:
    return git(["rev-parse", "--show-toplevel"], cwd).strip()


def rel_to_top(path: str, top: str) -> str:
    return os.path.relpath(os.path.abspath(path), top).replace(os.sep, "/")


def show(ref: str, path: str, cwd: Optional[str] = None) -> Optional[str]:
    """Return the file at ref, or None if it does not exist there."""
    try:
        git(["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"], cwd)
    except GitError:
        raise GitError(f"unknown ref '{ref}' (check the name, or run git fetch)")
    try:
        return git(["show", f"{ref}:{path}"], cwd)
    except GitError:
        return None


def acks_in_text(text: str) -> List[str]:
    """'Checked: <id>' lines at the start of a line, above git's scissors line."""
    text = text.split(SCISSORS, 1)[0]
    return [m.group(1) for m in TRAILER.finditer(text)]


def acks_in_range(base: str, head: str, cwd: Optional[str] = None) -> List[str]:
    log = git(["log", "--format=%B%x00", f"{base}..{head}"], cwd)
    return acks_in_text(log)


def has_commits(cwd: Optional[str] = None) -> bool:
    try:
        git(["rev-parse", "--verify", "--quiet", "HEAD"], cwd)
        return True
    except GitError:
        return False
