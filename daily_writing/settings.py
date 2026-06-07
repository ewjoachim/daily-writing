import datetime
import enum
import os
import pathlib
import zoneinfo
from typing import Annotated, Any, Literal, override

import pydantic
import pydantic.networks
import pydantic_extra_types.color
import pydantic_settings
import tzlocal
import yarl

from . import i18n


class CMSFieldOverride:
    """Overrides merged into the Sveltia field config auto-generated for a setting.

    Any keyword arguments are forwarded verbatim into the Sveltia field config.
    Attach to a setting through its annotation, e.g.
    ``Annotated[..., pydantic.Field(...), CMSFieldOverride(widget="image")]``.
    """

    def __init__(self, **kwargs: Any):
        self.kwargs: dict[str, Any] = kwargs


class IconLink(pydantic.BaseModel):
    rel: str
    type: str | None = None
    sizes: str | None = None
    href: str


class ColorCycle(pydantic.BaseModel):
    colors: list[pydantic_extra_types.color.Color]

    def __getitem__(self, i: int) -> str:
        return hex_color(self.colors[i % len(self.colors)])


LOCAL_TIMEZONE = tzlocal.get_localzone().key


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


class Settings(
    pydantic_settings.BaseSettings,
    env_prefix="DAILY_WRITING_",
    pyproject_toml_table_header=("tool", "daily-writing"),
    case_sensitive=False,
):
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
        pydantic.DirectoryPath,
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
            tz=zoneinfo.ZoneInfo(data.get("timezone", LOCAL_TIMEZONE))
        ).date(),
        description="Writings for dates strictly after this date will be ignored in build. Defaults to today.",
    )

    # Metadata
    site_name: Annotated[
        str,
        pydantic.Field(description="Name of the website. Appears in multiple places."),
    ]
    description: Annotated[
        str,
        pydantic.Field(description="Description of the website."),
        CMSFieldOverride(widget="text"),
    ]
    copyright: Annotated[
        str | None,
        pydantic.Field(description="Copyright mention, appears in the footer"),
    ] = None
    author: Annotated[
        str, pydantic.Field(description="Author name, appears in multiple places.")
    ]
    locale: Annotated[
        i18n.Locale,
        pydantic.BeforeValidator(validate_locale),
        pydantic.Field(
            description="Website language (used for the HTML declaration and the location of dates). Format: BCP47 (e.g. en-US)"
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
            description="Name of the timezone (used to determine midnight, which controls when new writings appear for the current day)"
        ),
    ] = LOCAL_TIMEZONE
    first_day_of_week: Annotated[
        DayOfWeek,
        pydantic.Field(
            description="Determines the first day of the week for the calendar display."
        ),
    ] = DayOfWeek.Monday

    # URLs
    server_url: Annotated[
        pydantic.networks.HttpUrl,
        pydantic.Field(
            description="Root server URL. (e.g. https://writober.ewjoach.im/)"
        ),
    ]
    base_path: Annotated[
        str,
        pydantic.Field(
            description="Under server_url, path to the root of the website (no leading slash)."
        ),
    ] = ""
    repository_url: Annotated[
        str | None,
        pydantic.Field(
            description="URL where the sources of the website are available."
        ),
    ] = None
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

    @property
    def build_static_path(self) -> str:
        path = "/"
        if self.build_static_dir:
            path += f"{self.build_static_dir}/"
        return path

    @property
    def site_full_url(self) -> yarl.URL:
        return yarl.URL(str(self.server_url)) / self.base_path

    @property
    def color_cycle(self) -> ColorCycle:
        return ColorCycle(colors=self.colors)

    @property
    def index_colors_hex(self) -> list[str]:
        return [hex_color(c) for c in self.index_colors]

    @property
    def subcommand(self) -> Build | Serve | Normalize | None:
        return pydantic_settings.get_subcommand(self)  # pyright: ignore[reportReturnType]

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
        return (  # pyright: ignore[reportUnknownVariableType]
            init_settings,
            pydantic_settings.CliSettingsSource(
                settings_cls,
                cli_kebab_case=True,
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
