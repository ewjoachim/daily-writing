import markdown_it
import yarl
from markdown_it.rules_core import StateCore


def external_links_plugin(md: markdown_it.MarkdownIt) -> None:
    """
    Open links to other sites in a new tab. The site URL is read from the
    ``site_url`` key of the env, and links are left untouched without it.
    """
    md.core.ruler.after("inline", "external_links", _external_links_rule)


def _external_links_rule(state: StateCore) -> None:
    site_url: yarl.URL | None = state.env.get("site_url")
    if site_url is None:
        return
    for token in state.tokens:
        for child in token.children or ():
            if child.type == "link_open" and _is_external(
                href=str(child.attrGet("href")), site_url=site_url
            ):
                child.attrSet("target", "_blank")
                child.attrSet("rel", "noopener")


def _is_external(href: str, site_url: yarl.URL) -> bool:
    url = yarl.URL(href)
    return url.absolute and url.host != site_url.host
