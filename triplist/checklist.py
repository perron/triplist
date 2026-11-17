"""Read a checklist written in Markdown.

Each item is a '## <id>' heading followed by 'key: value' lines:

    ## resume-old-transcripts
    paths: src/session/**, src/messages/*.ts
    added: \\bnew_field\\b
    check: Does the new field load safely from old transcripts that lack it?
    why: INC-2041, PR #318

Keys: paths, exclude (comma-separated globs), added, removed, changed (one
regex per line; several lines of the same key mean "any of"), check
(required), why (optional). A line may start with '- '. Other text is
treated as notes and ignored, except a key that looks like a typo of a
known key (for example 'excludes:'), which is an error. Repeated check or
why lines are joined. Any other '#' heading ends the current item.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from . import globs

KEYS = ("paths", "exclude", "added", "removed", "changed", "check", "why")
_KEY_LINE = re.compile(r"^(?:[-*]\s+)?([A-Za-z_]+)\s*:\s?(.*)$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


@dataclass
class Item:
    id: str
    line: int
    paths: List[str] = field(default_factory=list)
    exclude: List[str] = field(default_factory=list)
    added: List[str] = field(default_factory=list)
    removed: List[str] = field(default_factory=list)
    changed: List[str] = field(default_factory=list)
    check: str = ""
    why: str = ""
    compiled: dict = field(default_factory=dict, repr=False)

    def has_trigger(self) -> bool:
        return bool(self.paths or self.added or self.removed or self.changed)


@dataclass
class Problem:
    line: int
    item: Optional[str]
    message: str
    severity: str = "error"  # error or warning

    def __str__(self) -> str:
        where = f"line {self.line}"
        if self.item:
            where += f" [{self.item}]"
        return f"{self.severity}: {where}: {self.message}"


def _split_globs(value: str) -> List[str]:
    """Split on commas that are not inside {braces}."""
    parts, depth, cur = [], 0, ""
    for c in value:
        if c == "{":
            depth += 1
        elif c == "}":
            depth = max(0, depth - 1)
        if c == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += c
    parts.append(cur)
    return [g.strip().strip("`") for g in parts if g.strip().strip("`")]


def _unquote(value: str) -> str:
    v = value.strip()
    if len(v) >= 2 and v[0] == "`" and v[-1] == "`":
        return v[1:-1]
    return v


def parse(text: str) -> Tuple[List[Item], List[Problem]]:
    items: List[Item] = []
    problems: List[Problem] = []
    cur: Optional[Item] = None
    in_fence = False
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.rstrip()
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if line.startswith("## "):
            ident = line[3:].strip()
            if not _ID.match(ident):
                problems.append(Problem(n, ident, "item id must be letters, digits, '.', '_' or '-' with no spaces"))
            cur = Item(id=ident, line=n)
            items.append(cur)
            continue
        if line.startswith("#"):
            cur = None  # a heading of another level ends the current item
            continue
        if cur is None:
            continue
        m = _KEY_LINE.match(stripped)
        if not m:
            continue
        key, value = m.group(1).lower(), m.group(2).strip()
        if key not in KEYS:
            close = difflib.get_close_matches(key, KEYS, n=1, cutoff=0.6)
            if close:
                problems.append(Problem(n, cur.id, f"unknown key '{m.group(1)}' (did you mean '{close[0]}'?)"))
            continue  # anything else is a note
        if not value:
            problems.append(Problem(n, cur.id, f"'{key}' has no value"))
            continue
        if key in ("paths", "exclude"):
            for g in _split_globs(value):
                bad = globs.validate(g)
                if bad:
                    problems.append(Problem(n, cur.id, f"bad glob '{g}' in '{key}': {bad}"))
                else:
                    getattr(cur, key).append(g)
        elif key in ("added", "removed", "changed"):
            pat = _unquote(value)
            try:
                cur.compiled.setdefault(key, []).append(re.compile(pat))
                getattr(cur, key).append(pat)
            except re.error as exc:
                problems.append(Problem(n, cur.id, f"bad regex in '{key}': {exc}"))
        else:
            prev = getattr(cur, key)
            setattr(cur, key, (prev + " " + value).strip() if prev else value)
    seen = {}
    for it in items:
        if it.id in seen:
            problems.append(Problem(it.line, it.id, f"duplicate id (first used on line {seen[it.id]})"))
        else:
            seen[it.id] = it.line
        if not it.check:
            problems.append(Problem(it.line, it.id, "missing 'check:' (the question a reviewer must answer)"))
        if not it.has_trigger():
            problems.append(Problem(it.line, it.id, "no trigger: add 'paths:', 'added:', 'removed:' or 'changed:'"))
    if not items:
        problems.append(Problem(1, None, "no items found: each item starts with a '## <id>' heading"))
    return items, problems
