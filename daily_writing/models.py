from __future__ import annotations

import calendar
import dataclasses
import datetime
import functools
import hashlib
import pathlib
import tomllib
import zoneinfo
from collections.abc import Iterable, Mapping, Sequence
from typing import Self, override

import pydantic
import pydantic_extra_types.color
from pydantic import dataclasses as pdataclasses

from . import settings as settings_module
from . import utils


@pdataclasses.dataclass(kw_only=True)
class Prompt:
    day_number: int
    color_index: int
    title: str
    original_prompt: str


@pdataclasses.dataclass(kw_only=True)
class MarkdownFile:
    md_path: pathlib.Path

    @functools.cached_property
    def markdown(self) -> str:
        return self.md_path.read_text()

    def excerpt(self, max_length: int = 200) -> str:
        return utils.excerpt(markdown=self.markdown, max_length=max_length)

    @property
    def full_title(self) -> str:
        for line in self.markdown.splitlines():
            if line.startswith("# "):
                return line.removeprefix("# ")

        return ""

    @property
    def title_elements(self) -> tuple[str, str]:
        num, title = tuple(self.full_title.split(" - ", maxsplit=1))
        return num, title

    @property
    def title(self) -> str:
        return self.title_elements[-1]


@pdataclasses.dataclass(kw_only=True)
class Writing:
    date: datetime.date
    original_prompt: str

    @classmethod
    def from_path(cls, path: pathlib.Path, month: int) -> Self:
        year = path.parent.name
        day_title = path.stem
        day, word = day_title.split("-", 1)
        return cls(date=datetime.date(int(year), month, int(day)), original_prompt=word)

    @classmethod
    def get_all(cls, settings: settings_module.Settings) -> Writings:
        result: dict[int, list[Self]] = {}
        for year in settings.years:
            year_folder = settings.source_dir / f"{year}"
            for path in sorted(year_folder.glob("[0-9][0-9]-*.md")):
                writing = cls.from_path(path, month=settings.month)
                if writing.date > settings.provided_until:
                    return result
                result.setdefault(year, []).append(writing)

        return result

    @property
    def md_path(self) -> pathlib.Path:
        return self.path("md")

    @property
    def html_path(self) -> pathlib.Path:
        return self.path("html")

    def path(self, ext: str) -> pathlib.Path:
        return (
            pathlib.Path(f"{self.year}")
            / f"{self.day_number:02}-{self.original_prompt}.{ext}"
        )

    @property
    def day_number(self):
        return self.date.day

    @property
    def year(self):
        return self.date.year

    @classmethod
    @functools.cache
    def days_count_for_month(cls, year: int, month: int) -> int:
        return calendar.monthrange(year, month)[-1]

    @classmethod
    @functools.cache
    def first_weekday(cls, year: int, month: int) -> int:
        return calendar.monthrange(year, month)[0]

    @functools.cached_property
    def markdown_file(self) -> MarkdownFile:
        return MarkdownFile(md_path=self.md_path)

    def excerpt(self, max_length: int = 200) -> str:
        return utils.excerpt(markdown=self.markdown, max_length=max_length)

    @property
    def markdown(self) -> str:
        return self.markdown_file.markdown

    @property
    def full_title(self) -> str:
        return self.markdown_file.full_title

    @property
    def title_elements(self) -> tuple[str, str]:
        return self.markdown_file.title_elements

    @property
    def title(self) -> str:
        return self.markdown_file.title

    @property
    def prompts(self) -> Iterable[Prompt]:
        first = self.first_weekday(year=self.year, month=self.date.month)
        numbers, titles_str = self.title_elements
        day_numbers = (int(e) for e in numbers.split("&"))
        original_prompts = self.original_prompt.split("-")
        titles = titles_str.split(", ")
        for original_prompt, title, day_number in zip(
            original_prompts, titles, day_numbers
        ):
            yield Prompt(
                day_number=day_number,
                color_index=(day_number + first - 1),
                original_prompt=original_prompt.title(),
                title=title,
            )

    def social_preview_filename(self, signature: str) -> str:
        return str(self.path(f"{signature}.png")).replace("/", "-")


type Writings = Mapping[int, Sequence[Writing]]


@pdataclasses.dataclass(kw_only=True)
class PageMetadata:
    title: str | None
    url_path: str | None
    description: str
    social_preview_path: pathlib.Path
    repository_url_path: pathlib.Path


@pdataclasses.dataclass(kw_only=True)
class TextArtifact:
    path: pathlib.Path
    contents: str

    def write(self, dir: pathlib.Path):
        if self.path.is_absolute():
            raise ValueError("Only relative paths are accepted")

        (dir / self.path).parent.mkdir(exist_ok=True, parents=True)
        (dir / self.path).write_text(self.contents)


@pdataclasses.dataclass(kw_only=True)
class HTMLArtifact(TextArtifact):
    @override
    def write(self, dir: pathlib.Path):
        super().write(dir=dir)


@pdataclasses.dataclass(kw_only=True)
class BytesArtifact:
    path: pathlib.Path
    contents: bytes

    def write(self, dir: pathlib.Path):
        if self.path.is_absolute():
            raise ValueError("Only relative paths are accepted")

        (dir / self.path).parent.mkdir(exist_ok=True, parents=True)
        (dir / self.path).write_bytes(self.contents)


@pdataclasses.dataclass(kw_only=True)
class FeedEntryArtifact:
    id: str
    title: str
    link: str
    date: datetime.date


type Artifact = (
    TextArtifact | HTMLArtifact | BytesArtifact | FeedEntryArtifact | FileArtifact
)


@pdataclasses.dataclass(kw_only=True)
class FileArtifact:
    path: pathlib.Path
    source: pathlib.Path
    destination: pathlib.Path

    def write(self, dir: pathlib.Path):
        rel = self.path.relative_to(self.source)
        destination = dir / self.destination / rel
        destination.parent.mkdir(exist_ok=True, parents=True)
        self.path.copy(destination)


@pdataclasses.dataclass(kw_only=True)
class SocialPreviewContents:
    """
    Parameters for generating a social preview PNG.
    """

    top_line: str
    title: str
    description: str
    logo: pathlib.Path
    date: str | None  # this might not strictly be a date
    colors: list[str]
    body_font_file_woff2: pathlib.Path
    title_font_file_woff2: pathlib.Path

    @property
    def signature(self) -> str:
        return hashlib.md5(str(dataclasses.asdict(self)).encode()).hexdigest()[:8]
