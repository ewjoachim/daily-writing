import datetime
import functools
import io
import itertools
import logging
import pathlib
import re
from collections.abc import Iterator
from typing import Annotated, Any, Self

import frontmatter
import markdown_it
import markdown_it.tree
import pydantic
from mdit_py_plugins import footnote
from pydantic import dataclasses as pdataclasses

from . import i18n, utils
from . import settings as settings_module

logger = logging.getLogger("daily_writing")


class PartialPrompt(pydantic.BaseModel):
    title: str | None = None
    original_prompt: str | None = None
    date: datetime.date | None = None

    @classmethod
    def combine(cls, *items: Self | None) -> Self:

        return cls(
            title=next((e.title for e in items if e and e.title), None),
            original_prompt=next(
                (e.original_prompt for e in items if e and e.original_prompt), None
            ),
            date=next((e.date for e in items if e and e.date), None),
        )


class NotAWriting(Exception):
    pass


class TitleNotFound(Exception):
    pass


class DayNumberNotFound(Exception):
    pass


class DuplicateDate(Exception):
    pass


class NoPromptsFound(Exception):
    pass


@pdataclasses.dataclass(kw_only=True)
class Prompt:
    date: datetime.date
    color_index: int
    title: str
    original_prompt: str | None

    @classmethod
    def extract(
        cls,
        filename_prompts: list[PartialPrompt],
        markdown_title_prompts: list[PartialPrompt],
        front_matter_prompts: list[PartialPrompt],
        color_offset: int,
    ) -> Iterator[Self]:

        previous_date: datetime.date | None = None

        for (
            from_frontmatter,
            from_filename,
            from_markdown_title,
        ) in itertools.zip_longest(
            front_matter_prompts,
            filename_prompts,
            markdown_title_prompts,
            fillvalue=None,
        ):
            combined = PartialPrompt.combine(
                from_frontmatter, from_filename, from_markdown_title
            )

            if not combined.date:
                if not previous_date:
                    logger.warning("Could not determine date")
                    return
                combined.date = previous_date + datetime.timedelta(days=1)

            previous_date = combined.date

            combined.title = combined.title or ""

            yield cls(
                date=combined.date,
                color_index=(combined.date.day + color_offset - 1),
                original_prompt=combined.original_prompt,
                title=combined.title,
            )


class BaseFrontMatter(pydantic.BaseModel):
    full_title: Annotated[
        str | None,
        pydantic.Field(
            description="Full title for the writing (can be auto-generated from individual prompt titles)"
        ),
    ] = None
    description: Annotated[
        str | None,
        pydantic.Field(
            description="Additional text for the writing, appearing in various SEO tags or the social preview image. Defaults to the first words of the writing."
        ),
    ] = None
    redirect_aliases: Annotated[
        list[pathlib.Path],
        pydantic.Field(description=""),
        settings_module.CMSFieldOverride(
            collapsed=True,
            summary="{{fields.alias}}",
            field={
                "label": "Alias (url path that should redirect to the main url, e.g. previous/path/to/writing.html)"
            },
        ),
    ] = []
    date: Annotated[
        datetime.date | None,
        pydantic.Field(description="Date of first prompt (mainly used for CMS)"),
    ] = None


class SinglePromptFrontMatter(BaseFrontMatter, PartialPrompt):
    pass


class MultiplePromptsFrontMatter(BaseFrontMatter):
    prompts: Annotated[
        list[PartialPrompt],
        settings_module.CMSFieldOverride(
            collapsed=False,
            summary="{{fields.title}}",
        ),
    ]


def select_model(v: Any) -> Any:
    if isinstance(v, dict) and "prompts" in v:
        return "multiple"
    return "single"


class FrontMatter(
    pydantic.RootModel[
        Annotated[
            Annotated[SinglePromptFrontMatter, pydantic.Tag("single")]
            | Annotated[MultiplePromptsFrontMatter, pydantic.Tag("multiple")],
            pydantic.Discriminator(select_model),
        ]
    ]
):
    pass


