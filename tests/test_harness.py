import pytest
from PIL import Image

from kr_patch import shots
from kr_patch.sfc import libretro, script

SCRIPT = """\
# boot
500 start 4
800 A+b 2
900 tap a 40 1000
1000 shot
1000 dump
1100 poke 0010 1234
1100 poke 7E0020 FFFF
2000 end
"""


def test_parse_all_commands():
    sc = script.parse(SCRIPT.splitlines())
    assert sc.end == 2000
    assert sc.shots == {1000} and sc.dumps == {1000}
    assert sc.pokes == {1100: [(0x10, 0x1234), (0x20, 0xFFFF)]}
    assert (500, 504, {script.BUTTONS["start"]}) in sc.presses
    assert (800, 802, {script.BUTTONS["a"], script.BUTTONS["b"]}) in sc.presses
    taps = [p for p in sc.presses if p[0] >= 900]
    assert [p[0] for p in taps] == [900, 940, 980]
    assert all(p[1] - p[0] == script.TAP_LEN for p in taps)


def test_held():
    sc = script.parse(SCRIPT.splitlines())
    assert sc.held(499) == set()
    assert sc.held(500) == {script.BUTTONS["start"]}
    assert sc.held(503) == {script.BUTTONS["start"]}
    assert sc.held(504) == set()
    assert sc.held(801) == {script.BUTTONS["a"], script.BUTTONS["b"]}


@pytest.mark.parametrize("lines,match", [
    (["10 z 4", "20 end"], "unknown button"),
    (["", "10", "20 end"], "line 2"),
    (["10 tap a", "20 end"], "missing argument"),
    (["10 poke 7D0000 1", "20 end"], "outside WRAM"),
    (["10 poke 1FFFF 1", "20 end"], "outside WRAM"),          # 16-bit write would cross the end
    (["10 poke 7FFFFF 1", "20 end"], "outside WRAM"),
    (["10 shot"], "no 'end'"),
    (["10 end", "20 shot"], "line 2: frame is after 'end'"),
    (["10 end", "11 dump"], "after 'end'"),
    (["10 end", "11 poke 10 1"], "after 'end'"),
    (["10 end", "11 tap a 4 20"], "after 'end'"),
    (["10 end", "11 a 4"], "after 'end'"),
])
def test_parse_errors(lines, match):
    with pytest.raises(ValueError, match=match):
        script.parse(lines)


def test_poke_at_last_word_is_allowed():
    assert script.parse(["10 poke 7FFFFE 1", "10 end"]).pokes == {10: [(0x1FFFE, 1)]}


def test_load_from_file(tmp_path):
    p = tmp_path / "s.txt"
    p.write_text("10 shot\n20 end\n")
    assert script.load(p).end == 20


def test_wram_offsets_and_par_codes():
    assert script.wram_offset(0x7E0010) == 0x10
    assert script.wram_offset(0x7F0000) == 0x10000
    assert script.wram_offset(0x10) == 0x10
    assert script.par_codes(0x10, 0x1234) == ["7E001034", "7E001112"]


def test_watch():
    w = script.Watch.parse("7E0010:3")
    assert (w.offset, w.size) == (0x10, 3)
    assert w.format(0x0A1B2C) == "0A1B2C"
    assert script.Watch.parse("20:2", "03x").format(0x1F) == "01f"
    assert script.Watch.parse("30").format(5) == "05"
    for bad in ("10:0", "10:5", "1FFFF:2", "7FFFFE:4"):
        with pytest.raises(ValueError):
            script.Watch.parse(bad)
    assert script.Watch.parse("1FFFC:4").offset == 0x1FFFC


def test_env_vars():
    assert libretro.env_vars("a=1,b=x=y,,") == {"a": "1", "b": "x=y"}
    assert libretro.env_vars(None) == {}


def test_to_image_formats():
    w, h = 2, 1
    red565 = (0x1F << 11).to_bytes(2, "little") * 2
    assert libretro.to_image(red565, w, h, 4, libretro.PIX_RGB565).getpixel((0, 0))[0] > 240
    red8888 = bytes([0, 0, 255, 0]) * 2
    assert libretro.to_image(red8888, w, h, 8, libretro.PIX_XRGB8888).getpixel((1, 0)) == (255, 0, 0)


def _png(path, color, size=(16, 16), dot=None, dot_color=(255, 255, 255)):
    im = Image.new("RGB", size, color)
    if dot:
        im.putpixel(dot, dot_color)
    im.save(path)
    return path


def test_shotcmp(tmp_path):
    a = _png(tmp_path / "a.png", (0, 0, 0))
    b = _png(tmp_path / "b.png", (0, 0, 0), dot=(3, 4))
    assert shots.compare(a, a) == (None, "same")
    bbox, msg = shots.compare(a, b)
    assert bbox == (3, 4, 4, 5) and msg == "diff px=1 bbox=3,4,1,1"
    assert shots.compare(a, b, box=(8, 8, 8, 8))[1] == "same"
    assert shots.compare(a, b, box=(2, 2, 4, 4))[0] == (3, 4, 4, 5)
    c = _png(tmp_path / "c.png", (0, 0, 0), size=(8, 8))
    assert shots.compare(a, c)[1].startswith("size")
    d = _png(tmp_path / "d.png", (3, 3, 3))
    assert shots.compare(a, d, tol=5)[1] == "same"


def test_shotcmp_uses_channel_max(tmp_path):
    # pure blue +20 is only about 2 in luminance, so a luminance check with tol 5 would miss it
    a = _png(tmp_path / "a.png", (0, 0, 0))
    b = _png(tmp_path / "b.png", (0, 0, 0), dot=(1, 1), dot_color=(0, 0, 20))
    assert shots.compare(a, b, tol=5)[1] == "diff px=1 bbox=1,1,1,1"
    assert shots.compare(a, b, tol=20)[1] == "same"


def test_pairs_union_and_contact(tmp_path):
    act, ref = tmp_path / "act", tmp_path / "ref"
    act.mkdir(); ref.mkdir()
    for n in ("f00010.png", "f00020.png"):
        _png(act / n, (10, 20, 30), size=(256, 224))
    _png(ref / "f00030.png", (0, 0, 0))
    ps = shots.pairs(act, ref)
    assert [p[0].name for p in ps] == ["f00010.png", "f00020.png", "f00030.png"]
    assert ps[0][1] == ref / "f00010.png"
    assert not ps[2][0].exists()
    empty1, empty2 = tmp_path / "e1", tmp_path / "e2"
    empty1.mkdir(); empty2.mkdir()
    with pytest.raises(ValueError):
        shots.pairs(empty1, empty2)
    out = tmp_path / "contact.png"
    assert shots.contact(str(act / "*.png"), out, cols=2) == 2
    assert Image.open(out).size == (256, 112 + 10)
