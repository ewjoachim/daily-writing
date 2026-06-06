import datetime
import io
import pathlib
import zoneinfo
from typing import cast

from feedgen.feed import FeedGenerator
from pydantic import dataclasses as pdataclasses

from daily_writing import artifacts

from . import settings as settings_module


@pdataclasses.dataclass(kw_only=True)
class FeedEntryArtifact:
    artifact_id: str
    title: str
    link: str
    date: datetime.date


class Feed:
    def __init__(self, settings: settings_module.Settings):
        self.feed_gen: FeedGenerator = FeedGenerator()
        self.feed_gen.id(settings.base_url or "https://localhost")
        self.feed_gen.title(settings.site_name)
        self.feed_gen.author(name=settings.author)
        self.feed_gen.link(href=settings.base_url, rel="self")
        self.feed_gen.subtitle(settings.description)
        self.feed_gen.language(str(settings.locale.locale))
        self.timezone: str = settings.timezone
        self.atom_path: pathlib.Path = settings.atom_path

    def add_entry(self, item_id: str, title: str, link: str, date: datetime.date):
        entry = self.feed_gen.add_entry()  # pyright: ignore[reportUnknownVariableType]
        entry.id(item_id)
        entry.title(title)
        entry.link(href=link)
        entry.updated(
            datetime.datetime.combine(
                date, datetime.time(), tzinfo=zoneinfo.ZoneInfo(self.timezone)
            ).isoformat()
        )

    def get_artifact(self) -> artifacts.BytesArtifact:
        contents: bytes = cast(bytes, self.feed_gen.atom_str(pretty=True))

        return artifacts.BytesArtifact(
            path=self.atom_path, contents=io.BytesIO(contents)
        )