@pdataclasses.dataclass(
    kw_only=True, config=pydantic.ConfigDict(arbitrary_types_allowed=True)
)
class MarkdownFile:
    md_path: pathlib.Path
    post: frontmatter.Post
    markdown_it_preset: str = "commonmark"

    @classmethod
    def from_md_path(cls, md_path: pathlib.Path) -> Self:
        return cls(
            md_path=md_path, post=frontmatter.load(io.StringIO(md_path.read_text()))
        )

    @functools.cached_property
    def writing_metadata(self) -> SinglePromptFrontMatter | MultiplePromptsFrontMatter:
        return FrontMatter.model_validate(self.post.metadata).root

    @functools.cached_property
    def base_metadata(self) -> BaseFrontMatter:
        return BaseFrontMatter.model_validate(self.post.metadata)

    @property
    def markdown(self) -> str:
        return self.post.content

    def excerpt(self, max_length: int = 200) -> str:
        return utils.excerpt(text=self.text_content, max_length=max_length)

    @property
    def description(self) -> str:
        return self.writing_metadata.description or self.excerpt()

    @property
    def front_matter_prompts(self) -> list[PartialPrompt]:
        if isinstance(self.writing_metadata, MultiplePromptsFrontMatter):
            return sorted(
                self.writing_metadata.prompts,
                key=lambda p: p.date or datetime.date.max,
            )

        return [self.writing_metadata]

    @property
    def markdown_title(self) -> str | None:
        for node in self._root_node.walk():
            if node.type == "heading":
                return self._plain_text(node)

    @property
    def _markdown_it_parser(self):
        parser = markdown_it.MarkdownIt(
            config=self.markdown_it_preset, options_update={"typographer": True}
        )
        parser.enable(["replacements", "smartquotes"])
        parser.use(footnote.footnote_plugin)
        return parser

    def get_html(self, title_fallback: str):
        markdown = self.markdown
        if self.markdown_title is None:
            markdown = f"# {title_fallback}\n{markdown}"
        return self._markdown_it_parser.render(markdown)

    @functools.cached_property
    def text_content(self) -> str:
        return self._plain_text(self._root_node)

    @property
    def _root_node(self):
        parsed = self._markdown_it_parser.parse(self.markdown)
        return markdown_it.tree.SyntaxTreeNode(parsed)

    def _plain_text(self, node: markdown_it.tree.SyntaxTreeNode):
        return " ".join(el.content.strip() for el in node.walk() if not el.children)


def extract_filename_prompts(
    year: int, month: int, stem: str
) -> Iterator[PartialPrompt]:
    # When split by "-", parts that are integers are assumed to be day numbers
    # and other parts are assumed to be original prompts, in the same order.
    # Note: 1-foo-2-bar or 1-2-foo-bar are both ok.

    dates: list[datetime.date] = []
    original_prompts: list[str] = []
    for part in stem.split("-"):
        try:
            day_number = int(part)
        except ValueError:
            original_prompts.append(part)
        else:
            dates.append(datetime.date(year=year, month=month, day=day_number))

    yield from (
        PartialPrompt(date=date, original_prompt=original_prompt)
        for date, original_prompt in itertools.zip_longest(
            dates, original_prompts, fillvalue=None
        )
    )


def extract_markdown_title_prompts(
    year: int,
    month: int,
    markdown_title: str | None,
) -> Iterator[PartialPrompt]:
    if not markdown_title:
        return

    match = re.match(
        pattern=r"(?:(?P<day_numbers>\d+( *& *\d+)*)( *- *))?(?P<titles>.+)$",
        string=markdown_title,
    )
    if not match:
        yield PartialPrompt(date=None, title=markdown_title)
        return

    groups = match.groupdict()
    dates = [
        datetime.date(year=year, month=month, day=int(e.strip()))
        for e in (groups["day_numbers"] or "").split("&")
    ]
    titles = [e.strip() for e in groups["titles"].split(",")]
    if len(dates) != len(titles):
        titles = [groups["titles"].strip()]

    yield from (
        PartialPrompt(date=date, title=title)
        for date, title in itertools.zip_longest(dates, titles, fillvalue=None)
    )


