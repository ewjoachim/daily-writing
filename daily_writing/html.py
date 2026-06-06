import calendar
import datetime
import itertools
from collections.abc import Iterable
from typing import Literal

import htpy as h
import markupsafe

from daily_writing import build_context, i18n

from . import models, utils
from . import settings as settings_module

settings_context: h.Context[settings_module.Settings] = h.Context("settings")
writings_context: h.Context[list[models.Writing]] = h.Context("writings")
page_metadata_context: h.Context[models.PageMetadata] = h.Context("page_metadata")
node_cache_context: h.Context[dict[str, h.Node]] = h.Context("node_cache")


@settings_context.consumer
@page_metadata_context.consumer
def layout(
    page_metadata: models.PageMetadata,
    settings: settings_module.Settings,
    inject_hot_reload_js: bool,
    *,
    children: h.Node,
) -> h.Renderable:
    repository_url = str(page_metadata.repository_url)

    return h.html(lang=i18n.get_bcp47(settings.locale))[
        head(),
        h.body[
            nav(
                base_url=settings.base_url,
                site_name=settings.site_name,
            ),
            h.div(".content", role="main")[
                children,
                h.div(".footer", role="contentinfo")[
                    f"{settings.copyright} | ",
                    h.a(href=repository_url, target="_blank")[
                        settings.repository_link_name
                    ],
                    " | ",
                    h.a(href=f"/{settings.atom_path}", target="_blank")[
                        settings.feed_name
                    ],
                ],
            ],
            burger(),
        ],
        h.script[
            markupsafe.Markup("""
const ws = new WebSocket("ws://127.0.0.1:8000/ws");
ws.onmessage = () => window.location.reload();
""")
        ]
        if inject_hot_reload_js
        else None,
        h.script[
            markupsafe.Markup("""
function toggleMenu(){document.querySelector("body").classList.toggle("menu-open")}
""")
        ],
    ]


@settings_context.consumer
@page_metadata_context.consumer
def head(
    page_metadata: models.PageMetadata,
    settings: settings_module.Settings,
    additional_content: h.Node | None = None,
) -> h.Node:
    title_elements = [settings.site_name]
    if page_metadata.title:
        title_elements.insert(0, page_metadata.title)

    return (
        h.head[
            h.meta(charset="utf-8"),
            h.meta(name="viewport", content="width=device-width, initial-scale=1.0"),
            h.meta(
                name="description",
                content=page_metadata.description,
            ),
            social_preview_meta(),
            h.title[" — ".join(title_elements)],
            [
                h.link(
                    rel="stylesheet",
                    type="text/css",
                    href=f"{settings.build_static_path}{extra_css}?{utils.cache_bust()}",
                )
                for extra_css in settings.extra_css
            ],
            h.link(
                rel="stylesheet",
                type="text/css",
                href=f"{settings.build_static_path}style.css?{utils.cache_bust()}",
            ),
            h.link(
                rel="stylesheet",
                type="text/css",
                href=f"{settings.build_static_path}fonts.css?{utils.cache_bust()}",
            ),
            favicons(),
            h.link(
                rel="alternate",
                type="application/atom+xml",
                title="Atom",
                href=f"{settings.base_url / settings.atom_path}",
            ),
            additional_content,
        ],
    )


@settings_context.consumer
def favicons(
    settings: settings_module.Settings,
) -> h.Node:
    return [
        h.link(
            rel=icon_link.rel,
            type=icon_link.type,
            sizes=icon_link.sizes,
            href=f"/{settings.build_static_dir}/{icon_link.href}",
        )
        for icon_link in settings.icon_links or []
    ]


@page_metadata_context.consumer
@settings_context.consumer
def social_preview_meta(
    settings: settings_module.Settings,
    page_metadata: models.PageMetadata,
):
    url = f"{settings.base_url}/{page_metadata.url_path or ''}"
    image = f"{settings.base_url}/{page_metadata.social_preview_url}"
    return [
        h.meta(property="og:title", content=page_metadata.title),
        h.meta(property="og:type", content="website"),
        h.meta(property="og:url", content=url),
        h.meta(property="og:site_name", content=settings.site_name),
        h.meta(
            property="og:description",
            content=page_metadata.description,
        ),
        h.meta(property="og:image:width", content=f"{settings.social_preview_width}"),
        h.meta(property="og:image:height", content=f"{settings.social_preview_height}"),
        h.meta(
            property="og:image",
            content=f"{settings.base_url}/{page_metadata.social_preview_url}",
        ),
        h.meta(
            property="og:image:alt",
            content=page_metadata.description,
        ),
        h.meta(name="twitter:title", content=page_metadata.title),
        h.meta(name="twitter:description", content=page_metadata.description),
        h.meta(name="twitter:image", content=image),
        h.meta(name="twitter:card", content="summary_large_image"),
    ]


