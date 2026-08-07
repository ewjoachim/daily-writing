import pathlib

from daily_writing import artifacts, build


def test_build__writes_full_site(dw_settings, write_md, variable_font, tmp_path):
    write_md("2024/10/01-alpha.md", "# 01 - Alpha\n\nAlpha body.\n")
    write_md("2024/10/03-04-beta-gamma.md", "Beta gamma body.\n")
    (tmp_path / "static").mkdir()
    (tmp_path / "static" / "extra.txt").write_text("x")
    settings = dw_settings(
        title_ttf_font=[variable_font],
        body_ttf_font=[variable_font],
        include_cms=False,  # avoid the network download of the Sveltia CMS bundle
    )

    build.build(settings=settings)

    build_dir = tmp_path / "_build"
    assert (build_dir / "index.html").is_file()
    assert (build_dir / "feed.atom").is_file()
    assert (build_dir / "static" / "fonts.css").is_file()
    assert (
        build_dir / "static" / "extra.txt"
    ).is_file()  # project static, copied as-is
    assert (build_dir / "2024/10/1-alpha/index.html").is_file()
    assert (build_dir / "social_previews" / "index.png").is_file()


def test_build__empties_existing_build_dir(
    dw_settings, write_md, variable_font, tmp_path
):
    write_md("2024/10/01-alpha.md", "# 01 - Alpha\n\nBody.\n")
    (tmp_path / "static").mkdir()
    build_dir = tmp_path / "_build"
    build_dir.mkdir()
    stale = build_dir / "stale.html"
    stale.write_text("old")
    settings = dw_settings(
        title_ttf_font=[variable_font], body_ttf_font=[variable_font], include_cms=False
    )

    build.build(settings=settings)

    assert not stale.exists()


def test_build__includes_cms(
    dw_settings, write_md, variable_font, httpx_mock, tmp_path
):
    write_md("2024/10/01-alpha.md", "# 01 - Alpha\n\nBody.\n")
    (tmp_path / "static").mkdir()
    (tmp_path / "_cache").mkdir()
    httpx_mock.add_response(
        url="https://unpkg.com/@sveltia/cms@latest/dist/sveltia-cms.js",
        content=b"// sveltia",
    )
    settings = dw_settings(  # include_cms defaults to True
        title_ttf_font=[variable_font], body_ttf_font=[variable_font]
    )

    build.build(settings=settings)

    assert (tmp_path / "_build/admin/index.html").is_file()
    assert (tmp_path / "_build/admin/config.json").is_file()


def test_static_artifacts(dw_settings, tmp_path):
    (tmp_path / "static").mkdir()
    (tmp_path / "static" / "foo.txt").write_text("bar")
    settings = dw_settings()

    result = list(build.static_artifacts(settings=settings))
    paths = {str(a.path) for a in result}

    assert all(isinstance(a, artifacts.FileArtifact) for a in result)
    # The project static file, plus the framework's own static assets.
    assert "static/foo.txt" in paths
    assert "static/style.css" in paths


def test_get_redirect_alias_artifact(dw_settings, page_metadata):
    artifact = build.get_redirect_alias_artifact(
        settings=dw_settings(),
        page_metadata=page_metadata(),
        alias=pathlib.Path("old/path.html"),
        to_url="https://foo.bar/new/",
    )

    assert artifact.path == pathlib.Path("old/path.html")
    assert "https://foo.bar/new/" in artifact.contents
