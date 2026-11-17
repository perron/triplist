"""Path globs with ** support. A pattern without '/' matches the file name at any depth."""

from __future__ import annotations

import re
from functools import lru_cache


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
    return re.compile("^" + "".join(out) + "$")


def match(pattern: str, path: str) -> bool:
    return bool(_compile(pattern).match(path))
