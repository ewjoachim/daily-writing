import io
import pathlib
from typing import Any

import fontbuilder
import pytest
import yarl

from daily_writing import i18n, models, social_preview
from daily_writing import settings as settings_module


@pytest.fixture
def dw_settings(tmp_path: pathlib.Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "README.md").write_text("# Test\n")

    def f(**kwargs: Any) -> settings_module.Settings:
        defaults: dict[str, Any] = {
            "site_url": yarl.URL("https://foo.bar/"),
            "site_name": "Site Name",
            "timezone": "Europe/Paris",
            "locale": i18n.Locale.from_string("fr-fr"),
        }
        return settings_module.Settings(**(defaults | kwargs))

    return f


@pytest.fixture
def write_md(tmp_path: pathlib.Path):
    """Write a markdown file under tmp_path (creating parent dirs) and return its path."""

    def f(name: str, content: str) -> pathlib.Path:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    return f


@pytest.fixture
def make_writing(write_md):
    """Build a Writing through the real from_path pipeline (via an on-disk file)."""

    def f(
        name: str = "01-backpack.md",
        content: str = "# 01 - Backpack\n\nSome writing.\n",
        *,
        month: int = 10,
        year: int = 2024,
    ) -> models.Writing:
        return models.Writing.from_path(
            path=write_md(name, content), month=month, year=year
        )

    return f


@pytest.fixture
def variable_font_bytes() -> bytes:
    return fontbuilder.build_variable_font()


@pytest.fixture
def variable_font(tmp_path: pathlib.Path, variable_font_bytes: bytes) -> pathlib.Path:
    path = tmp_path / "TestVariable.ttf"
    path.write_bytes(variable_font_bytes)
    return path


@pytest.fixture
def page_metadata():
    def f(**kwargs: Any) -> models.PageMetadata:
        defaults: dict[str, Any] = {
            "title": "Title",
            "url_path": "",
            "description": "Description",
            "social_preview_path": pathlib.Path("social_previews/index.png"),
            "social_preview_signature": "abcd1234",
            "repository_url": None,
        }
        return models.PageMetadata(**{**defaults, **kwargs})

    return f


@pytest.fixture
def social_preview_contents():
    def f(**kwargs: Any) -> social_preview.SocialPreviewContents:
        defaults: dict[str, Any] = {
            "top_line": "Top",
            "title": "Title",
            "description": "Description",
            "logo": None,
            "date": "October 2024",
            "colors": ["#ffffff"],
            "body_font": [io.BytesIO(b"body")],
            "title_font": [io.BytesIO(b"title")],
        }
        return social_preview.SocialPreviewContents(**{**defaults, **kwargs})

    return f
