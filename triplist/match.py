"""Decide which checklist items a diff triggers, with the evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from . import globs
from .checklist import Item
from .diff import FileChange


@dataclass
class Hit:
    item: Item
    evidence: List[str] = field(default_factory=list)
    files: int = 0  # how many changed files triggered the item (evidence is capped)


def _path_ok(item: Item, fc: FileChange) -> bool:
    paths = fc.paths()
    # exclude looks at the file as it is after the change (its new path)
    if item.exclude and any(globs.match(g, fc.path) for g in item.exclude):
        return False
    if not item.paths:
        return True
    return any(globs.match(g, p) for g in item.paths for p in paths)


def evaluate(item: Item, changes: List[FileChange], max_evidence: int = 3) -> Tuple[List[str], int]:
    """Return (evidence, number of files that triggered the item).

    An item fires when at least one changed file passes its path filter
    (paths, minus exclude) and, if it has line patterns, one added or
    removed line in that file matches one of them. Evidence is capped at
    max_evidence lines; the count is not.
    """
    added_pats = item.compiled.get("added", []) + item.compiled.get("changed", [])
    removed_pats = item.compiled.get("removed", []) + item.compiled.get("changed", [])
    has_lines = bool(added_pats or removed_pats)
    evidence: List[str] = []
    count = 0
    for fc in changes:
        if not _path_ok(item, fc):
            continue
        found = None
        if not has_lines:
            found = f"{fc.path} ({fc.status})"
        else:
            found = _first_line_hit(added_pats, fc.added, "added", fc.path) or _first_line_hit(
                removed_pats, fc.removed, "removed", fc.old_path or fc.path)
        if found:
            count += 1
            if len(evidence) < max_evidence:
                evidence.append(found)
    return evidence, count


def _first_line_hit(pats, lines, kind, path) -> Optional[str]:
    for pat in pats:
        for ln, text in lines:
            if pat.search(text):
                return f"{path}:{ln} {kind} line matches `{pat.pattern}`"
    return None


def run(items: List[Item], changes: List[FileChange]) -> List[Hit]:
    hits = []
    for it in items:
        ev, count = evaluate(it, changes)
        if count:
            hits.append(Hit(it, ev, count))
    return hits
