import markdown_it
import pytest
import yarl

from daily_writing import links

SITE_URL = yarl.URL("https://foo.bar/blog/")


@pytest.fixture
def render():
    parser = markdown_it.MarkdownIt("commonmark").use(links.external_links_plugin)

    def _(source: str, site_url: yarl.URL | None = SITE_URL):
        env = {} if site_url is None else {"site_url": site_url}
        return parser.render(source, env=env)

    return _


def test_external_link(render):
    assert render("[a](https://example.com/page)") == (
        '<p><a href="https://example.com/page" target="_blank" rel="noopener">a</a></p>\n'
    )


@pytest.mark.parametrize(
    "href",
    [
        "/2024/10/04-Exotic/",
        "../other/",
        "#section",
        "https://foo.bar/blog/2024/",
        "mailto:me@foo.bar",
    ],
)
def test_internal_link(render, href):
    assert "target" not in render(f"[a]({href})")


def test_link_in_callout_like_blockquote(render):
    assert 'target="_blank"' in render("> [!note]\n> [a](https://example.com)\n")


def test_no_site_url(render):
    assert "target" not in render("[a](https://example.com)", site_url=None)
