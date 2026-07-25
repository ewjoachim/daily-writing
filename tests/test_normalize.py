from daily_writing import normalize


def test_normalize_writing__adds_frontmatter(make_writing):
    writing = make_writing(content="# 01 - Backpack\n\nSome content.\n")

    modified = normalize.normalize_writing(writing=writing, rewrite=False)

    assert modified is True
    new_text = writing.md_path.read_text()
    assert new_text.startswith("---")
    assert "full_title: 01 - Backpack" in new_text


def test_normalize_writing__skips_when_metadata_present(make_writing):
    writing = make_writing(
        content="---\nfull_title: 01 - Backpack\n"
        "prompts:\n  - {date: 2024-10-01, title: Backpack}\n"
        "---\nContent.\n",
    )
    original = writing.md_path.read_text()

    modified = normalize.normalize_writing(writing=writing, rewrite=False)

    assert modified is False
    assert writing.md_path.read_text() == original


def test_no_alias_dumper_ignores_aliases():
    dumper = normalize.NoAliasDumper(None)
    assert dumper.ignore_aliases(data=object()) is True
