from triplist.checklist import parse
from triplist.diff import FileChange
from triplist.match import run


def items(text):
    its, probs = parse(text)
    assert not [p for p in probs if p.severity == "error"], probs
    return its


def ids(hits):
    return [h.item.id for h in hits]


def test_paths_only_and_exclude():
    its = items("## m\npaths: migrations/**\nexclude: migrations/README.md\ncheck: c\n")
    assert ids(run(its, [FileChange("migrations/001.sql", added=[(1, "x")])])) == ["m"]
    assert ids(run(its, [FileChange("migrations/README.md")])) == []
    assert ids(run(its, [FileChange("src/a.py")])) == []


def test_paths_and_lines_must_both_hold_in_the_same_file():
    its = items("## s\npaths: src/session/**\nadded: workspaceId\ncheck: c\n")
    other = FileChange("src/other.ts", added=[(1, "workspaceId")])
    session = FileChange("src/session/t.ts", added=[(1, "name")])
    assert ids(run(its, [other, session])) == []
    session.added.append((2, "workspaceId: string"))
    hits = run(its, [other, session])
    assert ids(hits) == ["s"]
    assert hits[0].evidence == ["src/session/t.ts:2 added line matches `workspaceId`"]


def test_added_removed_changed_sides():
    its = items("## a\nadded: X\ncheck: c\n## r\nremoved: X\ncheck: c\n## ch\nchanged: X\ncheck: c\n")
    assert ids(run(its, [FileChange("f", added=[(1, "X")])])) == ["a", "ch"]
    assert ids(run(its, [FileChange("f", removed=[(1, "X")])])) == ["r", "ch"]


def test_rename_matches_old_path_and_removed_uses_old_name():
    its = items("## s\npaths: src/session/**\nremoved: legacy\ncheck: c\n")
    fc = FileChange("src/store/t.ts", old_path="src/session/t.ts", status="renamed",
                    removed=[(7, "legacy()")])
    hits = run(its, [fc])
    assert hits[0].evidence == ["src/session/t.ts:7 removed line matches `legacy`"]


def test_evidence_is_capped_but_counted():
    its = items("## any\npaths: **\ncheck: c\n")
    hits = run(its, [FileChange(f"f{i}") for i in range(10)])
    assert len(hits[0].evidence) == 3 and hits[0].files == 10


def test_exclude_uses_new_path_on_rename():
    its = items("## env\nadded: process\\.env\nexclude: **/*.test.ts\ncheck: c\n")
    fc = FileChange("src/a.ts", old_path="src/a.test.ts", status="renamed", added=[(2, "process.env.X")])
    assert ids(run(its, [fc])) == ["env"]
    fc2 = FileChange("src/a.test.ts", old_path="src/a.ts", status="renamed", added=[(2, "process.env.X")])
    assert ids(run(its, [fc2])) == []
