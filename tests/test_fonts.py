import io
import pathlib
import sys

import httpx
import pytest

from daily_writing import artifacts, fonts


@pytest.mark.parametrize(
    ("char_range", "expected"),
    [
        (fonts.CharRange(0x41), {0x41}),
        (fonts.CharRange(0x41, 0x43), {0x41, 0x42, 0x43}),
    ],
)
def test_char_range_to_set(char_range, expected):
    assert char_range.to_set() == expected


@pytest.mark.parametrize(
    ("char_range", "expected"),
    [
        (fonts.CharRange(0x41), "U+0041"),
        (fonts.CharRange(0x0100, 0x024F), "U+0100-024F"),
    ],
)
def test_char_range_to_css(char_range, expected):
    assert char_range.to_css() == expected


@pytest.mark.parametrize(
    ("style", "expected"),
    [
        (None, "MyFont.ttf"),
        ("italic", "MyFont-Italic.ttf"),
    ],
)
def test_get_file_name(style, expected):
    descriptor = fonts.FontDescriptor(contents=io.BytesIO(), name="MyFont", style=style)
    assert fonts.get_file_name(descriptor) == expected


def test_get_font_family__from_files(dw_settings, variable_font):
    family = fonts.get_font_family(
        settings=dw_settings(), font_input=[variable_font], fallback="serif"
    )

    assert family.name == "Test Variable"
    assert family.artifacts  # woff2 subsets were produced
    assert family.css_parts
    assert any("@font-face" in part for part in family.css_parts)


def test_get_all_font_files(dw_settings, variable_font):
    settings = dw_settings(
        title_ttf_font=[variable_font], body_ttf_font=[variable_font]
    )

    files = fonts.get_all_font_files(settings=settings)

    assert files.artifacts
    assert any(
        isinstance(a, artifacts.TextArtifact) and str(a.path).endswith("fonts.css")
        for a in files.artifacts
    )


def test_get_font_family__downloads_then_reads_cache(
    dw_settings, variable_font_bytes, httpx_mock
):
    settings = dw_settings()
    httpx_mock.add_response(
        url="https://api.github.com/repos/google/fonts/contents/ofl/testfont",
        json=[{"name": "Test.ttf", "download_url": "https://example.com/Test.ttf"}],
    )
    httpx_mock.add_response(
        url="https://example.com/Test.ttf", content=variable_font_bytes
    )

    downloaded = fonts.get_font_family(
        settings=settings, font_input="Test Font", fallback="serif"
    )
    assert downloaded.name == "Test Font"

    # Second call must not hit the network: httpx_mock would raise if it did.
    cached = fonts.get_font_family(
        settings=settings, font_input="Test Font", fallback="serif"
    )
    assert cached.name == "Test Font"


def test_get_font_family__unsupported_platform(dw_settings, monkeypatch):
    monkeypatch.setattr(sys, "platform", "commodore64")

    with pytest.raises(fonts.PlatformNotSupported):
        fonts.get_font_family(settings=dw_settings(), font_input=None, fallback="serif")


def test_get_font_family__default_uses_platform_font(dw_settings):
    family = fonts.get_font_family(
        settings=dw_settings(), font_input=None, fallback="sans-serif"
    )

    assert family.name is None
    assert family.fallback == "sans-serif"
    assert family.artifacts == []
    assert family.main_file == fonts.FONT_MAP[sys.platform]["sans-serif"]


def test_make_font_css():
    title = fonts.FontFamily(
        artifacts=[],
        name="TitleFont",
        fallback="sans-serif",
        css_parts=[],
        main_file=io.BytesIO(),
    )
    body = fonts.FontFamily(
        artifacts=[],
        name="BodyFont",
        fallback="serif",
        css_parts=[],
        main_file=io.BytesIO(),
    )

    artifact = fonts.make_font_css(
        font_css_parts=["@font-face { font-family: 'X'; }"],
        font_css_path=pathlib.Path("fonts.css"),
        title_font_family=title,
        body_font_family=body,
    )

    assert artifact.path == pathlib.Path("fonts.css")
    assert "@font-face { font-family: 'X'; }" in artifact.contents
    assert '"TitleFont", sans-serif' in artifact.contents
    assert '"BodyFont", serif' in artifact.contents


@pytest.fixture
def http_client():
    with httpx.Client() as client:
        yield client


def test_search_download_font__not_found(httpx_mock, http_client):
    # ofl, apache and ufl are all tried and all fail.
    for _ in range(3):
        httpx_mock.add_response(status_code=404)

    with pytest.raises(ValueError, match="not found"):
        list(
            fonts.search_download_font_from_github(client=http_client, font_name="Nope")
        )


def test_search_download_font__no_ttf(httpx_mock, http_client):
    httpx_mock.add_response(json=[{"name": "README.md"}])

    with pytest.raises(ValueError, match=r"No \.ttf files"):
        list(
            fonts.search_download_font_from_github(client=http_client, font_name="Foo")
        )
