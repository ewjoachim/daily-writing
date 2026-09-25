import json
import pathlib

import pytest

from daily_writing import cms


def test_cms_config_uses_homepage_path(dw_settings):
    settings = dw_settings(homepage_path="README.md")

    config = cms.get_cms_config(settings=settings)

    homepage = next(s for s in config["singletons"] if s["name"] == "homepage")
    assert homepage["file"] == "README.md"


def test_cms_config_omits_excluded_settings(dw_settings):
    """Build-steering settings are not editable content; they stay out of the form."""
    config = cms.get_cms_config(settings=dw_settings())

    settings_singleton = next(s for s in config["singletons"] if s["name"] == "config")
    names = [field["name"] for field in settings_singleton["fields"]]

    assert "verbosity" not in names
    assert "site_name" in names


def test_cms_config_states_defaults_in_the_hint(dw_settings):
    """Sveltia only applies `default` when creating an entry, and the settings file
    always exists — so the fallback has to be stated where it always renders."""
    config = cms.get_cms_config(settings=dw_settings())

    fields = next(s for s in config["singletons"] if s["name"] == "config")["fields"]
    by_name = {field["name"]: field for field in fields}

    assert not [field for field in fields if "default" in field]
    assert by_name["feed_name"]["hint"].endswith("Defaults to: RSS")
    # A list default reads as a plain enumeration rather than a repr.
    assert by_name["index_colors"]["hint"].endswith("Defaults to: white")
    # Nothing worth saying about a field that has no default.
    assert "Defaults to:" not in by_name["copyright"]["hint"]


def test_cms_config_hint_survives_an_unserializable_default(dw_settings):
    """`locale` defaults to a Babel locale, which has no JSON form; that must not
    take down the whole config."""
    config = cms.get_cms_config(settings=dw_settings())

    fields = next(s for s in config["singletons"] if s["name"] == "config")["fields"]

    assert (
        "Defaults to:" not in next(f for f in fields if f["name"] == "locale")["hint"]
    )


def test_cms_config_homepage_edits_the_body(dw_settings):
    """The homepage singleton edits page content, not the site settings."""
    config = cms.get_cms_config(settings=dw_settings())

    homepage = next(s for s in config["singletons"] if s["name"] == "homepage")

    assert homepage["fields"] == [{"name": "body", "widget": "markdown"}]


def test_cms_config_media_folders(dw_settings):
    """media_folder is where uploads are committed, public_folder where they are
    served from: distinct settings, and the latter carries the site's base path."""
    settings = dw_settings(
        site_url="https://example.com/my-project",
        source_static_dir="sources",
        build_static_dir="assets",
    )

    config = cms.get_cms_config(settings=settings)

    assert config["media_folder"] == "/sources"
    assert config["public_folder"] == "/my-project/assets"


