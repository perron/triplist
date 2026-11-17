import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from triplist.cli import main

ROOT = Path(__file__).resolve().parent.parent
CHECKLIST = "## session\npaths: src/session/**\ncheck: Old sessions still load?\nwhy: INC-1\n\n## env\nadded: getenv\\(\ncheck: Documented?\n"


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "config", "user.email", "t@example.com")
    git(tmp_path, "config", "user.name", "T")
    (tmp_path / "TRIPLIST.md").write_text(CHECKLIST)
    (tmp_path / "src" / "session").mkdir(parents=True)
    (tmp_path / "src" / "session" / "s.py").write_text("a = 1\n")
    (tmp_path / "app.py").write_text("x = 1\n")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "base")
    git(tmp_path, "checkout", "-q", "-b", "feature")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def commit(repo, msg):
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", msg)


def test_base_mode_triggers_and_reads_checklist_from_base(repo, capsys):
    (repo / "src/session/s.py").write_text("a = 1\nb = 2\n")
    (repo / "app.py").write_text("x = os.getenv('X')\n")
    # The change also tries to delete the session check. It must still apply.
    (repo / "TRIPLIST.md").write_text("## env\nadded: getenv\\(\ncheck: Documented?\n")
    commit(repo, "feature")
    assert main(["check", "--base", "main"]) == 0
    out = capsys.readouterr().out
    assert "2 of 2 checks triggered by 3 changed files (checklist: TRIPLIST.md at main)" in out
    assert "[session] Old sessions still load?" in out
    assert "app.py:1 added line matches `getenv\\(`" in out
    assert "note: This change edits TRIPLIST.md" in out


def test_enforce_uses_commit_trailers(repo, capsys):
    (repo / "src/session/s.py").write_text("a = 2\n")
    commit(repo, "change session")
    assert main(["check", "--base", "main", "--enforce"]) == 1
    assert "not acknowledged: session" in capsys.readouterr().err
    (repo / "src/session/s.py").write_text("a = 3\n")
    commit(repo, "more\n\nChecked: session - old files tested by hand")
    assert main(["check", "--base", "main", "--enforce"]) == 0
    assert "ok [session]" in capsys.readouterr().out


def test_staged_with_message_file_and_ack(repo, tmp_path_factory, capsys):
    (repo / "app.py").write_text("y = os.getenv('Y')\n")
    git(repo, "add", "app.py")
    msg = tmp_path_factory.mktemp("m") / "MSG"
    msg.write_text("add Y\n\nchecked: ENV\n")
    assert main(["check", "--staged", "--enforce"]) == 1
    assert main(["check", "--staged", "--enforce", "--message-file", str(msg)]) == 0
    assert main(["check", "--staged", "--enforce", "--ack", "env"]) == 0
    capsys.readouterr()


def test_default_mode_is_uncommitted_changes_vs_head(repo, capsys):
    assert main(["check"]) == 0
    assert "0 of 2 checks triggered by 0 changed files" in capsys.readouterr().out
    (repo / "src/session/s.py").write_text("a = 5\n")
    assert main(["check"]) == 0
    assert "[session]" in capsys.readouterr().out


def test_runs_from_subdirectory(repo, capsys):
    (repo / "src/session/s.py").write_text("a = 6\n")
    os.chdir(repo / "src")
    assert main(["check", "--file", "../TRIPLIST.md"]) == 0
    assert "checklist: TRIPLIST.md at HEAD" in capsys.readouterr().out


def test_missing_checklist_at_ref(repo, capsys):
    (repo / "NEW.md").write_text(CHECKLIST)
    assert main(["check", "--file", "NEW.md"]) == 2
    assert "does not exist at HEAD" in capsys.readouterr().err
    assert main(["check", "--file", "NEW.md", "--checklist-from", "worktree"]) == 0


