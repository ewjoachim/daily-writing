import logging
import pathlib
import shutil
from collections.abc import Iterable
from typing import Any

from . import (
    artifacts,
    atom,
    build_context,
    cms,
    fonts,
    html,
    i18n,
    models,
    social_preview,
    utils,
)
from . import settings as settings_module

logger = logging.getLogger("daily_writing")


def build(
    settings: settings_module.Settings,
    context: build_context.BuildContext | None = None,
):
    logger.info("Starting build")
    if settings.build_dir.exists():
        shutil.rmtree(settings.build_dir)

    context = context or build_context.BuildContext()
    feed = atom.Feed(settings=settings)
    for artifact in get_artifacts(settings=settings, context=context):
        if isinstance(artifact, atom.FeedEntryArtifact):
            feed.add_entry(
                item_id=artifact.artifact_id,
                title=artifact.title,
                link=artifact.link,
                date=artifact.date,
            )
            continue
        artifact.write(destination=settings.build_dir)
    feed.get_artifact().write(destination=settings.build_dir)


def get_artifacts(
    settings: settings_module.Settings, context: build_context.BuildContext
) -> Iterable[artifacts.BaseArtifact | atom.FeedEntryArtifact]:
    node_cache: dict[str, Any] = {}
    logger.info("Building fonts")
    font_files = fonts.get_all_font_files(settings=settings)
    yield from font_files.artifacts

    logger.info("Building index")
    writings = [
        writing
        for writing in models.Writing.get_all_writings(settings=settings)
        if writing.last_date <= settings.max_date
    ]
    yield from index_artifacts(
        settings=settings,
        context=context,
        writings=writings,
        font_files=font_files,
        node_cache=node_cache,
    )
    logger.info("Building static files")
    yield from static_artifacts(settings=settings)
    logger.info("Building writing files")
    for writing in writings:
        yield from writing_artifacts(
            settings=settings,
            context=context,
            writings=writings,
            writing=writing,
            font_files=font_files,
            node_cache=node_cache,
        )

    if settings.include_cms:
        logger.info("Building cms")
        yield from cms.cms_artifacts(settings=settings)


def static_artifacts(
    settings: settings_module.Settings,
) -> Iterable[artifacts.BaseArtifact]:
    framework_static = pathlib.Path(__file__).parent / "static"
    project_static = settings.source_dir / settings.source_static_dir

    yield from [
        artifacts.FileArtifact(
            path=p.relative_to(source.parent),
            source=p,
        )
        for source in [framework_static, project_static]
        for p in source.iterdir()
    ]


def writing_artifacts(  # noqa: PLR0917
    settings: settings_module.Settings,
    context: build_context.BuildContext,
    writings: list[models.Writing],
    writing: models.Writing,
    font_files: fonts.FontFiles,
    node_cache: dict[str, Any],
) -> Iterable[artifacts.BaseArtifact | atom.FeedEntryArtifact]:
    top_line = [
        settings.site_full_url.host or "",
        settings.site_name,
    ]
    colors = [settings.color_cycle[prompt.color_index] for prompt in writing.prompts]

    social_preview_contents = social_preview.SocialPreviewContents(
        top_line=" — ".join(top_line),
        title=writing.full_title,
        description=writing.markdown_file.excerpt(),
        logo=settings.source_static_dir / settings.logo if settings.logo else None,
        date=i18n.full_date(dates=writing.dates, locale=settings.locale),
        colors=colors,
        body_font=font_files.body_font,
        title_font=font_files.title_font,
    )
    social_preview_filename = str(writing.md_path.with_suffix(".png")).replace("/", "-")

    social_preview_path = settings.social_preview_path / social_preview_filename

    page_metadata = models.PageMetadata(
        title=writing.full_title,
        url_path=writing.url,
        description=writing.markdown_file.description,
        social_preview_url=get_social_preview_url(
            path=social_preview_path, signature=social_preview_contents.signature
        ),
        repository_url=utils.get_repository_url_for_file(
            repository_url=settings.repository_url,
            repository_file_url_prefix=settings.repository_file_url_prefix,
            file=writing.md_path,
        ),
    )

    renderable = html.writing_page(
        settings=settings,
        context=context,
        writings=writings,
        writing=writing,
        page_metadata=page_metadata,
        colors=colors,
        node_cache=node_cache,
    )

    link = str(settings.site_full_url / writing.url)

    html_path = pathlib.Path(writing.url) / "index.html"

    return [
        atom.FeedEntryArtifact(
            artifact_id=writing.first_date.isoformat(),
            title=writing.full_title,
            link=link,
            date=writing.first_date,
        ),
        artifacts.HTMLArtifact(path=html_path, contents=str(renderable)),
        social_preview_artifact(
            contents=social_preview_contents, path=social_preview_path
        ),
        *(
            get_redirect_alias_artifact(
                settings=settings, page_metadata=page_metadata, alias=alias, to_url=link
            )
            for alias in writing.markdown_file.base_metadata.redirect_aliases
        ),
    ]


def get_redirect_alias_artifact(
    settings: settings_module.Settings,
    page_metadata: models.PageMetadata,
    alias: pathlib.Path,
    to_url: str,
) -> artifacts.HTMLArtifact:
    return artifacts.HTMLArtifact(
        path=alias,
        contents=html.redirect_page(
            settings=settings, page_metadata=page_metadata, to_url=to_url
        ),
    )


def index_artifacts(
    settings: settings_module.Settings,
    context: build_context.BuildContext,
    writings: list[models.Writing],
    font_files: fonts.FontFiles,
    node_cache: dict[str, Any],
) -> Iterable[artifacts.BaseArtifact]:
    # Diagonal through the rectangle of colors
    colors = settings.index_colors_hex
    social_preview_contents = social_preview.SocialPreviewContents(
        top_line=settings.site_full_url.host or "",
        title=settings.site_name,
        description=settings.description,
        logo=settings.source_static_dir / settings.logo if settings.logo else None,
        date=None,
        colors=colors,
        body_font=font_files.body_font,
        title_font=font_files.title_font,
    )
    filename = "index.png"

    social_preview_path = settings.social_preview_path / filename

    markdown_file = models.MarkdownFile.from_md_path(md_path=pathlib.Path("README.md"))

    social_preview_url = get_social_preview_url(
        path=social_preview_path, signature=social_preview_contents.signature
    )

    page_metadata = models.PageMetadata(
        title=settings.site_name,
        url_path="",
        description=markdown_file.description,
        social_preview_url=social_preview_url,
        repository_url=utils.get_repository_url_for_file(
            repository_url=settings.repository_url,
            repository_file_url_prefix=settings.repository_file_url_prefix,
            file=markdown_file.md_path,
        ),
    )

    renderable = html.index_page(
        settings=settings,
        context=context,
        writings=writings,
        markdown_file=markdown_file,
        colors=colors,
        page_metadata=page_metadata,
        node_cache=node_cache,
    )

    return [
        artifacts.HTMLArtifact(
            path=pathlib.Path("index.html"), contents=str(renderable)
        ),
        social_preview_artifact(
            contents=social_preview_contents, path=social_preview_path
        ),
    ]


def get_social_preview_url(path: pathlib.Path, signature: str) -> str:
    return f"{path}?hash={signature}"


def social_preview_artifact(
    contents: social_preview.SocialPreviewContents, path: pathlib.Path
) -> artifacts.BytesArtifact:
    image_bytes = social_preview.generate_social_preview(contents=contents)

    return artifacts.BytesArtifact(path=path, contents=image_bytes)
