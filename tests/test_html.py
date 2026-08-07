import pytest

from daily_writing import build_context, html, models
from daily_writing import settings as settings_module


@pytest.fixture
def month_writings(make_writing):
    """Three writings in one month: a single day, a two-day span, and a later day.

    Exercises multi-day groups, empty days and prev/current/next navigation.
    """
    return [
        make_writing("01-alpha.md", "# 01 - Alpha\n\nAlpha body.\n"),
        make_writing("03-04-beta-gamma.md", "Beta gamma body.\n"),
        make_writing("10-delta.md", "# 10 - Delta\n\nDelta body.\n"),
    ]


@pytest.mark.parametrize(
    ("elements", "expected"),
    [
        (["a", "b", "c"], ["a", "-", "b", "-", "c"]),
        (["a"], ["a"]),
    ],
)
def test_join(elements, expected):
    assert html.join(elements, "-") == expected


@pytest.mark.parametrize("colors", [["#ffffff"], ["#000000", "#ffffff"]])
def test_css_linear_gradient(colors):
    result = html.css_linear_gradient(colors)

    assert result.startswith("linear-gradient(180deg,")
    assert all(color in result for color in colors)


def test_empty_day():
    assert str(html.empty_day()) == '<div class="day empty"></div>'


def test_burger():
    rendered = str(html.burger()[0])
    assert "burger" in rendered
    assert "<svg" in rendered


def test_redirect_page(dw_settings, page_metadata):
    result = html.redirect_page(
        settings=dw_settings(),
        page_metadata=page_metadata(),
        to_url="https://foo.bar/target/",
    )

    assert "0; url=https://foo.bar/target/" in result
    assert 'rel="canonical"' in result
    assert "https://foo.bar/target/" in result


def test_index_page(dw_settings, page_metadata):
    settings = dw_settings()
    markdown_file = models.MarkdownFile.from_md_path(md_path=settings.homepage_path)

    result = str(
        html.index_page(
            settings=settings,
            context=build_context.BuildContext(),
            writings=[],
            markdown_file=markdown_file,
            page_metadata=page_metadata(),
            colors=["#ffffff"],
            node_cache={},
        )
    )

    assert "<html" in result
    assert settings.site_name in result


def test_index_page__asset_urls(dw_settings, page_metadata, tmp_path):
    """Every asset link sits under the base path, and extra_css is served from the
    static dir rather than the source path it is configured with."""
    (tmp_path / "static" / "css").mkdir(parents=True)
    (tmp_path / "static" / "css" / "extra.css").write_text("/* extra */")
    settings = dw_settings(
        site_url="https://foo.bar/my-project",
        extra_css=["static/css/extra.css"],
        icon_links=[settings_module.IconLink(rel="icon", href="favicon.ico")],
    )
    markdown_file = models.MarkdownFile.from_md_path(md_path=settings.homepage_path)

    result = str(
        html.index_page(
            settings=settings,
            context=build_context.BuildContext(),
            writings=[],
            markdown_file=markdown_file,
            page_metadata=page_metadata(),
            colors=["#ffffff"],
            node_cache={},
        )
    )

    assert '"/my-project/static/css/extra.css?' in result
    assert '"/my-project/static/style.css?' in result
    assert '"/my-project/static/fonts.css?' in result
    assert '"/my-project/static/favicon.ico"' in result
    assert '"/my-project/feed.atom"' in result
    assert '"/static/' not in result


def test_writing_page__full_navigation(dw_settings, page_metadata, month_writings):
    settings = dw_settings(
        copyright="© Me",
        icon_links=[settings_module.IconLink(rel="icon", href="favicon.ico")],
    )
    writing = month_writings[1]  # middle → both prev and next links exist
    colors = [settings.color_cycle[p.color_index] for p in writing.prompts]

    result = str(
        html.writing_page(
            settings=settings,
            context=build_context.BuildContext(),
            writings=month_writings,
            writing=writing,
            # repository_url drives the footer repo link (comes from page metadata).
            page_metadata=page_metadata(repository_url="https://github.com/foo/bar"),
            colors=colors,
            node_cache={},
        )
    )

    assert "© Me" in result  # footer copyright
    assert "github.com/foo/bar" in result  # footer repository link
    assert "/static/favicon.ico" in result  # favicon <link>
    assert "octobre" in result.lower()  # month name in the nav (fr locale)
    assert "Beta" in result  # the current writing's original prompt


def test_index_page__month_links(dw_settings, page_metadata, month_writings):
    settings = dw_settings()
    markdown_file = models.MarkdownFile.from_md_path(md_path=settings.homepage_path)

    result = str(
        html.index_page(
            settings=settings,
            context=build_context.BuildContext(),
            writings=month_writings,
            markdown_file=markdown_file,
            page_metadata=page_metadata(),
            colors=["#ffffff"],
            node_cache={},
        )
    )

    assert 'href="#month-2024-10"' in result


def test_index_page__injects_hot_reload(dw_settings, page_metadata):
    settings = dw_settings()
    markdown_file = models.MarkdownFile.from_md_path(md_path=settings.homepage_path)

    result = str(
        html.index_page(
            settings=settings,
            context=build_context.BuildContext(inject_hot_reload_js=True),
            writings=[],
            markdown_file=markdown_file,
            page_metadata=page_metadata(),
            colors=["#ffffff"],
            node_cache={},
        )
    )

    assert "WebSocket" in result
