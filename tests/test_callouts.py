import markdown_it
import pytest

from daily_writing import callouts


@pytest.fixture
def render():
    parser = markdown_it.MarkdownIt("commonmark").use(callouts.callout_plugin)
    return parser.render


def test_callout__github_kind(render):
    assert render("> [!NOTE]\n> Body *text*.\n") == (
        '<div class="markdown-alert markdown-alert-note">\n'
        '<p class="markdown-alert-title">Note</p>\n'
        "<p>Body <em>text</em>.</p>\n"
        "</div>\n"
    )


def test_callout__custom_kind_and_title(render):
    assert render("> [!souvenir] Il y a *longtemps*\n> Body.\n") == (
        '<div class="markdown-alert markdown-alert-souvenir">\n'
        '<p class="markdown-alert-title">Il y a <em>longtemps</em></p>\n'
        "<p>Body.</p>\n"
        "</div>\n"
    )


def test_callout__marker_alone_then_blocks(render):
    assert render("> [!tip]\n>\n> - a\n> - b\n") == (
        '<div class="markdown-alert markdown-alert-tip">\n'
        '<p class="markdown-alert-title">Tip</p>\n'
        "<ul>\n<li>a</li>\n<li>b</li>\n</ul>\n"
        "</div>\n"
    )


def test_callout__nested(render):
    assert render("> [!outer]\n> > [!inner]\n> > Body.\n") == (
        '<div class="markdown-alert markdown-alert-outer">\n'
        '<p class="markdown-alert-title">Outer</p>\n'
        '<div class="markdown-alert markdown-alert-inner">\n'
        '<p class="markdown-alert-title">Inner</p>\n'
        "<p>Body.</p>\n"
        "</div>\n"
        "</div>\n"
    )


def test_callout__foldable_closed(render):
    assert render("> [!souvenir]-\n> Body.\n") == (
        '<details class="markdown-alert markdown-alert-souvenir">\n'
        '<summary class="markdown-alert-title">Souvenir</summary>\n'
        "<p>Body.</p>\n"
        "</details>\n"
    )


def test_callout__foldable_open_with_title(render):
    assert render("> [!souvenir]+ Il y a longtemps\n> Body.\n") == (
        '<details class="markdown-alert markdown-alert-souvenir" open="">\n'
        '<summary class="markdown-alert-title">Il y a longtemps</summary>\n'
        "<p>Body.</p>\n"
        "</details>\n"
    )


@pytest.mark.parametrize(
    "source",
    [
        "> Just a quote.\n",
        "> Not [!note] at start.\n",
        "> [!not a kind]\n",
        "[!note] outside a quote\n",
    ],
)
def test_callout__not_a_callout(render, source):
    assert "markdown-alert" not in render(source)
