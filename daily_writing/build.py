from __future__ import annotations

import pathlib
import shutil
import urllib.parse
from collections.abc import Iterable

from daily_writing import artifacts, build_context

from . import atom, fonts, html, i18n, models, social_preview
from . import settings as settings_module

type Artifact = (
    artifacts.TextArtifact
    | artifacts.HTMLArtifact
    | artifacts.BytesArtifact
    | atom.FeedEntryArtifact
    | artifacts.FileArtifact
)


def build(
    settings: settings_module.Settings,
    context: build_context.BuildContext | None = None,
):
    if settings.build_dir.exists():
        shutil.rmtree(settings.build_dir)

    context = context or build_context.BuildContext()
    feed = atom.Feed(settings=settings)
    for artifact in get_artifacts(settings=settings, context=context):
        if isinstance(artifact, atom.FeedEntryArtifact):
            feed.add_entry(
                id=artifact.id,
                title=artifact.title,
                link=artifact.link,
                date=artifact.date,
            )
            continue
        artifact.write(dir=settings.build_dir)
    feed.get_artifact().write(dir=settings.build_dir)


def get_artifacts(
    settings: settings_module.Settings, context: build_context.BuildContext
) -> Iterable[Artifact]:
    font_files = fonts.get_all_font_files(settings=settings)
    yield from font_files.artifacts
    all_writings = list(
        writing
        for writing in models.Writing.get_all_writings(settings=settings)
        if writing.date <= settings.max_date
    )
    writings: models.Writings = {}
    for writing in all_writings:
        writings.setdefault(writing.year, {}).setdefault(writing.month, []).append(
            writing
        )

    yield from index_artifacts(
        settings=settings, context=context, writings=writings, font_files=font_files
    )
    yield from static_artifacts(settings=settings)
    for writing in all_writings:
        yield from writing_artifacts(
            settings=settings,
            context=context,
            writings=writings,
            writing=writing,
            font_files=font_files,
        )


def static_artifacts(settings: settings_module.Settings) -> Iterable[Artifact]:
    framework_static = pathlib.Path(__file__).parent / "static"
    project_static = settings.source_dir / settings.source_static_dir

    yield from [
        artifacts.FileArtifact(
            path=p, source=source, destination=settings.build_static_dir
        )
        for source in [framework_static, project_static]
        for p in source.iterdir()
    ]


def writing_artifacts(
    settings: settings_module.Settings,
    context: build_context.BuildContext,
    writings: models.Writings,
    writing: models.Writing,
    font_files: fonts.FontFiles,
) -> Iterable[Artifact]:
    top_line = [
        urllib.parse.urlparse(settings.base_url).hostname or "",
        settings.site_name,
    ]
    colors = [settings.color_cycle[prompt.color_index] for prompt in writing.prompts]

    social_preview_contents = social_preview.SocialPreviewContents(
        top_line=" — ".join(top_line),
        title=writing.title,
        description=writing.excerpt(),
        logo=settings.source_static_dir / settings.logo,
        date=i18n.full_date(date=writing.date, locale=settings.locale),
        colors=colors,
        body_font=font_files.body_font,
        title_font=font_files.title_font,
    )
    social_preview_filename = writing.social_preview_filename()
    social_preview_path = settings.social_preview_path / social_preview_filename

    renderable = html.writing_page(
        settings=settings,
        context=context,
        writings=writings,
        writing=writing,
        social_preview_url=get_social_preview_url(
            path=social_preview_path, signature=social_preview_contents.signature
        ),
        colors=colors,
    )

    link = f"{settings.base_url}/{writing.html_path}"

    return [
        atom.FeedEntryArtifact(
            id=writing.date.isoformat(),
            title=writing.full_title,
            link=link,
            date=writing.date,
        ),
        artifacts.HTMLArtifact(path=writing.html_path, contents=str(renderable)),
        social_preview_artifact(
            contents=social_preview_contents, path=social_preview_path
        ),
    ]


def index_artifacts(
    settings: settings_module.Settings,
    context: build_context.BuildContext,
    writings: models.Writings,
    font_files: fonts.FontFiles,
) -> Iterable[Artifact]:
    # Diagonal through the rectangle of colors
    colors = settings.index_colors
    social_preview_contents = social_preview.SocialPreviewContents(
        top_line=urllib.parse.urlparse(settings.base_url).hostname or "",
        title=settings.site_name,
        description=settings.description,
        logo=settings.source_static_dir / settings.logo,
        date=None,
        colors=colors,
        body_font=font_files.body_font,
        title_font=font_files.title_font,
    )
    filename = "index.png"

    social_preview_path = settings.social_preview_path / filename

    markdown_file = models.MarkdownFile(md_path=pathlib.Path("README.md"))

    renderable = html.index_page(
        settings=settings,
        context=context,
        writings=writings,
        markdown_file=markdown_file,
        social_preview_url=get_social_preview_url(
            path=social_preview_path, signature=social_preview_contents.signature
        ),
        colors=colors,
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
