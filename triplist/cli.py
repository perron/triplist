"""Command line: triplist check | lint | init."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Optional

from . import __version__, checklist, gitio, match
from .diff import parse_diff

DEFAULT_FILE = "TRIPLIST.md"

STARTER = """# Reliability checklist

Each item says when it applies (a trigger you can read from a diff), the
question to answer, and why it exists. `triplist check` prints only the
items this change triggers. Replace these examples with your own.

## example-migrations
paths: migrations/**, **/*.sql
check: Can this migration run twice safely, and is there a rollback?
why: Replace with the incident or PR that taught you this.

## example-new-env-var
added: os\\.environ|process\\.env|getenv\\(
check: Is the new setting documented, and does the app start when it is missing?
why: Replace with the incident or PR that taught you this.
"""


def _n(count: int, word: str) -> str:
    return f"{count} {word}" + ("" if count == 1 else "s")


def _read(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError as exc:
        raise gitio.GitError(f"cannot read {path}: {exc.strerror}")
    except UnicodeDecodeError:
        raise gitio.GitError(f"cannot read {path}: not UTF-8 text")


def _err(msg: str) -> None:
    print(f"triplist: {msg}", file=sys.stderr)


def cmd_init(a) -> int:
    if os.path.exists(a.file):
        _err(f"{a.file} already exists; not overwriting")
        return 2
    try:
        with open(a.file, "w", encoding="utf-8") as fh:
            fh.write(STARTER)
    except OSError as exc:
        _err(f"cannot write {a.file}: {exc.strerror}")
        return 2
    print(f"wrote {a.file} with 2 example items")
    return 0


def cmd_lint(a) -> int:
    try:
        text = _read(a.file)
    except gitio.GitError as exc:
        _err(str(exc))
        return 2
    items, problems = checklist.parse(text)
    for p in problems:
        print(f"{a.file}: {p}")
    errors = [p for p in problems if p.severity == "error"]
    print(f"{a.file}: {len(items)} items, {len(errors)} errors, {len(problems) - len(errors)} warnings")
    return 2 if errors else 0


def _load(a):
    """Return (diff_text, checklist_text, checklist_source, notes, acks) or raise."""
    notes: List[str] = []
    acks: List[str] = list(a.ack or [])
    if a.checklist_ref and a.checklist_from == "worktree":
        raise gitio.GitError("--checklist-ref and --checklist-from worktree cannot be used together")
    if a.message_file:
        acks += gitio.acks_in_text(_read(a.message_file))

    if a.diff is not None:
        if a.diff == "-":
            diff_text = sys.stdin.buffer.read().decode("utf-8", "replace")
        else:
            try:
                with open(a.diff, encoding="utf-8", errors="replace") as fh:
                    diff_text = fh.read()
            except OSError as exc:
                raise gitio.GitError(f"cannot read {a.diff}: {exc.strerror}")
        if not a.checklist_ref:
            return diff_text, _read(a.file), a.file, notes, acks
        top = gitio.toplevel()
        ref = a.checklist_ref
    else:
        top = gitio.toplevel()
        unborn = not a.base and not gitio.has_commits(top)
        if unborn and a.checklist_from != "worktree":
            raise NothingToCheck("no commits yet, so there is no checklist to read; skipping")
        if a.staged:
            diff_text = gitio.git(gitio.DIFF_ARGS + ["--cached"], top)
            ref = "HEAD"
        elif a.base:
            head = a.head or "HEAD"
            diff_text = gitio.git(gitio.DIFF_ARGS + [f"{a.base}...{head}"], top)
            ref = a.base
            acks += gitio.acks_in_range(a.base, head, top)
        else:
            diff_text = gitio.git(gitio.DIFF_ARGS + [gitio.EMPTY_TREE if unborn else "HEAD"], top)
            ref = "HEAD"
        ref = a.checklist_ref or ref

    rel = gitio.rel_to_top(a.file, top)
    if a.checklist_from == "worktree":
        text = _read(os.path.join(top, rel))
        source = f"{rel} (working tree)"
    else:
        text = gitio.show(ref, rel, top)
        if text is None:
            raise gitio.GitError(
                f"{rel} does not exist at {ref}. Commit it first, or pass "
                "--checklist-from worktree while you are writing it."
            )
        source = f"{rel} at {ref}"
        changed = {p for fc in parse_diff(diff_text) for p in fc.paths()}
        if rel in changed:
            notes.append(
                f"This change edits {rel}. Items were read from {ref}, so the "
                "change cannot rewrite the checks that judge it."
            )
    return diff_text, text, source, notes, acks


class NothingToCheck(Exception):
    pass


def cmd_check(a) -> int:
    try:
        diff_text, text, source, notes, acks = _load(a)
    except NothingToCheck as exc:
        print(f"triplist: {exc}")
        return 0
    except gitio.GitError as exc:
        _err(str(exc))
        return 2
    items, problems = checklist.parse(text)
    errors = [p for p in problems if p.severity == "error"]
    if errors:
        for p in errors:
            _err(f"{source}: {p}")
        _err("fix the checklist first (see `triplist lint`)")
        return 2
    changes = parse_diff(diff_text)
    hits = match.run(items, changes)
    ack_set = {x.lower() for x in acks}
    missing = [h for h in hits if h.item.id.lower() not in ack_set]

    if a.format == "json":
        print(json.dumps({
            "checklist": source,
            "files_changed": len(changes),
            "items_total": len(items),
            "notes": notes,
            "triggered": [
                {"id": h.item.id, "check": h.item.check, "why": h.item.why,
                 "evidence": h.evidence, "files": h.files,
                 "acknowledged": h not in missing}
                for h in hits
            ],
        }, indent=2))
    elif a.format == "markdown":
        print(f"### Checks for this change ({len(hits)} of {len(items)})\n")
        for n in notes:
            print(f"> {n}\n")
        if not hits:
            print("No checklist items are triggered by this diff.")
        for h in hits:
            box = "x" if h not in missing else " "
            print(f"- [{box}] **{h.item.id}**: {h.item.check}")
            if h.item.why:
                print(f"  - Why: {h.item.why}")
            for e in h.evidence:
                print(f"  - Trigger: {e}")
            if h.files > len(h.evidence):
                print(f"  - ...and {_n(h.files - len(h.evidence), 'more file')}")
    else:
        print(f"triplist: {len(hits)} of {_n(len(items), 'check')} triggered by "
              f"{_n(len(changes), 'changed file')} (checklist: {source})")
        for n in notes:
            print(f"note: {n}")
        for h in hits:
            mark = "ok " if h not in missing else "-> "
            print(f"\n{mark}[{h.item.id}] {h.item.check}")
            if h.item.why:
                print(f"    why: {h.item.why}")
            for e in h.evidence:
                print(f"    trigger: {e}")
            if h.files > len(h.evidence):
                print(f"    ...and {_n(h.files - len(h.evidence), 'more file')}")

    if a.enforce and missing:
        ids = ", ".join(h.item.id for h in missing)
        _err(f"{_n(len(missing), 'triggered check')} not acknowledged: {ids}")
        _err("add a 'Checked: <id>' line to the commit message for each one you have answered")
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="triplist",
        description="A reliability checklist that triggers on the diff: print only the checks this change needs.",
    )
    p.add_argument("--version", action="version", version=f"triplist {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="print the checklist items this diff triggers")
    src = c.add_mutually_exclusive_group()
    src.add_argument("--base", metavar="REF", help="compare REF...HEAD (merge base); read the checklist from REF")
    src.add_argument("--staged", action="store_true", help="check staged changes; read the checklist from HEAD")
    src.add_argument("--diff", metavar="FILE", help="read a unified diff from FILE ('-' for stdin) instead of git")
    c.add_argument("--head", metavar="REF", help="head ref for --base (default HEAD)")
    c.add_argument("--file", default=DEFAULT_FILE, help=f"checklist path (default {DEFAULT_FILE})")
    c.add_argument("--checklist-from", choices=["base", "worktree"], default="base",
                   help="read the checklist from the base ref (default) or the working tree")
    c.add_argument("--checklist-ref", metavar="REF",
                   help="read the checklist from REF instead (for example origin/main); works with --diff too")
    c.add_argument("--format", choices=["text", "markdown", "json"], default="text")
    c.add_argument("--enforce", action="store_true",
                   help="exit 1 if a triggered item has no 'Checked: <id>' acknowledgement line")
    c.add_argument("--ack", action="append", metavar="ID", help="treat ID as acknowledged (repeatable)")
    c.add_argument("--message-file", metavar="FILE", help="also read 'Checked: <id>' lines from FILE (for a commit-msg hook)")
    c.set_defaults(func=cmd_check)

    l = sub.add_parser("lint", help="check the checklist file for mistakes")
    l.add_argument("file", nargs="?", default=DEFAULT_FILE)
    l.set_defaults(func=cmd_lint)

    i = sub.add_parser("init", help=f"write a starter {DEFAULT_FILE}")
    i.add_argument("--file", default=DEFAULT_FILE)
    i.set_defaults(func=cmd_init)
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if getattr(args, "head", None) and not getattr(args, "base", None):
        _err("--head needs --base")
        return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
