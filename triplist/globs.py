"""Path globs with ** and {a,b} support.

A pattern without '/' matches the file name at any depth. Matching is
case-sensitive. POSIX classes like [[:digit:]] are reported as bad globs.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import List, Optional


@lru_cache(maxsize=512)
def _compile(pattern: str) -> "re.Pattern[str]":
    pat = pattern.strip()
    if pat.startswith("./"):
        pat = pat[2:]
    if pat.startswith("/"):
        pat = pat[1:]
    if "/" not in pat.rstrip("/"):
        pat = "**/" + pat
    if pat.endswith("/"):
        pat += "**"
    try:
        return re.compile("^" + _translate(pat) + "$")
    except re.error as exc:
        raise ValueError(str(exc))


def _split_top(body: str) -> List[str]:
    parts, depth, cur = [], 0, ""
    for c in body:
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        if c == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += c
    parts.append(cur)
    return parts


def _translate(pat: str) -> str:
    out = []
    i = 0
    while i < len(pat):
        c = pat[i]
        if pat.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pat.startswith("**", i):
            out.append(".*")
            i += 2
        elif c == "*":
            out.append("[^/]*")
            i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        elif c == "{":
            depth, j = 0, i
            while j < len(pat):
                if pat[j] == "{":
                    depth += 1
                elif pat[j] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            if j >= len(pat):
                raise ValueError("unclosed '{' in glob")
            alts = _split_top(pat[i + 1:j])
            out.append("(?:" + "|".join(_translate(x) for x in alts) + ")")
            i = j + 1
        elif c == "}":
            raise ValueError("'}' without '{' in glob")
        elif c == "[":
            if pat.startswith("[[:", i):
                raise ValueError("POSIX classes like [[:digit:]] are not supported; use [0-9]")
            j = pat.find("]", i + 1)
            if j == -1:
                raise ValueError("unclosed '[' in glob")
            body = pat[i + 1:j]
            if body.startswith("!"):
                body = "^" + body[1:]
            out.append("[" + body.replace("\\", "\\\\") + "]")
            i = j + 1
        else:
            out.append(re.escape(c))
            i += 1
    return "".join(out)


def validate(pattern: str) -> Optional[str]:
    """Return an error message, or None if the glob is usable."""
    if not pattern.strip():
        return "empty glob"
    try:
        _compile(pattern)
    except ValueError as exc:
        return str(exc)
    return None


_MAGIC = set("*?[")


def match(pattern: str, path: str) -> bool:
    if _compile(pattern).match(path):
        return True
    # A plain path with no wildcards also matches everything under it, like "src/session".
    plain = pattern.strip()
    if plain.startswith("./"):
        plain = plain[2:]
    plain = plain.strip("/")
    return bool(plain) and not (_MAGIC & set(plain)) and "/" in plain and path.startswith(plain + "/")
