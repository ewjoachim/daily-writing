import functools
import io
import pathlib
import sys
from collections.abc import Callable, Iterable
from typing import Literal

import fontTools.merge
import fontTools.ttLib
import fontTools.varLib.instancer
import httpx
import pydantic
import tinycss2
import tinycss2.ast
from pydantic import dataclasses as pdataclasses

from daily_writing import artifacts
from daily_writing import settings as settings_module

type FontStyle = Literal["italic"] | None

# Extensions we can serve verbatim, mapped to their CSS ``format()`` keyword.
FONT_FORMATS = {
    ".woff2": "woff2",
    ".woff": "woff",
    ".ttf": "truetype",
    ".otf": "opentype",
}


@pdataclasses.dataclass(
    kw_only=True, config=pydantic.ConfigDict(arbitrary_types_allowed=True)
)
class FontFamily:
    artifacts: list[artifacts.BytesArtifact]
    name: str | None
    fallback: settings_module.GenericFont
    css_parts: list[str]
    # Faces that together cover every script the family supports. css2 slices a
    # font into one variable face per script; local/default fonts are a single
    # face. Merged into one static preview font by build_preview_font.
    coverage_faces: list[io.BytesIO | pathlib.Path]


@pdataclasses.dataclass(
    kw_only=True, config=pydantic.ConfigDict(arbitrary_types_allowed=True)
)
class FontFiles:
    body_font: list[io.BytesIO | pathlib.Path]
    title_font: list[io.BytesIO | pathlib.Path]
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


CSS2_ENDPOINT = "https://fonts.googleapis.com/css2"

# Google only serves woff2 to a UA it recognises as a modern browser; a bare or
# unknown UA gets ttf. We self-host the woff2, so we have to ask as a browser.
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# The generated stylesheet styles only body text (normal) and headings (bold),
# so those are the only two weights worth fetching.
FONT_WEIGHTS = "400;700"


def build_google_font(
    css: str,
    fetch: Callable[[str], bytes],
    static_path: pathlib.Path,
) -> tuple[list[artifacts.BytesArtifact], str, list[io.BytesIO | pathlib.Path]]:
    """Turn css2-style CSS into self-hosted font artifacts.

    ``fetch`` maps a font URL — gstatic on a fresh build, an already-local
    ``/static/…`` path on a cache hit — to its bytes. Google has already subsetted
    per script and emitted a matching ``unicode-range`` for every face, so we keep
    its CSS verbatim and only repoint the URLs at our own static dir. Returns the
    artifacts, the localized CSS, and one face per script for the social preview —
    each weight of a script shares glyph coverage, so one face per script is enough.
    """
    font_artifacts: list[artifacts.BytesArtifact] = []
    coverage_faces: dict[str, io.BytesIO | pathlib.Path] = {}
    subset: str | None = None

    for node in tinycss2.parse_stylesheet(
        css, skip_comments=False, skip_whitespace=False
    ):
        if isinstance(node, tinycss2.ast.Comment):
            subset = node.value.strip()  # css2 labels each block: /* latin */, …
            continue
        if not isinstance(node, tinycss2.ast.AtRule):
            continue
        if node.lower_at_keyword != "font-face":
            continue
        for token in node.content or ():
            # The url() src; skips format('woff2'), unicode-range, whitespace, etc.
            if not isinstance(token, tinycss2.ast.URLToken):
                continue
            data = fetch(token.value)
            font_path = static_path / token.value.rsplit("/", 1)[-1]
            font_artifacts.append(
                artifacts.BytesArtifact(contents=io.BytesIO(data), path=font_path)
            )
            # Keep one face per script; the preview merges them so any script
            # renders instead of tofu. Fall back to the filename if css2 ever
            # omits the subset comment, so distinct faces aren't collapsed.
            coverage_faces.setdefault(subset or font_path.name, io.BytesIO(data))
            css = css.replace(token.value, f"/{font_path}")

    if not coverage_faces:
        raise ValueError("css2 returned no font faces.")

    return font_artifacts, css, list(coverage_faces.values())


def download_google_font(
    settings: settings_module.Settings,
    name: str,
    fallback: settings_module.GenericFont,
) -> FontFamily:
    """Fetch a Google font as self-hosted woff2 through the css2 API."""
    static_path = settings.build_static_dir
    cache_dir = settings.cache_dir / name
    cached_css = cache_dir / settings.fonts_css_filename

    if cached_css.exists():
        # The cached CSS already points at /static/…; resolve each local URL back
        # to its cached bytes and let build_google_font rebuild the artifacts.
        font_artifacts, css, coverage_faces = build_google_font(
            css=cached_css.read_text(),
            fetch=lambda url: (cache_dir / url.rsplit("/", 1)[-1]).read_bytes(),
            static_path=static_path,
        )
    else:
        with httpx.Client(headers={"User-Agent": BROWSER_UA}) as client:

            def fetch(url: str) -> bytes:
                response = client.get(url)
                response.raise_for_status()
                return response.content

            stylesheet = client.get(
                CSS2_ENDPOINT,
                params={"family": f"{name}:wght@{FONT_WEIGHTS}", "display": "swap"},
            )
            stylesheet.raise_for_status()
            font_artifacts, css, coverage_faces = build_google_font(
                css=stylesheet.text, fetch=fetch, static_path=static_path
            )

        cache_dir.mkdir(parents=True, exist_ok=True)
        cached_css.write_text(css)
        for artifact in font_artifacts:
            (cache_dir / artifact.path.name).write_bytes(artifact.contents.getvalue())

    return FontFamily(
        artifacts=font_artifacts,
        name=name,
        fallback=fallback,
        css_parts=[css],
        coverage_faces=coverage_faces,
    )


