import dataclasses
import hashlib
import io
import itertools
import logging
import pathlib
import textwrap

import numpy as np
import pydantic
from PIL import Image, ImageDraw, ImageFont
from pydantic import dataclasses as pdataclasses

from daily_writing import fonts

logger = logging.getLogger("daily_writing")


@pdataclasses.dataclass(
    kw_only=True, config=pydantic.ConfigDict(arbitrary_types_allowed=True)
)
class SocialPreviewContents:
    """
    Parameters for generating a social preview PNG.
    """

    top_line: str
    title: str
    description: str | None
    logo: pathlib.Path | None
    date: str | None  # this might not strictly be a date
    colors: list[str]
    body_font: list[io.BytesIO | pathlib.Path]
    title_font: list[io.BytesIO | pathlib.Path]

    @property
    def signature(self) -> str:
        self_dict = dataclasses.asdict(self)
        self_dict["body_font"] = _faces_digest(self.body_font)
        self_dict["title_font"] = _faces_digest(self.title_font)

        return hashlib.md5(b"").hexdigest()[:8]


def _faces_digest(faces: list[io.BytesIO | pathlib.Path]) -> list[str]:
    return [
        hashlib.md5(face.getvalue()).hexdigest()
        if isinstance(face, io.BytesIO)
        else str(face)
        for face in faces
    ]


def _preview_font(
    faces: list[io.BytesIO | pathlib.Path], variation: str, size: int
) -> ImageFont.FreeTypeFont:
    """Load the merged, script-covering preview font (or a system font) at ``size``.

    ``build_preview_font`` bakes the weight in, so ``variation`` is applied here
    rather than through ``set_variation_by_name`` on a (now static) font.
    """
    if (data := fonts.build_preview_font(faces, variation)) is not None:
        return ImageFont.truetype(io.BytesIO(data), size=size)
    return ImageFont.truetype(str(faces[0]), size=size)


def generate_social_preview(contents: SocialPreviewContents) -> io.BytesIO:
    image = Image.new(mode="RGBA", size=(1200, 630), color="#1d1d1d")
    draw = ImageDraw.Draw(image)

    top_line_font = _preview_font(contents.title_font, "SemiBold", size=36)
    title_variant = _preview_font(contents.title_font, "SemiBold", size=60)
    text_variant = _preview_font(contents.body_font, "Medium", size=36)

    draw.text((100, 50), contents.top_line, font=top_line_font, fill="#ced6dd")
    if contents.logo:
        logo = Image.open(contents.logo)
        logo = logo.resize((36, 36))
        image.alpha_composite(logo, (55, 50))

    draw.text((100, 150), contents.title, font=title_variant, fill="#ced6dd")

    if date := contents.date:
        draw.text((100, 220), date, font=text_variant, fill="#ced6dd")

    draw_vertical_gradient(
        image=image, c1=(65, 150), c2=(70, 600), colors=contents.colors
    )

    char_width = 57

    text = "\n".join(textwrap.wrap(contents.description or "", width=char_width))
    lines = text.count("\n") + 1
    height = 36 * lines + 4 * (lines - 1)
    draw.text((100, 600 - height), text, font=text_variant, fill="#ced6dd")

    bytes_obj = io.BytesIO()
    image.save(bytes_obj, format="png")
    return bytes_obj


# This is ridiculously complex, and I'm ridiculously proud of having written it.
# Also, in 2 months time, I won't remember a thing of it :D
def draw_vertical_gradient(
    image: Image.Image,
    c1: tuple[int, int],  # corner top left
    c2: tuple[int, int],  # corner bottom right
    colors: list[str],
):
    colors_rgb = [tuple(int(h[i : i + 2], 16) for i in (1, 3, 5)) for h in colors]

    left, top = c1
    right, bottom = c2

    count_gradients = len(colors) - 1
    if count_gradients == 0:
        ImageDraw.Draw(image).rectangle([c1, c2], fill=colors[0])
        return

    increment = (c2[1] - c1[1]) // count_gradients

    # PIL undestands images as Y, X, Color
    array = np.zeros((image.height, image.width, 4), dtype=np.uint8)
    # Setting alpha to 100% only on our zone
    array[top:bottom, left:right, 3] = 255

    for i, (color_1, color_2) in enumerate(itertools.pairwise(colors_rgb)):
        start_h = top + increment * i
        end_h = start_h + increment

        # Create a gradient on a single line, the height of our section of rectangle
        gradient = np.linspace(color_1, color_2, increment, True)
        # Use broadcast to span it along the whole width of the rectangle
        array[start_h:end_h, left:right, 0:3] = gradient[:, None, :]

    # Finally, our gradient is ready, merge it with the image
    gradient_fragment = Image.fromarray(array, "RGBA")
    image.alpha_composite(gradient_fragment)
