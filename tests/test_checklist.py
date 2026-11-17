from triplist.checklist import parse


def test_parse_item_fields():
    items, problems = parse("""# Title
intro text: with a colon before any item is ignored

## one
- paths: src/**, `lib/*.py`
paths: more/**
added: `foo\\(`
added: bar
removed: baz
changed: qux
exclude: tests/**
check: First part
check: second part.
why: INC-1
Some free note line
""")
    assert problems == []
    (it,) = items
    assert it.paths == ["src/**", "lib/*.py", "more/**"]
    assert it.added == ["foo\\(", "bar"]
    assert it.removed == ["baz"] and it.changed == ["qux"]
    assert it.exclude == ["tests/**"]
    assert it.check == "First part second part."
    assert it.why == "INC-1"


def test_lint_problems():
    items, problems = parse("""## dup
paths: a
check: x
## dup
paths: b
check: y
## no-check
paths: c
## no-trigger
check: z
## bad-re
added: (unclosed
check: q
## has space
paths: d
check: e
## typo
pahts: e
paths: e
check: f
""")
    msgs = [str(p) for p in problems]
    assert any("duplicate id" in m for m in msgs)
    assert any("[no-check]" in m and "missing 'check:'" in m for m in msgs)
    assert any("[no-trigger]" in m and "no trigger" in m for m in msgs)
    assert any("[bad-re]" in m and "bad regex" in m for m in msgs)
    assert any("[has space]" in m and "item id" in m for m in msgs)
    assert any(m.startswith("warning") and "pahts" in m for m in msgs)


def test_fenced_code_is_ignored_and_other_heading_ends_item():
    items, problems = parse("""## a
paths: x
check: c
```
## not-an-item
paths: y
```
### Notes
paths: should-not-attach
""")
    assert [i.id for i in items] == ["a"]
    assert items[0].paths == ["x"]


def test_empty_file():
    items, problems = parse("just text\n")
    assert items == [] and "no items" in str(problems[0])
