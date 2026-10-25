import struct

import pytest

from kr_patch import cli
from kr_patch.nds.font import Font, sheet


def block(tag, body):
    return tag[::-1].encode() + struct.pack("<I", 8 + len(body)) + body


def pack_bits(rows, bpp, size):
    """Pixel rows to `size` bytes, MSB first, rows not padded."""
    bits, n = 0, 0
    for row in rows:
        for v in row:
            bits = bits << bpp | v
            n += bpp
    return (bits << (size * 8 - n)).to_bytes(size, "big")


# 3x3 cells at 2 bits per pixel: 18 bits, so pixels straddle byte boundaries
GLYPHS = [
    [[0, 0, 0], [0, 0, 0], [0, 0, 0]],
    [[3, 0, 1], [0, 2, 0], [1, 0, 3]],
    [[1, 1, 1], [2, 2, 2], [3, 3, 3]],
    [[0, 3, 0], [3, 3, 3], [0, 3, 0]],
    [[2, 0, 0], [0, 2, 0], [0, 0, 2]],
]


def make_nftr(cmaps=None, cwdh=True, cell=(3, 3), bpp=2, glyph_size=3, glyphs=GLYPHS):
    """Tiny NFTR: FINF, CGLP, an optional CWDH for glyphs 1..3 and the given
    CMAP blocks (default: one of each type)."""
    if cmaps is None:
        cmaps = [
            (0x41, 0x42, 0, struct.pack("<H", 1)),                                   # A,B -> 1,2
            (0x61, 0x63, 1, struct.pack("<3H", 3, 0xFFFF, 4)),                       # a -> 3, b missing, c -> 4
            (0, 0xFFFF, 2, struct.pack("<H", 2) + struct.pack("<HHHH", 0x3042, 2, 0x30A2, 0)),
        ]
    finf = struct.pack("<BBHBBBB", 0, 12, 0, 1, 3, 4, 1) + bytes(12)
    cglp = struct.pack("<BBHBBBB", *cell, glyph_size, 2, 3, bpp, 0)
    cglp += b"".join(pack_bits(g, bpp, glyph_size) for g in glyphs)
    blocks = [block("FINF", finf), block("CGLP", cglp)]
    if cwdh:
        blocks.append(block("CWDH", struct.pack("<HHI", 1, 3, 0) + bytes([0, 2, 3, 1, 1, 3, 0, 3, 4]) + b"\0"))
    for first, last, kind, body in cmaps:
        blocks.append(block("CMAP", struct.pack("<HHHHI", first, last, kind, 0, 0) + body))
    data = b"".join(blocks)
    head = b"RTFN" + struct.pack("<HHIHH", 0xFEFF, 0x0101, 16 + len(data), 16, len(blocks))
    return head + data


def test_header_fields():
    f = Font(make_nftr())
    assert (f.cell_w, f.cell_h, f.bpp, f.glyph_size, f.count) == (3, 3, 2, 3, 5)
    assert (f.line_height, f.baseline, f.max_w, f.encoding) == (12, 2, 3, 1)
    assert f.default_width == (1, 3, 4)


def test_glyph_bits_msb_first_across_bytes():
    f = Font(make_nftr())
    for i, g in enumerate(GLYPHS):
        assert f.glyph(i) == g
    assert f.glyph_bytes(1) == bytes([0b11000100, 0b10000100, 0b11000000])


def test_one_bit_glyph():
    g = [[1, 0, 1, 1, 0], [0, 1, 0, 0, 1]]
    f = Font(make_nftr(cell=(5, 2), bpp=1, glyph_size=2, glyphs=[g]))
    assert f.glyph(0) == g


def test_cmap_types_0_1_2():
    f = Font(make_nftr())
    assert f.cmap == {0x41: 1, 0x42: 2, 0x61: 3, 0x63: 4, 0x3042: 2, 0x30A2: 0}
    assert f.code_glyph(0x62) is None and f.code_glyph(0x63) == 4


def test_widths_and_default():
    f = Font(make_nftr())
    assert [f.width(i) for i in range(5)] == [(1, 3, 4), (0, 2, 3), (1, 1, 3), (0, 3, 4), (1, 3, 4)]
    assert Font(make_nftr(cwdh=False)).widths == {}


@pytest.mark.parametrize("data,match", [
    (b"NFTR" + bytes(28), "RTFN"),
    (make_nftr(cmaps=[(0, 0, 3, b"")]), "CMAP type 3"),
    (make_nftr(cmaps=[]), "no CMAP"),
    (make_nftr()[:-6], "malformed"),
])
def test_bad_fonts(data, match):
    with pytest.raises(ValueError, match=match):
        Font(data)


def test_glyph_index_out_of_range():
    with pytest.raises(ValueError, match="out of range"):
        Font(make_nftr()).glyph(5)


def test_sheet_layout():
    f = Font(make_nftr())
    img = sheet(f, [0x41, 0x62, 0x61], cols=2, scale=1)
    assert img.size == (8, 4)                       # A and a fit; b is not in the font
    assert img.getpixel((0, 0)) == 255 - 3 * 255 // 3   # glyph 1 top-left, value 3: black
    assert img.getpixel((1, 0)) == 230              # blank
    assert img.getpixel((3, 0)) == 60               # border


def test_cli_info_and_sheet(tmp_path, capsys):
    p = tmp_path / "f.nftr"
    p.write_bytes(make_nftr())
    cli.main(["nds", "font", "info", str(p)])
    out = capsys.readouterr().out
    assert "cell 3x3  bpp 2  glyphs 5  codes 6" in out and "encoding utf-16" in out
    assert "00xx:4 30xx:2" in out
    cli.main(["nds", "font", "sheet", str(p), str(tmp_path / "s.png"), "--codes", "41-61", "--scale", "1"])
    assert "3 glyphs" in capsys.readouterr().out
    from PIL import Image
    assert Image.open(tmp_path / "s.png").size == (32 * 4, 4)
