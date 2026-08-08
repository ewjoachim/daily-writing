import datetime
import pathlib

import pydantic
import pydantic_extra_types.color
import pytest
import yarl

from daily_writing import i18n
from daily_writing import settings as settings_module


@pytest.fixture
def pyproject(tmp_path, monkeypatch):
    """Factory writing an optional pyproject.toml in a fresh cwd and clearing the
    cached parse. Returns the (possibly absent) pyproject.toml path."""
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "pyproject.toml"

    def f(content: str | None = None) -> pathlib.Path:
        if content is not None:
            path.write_text(content)
        settings_module._pyproject_project.cache_clear()
        return path

    return f


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

    assert settings.static_url("style.css") == "/static/style.css"
    assert str(settings.base_path) == "/"
    assert isinstance(settings.color_cycle, settings_module.ColorCycle)
    assert settings.index_colors_hex == ["#ffffff"]


@pytest.mark.parametrize(
    ("site_url", "expected"),
    [
        ("http://localhost:8000", "/static/style.css"),
        ("https://example.com/", "/static/style.css"),
        ("https://example.com/my-project", "/my-project/static/style.css"),
        ("https://example.com/my-project/", "/my-project/static/style.css"),
    ],
)
def test_settings_static_url__base_path(dw_settings, site_url, expected):
    settings = dw_settings(site_url=site_url)

    assert settings.static_url("style.css") == expected


def test_settings_url_path__base_path(dw_settings):
    settings = dw_settings(site_url="https://example.com/my-project")

    assert settings.url_path(pathlib.Path("feed.atom")) == "/my-project/feed.atom"
    assert settings.url_path("/admin/script.js") == "/my-project/admin/script.js"


def test_settings_source_static_url(dw_settings, tmp_path):
    """A source path is rewritten to where the build serves it from, keeping any
    subdirectory."""
    (tmp_path / "sources" / "css").mkdir(parents=True)
    (tmp_path / "sources" / "css" / "extra.css").write_text("/* extra */")
    settings = dw_settings(source_static_dir="sources", build_static_dir="assets")

    result = settings.source_static_url(pathlib.Path("sources/css/extra.css"))

    assert result == "/assets/css/extra.css"


def test_settings_extra_css__outside_source_static_dir(dw_settings, tmp_path):
    (tmp_path / "elsewhere.css").write_text("/* nope */")

    with pytest.raises(pydantic.ValidationError, match="must be under"):
        dw_settings(extra_css=["elsewhere.css"])


def test_default_site_name__from_pyproject(pyproject):
    pyproject('[project]\nname = "my-site"\n')

    assert settings_module._default_site_name({}) == "My Site"


def test_default_site_name__from_source_dir(tmp_path, pyproject):
    pyproject()

    result = settings_module._default_site_name({"source_dir": tmp_path})
    assert result == settings_module._slug_to_title(tmp_path.resolve().name)


def test_default_author__from_pyproject(pyproject):
    pyproject('[project]\nname = "x"\nauthors = [{name = "Alice"}]\n')

    assert settings_module._default_author() == "Alice"


def test_default_site_url__from_pyproject(pyproject):
    pyproject('[project]\nname = "x"\nurls = {Homepage = "https://example.com/blog"}\n')

    assert settings_module._default_site_url() == yarl.URL("https://example.com/blog")


def test_default_site_url__fallback(pyproject):
    pyproject('[project]\nname = "x"\n')

    assert settings_module._default_site_url() == yarl.URL("http://localhost:8000")


def test_default_repository_url__from_pyproject(pyproject):
    pyproject(
        '[project]\nname = "x"\nurls = {Repository = "https://codeberg.org/me/repo"}\n'
    )

    assert settings_module._default_repository_url() == "https://codeberg.org/me/repo"


@pytest.fixture(autouse=True)
def _clear_pyproject_cache():
    yield
    settings_module._pyproject_project.cache_clear()


def test_settings_max_date_default(dw_settings):
    settings = dw_settings()
    assert isinstance(settings.max_date, datetime.date)


def test_atom_path_default(dw_settings):
    assert dw_settings().atom_path == pathlib.Path("feed.atom")
