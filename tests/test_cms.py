from daily_writing import cms


def test_cms_config_uses_homepage_path(dw_settings):
    settings = dw_settings(homepage_path="README.md")

    config = cms.get_cms_config(settings=settings)

    assert '"name": "homepage"' in config
    assert '"file": "README.md"' in config


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
