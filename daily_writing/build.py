from __future__ import annotations

import pathlib
import shutil
import urllib.parse
from collections.abc import Iterable

from . import atom, html, models, social_preview
from . import settings as settings_module


def build(settings: settings_module.Settings):
    if settings.build_dir.exists():
        shutil.rmtree(settings.build_dir)

    feed = atom.Feed(settings=settings)
    for artifact in get_artifacts(settings=settings):
        if isinstance(artifact, models.FeedEntryArtifact):
            feed.add_entry(
                id=artifact.id,
                title=artifact.title,
                link=artifact.link,
                date=artifact.date,
            )
            continue
        artifact.write(dir=settings.build_dir)
    feed.get_artifact().write(dir=settings.build_dir)


def get_artifacts(settings: settings_module.Settings) -> Iterable[models.Artifact]:
    writings = models.Writing.get_all(settings=settings)
    yield from index_artifacts(settings=settings, writings=writings)
    yield from static_artifacts(settings=settings)
    for year_writings in writings.values():
        for writing in year_writings:
            yield from writing_artifacts(
                settings=settings, writings=writings, writing=writing
            )


def static_artifacts(settings: settings_module.Settings) -> Iterable[models.Artifact]:
    framework_static = pathlib.Path(__file__).parent / "static"
    project_static = settings.source_dir / settings.source_static_dir

    yield from [
        models.FileArtifact(
            path=p, source=source, destination=settings.build_static_dir
        )
        for source in [framework_static, project_static]
        for p in source.iterdir()
    ]


def writing_artifacts(
    settings: settings_module.Settings,
    writings: models.Writings,
    writing: models.Writing,
) -> Iterable[models.Artifact]:
    top_line = [
        urllib.parse.urlparse(settings.base_url).hostname or "",
        settings.site_name,
    ]
    colors = [settings.color_cycle[prompt.color_index] for prompt in writing.prompts]
    social_preview_contents = models.SocialPreviewContents(
        top_line=" — ".join(top_line),
        title=writing.title,
        description=writing.excerpt(),
        logo=settings.source_static_dir / settings.logo,
        date=french_dates(writing=writing, month_name=settings.month_name),
        colors=colors,
        body_font_file_woff2=settings.source_static_dir / settings.body_font_file_woff2,
        title_font_file_woff2=settings.source_static_dir
        / settings.title_font_file_woff2,
    )
    filename = writing.social_preview_filename(
        signature=social_preview_contents.signature
    )
    social_preview_path = settings.social_preview_path / filename

    renderable = html.writing_page(
        settings=settings,
        writings=writings,
        writing=writing,
        social_preview_path=social_preview_path,
        colors=colors,
    )

    link = f"{settings.base_url}/{writing.html_path}"

    return [
        models.FeedEntryArtifact(
            id=writing.date.isoformat(),
            title=writing.full_title,
            link=link,
            date=writing.date,
        ),
        models.HTMLArtifact(path=writing.html_path, contents=str(renderable)),
        social_preview_artifact(
            contents=social_preview_contents, path=social_preview_path
        ),
    ]


def index_artifacts(
    settings: settings_module.Settings, writings: models.Writings
) -> Iterable[models.Artifact]:
    # Diagonal through the rectangle of colors
    colors = settings.index_colors
    social_preview_contents = models.SocialPreviewContents(
        top_line=urllib.parse.urlparse(settings.base_url).hostname or "",
        title=settings.site_name,
        description=settings.description,
        logo=settings.source_static_dir / settings.logo,
        date=None,
        colors=colors,
        body_font_file_woff2=settings.source_static_dir / settings.body_font_file_woff2,
        title_font_file_woff2=settings.source_static_dir
        / settings.title_font_file_woff2,
    )
    filename = f"index.{social_preview_contents.signature}.png"

    social_preview_path = settings.social_preview_path / filename

    markdown_file = models.MarkdownFile(md_path=pathlib.Path("README.md"))

    renderable = html.index_page(
        settings=settings,
        writings=writings,
        markdown_file=markdown_file,
        social_preview_path=social_preview_path,
        colors=colors,
    )

    return [
        models.HTMLArtifact(path=pathlib.Path("index.html"), contents=str(renderable)),
        social_preview_artifact(
            contents=social_preview_contents, path=social_preview_path
        ),
    ]


def social_preview_artifact(
    contents: models.SocialPreviewContents, path: pathlib.Path
) -> models.BytesArtifact:
    image_bytes = social_preview.generate_social_preview(contents=contents)

    return models.BytesArtifact(path=path, contents=image_bytes.getvalue())


# One of the few, if not the only place where French is baked in the system.
def french_dates(writing: models.Writing | None, month_name: str) -> str | None:
    if not writing:
        return None
    return f"{'&'.join(str(p.day_number) for p in writing.prompts)} {month_name} {writing.year}"
