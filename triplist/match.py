"""Decide which checklist items a diff triggers, with the evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from . import globs
from .checklist import Item
from .diff import FileChange


@dataclass
class Hit:
    item: Item
    evidence: List[str] = field(default_factory=list)


def _path_ok(item: Item, fc: FileChange) -> bool:
    paths = fc.paths()
    if item.exclude and any(globs.match(g, p) for g in item.exclude for p in paths):
        return False
    if not item.paths:
        return True
    return any(globs.match(g, p) for g in item.paths for p in paths)


def evaluate(item: Item, changes: List[FileChange], max_evidence: int = 3) -> List[str]:
    """Return evidence lines if the item fires, else an empty list.

    An item fires when at least one changed file passes its path filter
    (paths, minus exclude) and, if it has line patterns, one added or
    removed line in such a file matches one of them.
    """
    has_lines = bool(item.added or item.removed or item.changed)
    evidence: List[str] = []
    for fc in changes:
        if not _path_ok(item, fc):
            continue
        if not has_lines:
            evidence.append(f"{fc.path} ({fc.status})")
        else:
            checks = []
            for pat in item.compiled.get("added", []) + item.compiled.get("changed", []):
                checks += [("added", fc.path, ln, t, pat) for ln, t in fc.added]
            for pat in item.compiled.get("removed", []) + item.compiled.get("changed", []):
                checks += [("removed", fc.old_path or fc.path, ln, t, pat) for ln, t in fc.removed]
            for kind, path, ln, text, pat in checks:
                if pat.search(text):
                    evidence.append(f"{path}:{ln} {kind} line matches `{pat.pattern}`")
                    break
        if len(evidence) >= max_evidence:
            break
    return evidence


def run(items: List[Item], changes: List[FileChange]) -> List[Hit]:
    hits = []
    for it in items:
        ev = evaluate(it, changes)
        if ev:
            hits.append(Hit(it, ev))
    return hits
