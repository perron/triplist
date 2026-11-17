import pytest

from triplist.globs import match


@pytest.mark.parametrize("pat,path,ok", [
    ("src/session/**", "src/session/a.ts", True),
    ("src/session/**", "src/session/deep/b.ts", True),
    ("src/session/**", "src/sessions/a.ts", False),
    ("src/session/", "src/session/x/y", True),
    ("*.sql", "db/migrations/001.sql", True),
    ("*.sql", "a.sqlx", False),
    ("**/*.test.ts", "config.test.ts", True),
    ("**/*.test.ts", "src/x/config.test.ts", True),
    ("src/*.ts", "src/a/b.ts", False),
    ("src/?.ts", "src/a.ts", True),
    ("src/[ab].ts", "src/b.ts", True),
    ("src/[!ab].ts", "src/b.ts", False),
    ("/README.md", "README.md", True),
    ("./docs/**", "docs/x.md", True),
    ("a+b/(c).txt", "a+b/(c).txt", True),
])
def test_match(pat, path, ok):
    assert match(pat, path) is ok


def test_plain_folder_path_matches_contents():
    assert match("src/session", "src/session/a.ts")
    assert match("src/session", "src/session")
    assert not match("src/session", "src/sessions/a.ts")
    assert match("./src/session", "src/session/a.ts")


def test_braces():
    assert match("src/**/*.{ts,tsx}", "src/a/b.tsx")
    assert match("src/**/*.{ts,tsx}", "src/b.ts")
    assert not match("src/**/*.{ts,tsx}", "src/b.js")
    assert match("{app,lib}/*.py", "lib/x.py")


def test_validate():
    from triplist.globs import validate
    assert validate("src/**") is None
    assert validate("src/[z-a].ts")
    assert validate("src/{a,b")
    assert validate("a}")
