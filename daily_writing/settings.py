import datetime
import enum
import functools
import os
import pathlib
import tomllib
import types
import typing
import zoneinfo
from collections.abc import Iterable
from typing import Annotated, Any, Literal, Self, override

import pydantic
import pydantic_extra_types.color
import pydantic_settings
import tzlocal
import yarl
from pydantic import dataclasses as pdataclasses

from . import i18n

# Re-exported so cms.py can recognise colour fields without importing pydantic.
Color = pydantic_extra_types.color.Color


class _Missing:
    """Sentinel for a field with no default, kept independent of pydantic."""


MISSING = _Missing()


class CMSFieldOverride:
    """Overrides merged into the Sveltia field config auto-generated for a setting.

    Any keyword arguments are forwarded verbatim into the Sveltia field config.
    Attach to a setting through its annotation, e.g.
    ``Annotated[..., pydantic.Field(...), CMSFieldOverride(widget="image")]``.
    """

    def __init__(self, **kwargs: Any):
        self.kwargs: dict[str, Any] = kwargs


def _referenced_model(annotation: Any) -> type[pydantic.BaseModel] | None:
    """Return the pydantic model referenced by ``annotation``, directly or as a
    collection/optional item, if any. Keeps model introspection out of cms.py."""
    if isinstance(annotation, typing.TypeAliasType):
        return _referenced_model(annotation.__value__)
    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)
    if origin is typing.Annotated:
        return _referenced_model(args[0]) if args else None
    if origin is types.UnionType:
        return next(
            (
                model
                for arg in args
                if arg is not type(None)
                and (model := _referenced_model(arg)) is not None
            ),
            None,
        )
    if origin in {list, set, tuple}:
        return _referenced_model(args[0]) if args else None
    if isinstance(annotation, type) and issubclass(annotation, pydantic.BaseModel):
        return annotation
    return None


@pdataclasses.dataclass(config=pydantic.ConfigDict(arbitrary_types_allowed=True))
class Field:
    """
    Own class for abstracting pydantic while allowing introspection
    """

    name: str
    annotation: Any
    description: str
    required: bool
    override: CMSFieldOverride
    default: Any = MISSING
    fields: Iterable[Self] | None = None

    @property
    def has_default(self) -> bool:
        return self.default is not MISSING

    @property
    def serialized_default(self) -> Any:
        """The default as a JSON-serializable value, or None when there is none."""
        if not self.has_default:
            return None
        return pydantic.TypeAdapter(self.annotation).dump_python(
            self.default, mode="json"
        )

    @classmethod
    def from_model(cls, model: type[pydantic.BaseModel]) -> list[Self]:
        """Introspect a pydantic model into a flat list of ``Field``."""
        return [
            cls.from_field_info(name=name, field_info=field_info)
            for name, field_info in model.model_fields.items()
        ]

    @classmethod
    def from_field_info(cls, name: str, field_info: pydantic.fields.FieldInfo) -> Self:
        """Build a single ``Field`` from a pydantic ``FieldInfo``."""
        override = next(
            (
                meta
                for meta in field_info.metadata
                if isinstance(meta, CMSFieldOverride)
            ),
            CMSFieldOverride(),
        )
        default = (
            field_info.default
            if not field_info.is_required() and field_info.default_factory is None
            else MISSING
        )
        model = _referenced_model(field_info.annotation)
        return cls(
            name=name,
            annotation=field_info.annotation,
            description=field_info.description or "",
            required=field_info.is_required(),
            override=override,
            default=default,
            fields=cls.from_model(model) if model is not None else None,
        )


class IconLink(pydantic.BaseModel):
    rel: str
    type: str | None = None
    sizes: str | None = None
    href: str


class ColorCycle(pydantic.BaseModel):
    colors: list[pydantic_extra_types.color.Color]

    def __getitem__(self, i: int) -> str:
        return hex_color(self.colors[i % len(self.colors)])


class Build(pydantic.BaseModel):
    pass


class Serve(pydantic.BaseModel):
    additional_paths: Annotated[
        set[pydantic.DirectoryPath | pydantic.FilePath],
        pydantic.Field(description="Additional paths on which to use autoreload"),
    ] = set()


class Normalize(pydantic.BaseModel):
    paths: Annotated[
        pydantic_settings.CliPositionalArg[set[pydantic.FilePath]],
        pydantic.Field(description="Files to normalize"),
    ] = set()

    rewrite: Annotated[
        bool,
        pydantic.Field(description="If set, overwrites existing front-matters"),
    ] = False


type GenericFont = Literal["serif", "sans-serif"]


