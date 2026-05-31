from __future__ import annotations

import dataclasses
import functools
import io
import pathlib
import sys
from collections.abc import Iterable, Iterator
from typing import Literal

import fontTools.ttLib
import httpx
import pydantic
from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont
from pydantic import dataclasses as pdataclasses

from daily_writing import artifacts
from daily_writing import settings as settings_module

type FontStyle = Literal["italic"] | None


@pdataclasses.dataclass(
    kw_only=True, config=pydantic.ConfigDict(arbitrary_types_allowed=True)
)
class FontDescriptor:
    contents: io.BytesIO
    name: str
    style: FontStyle
    css_parts: list[str] = dataclasses.field(default_factory=list)


@pdataclasses.dataclass(
    kw_only=True, config=pydantic.ConfigDict(arbitrary_types_allowed=True)
)
class FontFamily:
    artifacts: list[artifacts.BytesArtifact]
    name: str | None
    fallback: settings_module.GenericFont
    css_parts: list[str]
    main_file: io.BytesIO | pathlib.Path


@pdataclasses.dataclass(
    kw_only=True, config=pydantic.ConfigDict(arbitrary_types_allowed=True)
)
class FontFiles:
    body_font: io.BytesIO | pathlib.Path
    title_font: io.BytesIO | pathlib.Path
    artifacts: Iterable[artifacts.BytesArtifact | artifacts.TextArtifact]


@pdataclasses.dataclass(frozen=True)
class CharRange:
    start: int
    end: int | None = None

    def to_set(self) -> set[int]:
        """Expands the range into a set of integers."""
        if self.end is None:
            return {self.start}
        return set(range(self.start, self.end + 1))

    def to_css(self) -> str:
        """Converts back to CSS unicode-range format (U+XXXX-XXXX)."""
        if self.end is None or self.start == self.end:
            return f"U+{self.start:04X}"
        return f"U+{self.start:04X}-{self.end:04X}"


FONT_MAP = {
    "win32": {
        "serif": pathlib.Path("times.ttf"),
        "sans-serif": pathlib.Path("arial.ttf"),
    },
    "darwin": {
        "serif": pathlib.Path("Times.ttc"),
        "sans-serif": pathlib.Path("Helvetica.ttc"),
    },
    "linux": {
        "serif": pathlib.Path("DejaVuSans.ttf"),
        "sans-serif": pathlib.Path("DejaVuSans.ttf"),
    },
}


def download_google_font(
    font_name: str, github_token: str | None
) -> Iterator[FontDescriptor]:
    """
    Downloads font files from the Google Fonts GitHub repository
    and returns them as an in-memory ZIP archive.
    """

    headers = {}
    if github_token:
        headers = {"Authorization": f"token {github_token}"}

    with httpx.Client(headers=headers) as client:
        yield from search_download_font_from_github(client=client, font_name=font_name)


def search_download_font_from_github(
    client: httpx.Client,
    font_name: str,
) -> Iterator[FontDescriptor]:
    dir_name = font_name.lower().replace(" ", "")

    base_api = "https://api.github.com/repos/google/fonts/contents"
    # Font is in one of the subdirs of those dirs, but we don't know which.
    licenses = ["ofl", "apache", "ufl"]
    for license_type in licenses:
        check_url = f"{base_api}/{license_type}/{dir_name}"
        response = client.get(check_url)
        try:
            response.raise_for_status()
        except httpx.HTTPError:
            continue
        break
    else:
        raise ValueError(
            f"Font '{font_name}' not found in Google Fonts GitHub repository."
        )

    files_data: list[dict[str, str]] = response.json()
    font_files = [f for f in files_data if f["name"].lower().endswith(".ttf")]

    if not font_files:
        raise ValueError(f"No .ttf files found for '{font_name}'.")

    for file in font_files:
        download_url: str = file["download_url"]
        file_response = client.get(download_url)
        file_response.raise_for_status()
        contents = io.BytesIO(file_response.content)
        yield get_font_descriptor(
            font_bytes=contents,
        )


class FontException(Exception):
    pass


class CouldNotExtractFontName(FontException):
    pass


class CouldNotExtractFontWeight(FontException):
    pass


def get_font_descriptor(font_bytes: io.BytesIO) -> FontDescriptor:
    font_obj = get_font_obj(font_bytes)
    font_name = get_font_name(font_obj)
    if not font_name:
        raise CouldNotExtractFontName
    return FontDescriptor(
        contents=font_bytes,
        style=get_font_style(font_obj),
        name=font_name,
    )


@functools.cache
def get_font_obj(font_bytes: io.BytesIO) -> fontTools.ttLib.TTFont:
    font_bytes.seek(0)
    return fontTools.ttLib.TTFont(font_bytes)


def get_font_name(font: fontTools.ttLib.TTFont) -> str | None:
    return font["name"].getBestFamilyName()


