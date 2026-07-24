import pathlib
from typing import Any

import pytest

from daily_writing import i18n
from daily_writing import settings as settings_module


@pytest.fixture
def dw_settings(tmp_path: pathlib.Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "README.md").write_text("# Test\n")

    def f(**kwargs: Any) -> settings_module.Settings:
        return settings_module.Settings(
            server_url=pydantic.networks.HttpUrl("https://foo.bar"),
            # Make tests deterministic:
            site_name="Site Name",
            timezone="Europe/Paris",
            locale=i18n.Locale.from_string("fr-fr"),
            **kwargs,
        )

    return f
