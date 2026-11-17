from triplist.diff import parse_diff

GIT = """diff --git a/a.py b/a.py
index 1..2 100644
--- a/a.py
+++ b/a.py
@@ -3,3 +3,3 @@ def f():
 keep
--- this removed line looks like a header
+++ this added line looks like a header
 keep
\\ No newline at end of file
@@ -20 +20,2 @@
-old
+new1
+new2
diff --git a/old/name.py b/new/name.py
similarity index 90%
rename from old/name.py
rename to new/name.py
index 3..4 100644
--- a/old/name.py
+++ b/new/name.py
@@ -1 +1 @@
-x = 1
+x = 2
diff --git a/gone.txt b/gone.txt
deleted file mode 100644
index 5..0
--- a/gone.txt
+++ /dev/null
@@ -1,2 +0,0 @@
-bye
-now
diff --git a/new.txt b/new.txt
new file mode 100644
index 0..6
--- /dev/null
+++ b/new.txt
@@ -0,0 +1 @@
+hello
diff --git a/img.png b/img.png
index 7..8 100644
Binary files a/img.png and b/img.png differ
"""


def by_path(files):
    return {f.path: f for f in files}


def test_git_diff_lines_and_numbers():
    f = by_path(parse_diff(GIT))
    a = f["a.py"]
    assert a.removed == [(4, "-- this removed line looks like a header"), (20, "old")]
    assert a.added == [(4, "++ this added line looks like a header"), (20, "new1"), (21, "new2")]


def test_rename_delete_add_binary():
    f = by_path(parse_diff(GIT))
    r = f["new/name.py"]
    assert r.status == "renamed" and r.old_path == "old/name.py"
    assert r.paths() == ["new/name.py", "old/name.py"]
    assert f["gone.txt"].status == "deleted"
    assert f["gone.txt"].removed == [(1, "bye"), (2, "now")]
    assert f["new.txt"].status == "added" and f["new.txt"].added == [(1, "hello")]
    assert f["img.png"].status == "binary"
    assert len(f) == 5


def test_plain_diff_without_git_headers():
    text = """--- a/x.txt\t2026-01-01
+++ b/x.txt\t2026-01-02
@@ -1,2 +1,2 @@
 same
-before
+after
--- y.txt
+++ y.txt
@@ -1 +1 @@
-1
+2
"""
    f = by_path(parse_diff(text))
    assert f["x.txt"].added == [(2, "after")]
    assert f["y.txt"].removed == [(1, "1")]


def test_blank_context_line_counts():
    text = "--- a/z\n+++ b/z\n@@ -1,3 +1,3 @@\n a\n\n-b\n+c\n"
    (z,) = parse_diff(text)
    assert z.added == [(3, "c")] and z.removed == [(3, "b")]


def test_empty_input():
    assert parse_diff("") == []