def extract_full_title(markdown_file: MarkdownFile, prompts: list[Prompt]) -> str:
    if markdown_title := markdown_file.markdown_title:
        return markdown_title

    if markdown_file.writing_metadata.full_title:
        return markdown_file.writing_metadata.full_title

    day_numbers = [p.date.day for p in prompts]
    title_parts = [p.title for p in prompts]

    return f"{'&'.join(f'{d:02d}' for d in day_numbers)} - {', '.join(e.capitalize() for e in title_parts)}"


@pdataclasses.dataclass(kw_only=True, frozen=True)
class Writing:
    url: str
    prompts: list[Prompt]
    markdown_file: MarkdownFile
    full_title: str

    @classmethod
    def from_path(
        cls,
        path: pathlib.Path,
        month: int,
        year: int,
    ) -> Self:
        if path.suffix.lower() != ".md":
            raise NotAWriting

        markdown_file = MarkdownFile.from_md_path(md_path=path)
        filename_prompts = list(
            extract_filename_prompts(
                year=year,
                month=month,
                stem=path.stem,
            )
        )
        markdown_title_prompts = list(
            extract_markdown_title_prompts(
                year=year,
                month=month,
                markdown_title=markdown_file.markdown_title,
            )
        )
        front_matter_prompts = markdown_file.front_matter_prompts
        prompts = sorted(
            Prompt.extract(
                filename_prompts=filename_prompts,
                markdown_title_prompts=markdown_title_prompts,
                front_matter_prompts=front_matter_prompts,
                color_offset=utils.first_weekday(year, month),
            ),
            key=lambda p: p.date,
        )
        if not prompts:
            raise NoPromptsFound(f"""Could not find prompts for {path}:
                {filename_prompts=},
                {markdown_title_prompts=},
                {front_matter_prompts=}""")
        full_title = extract_full_title(markdown_file=markdown_file, prompts=prompts)

        url_elements = [
            *[f"{p.date.day}" for p in prompts],
            *[p.original_prompt for p in prompts if p.original_prompt],
        ]
        url = f"{year}/{month}/{'-'.join(url_elements)}/"

        return cls(
            url=url,
            prompts=prompts,
            markdown_file=markdown_file,
            full_title=full_title,
        )

    @classmethod
    def get_all_writings(
        cls,
        settings: settings_module.Settings,
        restrict_to_paths: set[pathlib.Path] | None = None,
    ) -> list[Writing]:
        return sorted(
            cls._get_all_writings(
                settings=settings, restrict_to_paths=restrict_to_paths
            ),
            key=lambda w: w.first_date,
        )

    @classmethod
    def _get_all_writings(
        cls,
        settings: settings_module.Settings,
        restrict_to_paths: set[pathlib.Path] | None = None,
    ) -> Iterator[Writing]:
        all_seen_dates: set[datetime.date] = set()
        for year_folder in sorted(settings.source_dir.iterdir()):
            if not year_folder.is_dir():
                continue
            try:
                year = int(year_folder.name)
            except ValueError, TypeError:
                logger.debug(f"{year_folder}: Folder is not a number")
                continue
            if not (2000 < year < 3000):
                logger.debug(f"{year_folder}: Folder is not a year number")
                continue

            for month_folder in sorted(year_folder.iterdir()):
                if not month_folder.is_dir():
                    continue
                try:
                    month = int(month_folder.name)
                except TypeError:
                    logger.debug(f"{month_folder}: Folder is not a number")
                    continue
                if not (1 <= month <= 12):
                    logger.debug(f"{month_folder}: Folder is not a month number")
                    continue
                logger.info(f"Processing {year}/{month}")
                yield from cls.get_all_writings_for_month(
                    source_dir=settings.source_dir,
                    folder=month_folder,
                    month=month,
                    year=year,
                    restrict_to_paths=restrict_to_paths,
                    all_seen_dates=all_seen_dates,
                )

    @classmethod
    def by_year_month(
        cls, writings: list[Writing]
    ) -> dict[tuple[int, int], list[PromptGroup]]:
        writings_by_year_month: dict[tuple[int, int], list[PromptGroup]] = {}
        for writing in writings:
            for group in writing.prompt_groups:
                year = group.first_date.year
                month = group.first_date.month
                writings_by_year_month.setdefault((year, month), []).append(group)
        for pair in writings_by_year_month.values():
            pair.sort(key=lambda p: p.first_date)

        return writings_by_year_month

    @classmethod
    def get_all_writings_for_month(
        cls,
        *,
        source_dir: pathlib.Path,
        folder: pathlib.Path,
        month: int,
        year: int,
        restrict_to_paths: set[pathlib.Path] | None = None,
        all_seen_dates: set[datetime.date],
    ) -> Iterator[Writing]:
        for path in sorted(folder.iterdir()):
            if restrict_to_paths and path not in restrict_to_paths:
                logger.debug(
                    f"{path}: Skipping as not in request paths ({restrict_to_paths})"
                )
                continue
            try:
                writing = cls.from_path(
                    path=path.relative_to(source_dir, walk_up=True),
                    month=month,
                    year=year,
                )
            except NotAWriting:
                logger.debug(f"{path}: Skipping as not a writing", exc_info=True)
                continue
            dates = set(writing.dates)
            if duplicate_dates := (dates & all_seen_dates):
                raise DuplicateDate(
                    f"Multiple writings found for date(s) {', '.join(str(d) for d in duplicate_dates)}"
                )
            all_seen_dates |= dates
            yield writing

    @functools.cached_property
    def dates(self) -> list[datetime.date]:
        return [p.date for p in self.prompts]

    @property
    def md_path(self) -> pathlib.Path:
        return self.markdown_file.md_path

    @functools.cached_property
    def markdown(self) -> str:
        return self.markdown_file.markdown

    @functools.cached_property
    def first_date(self) -> datetime.date:
        return self.prompts[0].date

    @functools.cached_property
    def last_date(self) -> datetime.date:
        return self.prompts[-1].date

    @functools.cached_property
    def prompt_groups(self) -> list[PromptGroup]:
        def group_key(item: tuple[int, Prompt]) -> tuple[int, int, int, int]:
            index, prompt = item
            return utils.date_grouper(index, prompt, key=lambda p: p.date)

        return [
            PromptGroup(prompts=[prompt for _, prompt in enum_group], writing=self)
            for _, enum_group in itertools.groupby(
                enumerate(self.prompts), key=group_key
            )
        ]

    @functools.cached_property
    def single_prompt_group(self) -> PromptGroup:
        return PromptGroup(prompts=self.prompts, writing=self)


class PromptGroup(pydantic.BaseModel):
    """
    A group of prompts that can be displayed together (they're consecutive, in the same
    week and in the same months)
    """

    prompts: list[Prompt]
    writing: Writing

    @functools.cached_property
    def dates(self) -> list[datetime.date]:
        return [p.date for p in self.prompts]

    @property
    def first_date(self) -> datetime.date:
        return self.dates[0]

    def __len__(self) -> int:
        return len(self.prompts)

    def get_subtitle(self, locale: i18n.Locale) -> str | None:

        return ", ".join(
            i18n.month_date(
                year=year,
                month=month,
                locale=locale,
            )
            for year, month in sorted(
                {(p.date.year, p.date.month) for p in self.prompts}
            )
        )


@pdataclasses.dataclass(kw_only=True)
class PageMetadata:
    title: str | None
    url_path: str | None
    description: str
    social_preview_url: str
    repository_url: str
