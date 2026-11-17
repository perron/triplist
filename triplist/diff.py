"""Parse unified diffs (git or plain) into per-file added and removed lines."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


@dataclass
class FileChange:
    path: str  # new path, or old path when the file was deleted
    old_path: Optional[str] = None
    status: str = "modified"  # added, deleted, modified, renamed, binary
    added: List[Tuple[int, str]] = field(default_factory=list)
    removed: List[Tuple[int, str]] = field(default_factory=list)

    def paths(self) -> List[str]:
        out = [self.path]
        if self.old_path and self.old_path != self.path:
            out.append(self.old_path)
        return out


def _strip_prefix(p: str) -> Optional[str]:
    p = p.split("\t", 1)[0].strip()
    if p.startswith('"') and p.endswith('"'):
        p = p[1:-1]
    if p == "/dev/null":
        return None
    if p.startswith(("a/", "b/")):
        p = p[2:]
    return p


def parse_diff(text: str) -> List[FileChange]:
    files: List[FileChange] = []
    cur: Optional[FileChange] = None
    old_ln = new_ln = 0
    old_left = new_left = 0
    in_hunk = False
    pending_old: Optional[str] = None
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("diff --git "):
            m = re.match(r'^diff --git ("?a/.+?"?) ("?b/.+"?)$', line)
            a = _strip_prefix(m.group(1)) if m else None
            b = _strip_prefix(m.group(2)) if m else None
            cur = FileChange(path=b or a or "", old_path=a)
            files.append(cur)
            in_hunk = False
            pending_old = None
        elif not in_hunk and line.startswith("rename from ") and cur is not None:
            cur.old_path = line[len("rename from "):]
            cur.status = "renamed"
        elif not in_hunk and line.startswith("rename to ") and cur is not None:
            cur.path = line[len("rename to "):]
            cur.status = "renamed"
        elif not in_hunk and line.startswith("new file mode") and cur is not None:
            cur.status = "added"
        elif not in_hunk and line.startswith("deleted file mode") and cur is not None:
            cur.status = "deleted"
        elif not in_hunk and line.startswith("Binary files ") and cur is not None:
            if cur.status == "modified":
                cur.status = "binary"
        elif in_hunk and cur is not None:
            if line.startswith("+"):
                cur.added.append((new_ln, line[1:]))
                new_ln += 1
                new_left -= 1
            elif line.startswith("-"):
                cur.removed.append((old_ln, line[1:]))
                old_ln += 1
                old_left -= 1
            elif line.startswith("\\"):
                pass
            else:  # context line (a blank line counts as context)
                old_ln += 1
                new_ln += 1
                old_left -= 1
                new_left -= 1
            if old_left <= 0 and new_left <= 0:
                in_hunk = False
        elif line.startswith("--- "):
            pending_old = line[4:]
            in_hunk = False
        elif line.startswith("+++ ") and pending_old is not None:
            old = _strip_prefix(pending_old)
            new = _strip_prefix(line[4:])
            if cur is None or (cur.added or cur.removed):
                cur = FileChange(path=new or old or "", old_path=old)
                files.append(cur)
            else:
                if new:
                    cur.path = new
                if old:
                    cur.old_path = old
            if old is None:
                cur.status = "added"
                cur.path = new or cur.path
            elif new is None:
                cur.status = "deleted"
                cur.path = old
            pending_old = None
        elif line.startswith("@@"):
            m = _HUNK.match(line)
            if m and cur is not None:
                old_ln = int(m.group(1))
                new_ln = int(m.group(3))
                old_left = int(m.group(2)) if m.group(2) is not None else 1
                new_left = int(m.group(4)) if m.group(4) is not None else 1
                in_hunk = old_left > 0 or new_left > 0
        i += 1
    return [f for f in files if f.path]

