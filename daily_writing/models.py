from __future__ import annotations

import datetime
import functools
import io
import logging
import pathlib
import re
from collections.abc import Iterable, Iterator
from typing import Any, Self

import frontmatter
from pydantic import dataclasses as pdataclasses

from . import settings as settings_module
from . import utils

logger = logging.getLogger("daily_writing")


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
    def post(self) -> frontmatter.Post:
        return frontmatter.load(io.StringIO(self.md_path.read_text()))

    @property
    def metadata(self) -> dict[str, Any]:
        return self.post.metadata

    @property
    def markdown(self) -> str:
        return self.post.content

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


class NotAWriting(Exception):
    pass


@pdataclasses.dataclass(kw_only=True)
class Writing:
    path: pathlib.Path
    date: datetime.date
    original_prompt: str
    month_is_fixed: bool
    prompts: list[Prompt]

    @classmethod
    def from_path(
        cls, path: pathlib.Path, month: int, year: int, month_is_fixed: bool
    ) -> Self:
        if path.suffix.lower() != ".md":
            raise NotAWriting

        day = None
        original_prompt = None
        if match := re.match(r"^(?P<day_number>\d+)\-(?P<title>\w+)\.md$", path.name):
            day = int(match.group("day_number"))
            original_prompt = match.group("title")

        prompts
        return cls(
            date=datetime.date(year, month, day),
            original_prompt=original_prompt,
            month_is_fixed=month_is_fixed,
            prompts=prompts,
        )

    @classmethod
    def get_all_writings(cls, settings: settings_module.Settings) -> Iterator[Writing]:
        for year_folder in sorted(settings.source_dir.iterdir()):
            if not year_folder.is_dir():
                continue
            try:
                year = int(year_folder.name)
            except ValueError, TypeError:
                continue
            if not (2000 < year < 3000):
                continue
            logger.info(f"Processing year {year}")

            if settings.fixed_month:
                month = settings.fixed_month
                yield from cls._find_days(
                    folder=year_folder,
                    month=settings.fixed_month,
                    year=year,
                    month_is_fixed=True,
                )
            else:
                for month_folder in sorted(year_folder.iterdir()):
                    if not month_folder.is_dir():
                        continue
                    try:
                        month = int(month_folder.name)
                    except TypeError:
                        continue
                    if not (1 < month <= 12):
                        continue
                    yield from cls._find_days(
                        folder=month_folder,
                        month=month,
                        year=year,
                        month_is_fixed=False,
                    )

    @classmethod
    def _find_days(
        cls, folder: pathlib.Path, month: int, year: int, month_is_fixed: bool
    ) -> Iterator[Writing]:
        for path in sorted(folder.iterdir()):
            try:
                writing = cls.from_path(
                    path, month=month, year=year, month_is_fixed=month_is_fixed
                )
            except NotAWriting:
                continue
            yield writing

    @property
    def html_path(self) -> pathlib.Path:
        return self.path("html")

    def path(self, ext: str) -> pathlib.Path:
        path = pathlib.Path(f"{self.year}")
        if not self.month_is_fixed:
            path /= f"{self.month:02}"

        return path / f"{self.day_number:02}-{self.original_prompt}.{ext}"

    @functools.cached_property
    def year(self) -> int:
        return self.date.year

    @functools.cached_property
    def month(self) -> int:
        return self.date.month

    @functools.cached_property
    def day_number(self) -> int:
        return self.date.day

    @functools.cached_property
    def markdown_file(self) -> MarkdownFile:
        return MarkdownFile(md_path=self.md_path)

    def excerpt(self, max_length: int = 200) -> str:
        return utils.excerpt(markdown=self.markdown, max_length=max_length)

    @functools.cached_property
    def markdown(self) -> str:
        return self.markdown_file.markdown

    @functools.cached_property
    def full_title(self) -> str:
        return self.markdown_file.full_title

    @functools.cached_property
    def title_elements(self) -> tuple[str, str]:
        return self.markdown_file.title_elements

    @functools.cached_property
    def title(self) -> str:
        return self.markdown_file.title

    @functools.cached_property
    def prompts(self) -> Iterable[Prompt]:
        first = utils.first_weekday(self.year, self.month)
        numbers, titles_str = self.title_elements
        day_numbers = (int(e) for e in numbers.split("&"))
        original_prompts = self.original_prompt.split("-")
        titles = titles_str.split(", ")
        result: list[Prompt] = []
        for original_prompt, title, day_number in zip(
            original_prompts, titles, day_numbers
        ):
            result.append(
                Prompt(
                    day_number=day_number,
                    color_index=(day_number + first - 1),
                    original_prompt=original_prompt.title(),
                    title=title,
                )
            )

        return result

    def social_preview_filename(self) -> str:
        filename = str(self.path("png")).replace("/", "-")
        return filename


type Writings = dict[int, dict[int, list[Writing]]]


@pdataclasses.dataclass(kw_only=True)
class PageMetadata:
    title: str | None
    url_path: str | None
    description: str
    social_preview_url: str
    repository_url: str