class FontException(Exception):
    pass


class CouldNotExtractFontName(FontException):
    pass


class CouldNotExtractFontWeight(FontException):
    pass


class UnsupportedFontFormat(FontException):
    pass


@functools.cache
def get_font_obj(font_bytes: io.BytesIO) -> fontTools.ttLib.TTFont:
    font_bytes.seek(0)
    return fontTools.ttLib.TTFont(font_bytes)


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
    if body_font_family.name:
        body_font_families = [f'"{body_font_family.name}"', *body_font_families]

    css_file.write(f"""{"\n\n".join(font_css_parts)}

body {{
    font-family: {", ".join(body_font_families)};
}}

h1,
h2,
h3,
h4 {{
    font-family: {", ".join(title_font_families)};
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
            coverage_faces=[main_font[fallback]],
        )

    if isinstance(font_input, str):
        # A Google Font name: let Google subset and encode it, self-host the result.
        return download_google_font(
            settings=settings, name=font_input, fallback=fallback
        )

    # Local font file(s): served verbatim, one @font-face each. We don't subset
    # what we didn't make; the user brought a file, we host it as-is.
    if isinstance(font_input, pathlib.Path):
        font_input = [font_input]

    font_artifacts: list[artifacts.BytesArtifact] = []
    css_parts: list[str] = []
    faces: list[tuple[io.BytesIO, FontStyle]] = []
    names: list[str] = []
    for path in font_input:
        try:
            font_format = FONT_FORMATS[path.suffix.lower()]
        except KeyError as exc:
            raise UnsupportedFontFormat(
                f"Cannot serve '{path.name}': supported formats are "
                f"{', '.join(FONT_FORMATS)}."
            ) from exc

        contents = io.BytesIO(path.read_bytes())
        font_obj = get_font_obj(contents)
        family, weight = get_font_metadata(font_obj=font_obj)
        style = get_font_style(font_obj)
        names.append(family)
        faces.append((contents, style))

        font_path = settings.build_static_dir / path.name
        font_artifacts.append(
            artifacts.BytesArtifact(contents=contents, path=font_path)
        )
        css_parts.append(f"""@font-face {{
  font-family: '{family}';
  font-style: {style or "normal"};
  font-weight: {weight};
  font-display: swap;
  src: url('/{font_path}') format('{font_format}');
}}""")

    if len(different_names := set(names)) > 1:
        raise MultipleFonts(
            "Multiple fonts provided that don't seem to belong to the same family "
            f"({', '.join(different_names)})"
        )

    # Prefer an upright face to render the social preview.
    main_file = min(faces, key=lambda face: bool(face[1]))[0]

    return FontFamily(
        artifacts=font_artifacts,
        name=names[0],
        fallback=fallback,
        css_parts=css_parts,
        coverage_faces=[main_file],
    )


def get_all_font_files(
    settings: settings_module.Settings,
) -> FontFiles:
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
        body_font=body_font_family.coverage_faces,
        title_font=title_font_family.coverage_faces,
        artifacts=font_artifacts,
    )


def _named_instance_coords(
    font: fontTools.ttLib.TTFont, variation: str
) -> dict[str, float] | None:
    """Axis coordinates of the named instance ``variation``, if the font has one."""
    name_table = font["name"]
    fvar = font["fvar"]
    for instance in fvar.instances:  # pyright: ignore[reportUnknownVariableType]
        name = name_table.getDebugName(instance.subfamilyNameID)  # pyright: ignore[reportUnknownArgumentType]
        if name == variation:
            return dict(instance.coordinates)  # pyright: ignore[reportUnknownArgumentType]
    return None


@functools.cache
def _merge_preview_font(faces: tuple[bytes, ...], variation: str) -> bytes:
    statics: list[io.BytesIO] = []
    for face in faces:
        font = fontTools.ttLib.TTFont(io.BytesIO(face))
        # Merging variable fonts isn't supported, so pin each to a static
        # instance first — the named weight when present, else the default.
        if "fvar" in font:
            fvar = font["fvar"]
            coords = _named_instance_coords(font, variation) or {
                axis.axisTag: axis.defaultValue
                for axis in fvar.axes  # pyright: ignore[reportUnknownVariableType]
            }
            fontTools.varLib.instancer.instantiateVariableFont(
                font, coords, inplace=True
            )
        buf = io.BytesIO()
        font.save(buf)
        buf.seek(0)
        statics.append(buf)

    if len(statics) == 1:
        return statics[0].getvalue()

    merged = io.BytesIO()
    fontTools.merge.Merger().merge(statics).save(merged)
    return merged.getvalue()


def build_preview_font(
    faces: list[io.BytesIO | pathlib.Path], variation: str
) -> bytes | None:
    """One static font covering every ``faces`` script, pinned to ``variation``.

    Pillow does no font fallback, so a preview drawn with a single css2 script
    subset tofus on any other script. We pin each subset (a variable font) to
    ``variation``'s named instance and merge the disjoint subsets into one static
    file. Returns ``None`` for the default system fonts — a bare filename Pillow
    resolves against its own font dirs, not a path we can open and merge.
    """
    face_bytes: list[bytes] = []
    for face in faces:
        if isinstance(face, pathlib.Path):
            return None
        face_bytes.append(face.getvalue())
    return _merge_preview_font(tuple(face_bytes), variation)
