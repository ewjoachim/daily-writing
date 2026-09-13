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
import jsonschema
from typing_extensions import TypeForm

from daily_writing import utils

from . import artifacts, models
from . import settings as settings_module

logger = logging.getLogger("daily_writing")


class InvalidCMSConfig(Exception):
    pass


def _is_empty_default(value: typing.Any) -> bool:
    """Check if a serialized default value is empty (null, empty string, empty list, etc.).

    There is nothing worth telling the user about an empty default.
    """
    return value is None or (isinstance(value, str | list | dict) and not value)


def _describe_default(value: typing.Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in typing.cast("list[object]", value))
    return str(value)


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
    # Deliberately no `default` key: Sveltia only applies it when creating an
    # entry, and the settings file always exists, so it would never show. Worse,
    # on a new entry it would write the value into the file and freeze it, when
    # leaving it out lets the settings model supply it at build time. The hint is
    # the only part that renders either way, so that is where the fallback goes.
    serialized_default = field.serialized_default
    hint = field.description
    if not _is_empty_default(serialized_default):
        hint = f"{hint} Defaults to: {_describe_default(serialized_default)}".strip()

    return {
        "name": field.name,
        "label": field.name.replace("_", " ").title(),
        "required": field.required,
        "hint": hint,
        **sveltia_type_attributes(field=field),
        **field.override.kwargs,
    }


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
    config = get_cms_config(settings=settings)
    if schema := get_cms_schema(
        sveltia_version=settings.sveltia_version, cache_dir=settings.cache_dir
    ):
        validate_cms_config(config=config, schema=schema)
    yield artifacts.TextArtifact(
        path=config_path,
        contents=json.dumps(config, indent=2),
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


def get_cms_schema(
    sveltia_version: str, cache_dir: pathlib.Path
) -> dict[str, typing.Any] | None:
    cache_file = cache_dir / f"sveltia-schema-{sveltia_version}.json"
    if sveltia_version != "latest" and cache_file.exists():
        return json.loads(cache_file.read_text())

    schema_url = (
        f"https://unpkg.com/@sveltia/cms@{sveltia_version}/schema/sveltia-cms.json"
    )
    response = httpx.get(schema_url, follow_redirects=True)
    if response.status_code == httpx.codes.NOT_FOUND.value:
        # Sveltia only started shipping a schema in 0.202.0; an older pin is not a
        # reason to fail the build, it just cannot be checked.
        logger.warning(f"No CMS config schema at {schema_url}, skipping validation")
        return None
    response.raise_for_status()
    cache_file.write_text(response.text)
    return response.json()


def _variant_mismatch(errors: list[jsonschema.ValidationError]) -> bool:
    """A branch complaining about `widget` is just the wrong variant — a string
    field judging a list — so the rest of what it says describes nothing."""
    return any("widget" in list(error.schema_path) for error in errors)


def _error_path(error: jsonschema.ValidationError) -> str:
    return "/".join(str(part) for part in error.absolute_path) or "<root>"


def _config_errors(
    error: jsonschema.ValidationError,
) -> list[tuple[str, str]] | None:
    """Walk an error down to the (path, message) pairs worth showing, or None when
    no branch recognised what it was looking at.

    Fields are a deep pile of `anyOf`, one branch per widget, so a single mistake
    surfaces as a complaint from every widget that exists. Only branches that
    accepted the widget have anything to say about the field.
    """
    if not error.context:
        return [(_error_path(error), error.message)]

    branches: dict[typing.Any, list[jsonschema.ValidationError]] = {}
    for sub_error in error.context:
        branches.setdefault(sub_error.schema_path[0], []).append(sub_error)

    return [
        pair
        for errors in branches.values()
        if not _variant_mismatch(errors)
        for sub_error in errors
        if (pairs := _config_errors(sub_error)) is not None
        for pair in pairs
    ] or None


def validate_cms_config(
    config: dict[str, typing.Any], schema: dict[str, typing.Any]
) -> None:
    found: set[tuple[str, str]] = set()
    for error in jsonschema.Draft7Validator(schema).iter_errors(config):
        pairs = _config_errors(error)
        if pairs is None:
            instance = typing.cast("dict[str, typing.Any]", error.instance)
            widget = (
                instance.get("widget") if isinstance(error.instance, dict) else None
            )
            pairs = [(_error_path(error), f"unknown widget {widget!r}")]
        found.update(pairs)
    # An ancestor only ever restates what its own children already reported.
    deepest = {
        (path, message)
        for path, message in found
        if not any(other.startswith(f"{path}/") for other, _ in found)
    }
    if not deepest:
        return

    lines = "\n".join(f"  {path}: {message}" for path, message in sorted(deepest))
    raise InvalidCMSConfig(
        f"Sveltia would reject the generated CMS config:\n{lines}",
    )


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


def get_cms_config(settings: settings_module.Settings) -> dict[str, typing.Any]:
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
    return utils.deep_merge(config, settings.cms_config)


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
