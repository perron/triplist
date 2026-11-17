# triplist

A reliability checklist that triggers on the diff. You keep one list of
lessons from past incidents. Each item says what kind of change it applies to.
`triplist check` reads a diff and prints only the items that change needs,
with the file and line that triggered each one.

**Before:** a reviewer, human or agent, has to remember every past outage, or
read a long checklist where most items don't apply.
**After:** one command prints the few checks this diff actually touches. In
CI it reads the checklist from the base branch, so a change can't edit its
own checks away.

Python 3.9+, standard library only, no model, no network. MIT license.

## Why

On Nov 16 2026 the Claude Code team described how they verify agent-written
code in [How the Claude Code team thinks about verification](https://claude.dev/blog/how-the-claude-code-team-thinks-about-verification/).
Two ideas from that post are the core of this tool:

- They keep a reliability checklist where each item has a trigger you can read
  from a diff, a check, and the incidents or PRs behind it. Only the items
  whose trigger matches are checked, so nobody has to memorize past outages.
- A change can't modify the checks that judge it. The rules are read from the
  base branch, not from the change.

They didn't publish a tool for this. triplist is an original, independent
version of the idea. It is not affiliated with Anthropic.

## Install

Not on PyPI yet. Install from a clone:

```sh
git clone https://github.com/perron/triplist
cd triplist
python3 -m venv .venv
. .venv/bin/activate
pip install .
```

## Quick start

Try it on the demo files in `examples/`. They are made-up demo data: the
incident names and PR numbers are not real.

```sh
triplist check --diff examples/demo.diff --file examples/TRIPLIST.md
```

Output:

```text
triplist: 2 of 6 checks triggered by 4 changed files (checklist: examples/TRIPLIST.md)

-> [resume-old-sessions] Does the new field load safely from old saved sessions that do not have it?
    why: Demo incident INC-12 (resume crashed on sessions saved before a field was added)
    trigger: src/session/types.ts:5 added line matches `^\s*\w+\??:\s`

-> [new-env-var] Is the new setting documented, and does the app still start when it is missing?
    why: Demo PR #41
    trigger: src/server/config.ts:11 added line matches `process\.env\.|os\.environ|getenv\(`
```

The demo checklist has 6 items. The diff changes 4 files. Two items fire.
`new-env-var` lists `config.ts` as its trigger but not `config.test.ts`,
because that item excludes test files. `README.md` triggers nothing.

In your own repo:

```sh
triplist init                        # writes a starter TRIPLIST.md
triplist lint                        # checks it for mistakes
git add TRIPLIST.md && git commit -m "Add reliability checklist"
triplist check                       # uncommitted changes vs HEAD
triplist check --base origin/main    # this branch vs main
```

## The checklist format

`TRIPLIST.md` is plain Markdown. Each item is a `## id` heading followed by
`key: value` lines. Other text is ignored, so you can add notes.

```markdown
## resume-old-sessions
paths: src/session/**
added: ^\s*\w+\??:\s
check: Does the new field load safely from old saved sessions that do not have it?
why: INC-12, PR #318
```

| Key | Meaning |
|---|---|
| `paths` | Comma-separated globs. `**` matches any number of folders. A glob with no `/` matches the file name at any depth. A plain folder path like `src/session` matches everything in it. |
| `exclude` | Globs for files this item ignores. |
| `added` | A regex tested against added lines. |
| `removed` | A regex tested against removed lines. |
| `changed` | A regex tested against added and removed lines. |
| `check` | Required. The question someone must answer. |
| `why` | Optional. The incident or PR behind the item. |

Repeat a regex key on several lines to mean "any of these". An item fires
when one changed file passes its path filter and, if the item has regexes,
one added or removed line in that same file matches. Renamed files match on
their old or new path. Each item needs at least one of `paths`, `added`,
`removed` or `changed`.

## Commands

```text
triplist check [--base REF [--head REF] | --staged | --diff FILE]
               [--file TRIPLIST.md] [--checklist-from base|worktree]
               [--checklist-ref REF]
               [--format text|markdown|json]
               [--enforce] [--ack ID] [--message-file FILE]
triplist lint [FILE]
triplist init [--file FILE]
```

Which diff, and where the checklist comes from:

| Mode | Diff | Checklist read from |
|---|---|---|
| (default) | uncommitted changes vs `HEAD` | `HEAD` |
| `--staged` | staged changes | `HEAD` |
| `--base REF` | `REF...HEAD` (from the merge base) | `REF` |
| `--diff FILE` | a unified diff file, `-` for stdin | the file on disk |

`--checklist-ref REF` reads the checklist from another ref in any mode, for
example `--staged --checklist-ref origin/main`, or
`--diff pr.diff --checklist-ref origin/main`. With `--base`, the checklist
comes from the tip of REF, and the diff starts at the merge base.

If the change edits the checklist itself, triplist still uses the copy from
the ref and prints a note. While you write a new checklist, use
`--checklist-from worktree`.

Each item shows up to 3 triggers, then a count of the other files.

`triplist lint` reports duplicate ids, missing `check:` lines, items with no
trigger, bad regexes, bad globs, and keys that look like typos of a real key
(such as `excludes:`). It cannot tell you that a trigger is too broad or
too narrow.

`--format markdown` prints a task list you can paste into a pull request or
hand to a coding agent. `--format json` is for scripts.

## Observe first, then enforce

By default `check` only reports and exits 0. Add `--enforce` to exit 1 when
a triggered item has not been acknowledged. An acknowledgement is a line the
author writes. It makes someone stop and answer the question; it does not
prove they did. Acknowledge an item with a
`Checked: <id>` line in a commit message on the branch (read with
`--base`), in a message file (`--message-file`), or with `--ack <id>`.

As a commit-msg hook (`.git/hooks/commit-msg`, made executable):

```sh
#!/bin/sh
exec triplist check --staged --enforce --message-file "$1" --checklist-ref origin/main
```

`--checklist-ref origin/main` matters here. Without it, the hook reads the
checklist from `HEAD`, which is your own branch, so an earlier commit on the
branch could weaken it. Drop the flag if your repo has no `origin/main`.
On a repo with no commits yet, the hook prints a note and lets the commit
through.

A commit that triggers `resume-old-sessions` is then blocked until its
message has a line like:

```text
Checked: resume-old-sessions - loaded three old sessions by hand
```

With `--base`, a `Checked: <id>` line in any commit on the branch covers
that item for the whole branch.

Exit codes: 0 ok, 1 enforce found unacknowledged items, 2 bad checklist,
missing file, or git error.

## Limits

- Triggers are globs and regexes on changed lines. triplist does not
  understand code. A trigger that is too broad fires too often. Tune it.
- The default mode uses `git diff HEAD`, which skips untracked files. Run
  `git add -N <file>` or use `--staged` to include new files.
- Binary files can match `paths` but never a line regex.
- Globs are case-sensitive. `**` and `{a,b}` work; POSIX classes like
  `[[:digit:]]` do not. Any other `#` heading in the file ends the current item.
- Regexes are Python regexes, and they are yours. A badly written one can be
  slow on a huge diff; there is no timeout.
- triplist tells you which questions to answer. It does not answer them.

## When to use something else

- **CODEOWNERS** if what you need is a named person or team to approve
  changes to some files. GitHub enforces that; triplist can't.
- **Danger** (danger.systems) if you want rules written as code with access
  to your CI and pull request API.
- **grep** if you have one rule. `git diff -U0 origin/main...HEAD | grep '^+.*getenv('`
  is fine for that.

triplist fits when you have a growing list of lessons, want each one tied to
the incident behind it, and want a coding agent or reviewer to see only the
ones that apply, offline, with no setup beyond one Markdown file.

## Contributing

Issues and pull requests are welcome. Run `pip install -e '.[dev]'` and
`pytest` before you send a change, and add a test for any behavior change.
If you change `examples/`, update the Quick start output: a test checks
that it matches. Coding agents should read [AGENTS.md](AGENTS.md) first.
You can also point your own agent at this repo and ask it to write a
TRIPLIST.md from your incident history, or to build its own version.

## License

MIT. See [LICENSE](LICENSE).
