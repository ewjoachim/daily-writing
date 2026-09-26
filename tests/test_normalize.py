from daily_writing import normalize


def test_normalize_writing__adds_frontmatter(make_writing):
    writing = make_writing(
        content="""\
# 01 - Backpack

Some content.
"""
    )

    modified = normalize.normalize_writing(writing=writing)

    assert modified is True
    assert (
        writing.md_path.read_text(encoding="utf-8")
        == """\
---
date: 2024-10-01
full_title: 01 - Backpack
prompts:
- date: 2024-10-01
  original_prompt: backpack
  title: Backpack
---
# 01 - Backpack

Some content.
"""
    )


def test_normalize_writing__fills_missing_keeps_existing(make_writing):
    writing = make_writing(
        content="""\
---
full_title: Custom
prompts:
  - {date: 2024-10-01, title: Explicit}
---
Content...
"""
    )

    modified = normalize.normalize_writing(writing=writing)

    assert modified is True
    assert (
        writing.md_path.read_text(encoding="utf-8")
        == """\
---
date: 2024-10-01
full_title: Custom
prompts:
- date: 2024-10-01
  original_prompt: backpack
  title: Explicit
---
Content …
"""
    )


def test_normalize_writing__idempotent(make_writing):
    writing = make_writing(
        content="""\
# 01 - Backpack

Some content.
"""
    )
    normalize.normalize_writing(writing=writing)
    writing = make_writing(content=writing.md_path.read_text(encoding="utf-8"))

    assert normalize.normalize_writing(writing=writing) is False


def test_normalize_writing__converts_single_prompt_frontmatter(make_writing):
    writing = make_writing(
        content="""\
---
title: Explicit
---
Content.
"""
    )

    normalize.normalize_writing(writing=writing)

    assert (
        writing.md_path.read_text(encoding="utf-8")
        == """\
---
date: 2024-10-01
full_title: 01 - Explicit
prompts:
- date: 2024-10-01
  original_prompt: backpack
  title: Explicit
---
Content.
"""
    )


def test_no_alias_dumper_ignores_aliases():
    dumper = normalize.NoAliasDumper(None)
    assert dumper.ignore_aliases(data=object()) is True
