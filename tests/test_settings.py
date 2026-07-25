import datetime
import pathlib

import pydantic
import pydantic_extra_types.color
import pytest

from daily_writing import i18n
from daily_writing import settings as settings_module


def test_hex_color():
    color = pydantic_extra_types.color.Color("#abc")
    assert settings_module.hex_color(color) == "#aabbcc"


def test_color_cycle_getitem_wraps():
    cycle = settings_module.ColorCycle(
        colors=[
            pydantic_extra_types.color.Color("#000000"),
            pydantic_extra_types.color.Color("#ffffff"),
        ]
    )
    assert cycle[0] == "#000000"
    assert cycle[2] == "#000000"  # wraps around


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (settings_module.DayOfWeek.Monday, 0),
        (settings_module.DayOfWeek.Sunday, 6),
    ],
)
def test_day_of_week_as_int(day, expected):
    assert day.as_int == expected


def test_slug_to_title():
    assert settings_module._slug_to_title("my-cool_site") == "My Cool Site"


def test_cms_field_override_stores_kwargs():
    override = settings_module.CMSFieldOverride(widget="image", foo="bar")
    assert override.kwargs == {"widget": "image", "foo": "bar"}


def test_validate_locale__from_string():
    result = settings_module.validate_locale("fr-fr")
    assert isinstance(result, i18n.Locale)


def test_validate_locale__passthrough_locale():
    locale = i18n.Locale.from_string("fr-fr")
    assert settings_module.validate_locale(locale) is locale


def test_validate_locale__empty_passthrough():
    assert settings_module.validate_locale(None) is None


class _Model(pydantic.BaseModel):
    required_field: str
    optional_field: int = 5


def test_field_from_model():
    fields = {f.name: f for f in settings_module.Field.from_model(_Model)}

    assert fields["required_field"].required is True
    assert fields["required_field"].has_default is False
    assert fields["optional_field"].required is False
    assert fields["optional_field"].has_default is True
    assert fields["optional_field"].default == 5


def test_field_serialized_default():
    fields = {f.name: f for f in settings_module.Field.from_model(_Model)}

    assert fields["optional_field"].serialized_default == 5
    assert fields["required_field"].serialized_default is None


class _Nested(pydantic.BaseModel):
    value: str


class _Outer(pydantic.BaseModel):
    items: list[_Nested] = []


def test_field_from_model__nested_model_expands_subfields():
    field = settings_module.Field.from_model(_Outer)[0]
    assert field.fields is not None
    assert [f.name for f in field.fields] == ["value"]


@pytest.mark.parametrize(
    ("annotation", "expected"),
    [
        (list[_Nested], _Nested),
        (_Nested | None, _Nested),
        (str, None),
    ],
)
def test_referenced_model(annotation, expected):
    assert settings_module._referenced_model(annotation) is expected


def test_settings_properties(dw_settings):
    settings = dw_settings()

    assert settings.build_static_path == "/static/"
    assert str(settings.base_path) == "/"
    assert isinstance(settings.color_cycle, settings_module.ColorCycle)
    assert settings.index_colors_hex == ["#ffffff"]


def test_default_site_name__from_pyproject(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "my-site"\n')
    settings_module._pyproject_project.cache_clear()

    assert settings_module._default_site_name({}) == "My Site"


def test_default_site_name__from_source_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    settings_module._pyproject_project.cache_clear()

    result = settings_module._default_site_name({"source_dir": tmp_path})
    assert result == settings_module._slug_to_title(tmp_path.resolve().name)


def test_default_author__from_pyproject(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nauthors = [{name = "Alice"}]\n'
    )
    settings_module._pyproject_project.cache_clear()

    assert settings_module._default_author() == "Alice"


@pytest.fixture(autouse=True)
def _clear_pyproject_cache():
    yield
    settings_module._pyproject_project.cache_clear()


def test_settings_max_date_default(dw_settings):
    settings = dw_settings()
    assert isinstance(settings.max_date, datetime.date)


def test_atom_path_default(dw_settings):
    assert dw_settings().atom_path == pathlib.Path("feed.atom")
