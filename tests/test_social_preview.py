import io

from PIL import Image

from daily_writing import fonts, social_preview


def test_signature_is_stable_hex(social_preview_contents):
    contents = social_preview_contents()
    signature = contents.signature

    assert len(signature) == 8
    assert all(c in "0123456789abcdef" for c in signature)
    assert signature == contents.signature


def test_signature__path_fonts(social_preview_contents, variable_font):
    # Path (not BytesIO) fonts take the other branch of signature().
    contents = social_preview_contents(
        body_font=variable_font, title_font=variable_font
    )
    assert len(contents.signature) == 8


def test_generate_social_preview(
    social_preview_contents, variable_font_bytes, tmp_path
):
    logo = tmp_path / "logo.png"
    Image.new("RGBA", (16, 16), (255, 0, 0, 255)).save(logo)
    contents = social_preview_contents(
        description="A fairly long description " * 20,  # forces multi-line wrapping
        logo=logo,
        colors=["#ff0000", "#00ff00", "#0000ff"],
        body_font=io.BytesIO(variable_font_bytes),
        title_font=io.BytesIO(variable_font_bytes),
    )

    png = social_preview.generate_social_preview(contents)

    assert png.getvalue().startswith(b"\x89PNG")


def test_get_ttf_font(variable_font_bytes, tmp_path):
    woff2 = fonts.generate_subset(
        fonts.get_font_obj(io.BytesIO(variable_font_bytes)), {0x41, 0x42}, "woff2"
    )
    path = tmp_path / "font.woff2"
    path.write_bytes(woff2.getvalue())

    assert social_preview.get_ttf_font(path) is not None


def test_draw_vertical_gradient__single_color():
    image = Image.new(mode="RGBA", size=(100, 100), color=(0, 0, 0, 0))

    social_preview.draw_vertical_gradient(
        image=image, c1=(10, 10), c2=(50, 50), colors=["#ff0000"]
    )

    assert image.getpixel((30, 30)) == (255, 0, 0, 255)


def test_draw_vertical_gradient__multiple_colors():
    image = Image.new(mode="RGBA", size=(100, 100), color=(0, 0, 0, 0))

    social_preview.draw_vertical_gradient(
        image=image, c1=(10, 10), c2=(50, 50), colors=["#000000", "#ffffff"]
    )

    # Alpha is set to fully opaque only within the drawn zone.
    assert image.getpixel((20, 20))[3] == 255
    assert image.getpixel((5, 5))[3] == 0