def get_font_style(font: fontTools.ttLib.TTFont) -> FontStyle:
    # Check OS/2 table fsSelection (Bit 0 is Italic)
    # We use bitwise AND to check if the bit is set
    try:
        if font["OS/2"].fsSelection & 0b1:  # pyright: ignore[reportAttributeAccessIssue]
            return "italic"
    except KeyError:
        pass  # Table might be missing in very old fonts

    # Check head table macStyle (Bit 1 is Italic)
    try:
        if font["head"].macStyle & 0b10:  # pyright: ignore[reportAttributeAccessIssue]
            return "italic"
    except KeyError:
        pass

    # Check post table italicAngle (usually non-zero for italics)
    # This is a fallback; some "upright italics" might have 0 angle.
    try:
        if font["post"].italicAngle != 0:  # pyright: ignore[reportAttributeAccessIssue]
            return "italic"
    except KeyError:
        pass

    return None


RANGES = {
    "latin": [
        CharRange(0x0000, 0x00FF),
        # Individual codepoints
        CharRange(0x0131),
        CharRange(0x0152),
        CharRange(0x0153),
        CharRange(0x02BB),
        CharRange(0x02BC),
        CharRange(0x02C6),
        CharRange(0x02DA),
        CharRange(0x02DC),
        CharRange(0x2000, 0x206F),
        CharRange(0x20AC),
        CharRange(0x2122),
        CharRange(0x2191),
        CharRange(0x2193),
        CharRange(0x2212),
        CharRange(0x2215),
        CharRange(0xFEFF),
        CharRange(0xFFFD),
    ],
    "latin-ext": [
        CharRange(0x0100, 0x024F),
        CharRange(0x0250, 0x02AF),
        CharRange(0x1E00, 0x1EFF),
        CharRange(0x20A0, 0x20CF),
    ],
}


def get_font_supported_unicodes(font_obj: TTFont) -> set[int]:
    """Returns a set of all unicode codepoints supported by the font."""
    # font.getBestCmap() returns a dict {int: str}, we only need the keys
    return set(font_obj.getBestCmap() or ())


def get_font_metadata(font_obj: fontTools.ttLib.TTFont) -> tuple[str, str]:
    """Extracts weight and family name from the TTF file."""
    # Check for Variable Font 'fvar' table
    weight = None
    if "fvar" in font_obj:
        # accessing the 'fvar' table returns an object that has an 'axes' attribute
        fvar = font_obj["fvar"]
        for axis in fvar.axes:  # pyright: ignore[reportUnknownVariableType]
            if axis.axisTag == "wght":
                weight = f"{int(axis.minValue)} {int(axis.maxValue)}"  # pyright: ignore[reportUnknownArgumentType]
    else:
        # Get weight from OS/2 table
        weight = str(font_obj["OS/2"].usWeightClass)  # pyright: ignore[reportUnknownArgumentType, reportAttributeAccessIssue]

    # Get family name from name table (ID 1 is Font Family)
    family_name = font_obj["name"].getBestFamilyName()
    if not family_name:
        raise CouldNotExtractFontName
    if not weight:
        raise CouldNotExtractFontWeight

    return family_name, weight


def generate_subset(
    font_obj: fontTools.ttLib.TTFont, unicode_subset: set[int], font_format: str
) -> io.BytesIO:
    """Generates a subsetted font file."""

    subsetter = Subsetter(
        options=Options(
            flavor=font_format,
            layout_features=["*"],  # Keep all OpenType features
            ignore_missing_unicodes=True,
        )
    )
    subsetter.populate(unicodes=list(unicode_subset))

    subsetter.subset(font_obj)
    result = io.BytesIO()
    font_obj.save(result)
    font_obj.close()

    return result


def process_font(
    font_descriptor: FontDescriptor,
    static_path: pathlib.Path,
) -> Iterator[artifacts.BytesArtifact]:
    """Main pipeline: extracts info, subsets files, and prints CSS."""
    font_obj = get_font_obj(font_bytes=font_descriptor.contents)
    family, weight = get_font_metadata(font_obj=font_obj)

    css_parts = []
    font_format = "woff2"
    supported_unicode = get_font_supported_unicodes(font_obj=font_obj)

    for subset_name, char_ranges in RANGES.items():
        style_suffix = "-italic" if font_descriptor.style == "italic" else ""
        filename = f"{font_descriptor.name}{style_suffix}-{subset_name}.{font_format}"

        unicode_subset: set[int] = set.union(*(r.to_set() for r in char_ranges))  # pyright: ignore[reportUnknownVariableType]
        unicode_subset &= supported_unicode

        font_path = static_path / filename

        # Create the physical file
        yield artifacts.BytesArtifact(
            contents=generate_subset(
                font_obj=font_obj,
                unicode_subset=unicode_subset,
                font_format=font_format,
            ),
            path=font_path,
        )

        # Generate the CSS block
        css_range = ", ".join(r.to_css() for r in char_ranges)

        css_parts.append(f"""@font-face {{
  font-family: '{family}';
  font-style: {font_descriptor.style};
  font-weight: {weight};
  font-display: swap;
  src: url('/{font_path}') format('woff2');
  unicode-range: {css_range};
}}""")

    font_descriptor.css_parts = css_parts


