from typing import Any

import pydantic.networks
import pytest

from daily_writing import i18n
from daily_writing import settings as settings_module


@pytest.fixture
def dw_settings(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

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