@node_cache_context.consumer
@writings_context.consumer
@settings_context.consumer
def nav(
    settings: settings_module.Settings,
    writings: Iterable[models.Writing],
    node_cache: dict[str, h.Node],
    *,
    base_url: str,
    site_name: str,
) -> h.Node:
    if "nav" in node_cache:
        return node_cache["nav"]
    writings_by_year_month = models.Writing.by_year_month(list(writings))
    node_cache["nav"] = h.div("#menu.closed")[
        h.nav(role="navigation", aria_label="Main")[
            h.h4[h.a(href=base_url)[site_name]],
            [
                nav_month(
                    year=year,
                    month=month,
                    prompt_groups=prompt_groups,
                    settings=settings,
                )
                for (year, month), prompt_groups in reversed(
                    writings_by_year_month.items()
                )
            ],
        ],
    ]
    return node_cache["nav"]


def burger() -> h.Node:
    stroke = {
        "stroke": "#ced6dd",
        "stroke_width": "2",
        "stroke_linecap": "round",
        "stroke_linejoin": "round",
    }
    return [
        h.div(
            "#burger.svg-button",
            onclick="toggleMenu()",
        )[
            h.svg(
                width="2em",
                height="2em",
                viewbox="0 0 24 24",
                fill="none",
                xmlns="http://www.w3.org/2000/svg",
            )[
                h.line(".top-bar", x1=5, y1=19, x2=19, y2=19, **stroke),
                h.line(".middle-bar", x1=5, y1=12, x2=19, y2=12, **stroke),
                h.line(".bottom-bar", x1=5, y1=5, x2=19, y2=5, **stroke),
            ],
        ]
    ]


def empty_day() -> h.Node:
    return h.div(".day.empty")


def iter_prompts_groups(
    prompt_groups: list[models.PromptGroup],
    year: int,
    month: int,
    first_day_of_week: settings_module.DayOfWeek,
) -> Iterable[models.PromptGroup | None]:
    """
    For a given year and month, yield the prompt groups for each day, or None if there
    is no prompt group for that day. When a prompt group spans multiple days, it will be
    yielded on the first day only, the next thing yielded will then be for the day after
    the end of that prompt group.
    """
    dates = iter(
        calendar.Calendar(firstweekday=first_day_of_week).itermonthdates(year, month)
    )
    by_date = {date: pg for pg in prompt_groups for date in pg.dates}
    # Min date is the first day of week of the first week containing a prompt
    min_date = min(by_date)
    min_date -= datetime.timedelta(days=min_date.weekday() - first_day_of_week)
    # Max date is the last day containing a prompt (no need to yield empty days after that)
    max_date = max(by_date)
    while True:
        date = next(dates, None)
        if date is None:
            break

        if date < min_date:
            continue

        if date > max_date:
            break

        if date.month != month:
            yield None
            continue

        if not (prompt_group := by_date.get(date)):
            yield None
            continue

        yield prompt_group
        for _ in prompt_group.prompts[1:]:
            next(dates)


def nav_month(
    settings: settings_module.Settings,
    year: int,
    month: int,
    prompt_groups: list[models.PromptGroup],
) -> h.Node:

    nodes = []
    for prompt_group in iter_prompts_groups(
        prompt_groups=prompt_groups,
        year=year,
        month=month,
        first_day_of_week=settings.first_day_of_week,
    ):
        if prompt_group is None:
            nodes.append(empty_day())
        else:
            nodes.append(
                nav_day(
                    prompt_group=prompt_group,
                    role="menu",
                    settings=settings,
                )
            )
    return [
        h.h4(".month")[
            h.a(f"#month-{year}-{month}")[
                i18n.month_date(year=year, month=month, locale=settings.locale)
            ]
        ],
        h.div(".toc-month")[nodes],
    ]


def nav_day(
    prompt_group: models.PromptGroup,
    settings: settings_module.Settings,
    role: Literal["prev", "current", "next", "menu"],
):
    prompts = prompt_group.prompts
    node_cls = h.a
    attrs: dict[str, str] = {}
    subtitle = prompt_group.get_subtitle(locale=settings.locale)
    if role == "current":
        node_cls = h.span
    else:
        attrs["href"] = f"{settings.base_url}/{prompt_group.writing.url}"

    if role == "menu":
        attrs["style"] = f"grid-column: span {len(list(prompt_group.prompts))}"

    return node_cls(class_=["day", "full"], **attrs)[
        (
            h.div(".original-prompt")[
                join(
                    (
                        h.span(
                            {"style": f"color: {settings.color_cycle[p.color_index]}"}
                        )[p.original_prompt]
                        for p in prompts
                    ),
                    ", ",
                )
            ]
            if any(p.original_prompt != p.title for p in prompts)
            else None
        ),
        h.div(".title")[
            join(
                [
                    h.span({"style": f"color: {settings.color_cycle[p.color_index]}"})[
                        p.title
                    ]
                    for p in prompts
                ],
                ", ",
            )
        ],
        h.div(".number")[
            h.h4[
                "<" if role == "prev" else None,
                join(
                    (
                        h.span(
                            {
                                "style": f"text-decoration-color: {settings.color_cycle[p.color_index]}"
                            }
                        )[f"{p.date.day:02}",]
                        for p in prompts
                    ),
                    "&",
                ),
                ">" if role == "next" else None,
            ]
        ],
        (h.div(".full_date")[subtitle] if subtitle else markupsafe.Markup("&nbsp;")),
    ]


