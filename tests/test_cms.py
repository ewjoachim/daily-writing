import json

from daily_writing import cms


def test_cms_config_uses_homepage_path(dw_settings):
    settings = dw_settings(homepage_path="README.md")

    config = cms.get_cms_config(settings=settings)

    assert '"name": "homepage"' in config
    assert '"file": "README.md"' in config


def test_cms_config_omits_excluded_settings(dw_settings):
    """Build-steering settings are not editable content; they stay out of the form."""
    config = json.loads(cms.get_cms_config(settings=dw_settings()))

    settings_singleton = next(s for s in config["singletons"] if s["name"] == "config")
    names = [field["name"] for field in settings_singleton["fields"]]

    assert "verbosity" not in names
    assert "site_name" in names


def test_cms_config_states_defaults_in_the_hint(dw_settings):
    """Sveltia only applies `default` when creating an entry, and the settings file
    always exists — so the fallback has to be stated where it always renders."""
    config = json.loads(cms.get_cms_config(settings=dw_settings()))

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
    config = json.loads(cms.get_cms_config(settings=dw_settings()))

    fields = next(s for s in config["singletons"] if s["name"] == "config")["fields"]

    assert (
        "Defaults to:" not in next(f for f in fields if f["name"] == "locale")["hint"]
    )


def test_cms_config_homepage_edits_the_body(dw_settings):
    """The homepage singleton edits page content, not the site settings."""
    config = json.loads(cms.get_cms_config(settings=dw_settings()))

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

    config = json.loads(cms.get_cms_config(settings=settings))

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


def test_cms_artifacts(dw_settings, httpx_mock, tmp_path):
    (tmp_path / "_cache").mkdir()
    httpx_mock.add_response(
        url="https://unpkg.com/@sveltia/cms@latest/dist/sveltia-cms.js",
        content=b"// sveltia",
    )

    paths = {str(a.path) for a in cms.cms_artifacts(settings=dw_settings())}

    assert paths == {"admin/script.js", "admin/index.html", "admin/config.json"}
