import datetime
import enum
import io
import json
import logging
import pathlib
import types
import typing
from collections.abc import Iterable, Iterator

import httpx
from typing_extensions import TypeForm

from daily_writing import utils

from . import artifacts, models
from . import settings as settings_module

logger = logging.getLogger("daily_writing")


def _is_empty_default(value: typing.Any) -> bool:
    """Check if a serialized default value is empty (null, empty string, empty list, etc.).

    Empty defaults are not useful for CMS pre-population and cause unnecessary
    values to be written to content files.
    """
    return value is None or (isinstance(value, str | list | dict) and not value)


def clean_annotation(annotation: TypeForm[typing.Any]) -> TypeForm[typing.Any]:
    if isinstance(annotation, typing.TypeAliasType):
        return clean_annotation(annotation.__value__)
    origin = typing.get_origin(annotation)
    if origin is types.UnionType:
        members = [arg for arg in typing.get_args(annotation) if arg is not type(None)]
        if members:
            return clean_annotation(members[0])
    if origin is typing.Annotated:
        args = typing.get_args(annotation)
        if args:
            return clean_annotation(args[0])
    return annotation


def to_sveltia(field: settings_module.Field) -> dict[str, typing.Any]:
    serialized_default = field.serialized_default
    result: dict[str, typing.Any] = {
        "name": field.name,
        "label": field.name.replace("_", " ").title(),
        "required": field.required,
        "hint": field.description,
        **sveltia_type_attributes(field=field),
        **field.override.kwargs,
    }
    if not _is_empty_default(serialized_default):
        result["default"] = serialized_default
    return result


def _annotation_to_sveltia(
    annotation: typing.Any,
    override: settings_module.CMSFieldOverride,
    fields: Iterable[settings_module.Field] | None = None,
) -> dict[str, typing.Any]:
    """Infer the Sveltia widget name from a Python type annotation."""
    annotation = clean_annotation(annotation)
    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)
    if origin in {list, set, tuple}:
        result: dict[str, typing.Any] = {"widget": "list"}

        # A nested model surfaces as sub-fields; anything else recurses on its item.
        if fields is not None:
            result["fields"] = [to_sveltia(f) for f in fields]
        else:
            result["field"] = _annotation_to_sveltia(
                args[0], override=settings_module.CMSFieldOverride()
            ) | override.kwargs.pop("field", {})

        return result

    if fields is not None:
        return {"widget": "object", "fields": [to_sveltia(f) for f in fields]}

    if origin is typing.Literal:
        return {"widget": "select", "options": [str(e) for e in args]}
    if isinstance(annotation, type):
        if issubclass(annotation, bool):
            return {"widget": "boolean"}
        if issubclass(annotation, enum.Enum):
            return {
                "widget": "select",
                "option": [{"label": e.name, "value": e.value} for e in annotation],
            }
        if issubclass(annotation, (int, float)):
            return {"widget": "number"}
        if issubclass(annotation, datetime.date):
            return {
                "widget": "datetime",
                "format": "YYYY-MM-DD",
                "date_format": "YYYY-MM-DD",
                "time_format": False,
            }
        if issubclass(annotation, settings_module.Color):
            return {"widget": "color"}

    return {"widget": "string"}


def sveltia_type_attributes(field: settings_module.Field) -> dict[str, typing.Any]:
    """Infer the Sveltia widget name from a field's Python type annotation."""
    return _annotation_to_sveltia(field.annotation, field.override, fields=field.fields)


def cms_artifacts(
    settings: settings_module.Settings,
) -> Iterator[artifacts.BaseArtifact]:
    script_path = settings.build_cms_dir / "script.js"
    yield artifacts.BytesArtifact(
        contents=io.BytesIO(
            get_cms_script(
                sveltia_version=settings.sveltia_version,
                cache_dir=settings.cache_dir,
            )
        ),
        path=script_path,
    )
    config_path = settings.build_cms_dir / "config.json"
    yield artifacts.TextArtifact(
        path=settings.build_cms_dir / "index.html",
        contents=get_cms_index(
            title=f"{settings.site_name} - Admin",
            script_url=settings.url_path(script_path),
            config_url=settings.url_path(config_path),
        ),
    )
    yield artifacts.TextArtifact(
        path=config_path,
        contents=get_cms_config(settings=settings),
    )


