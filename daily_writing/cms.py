import datetime
import enum
import io
import json
import logging
import pathlib
import types
import typing
from collections.abc import Iterator

import httpx
import pydantic.fields
import pydantic_extra_types.color
from pydantic import TypeAdapter
from pydantic import dataclasses as pdataclasses
from pydantic_core import PydanticUndefined
from pydantic_settings.sources.types import _CliSubCommand  # noqa: PLC2701
from typing_extensions import TypeForm

from daily_writing import utils

from . import artifacts, models
from . import settings as settings_module

logger = logging.getLogger("daily_writing")


def _serialize_default(value: typing.Any, annotation: typing.Any) -> typing.Any:
    """Convert a Python default value to a JSON-serializable Sveltia default value."""
    if value is PydanticUndefined:
        return None
    return TypeAdapter(annotation).dump_python(value, mode="json")


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


@pdataclasses.dataclass(config=pydantic.ConfigDict(arbitrary_types_allowed=True))
class Field:
    name: str
    annotation: typing.Any
    description: str
    required: bool
    override: settings_module.CMSFieldOverride
    default: typing.Any = PydanticUndefined

    @classmethod
    def from_pydantic(
        cls, name: str, field_info: pydantic.fields.FieldInfo
    ) -> typing.Self:
        """Pull the type annotation and optional CMS override out of a settings field."""
        override = next(
            (
                meta
                for meta in field_info.metadata
                if isinstance(meta, settings_module.CMSFieldOverride)
            ),
            settings_module.CMSFieldOverride(),
        )
        default = (
            field_info.default
            if not field_info.is_required() and field_info.default_factory is None
            else PydanticUndefined
        )
        return cls(
            name=name,
            annotation=field_info.annotation,
            description=field_info.description or "",
            required=field_info.is_required(),
            override=override,
            default=default,
        )

    def to_sveltia(self) -> dict[str, typing.Any]:
        serialized_default = _serialize_default(
            self.default, annotation=self.annotation
        )
        result: dict[str, typing.Any] = {
            "name": self.name,
            "label": self.name.replace("_", " ").title(),
            "required": self.required,
            "hint": self.description,
            **self.sveltia_type_attributes(),
            **self.override.kwargs,
        }
        if not _is_empty_default(serialized_default):
            result["default"] = serialized_default
        return result

    @staticmethod
    def _annotation_to_sveltia(
        annotation: typing.Any,
        override: settings_module.CMSFieldOverride,
    ) -> dict[str, typing.Any]:
        """Infer the Sveltia widget name from a Python type annotation."""
        annotation = clean_annotation(annotation)
        origin = typing.get_origin(annotation)
        args = typing.get_args(annotation)
        if origin in {list, set, tuple}:
            result: dict[str, typing.Any] = {"widget": "list"}

            item_type = args[0]

            # Pydantic BaseModel -> generate a fields array
            if isinstance(item_type, type) and issubclass(
                item_type, pydantic.BaseModel
            ):
                result["fields"] = [
                    Field.from_pydantic(name=name, field_info=field_info).to_sveltia()
                    for name, field_info in item_type.model_fields.items()
                ]
            else:
                result["field"] = Field._annotation_to_sveltia(
                    item_type, override=settings_module.CMSFieldOverride()
                ) | override.kwargs.pop("field", {})

            return result

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
            if issubclass(annotation, pydantic_extra_types.color.Color):
                return {"widget": "color"}

        return {"widget": "string"}

    def sveltia_type_attributes(self) -> dict[str, typing.Any]:
        """Infer the Sveltia widget name from a field's Python type annotation."""
        return self._annotation_to_sveltia(self.annotation, self.override)


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
    config_url = settings.build_cms_dir / "config.json"
    yield artifacts.TextArtifact(
        path=settings.build_cms_dir / "index.html",
        contents=get_cms_index(
            title=f"{settings.site_name} - Admin",
            script_url=f"/{script_path}",
            config_url=f"/{config_url}",
        ),
    )
    yield artifacts.TextArtifact(
        path=config_url,
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
        "media_folder": f"/{settings.build_static_dir}",
        "public_folder": f"/{settings.build_static_dir}",
        "singletons": [get_config_collection()],
        "collections": [get_writings_collection()],
        "site_url": str(settings.site_full_url),
        "logo": (
            {"src": f"/{settings.source_static_dir / settings.logo}"}
            if settings.logo
            else None
        ),
        "app_title": f"{settings.site_name} - Admin",
        "editor": {"preview": False},
        "output": {
            "omit_empty_optional_fields": True,
        },
    }
    config = utils.deep_merge(config, settings.cms_config)
    return json.dumps(config, indent=2)


def get_config_collection() -> dict[str, typing.Any]:
    return {
        "name": "config",
        "label": "Settings",
        "file": "daily-writing.toml",
        "icon": "settings",
        "fields": [
            Field.from_pydantic(name=name, field_info=field_info).to_sveltia()
            for name, field_info in settings_module.Settings.model_fields.items()
            if not any(m is _CliSubCommand for m in field_info.metadata)
        ],
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
                Field.from_pydantic(name=name, field_info=field_info).to_sveltia()
                for name, field_info in models.MultiplePromptsFrontMatter.model_fields.items()
            ),
        ],
    }
