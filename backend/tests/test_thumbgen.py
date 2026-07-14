import io
from PIL import Image
from app.thumbgen import fit_to_16_9


def test_fit_to_16_9_square():
    img = Image.new("RGB", (100, 100), (255, 0, 0))
    result = fit_to_16_9(img, 480)
    opened = Image.open(io.BytesIO(result))
    assert opened.size == (480, 270)
    # 检查宽高比是 16:9
    assert abs(opened.size[0] / opened.size[1] - 16 / 9) < 0.01


def test_fit_to_16_9_wide():
    img = Image.new("RGB", (1920, 1080), (0, 255, 0))
    result = fit_to_16_9(img, 480)
    opened = Image.open(io.BytesIO(result))
    assert opened.size == (480, 270)