def get_file_name(font_descriptor: FontDescriptor) -> str:
    suffix = "-Italic" if font_descriptor.style == "italic" else ""
    return f"{font_descriptor.name}{suffix}.ttf"


def make_font_css(
    font_css_parts: list[str],
    font_css_path: pathlib.Path,
    title_font_family: FontFamily,
    body_font_family: FontFamily,
) -> artifacts.TextArtifact:
    css_file = io.StringIO()

    title_font_families = [title_font_family.fallback]
    if title_font_family.name:
        title_font_families = [f'"{title_font_family.name}"', *title_font_families]

    body_font_families = [body_font_family.fallback]
    if body_font_family:
        body_font_families = [f'"{body_font_family.name}"', *body_font_families]

    css_file.write(f"""{"\n\n".join(font_css_parts)}

body {{
    font-family: {", ".join(title_font_families)};
}}

h1,
h2,
h3,
h4 {{
    font-family: {", ".join(body_font_families)};
}}""")

    return artifacts.TextArtifact(path=font_css_path, contents=css_file.getvalue())


class MultipleFonts(Exception):
    pass


class PlatformNotSupported(Exception):
    pass


def get_font_family(
    settings: settings_module.Settings,
    font_input: pathlib.Path | list[pathlib.Path] | str | None,
    fallback: settings_module.GenericFont,
) -> FontFamily:
    if not font_input:
        try:
            main_font = FONT_MAP[sys.platform]
        except KeyError as exc:
            raise PlatformNotSupported(
                f"Cannot guess default fonts for {sys.platform}, please provide font files explicitly."
            ) from exc

        return FontFamily(
            artifacts=[],
            name=None,
            fallback=fallback,
            css_parts=[],
            main_file=main_font[fallback],
        )

    fonts: list[FontDescriptor] = []
    if isinstance(font_input, pathlib.Path):
        font_input = [font_input]

    if isinstance(font_input, list):
        names: list[str] = []
        for font in font_input:
            descriptor = get_font_descriptor(font_bytes=io.BytesIO(font.read_bytes()))
            fonts.append(descriptor)
            names.append(descriptor.name)
        if len(different_names := set(names)) > 1:
            raise MultipleFonts(
                "Multiple fonts provided that don't seem to belong to the same family "
                f"({', '.join(different_names)})"
            )
        name = names[0]

    else:
        name = font_input
        cache_dir = settings.cache_dir / name

        if cache_dir.exists() and (cached_files := list(cache_dir.iterdir())):
            # Read fonts from cache
            fonts.extend(
                get_font_descriptor(font_bytes=io.BytesIO(f.read_bytes()))
                for f in cached_files
            )
        else:
            # Fetch fonts
            downloaded = list(
                download_google_font(font_name=name, github_token=settings.github_token)
            )
            fonts.extend(downloaded)
            # Cache fonts
            cache_dir.mkdir(parents=True, exist_ok=True)
            for font_file in downloaded:
                (cache_dir / get_file_name(font_file)).write_bytes(
                    font_file.contents.getvalue()
                )

    font_artifacts: list[artifacts.BytesArtifact] = []
    for font in fonts:
        font_artifacts.extend(
            process_font(font_descriptor=font, static_path=settings.build_static_dir)
        )

    main_font = sorted(fonts, key=lambda x: bool(x.style))[0]

    return FontFamily(
        artifacts=font_artifacts,
        name=name,
        fallback=fallback,
        css_parts=[part for font in fonts for part in font.css_parts],
        main_file=main_font.contents,
    )


def get_all_font_files(
    settings: settings_module.Settings,
) -> FontFiles:
    (settings.source_dir / settings.cache_dir).mkdir(exist_ok=True, parents=True)
    body_font_family = get_font_family(
        settings=settings,
        font_input=settings.body_ttf_font,
        fallback=settings.body_ttf_font_fallback,
    )
    title_font_family = get_font_family(
        settings=settings,
        font_input=settings.title_ttf_font,
        fallback=settings.title_ttf_font_fallback,
    )
    font_artifacts = [
        *body_font_family.artifacts,
        *title_font_family.artifacts,
        make_font_css(
            font_css_parts=[
                part
                for family in [body_font_family, title_font_family]
                for part in family.css_parts
            ],
            font_css_path=settings.build_static_dir / settings.fonts_css_filename,
            title_font_family=title_font_family,
            body_font_family=body_font_family,
        ),
    ]

    return FontFiles(
        body_font=body_font_family.main_file,
        title_font=title_font_family.main_file,
        artifacts=font_artifacts,
    )