def get_cms_script(sveltia_version: str, cache_dir: pathlib.Path) -> bytes:
    cache_file = cache_dir / f"sveltia-{sveltia_version}.js"
    if sveltia_version != "latest" and cache_file.exists():
        logger.info(f"Using cached Sveltia CMS version {sveltia_version}")
        return cache_file.read_bytes()

    cms_script_url = (
        f"https://unpkg.com/@sveltia/cms@{sveltia_version}/dist/sveltia-cms.js"
    )
    logger.debug(f"Downloading Sveltia @ {sveltia_version} from {cms_script_url}")
    response = httpx.get(cms_script_url, follow_redirects=True)
    response.raise_for_status()
    final_version = response.url.path.split("@", 1)[-1].split("/", 1)[0]
    logger.info(f"Using Sveltia CMS version {final_version} from {response.url}")
    result = response.content
    cache_file.write_bytes(result)
    return result


def get_cms_index(title: str, script_url: str, config_url: str) -> str:
    return f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="robots" content="noindex" />
    <title>{title}</title>
    <link href="{config_url}" type="application/json" rel="cms-config-url" />
  </head>
  <body>
    <script src="{script_url}"></script>
  </body>
</html>"""


def get_cms_config(settings: settings_module.Settings) -> str:
    config = {
        # Uploads are committed to the source tree, then copied to the build dir,
        # so these two are the same folder seen from the repo and from a browser.
        "media_folder": f"/{settings.source_static_dir}",
        "public_folder": settings.url_path(settings.build_static_dir),
        "singletons": [
            get_config_singleton(),
            get_homepage_singleton(homepage_path=settings.homepage_path),
        ],
        "collections": [get_writings_collection()],
        "site_url": str(settings.site_url),
        "logo": (
            {"src": settings.static_url(settings.logo)} if settings.logo else None
        ),
        "app_title": f"{settings.site_name} - Admin",
        "editor": {"preview": False},
        "output": {
            "omit_empty_optional_fields": True,
        },
    }
    config = utils.deep_merge(config, settings.cms_config)
    return json.dumps(config, indent=2)


def get_config_singleton() -> dict[str, typing.Any]:
    return {
        "name": "config",
        "label": "Settings",
        "file": "daily-writing.toml",
        "icon": "settings",
        "fields": [
            to_sveltia(field)
            for field in settings_module.Field.from_model(settings_module.Settings)
        ],
    }


def get_homepage_singleton(homepage_path: pathlib.Path) -> dict[str, typing.Any]:
    return {
        "name": "homepage",
        "label": "Home page",
        "file": str(homepage_path),
        "icon": "home",
        # Body only: the homepage file doubles as the repository README, and any
        # front matter we'd add here would render as a stray table on the repo
        # landing page. Its description falls back to an excerpt of the body.
        "fields": [{"name": "body", "widget": "markdown"}],
    }


def get_writings_collection() -> dict[str, typing.Any]:
    return {
        "name": "writings",
        "label": "Writings",
        "label_singular": "Writing",
        "folder": ".",
        "create": True,
        "sortable_fields": {
            "fields": ["date"],
            "default": {"field": "date", "direction": "descending"},
        },
        "view_groups": {
            "groups": [
                {
                    "name": "year-month",
                    "field": "date",
                    "label": "Year/Month",
                    "pattern": r"\d{4}-\d{2}",
                },
            ],
            "default": "year-month",
        },
        "path": "{{year}}/{{month}}/{{day}}-{{slug}}",
        "identifier_field": "full_title",
        "summary": "{{date | date('YYYY-MM')}}-{{full_title}}",
        "icon": "book_3",
        "fields": [
            {"name": "body", "widget": "markdown"},
            *(
                to_sveltia(field)
                for field in settings_module.Field.from_model(
                    models.MultiplePromptsFrontMatter
                )
            ),
        ],
    }