def validate_locale(value: Any) -> Any:
    if not value:
        return value

    if isinstance(value, i18n.Locale):
        return value

    try:
        return i18n.Locale.from_string(value)
    except i18n.LocaleError as exc:
        raise pydantic.ValidationError(str(exc)) from exc


class DayOfWeek(enum.StrEnum):
    Monday = "Monday"
    Tuesday = "Tuesday"
    Wednesday = "Wednesday"
    Thursday = "Thursday"
    Friday = "Friday"
    Saturday = "Saturday"
    Sunday = "Sunday"

    @property
    def as_int(self) -> int:
        return list(type(self)).index(self)


@functools.cache
def _pyproject_project() -> dict[str, Any]:
    """Read and cache the [project] section from pyproject.toml."""
    try:
        data = tomllib.loads(pathlib.Path("pyproject.toml").read_text())
        return data.get("project", {})
    except FileNotFoundError, tomllib.TOMLDecodeError:
        return {}


def _slug_to_title(slug: str) -> str:
    return slug.replace("-", " ").replace("_", " ").title()


def _default_site_name(data: dict[str, Any]) -> str:
    project = _pyproject_project()
    name = project.get("name")
    if name:
        return _slug_to_title(name)
    src_dir = data.get("source_dir", pathlib.Path("."))
    return _slug_to_title(pathlib.Path(str(src_dir)).resolve().name)


def _default_description() -> str | None:
    return _pyproject_project().get("description")


def _default_author() -> str | None:
    authors = _pyproject_project().get("authors", [])
    if authors:
        return authors[0].get("name")
    return None


def _default_repository_url() -> str:
    if (repo := os.environ.get("GITHUB_REPOSITORY")) and (
        github_server := os.environ.get("GITHUB_SERVER_URL")
    ):
        return str(yarl.URL(github_server) / repo)
    project = _pyproject_project()
    urls = project.get("urls", {})
    return urls.get("Repository") or urls.get("Repository")


