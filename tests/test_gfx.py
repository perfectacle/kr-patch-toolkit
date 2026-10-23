import pytest

from kr_patch.snes import bg, tiles

# a diagonal with every colour index of the depth
def _pattern(bpp, rows=8):
    top = (1 << bpp) - 1
    return [[(x + y) % (top + 1) if x >= y else 0 for x in range(8)] for y in range(rows)]


@pytest.mark.parametrize("bpp,rows", [(1, 8), (2, 8), (4, 8), (8, 8), (2, 12), (2, 16)])
def test_encode_decode_round_trip(bpp, rows):
    pix = _pattern(bpp, rows)
    data = tiles.encode(pix, bpp)
    assert len(data) == tiles.tile_size(bpp, rows)
    assert tiles.decode(data, 0, bpp, rows) == pix


def test_2bpp_layout():
    # row 0: low plane 0x80, high plane 0x80 -> pixel 0 = 3; row 1: high plane only -> 2
    data = bytes([0x80, 0x80, 0x00, 0x40]) + bytes(12)
    pix = tiles.decode(data, 0, 2)
    assert pix[0][0] == 3 and pix[1][1] == 2 and pix[0][1] == 0


def test_4bpp_planes_3_and_4_follow_after_16_bytes():
    data = bytearray(32)
    data[16] = 0x80   # plane 2, row 0
    data[17] = 0x80   # plane 3, row 0
    assert tiles.decode(bytes(data), 0, 4)[0][0] == 0b1100


def test_render_sheet_size():
    data = b"".join(tiles.encode(_pattern(2), 2) for _ in range(20))
    im = tiles.render(data, 0, 20, 2, cols=8, scale=2)
    assert im.size == (8 * 9 * 2, 3 * 9 * 2)
    assert im.mode == "L"
    # top-left pixel of tile 0 is index 0 -> white
    assert im.getpixel((0, 0)) == 255
    tall = tiles.render(data, 0, 20, 2, cols=5, scale=1, tall=True)
    assert tall.size == (5 * 9, 2 * 17)


def test_render_clamps_to_data():
    im = tiles.render(bytes(40), 0, 100, 2, cols=4, scale=1)
    assert im.size == (4 * 9, 9)


def test_bg_render_and_refs():
    vram = bytearray(0x10000)
    cgram = bytearray(512)
    cgram[2:4] = (31).to_bytes(2, "little")              # colour 1 = red
    cgram[16 * 2 + 2:16 * 2 + 4] = (31 << 10).to_bytes(2, "little")   # palette 1 colour 1 = blue
    chr_word, map_word = 0x1000, 0x0000
    tile = tiles.encode([[1] * 8] + [[0] * 8] * 7, 4)
    vram[chr_word * 2 + 5 * 32:chr_word * 2 + 6 * 32] = tile
    vram[0:2] = (5).to_bytes(2, "little")                 # (0,0): tile 5, palette 0
    vram[2:4] = (5 | 1 << 10 | 1 << 15).to_bytes(2, "little")   # (1,0): palette 1, v-flip
    im = bg.render(bytes(vram), bytes(cgram), map_word, chr_word, 4, scale=1)
    assert im.getpixel((0, 0)) == (248, 0, 0)
    assert im.getpixel((8, 7)) == (0, 0, 248)              # flipped row lands at the bottom
    assert im.getpixel((0, 1)) == (255, 0, 255)            # colour 0 shows the backdrop
    ts, offs = bg.refs(bytes(vram), map_word, chr_word, 4)
    assert ts == [0, 5]
    h = bg.hits(bytes(vram), map_word, chr_word, 4, 0x2000 + 5 * 32, 0x2000 + 6 * 32)
    assert h == (0x2000 + 5 * 32, 0x2000 + 6 * 32 - 1, 1)
