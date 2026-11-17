"""Path globs with ** and {a,b} support.

A pattern without '/' matches the file name at any depth. Matching is
case-sensitive. POSIX classes like [[:digit:]] are not supported.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Optional


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
            j = pat.find("}", i + 1)
            if j == -1 or "{" in pat[i + 1:j]:
                raise ValueError("unclosed or nested '{' in glob")
            alts = pat[i + 1:j].split(",")
            out.append("(?:" + "|".join(_compile_part(a) for a in alts) + ")")
            i = j + 1
        elif c == "}":
            raise ValueError("'}' without '{' in glob")
        elif c == "[":
            j = pat.find("]", i + 1)
            if j == -1:
                out.append(re.escape(c))
                i += 1
            else:
                body = pat[i + 1:j]
                if body.startswith("!"):
                    body = "^" + body[1:]
                out.append("[" + body.replace("\\", "\\\\") + "]")
                i = j + 1
        else:
            out.append(re.escape(c))
            i += 1
    try:
        return re.compile("^" + "".join(out) + "$")
    except re.error as exc:
        raise ValueError(str(exc))


def _compile_part(text: str) -> str:
    """Regex for one brace alternative: * and ? only, no slashes rules."""
    out = []
    for c in text:
        if c == "*":
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(c))
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
