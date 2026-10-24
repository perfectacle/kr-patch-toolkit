import pytest

from kr_patch import linear


@pytest.mark.parametrize("bpp", [1, 2, 4, 8])
@pytest.mark.parametrize("order", ["lsb", "msb"])
def test_round_trip(bpp, order):
    pix = [[(x * 3 + y) % (1 << bpp) for x in range(16)] for y in range(6)]
    data = linear.encode(pix, bpp, order)
    assert len(data) == linear.glyph_size(16, 6, bpp)
    assert linear.decode(data, 16, 6, bpp, order) == pix


def test_bit_order():
    # first pixel 3, others 0
    assert linear.decode(b"\x03", 4, 1, 2, "lsb") == [[3, 0, 0, 0]]
    assert linear.decode(b"\xC0", 4, 1, 2, "msb") == [[3, 0, 0, 0]]
    assert linear.decode(b"\x21", 2, 1, 4, "lsb") == [[1, 2]]


def test_offset_and_sheet():
    g = linear.encode([[1] * 8] * 8, 1)
    data = b"\0" * 8 + g
    assert linear.decode(data, 8, 8, 1, off=8) == [[1] * 8] * 8
    img = linear.sheet(data, 8, 8, 1, cols=2, scale=1)
    assert img.size == (2 * 9 + 1, 9 + 1)
    assert img.getpixel((10, 1)) == 0 and img.getpixel((1, 1)) == 255


def test_errors():
    with pytest.raises(ValueError):
        linear.glyph_size(3, 1, 1)
    with pytest.raises(ValueError):
        linear.encode([[4]], 2)
    with pytest.raises(ValueError):
        linear.decode(b"\0", 1, 1, 3)