def test_get_cms_script__downloads_then_uses_cache(httpx_mock, tmp_path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    httpx_mock.add_response(
        url="https://unpkg.com/@sveltia/cms@1.2.3/dist/sveltia-cms.js",
        content=b"// sveltia",
    )

    first = cms.get_cms_script(sveltia_version="1.2.3", cache_dir=cache_dir)
    assert first == b"// sveltia"

    # A pinned version is cached; the second call must not hit the network.
    second = cms.get_cms_script(sveltia_version="1.2.3", cache_dir=cache_dir)
    assert second == b"// sveltia"


def test_cms_config_select_lists_its_options(dw_settings):
    """`first_day_of_week` is an enum: Sveltia renders it as a select, and a select
    without `options` is rejected outright."""
    config = cms.get_cms_config(settings=dw_settings())

    fields = next(s for s in config["singletons"] if s["name"] == "config")["fields"]
    field = next(f for f in fields if f["name"] == "first_day_of_week")

    assert field["widget"] == "select"
    assert {"label": "Monday", "value": "Monday"} in field["options"]


def test_cms_config_list_items_are_named(dw_settings):
    """Sveltia requires a name on a list's item field, even for a list of plain
    values, and rejects the whole field without one."""
    config = cms.get_cms_config(settings=dw_settings())

    fields = next(s for s in config["singletons"] if s["name"] == "config")["fields"]
    by_name = {field["name"]: field for field in fields}

    assert by_name["colors"]["field"]["name"] == "value"
    assert by_name["colors"]["field"]["widget"] == "color"


def test_cms_config_list_item_name_can_be_overridden(dw_settings):
    """`redirect_aliases` names its item field so its `summary` can refer to it."""
    config = cms.get_cms_config(settings=dw_settings())

    fields = next(c for c in config["collections"] if c["name"] == "writings")["fields"]
    field = next(f for f in fields if f["name"] == "redirect_aliases")

    assert field["field"]["name"] == "alias"
    assert field["summary"] == "{{fields.alias}}"


def test_get_cms_schema__downloads_then_uses_cache(httpx_mock, tmp_path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    httpx_mock.add_response(
        url="https://unpkg.com/@sveltia/cms@1.2.3/schema/sveltia-cms.json",
        json={"type": "object"},
    )

    first = cms.get_cms_schema(sveltia_version="1.2.3", cache_dir=cache_dir)
    assert first == {"type": "object"}

    second = cms.get_cms_schema(sveltia_version="1.2.3", cache_dir=cache_dir)
    assert second == {"type": "object"}


def test_get_cms_schema__missing_schema_skips_validation(httpx_mock, tmp_path):
    """Sveltia only ships a schema since 0.202.0; an older pin just goes unchecked."""
    httpx_mock.add_response(
        url="https://unpkg.com/@sveltia/cms@1.2.3/schema/sveltia-cms.json",
        status_code=404,
    )

    assert cms.get_cms_schema(sveltia_version="1.2.3", cache_dir=tmp_path) is None


SCHEMA = {
    "type": "object",
    "properties": {
        "fields": {
            "type": "array",
            "items": {
                "anyOf": [
                    {
                        "type": "object",
                        "properties": {"widget": {"const": "string"}},
                        "required": ["name", "widget"],
                    },
                    {
                        "type": "object",
                        "properties": {"widget": {"const": "select"}},
                        "required": ["name", "widget", "options"],
                    },
                ]
            },
        }
    },
}


def test_validate_cms_config__accepts_a_valid_config():
    config = {"fields": [{"name": "a", "widget": "string"}]}

    cms.validate_cms_config(config=config, schema=SCHEMA)


def test_validate_cms_config__reports_the_matching_widget_only():
    """Every widget variant complains when one field is wrong; only the variant
    that recognised the widget describes what is actually missing."""
    config = {"fields": [{"name": "a", "widget": "select"}]}

    with pytest.raises(cms.InvalidCMSConfig) as exc_info:
        cms.validate_cms_config(config=config, schema=SCHEMA)

    message = str(exc_info.value)
    assert "fields/0: 'options' is a required property" in message
    assert "'name' is a required property" not in message


def test_validate_cms_config__reports_an_unknown_widget():
    config = {"fields": [{"name": "a", "widget": "markdwon"}]}

    with pytest.raises(cms.InvalidCMSConfig) as exc_info:
        cms.validate_cms_config(config=config, schema=SCHEMA)

    assert "fields/0: unknown widget 'markdwon'" in str(exc_info.value)


def test_cms_artifacts(dw_settings, httpx_mock, tmp_path):
    (tmp_path / "_cache").mkdir()
    version = dw_settings().sveltia_version
    httpx_mock.add_response(
        url=f"https://unpkg.com/@sveltia/cms@{version}/dist/sveltia-cms.js",
        content=b"// sveltia",
    )
    httpx_mock.add_response(
        url=f"https://unpkg.com/@sveltia/cms@{version}/schema/sveltia-cms.json",
        json={"type": "object"},
    )

    paths = {a.path.as_posix() for a in cms.cms_artifacts(settings=dw_settings())}

    assert paths == {"admin/script.js", "admin/index.html", "admin/config.json"}


def test_cms_artifacts__rejects_an_invalid_config(dw_settings, httpx_mock, tmp_path):
    """A `cms_config` override that Sveltia would refuse fails the build rather
    than shipping an admin page that cannot load."""
    (tmp_path / "_cache").mkdir()
    settings = dw_settings(cms_config={"collections": "not a list"})
    httpx_mock.add_response(
        url=f"https://unpkg.com/@sveltia/cms@{settings.sveltia_version}/dist/sveltia-cms.js",
        content=b"// sveltia",
    )
    httpx_mock.add_response(
        url=f"https://unpkg.com/@sveltia/cms@{settings.sveltia_version}/schema/sveltia-cms.json",
        json={
            "type": "object",
            "properties": {"collections": {"type": "array"}},
        },
    )

    with pytest.raises(cms.InvalidCMSConfig):
        list(cms.cms_artifacts(settings=settings))


def test_cms_config_is_json(dw_settings, httpx_mock, tmp_path):
    """The config artifact is what the admin page fetches, so it has to be JSON."""
    (tmp_path / "_cache").mkdir()
    version = dw_settings().sveltia_version
    httpx_mock.add_response(
        url=f"https://unpkg.com/@sveltia/cms@{version}/dist/sveltia-cms.js",
        content=b"// sveltia",
    )
    httpx_mock.add_response(
        url=f"https://unpkg.com/@sveltia/cms@{version}/schema/sveltia-cms.json",
        json={"type": "object"},
    )

    artifact = next(
        a
        for a in cms.cms_artifacts(settings=dw_settings())
        if a.path == pathlib.Path("admin/config.json")
    )

    assert json.loads(artifact.contents)["app_title"] == "Site Name - Admin"
