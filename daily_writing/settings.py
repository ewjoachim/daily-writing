from __future__ import annotations

import datetime
import pathlib
import zoneinfo
from typing import Annotated, final, override

import pydantic
import pydantic_extra_types.color
import pydantic_extra_types.language_code
import pydantic_settings
import tzlocal


class IconLink(pydantic.BaseModel):
    rel: str
    type: str | None = None
    sizes: str | None = None
    href: str


class ColorCycle(pydantic.BaseModel):
    colors: list[pydantic_extra_types.color.Color]

    def __getitem__(self, i: int) -> str:
        return self.colors[i % len(self.colors)].as_hex()


LOCAL_TIMEZONE = tzlocal.get_localzone().key


class Build(pydantic.BaseModel):
    pass


class Serve(pydantic.BaseModel):
    pass


class Settings(
    pydantic_settings.BaseSettings,
    env_prefix="DAILY_WRITING_",
    pyproject_toml_table_header=("tool", "daily-writing"),
):
    # Dirs
    source_dir: pathlib.Path = pathlib.Path.cwd()
    build_dir: pathlib.Path = pathlib.Path("_build")
    source_static_dir: pathlib.Path = pathlib.Path("static")
    build_static_dir: pathlib.Path = pathlib.Path("static")

    # Cutoff date
    provided_until: datetime.date = pydantic.Field(
        default_factory=lambda data: datetime.datetime.now(
            tz=zoneinfo.ZoneInfo(data.get("timezone", LOCAL_TIMEZONE))
        ).date()
    )

    # Metadata
    site_name: str
    description: str
    copyright: str
    author: str
    month: int
    month_name: str
    years: list[int]
    language: pydantic_extra_types.language_code.LanguageAlpha2
    timezone: str = LOCAL_TIMEZONE

    # URLs
    base_url: str
    repository_url: str
    atom_path: pathlib.Path = pathlib.Path("feed.atom")

    # Style
    colors: list[pydantic_extra_types.color.Color]
    index_colors: list[str]
    extra_css: list[pathlib.Path] = []
    ## Images
    social_preview_width: int = 1200
    social_preview_height: int = 630
    social_preview_path: pathlib.Path = pathlib.Path("social_previews")
    logo: pathlib.Path
    icon_links: list[IconLink]
    # Fonts
    body_font_family: list[str]
    body_font_file_woff2: pathlib.Path
    title_font_family: list[str]
    title_font_file_woff2: pathlib.Path

    # Server
    inject_hot_reload_js: bool = False

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

    @property
    def color_cycle(self) -> ColorCycle:
        return ColorCycle(colors=self.colors)

    @property
    def subcommand(self) -> Build | Serve:
        return pydantic_settings.get_subcommand(self)

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
            pydantic_settings.CliSettingsSource(
                settings_cls,
                cli_parse_args=True,
                cli_kebab_case=True,
            ),
            env_settings,
            pydantic_settings.TomlConfigSettingsSource(
                settings_cls,
                toml_file="daily-writing.toml",
            ),
            pydantic_settings.PyprojectTomlConfigSettingsSource(settings_cls),
        )
