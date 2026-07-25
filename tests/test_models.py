import datetime

import pytest

from daily_writing import i18n, models


def test_partial_prompt_combine__first_wins():
    combined = models.PartialPrompt.combine(
        models.PartialPrompt(title=None, original_prompt="orig"),
        models.PartialPrompt(title="from second", date=datetime.date(2024, 10, 1)),
    )
    assert combined.title == "from second"
    assert combined.original_prompt == "orig"
    assert combined.date == datetime.date(2024, 10, 1)


def test_partial_prompt_combine__ignores_none():
    assert models.PartialPrompt.combine(None, None) == models.PartialPrompt()


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ({"prompts": []}, "multiple"),
        ({"title": "x"}, "single"),
        ("not a dict", "single"),
    ],
)
def test_select_model(value, expected):
    assert models.select_model(value) == expected


def test_extract_filename_prompts():
    prompts = list(models.extract_filename_prompts(year=2024, month=10, stem="01-foo"))
    assert len(prompts) == 1
    assert prompts[0].date == datetime.date(2024, 10, 1)
    assert prompts[0].original_prompt == "foo"


def test_extract_filename_prompts__multiple():
    prompts = list(
        models.extract_filename_prompts(year=2024, month=10, stem="1-foo-2-bar")
    )
    assert [p.date.day for p in prompts] == [1, 2]
    assert [p.original_prompt for p in prompts] == ["foo", "bar"]


def test_extract_markdown_title_prompts__none():
    assert list(models.extract_markdown_title_prompts(2024, 10, None)) == []


def test_extract_markdown_title_prompts__day_and_title():
    prompts = list(models.extract_markdown_title_prompts(2024, 10, "5 - Something"))
    assert len(prompts) == 1
    assert prompts[0].date == datetime.date(2024, 10, 5)
    assert prompts[0].title == "Something"


def test_extract_markdown_title_prompts__multiple_days():
    prompts = list(models.extract_markdown_title_prompts(2024, 10, "5 & 6 - Foo, Bar"))
    assert [p.date.day for p in prompts] == [5, 6]
    assert [p.title for p in prompts] == ["Foo", "Bar"]


def test_markdown_file(write_md):
    path = write_md("w.md", "# My Title\n\nHello world content.\n")
    md = models.MarkdownFile.from_md_path(md_path=path)

    assert md.markdown_title == "My Title"
    assert "Hello world content." in md.text_content
    assert "<h1>My Title</h1>" in md.get_html(title_fallback="fallback")


def test_markdown_file__title_fallback(write_md):
    path = write_md("w.md", "No heading here.\n")
    md = models.MarkdownFile.from_md_path(md_path=path)

    assert md.markdown_title is None
    assert "<h1>fallback</h1>" in md.get_html(title_fallback="fallback")


def test_markdown_file__description_from_frontmatter(write_md):
    path = write_md("w.md", "---\ndescription: A description\n---\n# Title\n\nBody.\n")
    md = models.MarkdownFile.from_md_path(md_path=path)
    assert md.description == "A description"


def test_markdown_file__front_matter_prompts_multiple(write_md):
    path = write_md(
        "w.md",
        "---\nprompts:\n"
        "  - {title: B, date: 2024-10-02}\n"
        "  - {title: A, date: 2024-10-01}\n"
        "---\nBody.\n",
    )
    md = models.MarkdownFile.from_md_path(md_path=path)
    prompts = md.front_matter_prompts
    # Sorted by date
    assert [p.title for p in prompts] == ["A", "B"]


def test_writing_from_path__not_a_writing(write_md):
    path = write_md("w.txt", "content")
    with pytest.raises(models.NotAWriting):
        models.Writing.from_path(path=path, month=10, year=2024)


def test_writing_from_path(make_writing):
    writing = make_writing()

    assert writing.full_title == "01 - Backpack"
    assert writing.first_date == datetime.date(2024, 10, 1)
    assert writing.url == "2024/10/1-backpack/"
    assert writing.dates == [datetime.date(2024, 10, 1)]


def test_writing_from_path__no_prompts(write_md):
    path = write_md("nodigits.md", "No heading, no digits in name.\n")
    with pytest.raises(models.NoPromptsFound):
        models.Writing.from_path(path=path, month=10, year=2024)


def test_extract_full_title__from_prompts(make_writing):
    # No markdown title, no frontmatter full_title: built from prompts
    writing = make_writing(
        "prompts.md",
        "---\nprompts:\n"
        "  - {date: 2024-10-01, title: Foo, original_prompt: foo}\n"
        "  - {date: 2024-10-02, title: Bar, original_prompt: bar}\n"
        "---\nBody, no heading.\n",
    )
    assert writing.full_title == "01&02 - Foo, Bar"


def build_writings(write_md):
    write_md("2024/10/01-foo.md", "A.\n")
    write_md("2024/10/02-bar.md", "B.\n")


def test_get_all_writings(dw_settings, write_md):
    build_writings(write_md)

    writings = models.Writing.get_all_writings(settings=dw_settings())

    assert [w.first_date for w in writings] == [
        datetime.date(2024, 10, 1),
        datetime.date(2024, 10, 2),
    ]


def test_get_all_writings__duplicate_date(dw_settings, write_md):
    write_md("2024/10/01-foo.md", "A.\n")
    write_md("2024/10/01-bar.md", "B.\n")

    with pytest.raises(models.DuplicateDate):
        models.Writing.get_all_writings(settings=dw_settings())


def test_by_year_month(dw_settings, write_md):
    build_writings(write_md)
    writings = models.Writing.get_all_writings(settings=dw_settings())

    by_ym = models.Writing.by_year_month(writings)

    assert list(by_ym) == [(2024, 10)]
    assert len(by_ym[2024, 10]) == 2


def test_prompt_group(make_writing):
    writing = make_writing("01-02-foo-bar.md", "No heading.\n")

    group = writing.single_prompt_group
    assert len(group) == 2
    assert group.first_date == datetime.date(2024, 10, 1)
    assert group.get_subtitle(locale=i18n.Locale.from_string("en-us")) == "October 2024"
