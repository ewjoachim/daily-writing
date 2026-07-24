from daily_writing import cms


def test_cms_config_uses_homepage_path(dw_settings):
    settings = dw_settings(homepage_path="README.md")

    config = cms.get_cms_config(settings=settings)

    assert '"name": "homepage"' in config
    assert '"file": "README.md"' in config
