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
