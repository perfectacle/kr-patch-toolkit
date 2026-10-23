import sys

import pytest

from kr_patch.glyph import hangul
from kr_patch.glyph import store as glyphs


def test_store_round_trip(tmp_path):
    p = tmp_path / "g.json"
    assert glyphs.load(p) == {}
    g = glyphs.parse([".#.", "#.#"])
    glyphs.save(p, {"가": g})
    assert glyphs.load(p) == {"가": [[0, 1, 0], [1, 0, 1]]}


def test_transplant_and_spec():
    base = glyphs.parse(["...", "...", "..."])
    src = glyphs.parse(["###", "###", "###"])
    out = glyphs.transplant(base, src, (0, 1), (1, 2))
    assert glyphs.art(out) == [".##", ".##", "..."]
    assert glyphs.art(base) == ["...", "...", "..."]
    assert glyphs.parse_spec("ini=각:0-6,0-5") == ("각", (0, 6), (0, 5))
    assert glyphs.parse_spec("각:1-2,3-4") == ("각", (1, 2), (3, 4))


def test_side_by_side():
    lines = glyphs.side_by_side([("a", glyphs.parse(["#."])), ("b", glyphs.parse([".#", "##"]))])
    assert lines == ["a   b", "#.  .#", "    ##"]


def test_hangul_split_join():
    assert hangul.split("한") == (18, 0, 4)
    assert hangul.join(18, 0, 4) == "한"
    assert not hangul.is_syllable("A")


def _box(filled_corners):
    c = 1 if filled_corners else 0
    return [[0, 0, 0, 0, 0, 0],
            [0, c, 1, 1, c, 0],
            [0, 1, 0, 0, 1, 0],
            [0, c, 1, 1, c, 0],
            [0, 0, 0, 0, 0, 0]]


def test_fix_mieum_ieung():
    # a lone consonant box stands in for both the initial (top row) and final (bottom row)
    assert hangul.fix_mieum_ieung("앙", _box(True)) == "맘"
    assert hangul.fix_mieum_ieung("맘", _box(False)) == "앙"
    assert hangul.fix_mieum_ieung("가", _box(True)) == "가"
    assert hangul.fix_mieum_ieung("?", _box(True)) == "?"
    assert hangul.fix_mieum_ieung("앙", [[0, 0]]) == "앙"


def test_ocr_row_image():
    pytest.importorskip("PIL")
    from kr_patch.glyph import ocr
    g = glyphs.parse(["#.", ".#"])
    im = ocr.row_image([g, g], scale=4, margin=2, spacing=1)
    assert im.size == ((2 + 1) * 2 * 4 + 4, 2 * 4 + 4)
    assert im.getpixel((2, 2)) == 0 and im.getpixel((2 + 4, 2)) == 255


@pytest.mark.skipif(sys.platform == "darwin", reason="checks the non-macOS error path")
def test_ocr_needs_macos():
    from kr_patch.glyph import ocr
    with pytest.raises(RuntimeError):
        ocr.binary()
