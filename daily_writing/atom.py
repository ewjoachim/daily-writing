import datetime
import pathlib
import zoneinfo

from feedgen.feed import FeedGenerator  # pyright: ignore[reportMissingTypeStubs]

from . import models
from . import settings as settings_module


class Feed:
    def __init__(self, settings: settings_module.Settings):
        self.feed_gen: FeedGenerator = FeedGenerator()
        self.feed_gen.id(settings.base_url)
        self.feed_gen.title(settings.site_name)
        self.feed_gen.author(name=settings.author)
        self.feed_gen.link(href=settings.base_url, rel="self")
        self.feed_gen.subtitle(settings.description)
        self.feed_gen.language(settings.language)
        self.timezone: str = settings.timezone
        self.atom_path: pathlib.Path = settings.atom_path

    def add_entry(self, id: str, title: str, link: str, date: datetime.date):
        entry = self.feed_gen.add_entry()  # pyright: ignore[reportUnknownVariableType]
        entry.id(id)
        entry.title(title)
        entry.link(href=link)
        entry.updated(
            datetime.datetime.combine(
                date, datetime.time(), tzinfo=zoneinfo.ZoneInfo(self.timezone)
            ).isoformat()
        )

    def get_artifact(self) -> models.BytesArtifact:
        contents: bytes = self.feed_gen.atom_str(pretty=True)  # pyright: ignore[reportUnknownVariableType]
        return models.BytesArtifact(path=self.atom_path, contents=contents)  # pyright: ignore[reportUnknownArgumentType]
