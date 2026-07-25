"""Build a tiny variable font in memory for tests.

The real pipeline needs a *variable* font that exposes the "Medium" and "SemiBold"
named instances (``social_preview`` selects them) and enough tables for fontTools to
read metadata and subset to woff2. Vendoring a real font would be a large binary blob;
synthesising a minimal one keeps it a few KB and self-documenting.
"""

import io

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 .,-—…"
_UPM = 1000


def _square_glyph():
    pen = TTGlyphPen(None)
    pen.moveTo((100, 0))
    pen.lineTo((100, 700))
    pen.lineTo((500, 700))
    pen.lineTo((500, 0))
    pen.closePath()
    return pen.glyph()


def build_variable_font() -> bytes:
    cmap = {ord(c): f"g{ord(c)}" for c in _LETTERS}
    glyph_order = [".notdef", *cmap.values()]

    fb = FontBuilder(_UPM, isTTF=True)
    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap(cmap)

    space = f"g{ord(' ')}"
    fb.setupGlyf(
        {
            name: (
                TTGlyphPen(None).glyph()
                if name in {".notdef", space}
                else _square_glyph()
            )
            for name in glyph_order
        }
    )

    fb.setupHorizontalMetrics({name: (600, 100) for name in glyph_order})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "Test Variable", "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWeightClass=400)
    fb.setupPost()
    fb.setupFvar(
        axes=[("wght", 400, 400, 700, "Weight")],
        instances=[
            {"stylename": "Regular", "location": {"wght": 400}},
            {"stylename": "Medium", "location": {"wght": 500}},
            {"stylename": "SemiBold", "location": {"wght": 600}},
            {"stylename": "Bold", "location": {"wght": 700}},
        ],
    )

    buf = io.BytesIO()
    fb.save(buf)
    return buf.getvalue()
