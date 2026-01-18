from __future__ import annotations

import itertools
from collections.abc import Iterable

import htpy as h
import markdown
import markupsafe

from daily_writing import build_context, i18n

from . import models, utils
from . import settings as settings_module

settings_context: h.Context[settings_module.Settings] = h.Context("settings")
writings_context: h.Context[models.Writings] = h.Context("writings")
page_metadata_context: h.Context[models.PageMetadata] = h.Context("page_metadata")


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
            nav(),
            h.div(".content", role="main")[
                children,
                h.div(".footer", role="contentinfo")[
                    f"{settings.copyright} | ",
                    h.a(href=(repository_url))["GitHub"],
                    " | ",
                    h.a(href=(f"/{settings.atom_path}"))["Feed"],
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


@writings_context.consumer
@settings_context.consumer
def nav(settings: settings_module.Settings, writings: models.Writings) -> h.Node:
    return h.div("#menu.closed")[
        h.nav(role="navigation", aria_label="Main")[
            h.h4[h.a(href="/")[settings.site_name]],
            (
                nav_month(year=year, month=month)
                for year, writings_months in sorted(writings.items(), reverse=True)
                for month in sorted(writings_months, reverse=True)
            ),
        ],
    ]


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


@settings_context.consumer
@writings_context.consumer
def nav_month(
    writings: models.Writings,
    settings: settings_module.Settings,
    *,
    year: int,
    month: int,
) -> h.Node:
    return [
        h.h4(".month")[
            h.a(f"#month-{year}-{month}")[
                i18n.month_date(year=year, month=month, locale=settings.locale)
            ]
        ],
        h.div(".toc-month")[
            (empty_day() for _ in range(utils.first_weekday(year, month))),
            (
                nav_day(writing=writing, settings=settings)
                for writing in writings[year][month]
            ),
        ],
    ]


def nav_day(writing: models.Writing, settings: settings_module.Settings):
    return h.a(
        class_=[
            "day",
            "full",
            "gradient-hover",
            {"double": len(list(writing.prompts)) == 2},
        ],
        href=f"/{writing.html_path}",
    )[
        (
            h.div(".original-prompt")[
                join(
                    (
                        h.span(
                            {"style": f"color: {settings.color_cycle[p.color_index]}"}
                        )[p.original_prompt]
                        for p in writing.prompts
                    ),
                    ", ",
                )
            ]
            if writing.original_prompt != writing.title
            else None
        ),
        h.div(".title")[
            join(
                (
                    h.span({"style": f"color: {settings.color_cycle[p.color_index]}"})[
                        p.title
                    ]
                    for p in writing.prompts
                ),
                ", ",
            )
        ],
        h.div(".number")[
            h.h4[
                join(
                    (
                        h.span(
                            {
                                "style": f"text-decoration-color: {settings.color_cycle[p.color_index]}"
                            }
                        )[f"{p.day_number:02}"]
                        for p in writing.prompts
                    ),
                    "&",
                )
            ]
        ],
    ]


def join(elements: Iterable[h.Node], joiner: h.Node) -> list[h.Node]:
    return list(e for f in zip(elements, itertools.repeat(joiner)) for e in f)[:-1]


def linear_gradient(colors: list[str]) -> str:
    colors_css = ", ".join(
        f"{color} {level:2%}" for color, level in utils.color_gradient(colors)
    )
    return f"linear-gradient(180deg, {colors_css})"


def writing_page(
    *,
    settings: settings_module.Settings,
    context: build_context.BuildContext,
    writings: models.Writings,
    writing: models.Writing,
    social_preview_url: str,
    colors: list[str],
) -> h.Renderable:
    border_color = linear_gradient(colors=colors)

    page_metadata = models.PageMetadata(
        title=writing.title,
        url_path=str(writing.html_path),
        description=writing.excerpt(),
        social_preview_url=social_preview_url,
        repository_url=utils.get_repository_url_for_file(
            repository_url=settings.repository_url,
            repository_file_url_prefix=settings.repository_file_url_prefix,
            file=writing.md_path,
        ),
    )
    links = []
    if prev_writing := utils.get_prev(
        obj=writing, iterable=writings[writing.year][writing.month]
    ):
        links.append(nav_day(writing=prev_writing, settings=settings))
    else:
        links.append(empty_day())

    if next_writing := utils.get_next(
        obj=writing, iterable=writings[writing.year][writing.month]
    ):
        links.append(nav_day(writing=next_writing, settings=settings))
    else:
        links.append(empty_day())

    return settings_context.provider(
        settings,
        writings_context.provider(
            writings,
            page_metadata_context.provider(
                page_metadata,
                layout(
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
                                markupsafe.Markup(
                                    markdown.markdown(
                                        writing.markdown,
                                        format="html",  # pyright: ignore[reportCallIssue]
                                    )
                                ),
                            ],
                        ],
                        h.div("#prev-next-links")[links],
                    ],
                ),
            ),
        ),
    )


def index_page(
    *,
    settings: settings_module.Settings,
    context: build_context.BuildContext,
    writings: models.Writings,
    markdown_file: models.MarkdownFile,
    social_preview_url: str,
    colors: list[str],
) -> h.Renderable:
    border_color = linear_gradient(colors=colors)
    page_metadata = models.PageMetadata(
        title=settings.site_name,
        url_path="/",
        description=markdown_file.excerpt(),
        social_preview_url=social_preview_url,
        repository_url=utils.get_repository_url_for_file(
            repository_url=settings.repository_url,
            repository_file_url_prefix=settings.repository_file_url_prefix,
            file=markdown_file.md_path,
        ),
    )

    return settings_context.provider(
        settings,
        writings_context.provider(
            writings,
            page_metadata_context.provider(
                page_metadata,
                layout(
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
                                markupsafe.Markup(
                                    markdown.markdown(
                                        markdown_file.markdown,
                                        format="html",  # pyright: ignore[reportCallIssue]
                                    )
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
                                for year, months in writings.items()
                                for month in months
                            )
                        ],
                    ],
                ),
            ),
        ),
    )