class Settings(
    pydantic_settings.BaseSettings,
    env_prefix="DAILY_WRITING_",
    pyproject_toml_table_header=("tool", "daily-writing"),
    case_sensitive=False,
):
    # Metadata
    site_name: Annotated[
        str,
        pydantic.Field(
            description="Name of the website. Appears in multiple places.",
            default_factory=_default_site_name,
        ),
    ]
    description: Annotated[
        str | None,
        pydantic.Field(
            description="Description of the website.",
            default_factory=_default_description,
        ),
        CMSFieldOverride(widget="text"),
    ]
    copyright: Annotated[
        str | None,
        pydantic.Field(description="Copyright mention, appears in the footer"),
    ] = None
    author: Annotated[
        str | None,
        pydantic.Field(
            description="Author name, appears in the RSS feed.",
            default_factory=_default_author,
        ),
    ]
    locale: Annotated[
        i18n.Locale,
        pydantic.BeforeValidator(validate_locale),
        pydantic.Field(
            description="Website language (used for the HTML declaration and the location of dates). Format: BCP47 (e.g. en-US)",
            default_factory=i18n.Locale.default,
        ),
        CMSFieldOverride(
            pattern=[
                "^[a-z]{2}-[a-z]{2}$",
                "Must be in format xx-xx (e.g. fr-fr)",
            ],
        ),
    ]
    repository_link_name: Annotated[
        str,
        pydantic.Field(
            description="Text of the link to the corresponding repositry page in the footer"
        ),
    ] = "GitHub"
    feed_name: Annotated[
        str,
        pydantic.Field(description="Text of the link to the RSS feed in the footer"),
    ] = "RSS"

    timezone: Annotated[
        str,
        pydantic.Field(
            description="Name of the timezone (used to determine midnight, which controls when new writings appear for the current day)",
            default_factory=lambda: tzlocal.get_localzone().key,
        ),
    ]
    first_day_of_week: Annotated[
        DayOfWeek,
        pydantic.Field(
            description="Determines the first day of the week for the calendar display."
        ),
    ] = DayOfWeek.Monday

    # URLs
    site_url: Annotated[
        yarl.URL,
        pydantic.Field(description="Website URL. (e.g. https://example.com/path)"),
    ] = yarl.URL("http://localhost:8000")

    repository_url: Annotated[
        str | None,
        pydantic.Field(
            description="URL where the sources of the website are available.",
            default_factory=_default_repository_url,
        ),
    ]
    repository_file_url_prefix: Annotated[
        str,
        pydantic.Field(
            description="Path element to add after the repository URL so that adding the path to a file to this yields a valid URL to a file on the repository"
        ),
    ] = "blob/HEAD"
    atom_path: Annotated[
        pathlib.Path,
        pydantic.Field(
            description="Path at which the Atom feed file will be written in the build directory (no leading slash)."
        ),
    ] = pathlib.Path("feed.atom")
    homepage_path: Annotated[
        pydantic.FilePath,
        pydantic.Field(
            description="Path to the file for which content will be used for the homepage of the site."
        ),
    ] = pathlib.Path("README.md")

    # Style
    colors: Annotated[
        list[pydantic_extra_types.color.Color],
        pydantic.Field(
            description="List of colors used throughout a given month. Will cycle if there are less than the number of days in said month. Should be harmonious if displayed as a grid of width 7 or less."
        ),
        CMSFieldOverride(field={"label": "Color", "required": True}),
    ] = [pydantic_extra_types.color.Color("#ffffff")]
    index_colors: Annotated[
        list[pydantic_extra_types.color.Color],
        pydantic.Field(
            description="The index page will have a color bar containing a gradient of the colors defined here from top to bottom."
        ),
        CMSFieldOverride(field={"label": "Color", "required": True}),
    ] = [pydantic_extra_types.color.Color("#ffffff")]
    extra_css: Annotated[
        list[pydantic.FilePath],
        pydantic.Field(
            description="List of extra CSS files to add to the HTML pages. Must all be under the source static folder."
        ),
        CMSFieldOverride(field={"label": "Path to CSS"}),
    ] = []
    # Images
    social_preview_width: Annotated[
        int,
        pydantic.Field(description="Horizontal dimension of the social preview image."),
    ] = 1200
    social_preview_height: Annotated[
        int,
        pydantic.Field(description="Vertical dimension of the social preview image."),
    ] = 630
    social_preview_path: Annotated[
        pathlib.Path,
        pydantic.Field(
            description="Path to which social preview images will be saved."
        ),
    ] = pathlib.Path("social_previews")
    logo: Annotated[
        pathlib.Path | None,
        pydantic.Field(
            description="Website logo. Must be under the source static folder."
        ),
        CMSFieldOverride(widget="image"),
    ] = None
    icon_links: Annotated[
        list[IconLink],
        pydantic.Field(
            description="All the information necessary to build the <link> tags that describe different favicons (compatible with, e.g. https://favicon.io/)"
        ),
    ] = []
    # Fonts
    title_ttf_font: Annotated[
        pydantic.FilePath | list[pydantic.FilePath] | str | None,
        pydantic.Field(
            description="Font for titles (all sizes). Either a path to a .ttf file or the name of a Google Font that will be downloaded. In case direct paths to ttf files are provided, it may be multiple files for font variant, but you all the files will need to be part of the same font family."
        ),
    ] = None
    title_ttf_font_fallback: Annotated[
        GenericFont,
        pydantic.Field(
            description='Fallback font for titles. Either "serif" or "sans-serif".'
        ),
    ] = "sans-serif"
    body_ttf_font: Annotated[
        pydantic.FilePath | list[pydantic.FilePath] | str | None,
        pydantic.Field(
            description="Font for body. Either a path to a .ttf file or the name of a Google Font that will be downloaded. In case direct paths to ttf files are provided, it may be multiple files for font variant, but you all the files will need to be part of the same font family."
        ),
    ] = None
    body_ttf_font_fallback: Annotated[
        GenericFont,
        pydantic.Field(
            description='Fallback font for body. Either "serif" or "sans-serif".'
        ),
    ] = "sans-serif"

    verbosity: Annotated[
        Literal["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
        pydantic.Field(
            description="Verbosity level (0=Critical, 1=Error, 2=Warning, 3=Info, 4=debug)"
        ),
        CMSFieldOverride(hint="Verbosity level"),
    ] = "INFO"

    include_cms: Annotated[
        bool,
        pydantic.Field(description="Whether to include a Sveltia CMS admin"),
        CMSFieldOverride(widget="hidden"),
    ] = True

    cms_config: Annotated[
        dict[str, pydantic.JsonValue],
        pydantic.Field(description="Additional config for the CMS"),
        CMSFieldOverride(widget="hidden"),
    ] = {}

    sveltia_version: Annotated[
        str,
        pydantic.Field(
            description="Version of Sveltia to pull or 'latest' for the latest one (download is cached unless latest is used)"
        ),
        CMSFieldOverride(widget="hidden"),
    ] = "latest"

    # Dirs
    source_dir: Annotated[
        pydantic.DirectoryPath,
        pydantic.Field(
            description="Directory containing the source files for the website"
        ),
    ] = pathlib.Path(".")

    build_dir: Annotated[
        pydantic.DirectoryPath | pydantic.NewPath,
        pydantic.Field(
            description="Directory in which to place the resulting website. If it exists, it will be emptied at the start of the run."
        ),
    ] = pathlib.Path("_build")

    cache_dir: Annotated[
        pydantic.DirectoryPath | pydantic.NewPath,
        pydantic.Field(
            description="Directory containing cached assets to simplify subsequent builds."
        ),
    ] = pathlib.Path("_cache")

    source_static_dir: Annotated[
        pathlib.Path,
        pydantic.Field(
            description="Path where the static assets are stored. All files in here will be copied as-is to the build static dir."
        ),
    ] = pathlib.Path("static")

    build_static_dir: Annotated[
        pathlib.Path,
        pydantic.Field(
            description="Path to which static should be stored in the build dir. Will likely be a part of the URL for static files."
        ),
    ] = pathlib.Path("static")

    build_cms_dir: Annotated[
        pathlib.Path,
        pydantic.Field(
            description="Path to which the CMS will be written to. Will likely be the URL path of the CMS."
        ),
    ] = pathlib.Path("admin")

    fonts_css_filename: Annotated[
        str,
        pydantic.Field(
            description="Name of the generated css file containing font definitions."
        ),
    ] = "fonts.css"

    # Cutoff date
    max_date: datetime.date = pydantic.Field(
        default_factory=lambda data: datetime.datetime.now(
            tz=zoneinfo.ZoneInfo(data.get("timezone") or tzlocal.get_localzone().key)
        ).date(),
        description="Writings for dates strictly after this date will be ignored in build. Defaults to today.",
    )

    @property
    def build_static_path(self) -> str:
        path = "/"
        if self.build_static_dir:
            path += f"{self.build_static_dir}/"
        return path

    @property
    def base_path(self) -> yarl.URL:
        return yarl.URL(self.site_url.path)

    @property
    def color_cycle(self) -> ColorCycle:
        return ColorCycle(colors=self.colors)

    @property
    def index_colors_hex(self) -> list[str]:
        return [hex_color(c) for c in self.index_colors]

    @property
    def github_token(self):
        return os.environ.get("GITHUB_TOKEN")

    @override
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[pydantic_settings.BaseSettings],
        init_settings: pydantic_settings.PydanticBaseSettingsSource,
        env_settings: pydantic_settings.PydanticBaseSettingsSource,
        dotenv_settings: pydantic_settings.PydanticBaseSettingsSource,
        file_secret_settings: pydantic_settings.PydanticBaseSettingsSource,
    ) -> tuple[pydantic_settings.PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            pydantic_settings.TomlConfigSettingsSource(
                settings_cls,
                toml_file="daily-writing.toml",
            ),
            pydantic_settings.PyprojectTomlConfigSettingsSource(settings_cls),
        )


