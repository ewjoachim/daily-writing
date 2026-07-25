import io
import pathlib
import re
import sys

import pytest

from daily_writing import artifacts, fonts


def test_get_font_family__from_files(dw_settings, variable_font):
    family = fonts.get_font_family(
        settings=dw_settings(), font_input=[variable_font], fallback="serif"
    )

    assert family.name == "Test Variable"
    # The file is served verbatim: one artifact, one @font-face, no subsetting.
    assert len(family.artifacts) == 1
    assert str(family.artifacts[0].path).endswith("TestVariable.ttf")
    assert len(family.css_parts) == 1
    assert "@font-face" in family.css_parts[0]
    assert "format('truetype')" in family.css_parts[0]
    assert "unicode-range" not in family.css_parts[0]


def test_get_font_family__unsupported_format(dw_settings, tmp_path):
    bad = tmp_path / "MyFont.pfb"
    bad.write_bytes(b"not a font")

    with pytest.raises(fonts.UnsupportedFontFormat):
        fonts.get_font_family(
            settings=dw_settings(), font_input=[bad], fallback="serif"
        )


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


CSS2_STYLESHEET = """/* latin */
@font-face {
  font-family: 'Test Font';
  font-style: normal;
  font-weight: 400;
  font-display: swap;
  src: url(https://fonts.gstatic.com/s/testfont/v1/aaaa.woff2) format('woff2');
  unicode-range: U+0000-00FF;
}
"""


def test_get_font_family__downloads_then_reads_cache(dw_settings, httpx_mock):
    settings = dw_settings()
    httpx_mock.add_response(
        url=re.compile(r"https://fonts\.googleapis\.com/css2.*"), text=CSS2_STYLESHEET
    )
    httpx_mock.add_response(
        url="https://fonts.gstatic.com/s/testfont/v1/aaaa.woff2", content=b"woff2-bytes"
    )

    downloaded = fonts.get_font_family(
        settings=settings, font_input="Test Font", fallback="serif"
    )
    assert downloaded.name == "Test Font"
    assert downloaded.artifacts
    # The gstatic URL was repointed at our own static dir.
    assert any("/static/aaaa.woff2" in part for part in downloaded.css_parts)
    assert "gstatic" not in downloaded.css_parts[0]
    # The latin face is kept in memory to render the social preview.
    assert downloaded.main_file.getvalue() == b"woff2-bytes"

    # Second call must not hit the network: httpx_mock would raise if it did.
    cached = fonts.get_font_family(
        settings=settings, font_input="Test Font", fallback="serif"
    )
    assert cached.name == "Test Font"
    assert cached.main_file.getvalue() == b"woff2-bytes"


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