def join(elements: Iterable[h.Node], joiner: h.Node) -> list[h.Node]:
    return [e for f in zip(elements, itertools.repeat(joiner)) for e in f][:-1]


def css_linear_gradient(colors: list[str]) -> str:
    colors_css = ", ".join(
        f"{color} {level:2%}" for color, level in utils.color_gradient(colors)
    )
    return f"linear-gradient(180deg, {colors_css})"


def providers(
    settings: settings_module.Settings,
    writings: list[models.Writing],
    page_metadata: models.PageMetadata,
    node_cache: dict[str, h.Node],
    children: h.Node,
) -> h.Renderable:
    return settings_context.provider(
        settings,
        writings_context.provider(
            writings,
            page_metadata_context.provider(
                page_metadata, node_cache_context.provider(node_cache, children)
            ),
        ),
    )


def writing_page(
    *,
    settings: settings_module.Settings,
    context: build_context.BuildContext,
    writings: list[models.Writing],
    writing: models.Writing,
    page_metadata: models.PageMetadata,
    colors: list[str],
    node_cache: dict[str, h.Node],
) -> h.Renderable:
    border_color = css_linear_gradient(colors=colors)

    links = []
    if prev_writing := utils.get_prev(
        obj=writing,
        iterable=writings,
    ):
        links.append(
            nav_day(
                prompt_group=prev_writing.single_prompt_group,
                role="prev",
                settings=settings,
            )
        )
    else:
        links.append(empty_day())

    links.append(
        nav_day(
            prompt_group=writing.single_prompt_group,
            role="current",
            settings=settings,
        )
    )

    if next_writing := utils.get_next(
        obj=writing,
        iterable=writings,
    ):
        links.append(
            nav_day(
                prompt_group=next_writing.single_prompt_group,
                role="next",
                settings=settings,
            )
        )
    else:
        links.append(empty_day())

    return providers(
        settings=settings,
        page_metadata=page_metadata,
        writings=writings,
        node_cache=node_cache,
        children=layout(
            inject_hot_reload_js=context.inject_hot_reload_js,
            children=[
                h.div(".markdown-block")[
                    h.div(
                        ".markdown-line",
                        {"style": f"background: {border_color}"},
                    ),
                    h.main(
                        ".markdown",
                    )[
                        markupsafe.Markup(  # noqa: S704
                            writing.markdown_file.html
                        ),
                    ],
                ],
                h.div("#prev-next-links")[links],
            ],
        ),
    )


def index_page(
    *,
    settings: settings_module.Settings,
    context: build_context.BuildContext,
    writings: list[models.Writing],
    markdown_file: models.MarkdownFile,
    page_metadata: models.PageMetadata,
    colors: list[str],
    node_cache: dict[str, h.Node],
) -> h.Renderable:
    border_color = css_linear_gradient(colors=colors)

    return providers(
        settings=settings,
        page_metadata=page_metadata,
        writings=writings,
        node_cache=node_cache,
        children=layout(
            inject_hot_reload_js=context.inject_hot_reload_js,
            children=[
                h.div(".markdown-block")[
                    h.div(
                        ".markdown-line",
                        {"style": f"background: {border_color}"},
                    ),
                    h.main(
                        ".markdown",
                    )[
                        markupsafe.Markup(  # noqa: S704
                            markdown_file.html
                        ),
                    ],
                ],
                h.div("#month-links")[
                    (
                        h.h4[
                            h.a(
                                href=f"#month-{year}-{month}",
                                onclick="""toggleMenu()""",
                            )[
                                i18n.month_date(
                                    year=year,
                                    month=month,
                                    locale=settings.locale,
                                )
                            ]
                        ]
                        for year, month in models.Writing.by_year_month(
                            writings=writings
                        )
                    )
                ],
            ],
        ),
    )


def redirect_page(
    settings: settings_module.Settings, page_metadata: models.PageMetadata, to_url: str
) -> str:
    return str(
        settings_context.provider(
            settings,
            page_metadata_context.provider(
                page_metadata,
                h.html(lang="en")[
                    head(
                        additional_content=[
                            h.meta(http_equiv="refresh", content=f"0; url={to_url}"),
                            h.link(rel="canonical", href=to_url),
                        ]
                    ),
                    h.body,
                ],
            ),
        )
    )