class CLISettings(Settings):
    # Subcommands
    build: Annotated[
        pydantic_settings.CliSubCommand[Build],
        pydantic.Field(description="Build the website"),
    ]
    serve: Annotated[
        pydantic_settings.CliSubCommand[Serve],
        pydantic.Field(
            description="Start a local server that rebuilds the server on every change, with hot reload"
        ),
    ]
    normalize: Annotated[
        pydantic_settings.CliSubCommand[Normalize],
        pydantic.Field(
            description="Add frontmatter to writings that don't have it, extracting metadata from filename and content"
        ),
    ]

    @property
    def subcommand(self) -> Build | Serve | Normalize | None:
        return pydantic_settings.get_subcommand(self)  # pyright: ignore[reportReturnType]

    @override
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[pydantic_settings.BaseSettings],
        init_settings: pydantic_settings.PydanticBaseSettingsSource,
        env_settings: pydantic_settings.PydanticBaseSettingsSource,
        dotenv_settings: pydantic_settings.PydanticBaseSettingsSource,
        file_secret_settings: pydantic_settings.PydanticBaseSettingsSource,
    ) -> tuple[pydantic_settings.PydanticBaseSettingsSource, ...]:
        return (  # pyright: ignore[reportUnknownVariableType]
            init_settings,
            pydantic_settings.CliSettingsSource(
                settings_cls,
                cli_kebab_case=True,
                cli_parse_args=True,
                cli_implicit_flags=True,
            ),
            env_settings,
            pydantic_settings.TomlConfigSettingsSource(
                settings_cls,
                toml_file="daily-writing.toml",
            ),
            pydantic_settings.PyprojectTomlConfigSettingsSource(settings_cls),
        )


def hex_color(color: pydantic_extra_types.color.Color) -> str:
    return color.as_hex(format="long")
