import io
import pathlib
import re
import sys

import fontbuilder
import fontTools.ttLib
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
    # Every script's face is kept in memory to render the social preview.
    assert downloaded.coverage_faces[0].getvalue() == b"woff2-bytes"

    # Second call must not hit the network: httpx_mock would raise if it did.
    cached = fonts.get_font_family(
        settings=settings, font_input="Test Font", fallback="serif"
    )
    assert cached.name == "Test Font"
    assert cached.coverage_faces[0].getvalue() == b"woff2-bytes"


def test_build_google_font__keeps_one_face_per_subset():
    css = (
        "/* latin */\n"
        "@font-face { src: url(https://f/latin-400.woff2) format('woff2'); }\n"
        "/* latin */\n"
        "@font-face { src: url(https://f/latin-700.woff2) format('woff2'); }\n"
        "/* cyrillic */\n"
        "@font-face { src: url(https://f/cyr-400.woff2) format('woff2'); }\n"
    )

    font_artifacts, localized_css, faces = fonts.build_google_font(
        css=css, fetch=lambda url: url.encode(), static_path=pathlib.Path("static")
    )

    # Both weights of latin collapse to one face; cyrillic adds the second, so the
    # preview covers every script instead of only latin.
    assert [face.getvalue() for face in faces] == [
        b"https://f/latin-400.woff2",
        b"https://f/cyr-400.woff2",
    ]
    # Dedup is preview-only: every @font-face still becomes a served artifact.
    assert len(font_artifacts) == 3
    assert "https://" not in localized_css


def test_build_preview_font__merges_disjoint_subsets():
    latin = fontbuilder.build_variable_font("AB")
    cyrillic = fontbuilder.build_variable_font("ДЕ")

    data = fonts.build_preview_font(
        [io.BytesIO(latin), io.BytesIO(cyrillic)], "SemiBold"
    )

    assert data is not None
    font = fontTools.ttLib.TTFont(io.BytesIO(data))
    cmap = font.getBestCmap()
    # One static font now covers both scripts, so neither tofus.
    assert cmap is not None
    assert ord("A") in cmap
    assert ord("Д") in cmap
    assert "fvar" not in font  # merging requires (and produces) a static font
    assert font["OS/2"].usWeightClass == 600  # pinned to SemiBold


def test_build_preview_font__single_face_pins_weight():
    data = fonts.build_preview_font(
        [io.BytesIO(fontbuilder.build_variable_font())], "Medium"
    )

    assert data is not None
    font = fontTools.ttLib.TTFont(io.BytesIO(data))
    assert "fvar" not in font
    assert font["OS/2"].usWeightClass == 500  # Medium


def test_build_preview_font__system_font_returns_none():
    # A bare filename Pillow resolves against its own dirs can't be opened and merged.
    assert fonts.build_preview_font([pathlib.Path("Helvetica.ttc")], "Medium") is None


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
    assert family.coverage_faces == [fonts.FONT_MAP[sys.platform]["sans-serif"]]


def test_make_font_css():
    title = fonts.FontFamily(
        artifacts=[],
        name="TitleFont",
        fallback="sans-serif",
        css_parts=[],
        coverage_faces=[io.BytesIO()],
    )
    body = fonts.FontFamily(
        artifacts=[],
        name="BodyFont",
        fallback="serif",
        css_parts=[],
        coverage_faces=[io.BytesIO()],
    )

    artifact = fonts.make_font_css(
        font_css_parts=["@font-face { font-family: 'X'; }"],
        font_css_path=pathlib.Path("fonts.css"),
        title_font_family=title,
        body_font_family=body,
    )

    assert artifact.path == pathlib.Path("fonts.css")
    assert "@font-face { font-family: 'X'; }" in artifact.contents
    # Body text uses the body font, headings use the title font.
    body_block = artifact.contents.split("body {")[1].split("}")[0]
    headings_block = artifact.contents.split("h4 {")[1].split("}")[0]
    assert '"BodyFont", serif' in body_block
    assert '"TitleFont", sans-serif' in headings_block