def test_json_and_markdown(repo, capsys):
    (repo / "src/session/s.py").write_text("a = 7\n")
    assert main(["check", "--format", "json", "--ack", "session"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["triggered"][0]["id"] == "session"
    assert data["triggered"][0]["acknowledged"] is True
    assert main(["check", "--format", "markdown"]) == 0
    md = capsys.readouterr().out
    assert "- [ ] **session**: Old sessions still load?" in md


def test_bad_checklist_and_bad_ref(repo, capsys):
    assert main(["check", "--base", "nope"]) == 2
    assert "triplist: git" in capsys.readouterr().err
    (repo / "TRIPLIST.md").write_text("## x\ncheck: no trigger\n")
    commit(repo, "break")
    assert main(["check"]) == 2
    assert "no trigger" in capsys.readouterr().err
    assert main(["lint"]) == 2


def test_head_requires_base(repo, capsys):
    assert main(["check", "--head", "main"]) == 2


def test_init_does_not_overwrite(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["init"]) == 0
    assert main(["lint"]) == 0
    assert main(["init"]) == 2


def test_readme_demo_output_matches():
    """The README shows this command's output verbatim."""
    out = subprocess.run(
        [sys.executable, "-m", "triplist", "check", "--diff", "examples/demo.diff", "--file", "examples/TRIPLIST.md"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout
    readme = (ROOT / "README.md").read_text()
    assert out.strip() in readme


def test_checklist_ref_protects_staged_hook(repo, capsys):
    # The branch guts its own checklist in one commit...
    (repo / "TRIPLIST.md").write_text("## noop\npaths: nothing/**\ncheck: c\n")
    commit(repo, "simplify checklist")
    (repo / "src/session/s.py").write_text("a = 8\n")
    git(repo, "add", "-A")
    # ...so HEAD no longer has the session item,
    assert main(["check", "--staged", "--enforce"]) == 0
    # but reading from main still catches it.
    assert main(["check", "--staged", "--enforce", "--checklist-ref", "main"]) == 1
    assert "checklist: TRIPLIST.md at main" in capsys.readouterr().out


def test_diff_file_with_checklist_ref(repo, capsys):
    (repo / "TRIPLIST.md").write_text("## noop\npaths: nothing/**\ncheck: c\n")
    commit(repo, "simplify checklist")
    (repo / "src/session/s.py").write_text("a = 9\n")
    commit(repo, "touch")
    diff = subprocess.run(["git", "diff", "main...HEAD"], cwd=repo, capture_output=True, text=True).stdout
    (repo / "pr.diff").write_text(diff)
    assert main(["check", "--diff", "pr.diff", "--checklist-ref", "main"]) == 0
    out = capsys.readouterr().out
    assert "[session]" in out and "note: This change edits TRIPLIST.md" in out


def test_unborn_head_is_skipped(tmp_path, monkeypatch, capsys):
    git(tmp_path, "init", "-q")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "TRIPLIST.md").write_text(CHECKLIST)
    git(tmp_path, "add", "-A")
    assert main(["check", "--staged", "--enforce"]) == 0
    assert "no commits yet" in capsys.readouterr().out


def test_respects_odd_user_diff_config(repo, capsys):
    git(repo, "config", "diff.mnemonicPrefix", "true")
    git(repo, "config", "diff.noprefix", "true")
    (repo / "src/session/s.py").write_text("a = 10\n")
    os.chmod(repo / "app.py", 0o755)
    assert main(["check", "--format", "json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["files_changed"] == 2
    assert [t["id"] for t in data["triggered"]] == ["session"]


def test_more_files_line(repo, capsys):
    for i in range(5):
        (repo / f"src/session/n{i}.py").write_text("x\n")
    git(repo, "add", "-A")
    assert main(["check", "--staged"]) == 0
    assert "...and 2 more files" in capsys.readouterr().out


def test_scissors_and_indented_lines_do_not_ack(repo, tmp_path_factory, capsys):
    (repo / "app.py").write_text("z = os.getenv('Z')\n")
    git(repo, "add", "app.py")
    msg = tmp_path_factory.mktemp("m") / "MSG"
    msg.write_text("add Z\n\n    Checked: env\n# ------------------------ >8 ------------------------\nChecked: env\n")
    assert main(["check", "--staged", "--enforce", "--message-file", str(msg)]) == 1
    capsys.readouterr()


def test_unknown_ref_and_conflicting_flags(repo, capsys):
    assert main(["check", "--checklist-ref", "origin/mian"]) == 2
    assert "unknown ref 'origin/mian'" in capsys.readouterr().err
    assert main(["check", "--checklist-ref", "main", "--checklist-from", "worktree"]) == 2


def test_unborn_head_with_worktree_checklist(tmp_path, monkeypatch, capsys):
    git(tmp_path, "init", "-q")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "TRIPLIST.md").write_text(CHECKLIST)
    (tmp_path / "src" / "session").mkdir(parents=True)
    (tmp_path / "src" / "session" / "s.py").write_text("a\n")
    git(tmp_path, "add", "-A")
    assert main(["check", "--staged", "--checklist-from", "worktree"]) == 0
    assert "[session]" in capsys.readouterr().out
    assert main(["check", "--checklist-from", "worktree"]) == 0
    assert "[session]" in capsys.readouterr().out


def test_bad_paths_and_encoding_exit_2(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--file", "nope/TRIPLIST.md"]) == 2
    (tmp_path / "TRIPLIST.md").write_bytes(b"## a\npaths: x\ncheck: caf\xe9?\n")
    assert main(["lint"]) == 2
    assert "not UTF-8" in capsys.readouterr().err
