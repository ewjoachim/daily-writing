import re

import markdown_it
from markdown_it.rules_core import StateCore
from markdown_it.token import Token

CALLOUT_MARKER = re.compile(r"\[!(?P<kind>[\w-]+)\][ \t]*(?P<title>[^\n]*)\n?")


def callout_plugin(md: markdown_it.MarkdownIt) -> None:
    """
    Turn blockquotes starting with ``[!kind] Optional title`` into callouts
    (Obsidian-style, a superset of GitHub alerts), accepting any kind.
    The HTML uses GitHub's ``markdown-alert`` classes.
    """
    md.core.ruler.after("block", "callout", _callout_rule)


def _callout_rule(state: StateCore) -> None:
    tokens = state.tokens
    i = 0
    while i < len(tokens):
        if _is_callout(tokens, i):
            _convert(tokens, i)
        i += 1


def _is_callout(tokens: list[Token], i: int) -> bool:
    return (
        tokens[i].type == "blockquote_open"
        and i + 2 < len(tokens)
        and tokens[i + 1].type == "paragraph_open"
        and tokens[i + 2].type == "inline"
        and CALLOUT_MARKER.match(tokens[i + 2].content) is not None
    )


def _convert(tokens: list[Token], i: int) -> None:
    open_token, paragraph_open, inline = tokens[i : i + 3]
    match = CALLOUT_MARKER.match(inline.content)
    assert match
    kind = match["kind"].lower()
    body = inline.content[match.end() :]

    close_token = next(
        token
        for token in tokens[i + 1 :]
        if token.type == "blockquote_close" and token.level == open_token.level
    )
    for token, nesting in ((open_token, "open"), (close_token, "close")):
        token.type = f"callout_{nesting}"
        token.tag = "div"
    open_token.attrSet("class", f"markdown-alert markdown-alert-{kind}")
    open_token.info = kind

    paragraph_open.attrSet("class", "markdown-alert-title")
    inline.content = match["title"].strip() or kind.capitalize()

    if body:
        body_tokens = [
            Token("paragraph_open", "p", 1, level=paragraph_open.level, block=True),
            Token("inline", "", 0, level=inline.level, content=body, children=[]),
            Token("paragraph_close", "p", -1, level=paragraph_open.level, block=True),
        ]
        tokens[i + 4 : i + 4] = body_tokens
