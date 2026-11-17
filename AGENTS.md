# AGENTS.md

Notes for coding agents working on triplist.

- Python 3.9+, standard library only at runtime. Do not add runtime dependencies.
- Layout: `triplist/diff.py` (unified diff parser), `triplist/globs.py` (path globs with `**`), `triplist/checklist.py` (TRIPLIST.md parser and lint), `triplist/match.py` (which items fire, with evidence), `triplist/gitio.py` (read-only git calls), `triplist/cli.py` (commands, output, exit codes).
- Git use must stay read-only. Never write to the repo being checked.
- Exit codes: 0 ok, 1 `--enforce` found unacknowledged items, 2 bad checklist, missing file or git error. Keep them stable.
- In git modes the checklist is read from the base ref, not the working tree. Do not change that default.
- Every behavior change needs a test in `tests/`. Run `pytest` before you finish.
- `examples/` is demo data. If you change it, rerun the Quick start command and paste the exact output into README.md; `test_readme_demo_output_matches` checks it.
