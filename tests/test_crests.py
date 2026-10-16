"""Tests del color dominante de los escudos (futdata.crests) con imágenes sintéticas."""
from PIL import Image

from futdata.crests import dominant_color


def test_dominant_color_half_red_half_white(tmp_path):
    img = Image.new("RGBA", (40, 40), (255, 255, 255, 255))
    img.paste((255, 0, 0, 255), (0, 0, 20, 40))
    path = tmp_path / "red_white.png"
    img.save(path)

    color = dominant_color(path)

    assert color is not None and color.startswith("#") and len(color) == 7
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    assert r >= 200 and g <= 80 and b <= 80  # rojizo: el blanco se descarta
