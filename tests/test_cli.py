from PIL import Image

from kr_patch import cli, lzss
from kr_patch.snes import tiles


def run(capsys, *args, err=False):
    code = 0
    try:
        cli.main([str(a) for a in args])
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else (1 if e.code else 0)
    o = capsys.readouterr()
    return (code, o.out, o.err) if err else (code, o.out)


def test_ips_make_apply(tmp_path, capsys, rom_factory):
    a = rom_factory("lorom")
    b = bytearray(a)
    b[0x100:0x110] = b"\x11" * 16
    (tmp_path / "a.sfc").write_bytes(a)
    (tmp_path / "b.sfc").write_bytes(bytes(b))
    code, out = run(capsys, "ips", "make", tmp_path / "a.sfc", tmp_path / "b.sfc", tmp_path / "p.ips",
                    "--headered", tmp_path / "ph.ips")
    assert code == 0 and "p.ips" in out and "ph.ips" in out
    run(capsys, "ips", "apply", tmp_path / "a.sfc", tmp_path / "p.ips", tmp_path / "c.sfc")
    assert (tmp_path / "c.sfc").read_bytes() == bytes(b)


def test_checksum(tmp_path, capsys, rom_factory):
    rom = bytearray(rom_factory("hirom"))
    p = tmp_path / "r.sfc"
    p.write_bytes(bytes(rom))
    code, out = run(capsys, "snes", "checksum", p)
    assert code == 0 and out.startswith("hirom") and out.rstrip().endswith("ok")
    rom[0x1000] ^= 0xFF
    p.write_bytes(b"\0" * 512 + bytes(rom))
    code, out = run(capsys, "snes", "checksum", p)
    assert code == 1 and "BAD" in out
    code, out = run(capsys, "snes", "checksum", p, "--fix")
    assert out.startswith("checksum ")
    assert run(capsys, "snes", "checksum", p)[0] == 0
    assert p.read_bytes()[:512] == b"\0" * 512


def test_dis(tmp_path, capsys, rom_factory):
    p = tmp_path / "r.sfc"
    p.write_bytes(rom_factory("lorom", code=bytes.fromhex("C230A93412"), code_at=0x808000))
    code, out = run(capsys, "snes", "dis", p, "808000", "2")
    assert out.splitlines() == ["80:8000  c2 30        REP #$30", "80:8002  a9 34 12     LDA #$1234"]
    code, out = run(capsys, "snes", "dis", p, "808002", "1", "--m16", "--mapper", "lorom")
    assert out.strip().endswith("LDA #$1234")


def test_lz(tmp_path, capsys):
    data = tiles.encode([[1, 2, 3, 0, 1, 2, 3, 0]] * 8, 2) * 4
    (tmp_path / "in.bin").write_bytes(data)
    run(capsys, "lzss", "encode", tmp_path / "in.bin", tmp_path / "c.bin", "--planar")
    c = (tmp_path / "c.bin").read_bytes()
    assert lzss.decompress(c)[0] == tiles.snes_to_planar(data)
    (tmp_path / "rom.bin").write_bytes(b"\xAA" * 16 + c)
    code, out = run(capsys, "lzss", "decode", tmp_path / "rom.bin", "10", tmp_path / "d.bin", "--planar")
    assert (tmp_path / "d.bin").read_bytes() == data


def test_tiles_bg_bgrefs(tmp_path, capsys):
    data = tiles.encode([[3] * 8] * 8, 2) * 10
    (tmp_path / "t.bin").write_bytes(data)
    run(capsys, "snes", "tiles", tmp_path / "t.bin", "0", "A0", tmp_path / "t.png", "--cols", "5", "--scale", "1")
    assert Image.open(tmp_path / "t.png").size == (45, 18)
    (tmp_path / "vram.bin").write_bytes(bytes(0x10000))
    (tmp_path / "cg.bin").write_bytes(bytes(512))
    run(capsys, "snes", "bg", tmp_path / "vram.bin", tmp_path / "cg.bin", "0", "0x1000", "4", tmp_path / "bg.png", "--scale", "1")
    assert Image.open(tmp_path / "bg.png").size == (256, 256)
    code, out = run(capsys, "snes", "bgrefs", tmp_path / "vram.bin", "--layer", "0:0x1000:4", "--range", "2000-2FFF")
    assert out.strip() == "BG1 tiles->2000-2FFF: 1 2000-201F"


def test_diff(tmp_path, capsys):
    (tmp_path / "a").write_bytes(bytes(64))
    (tmp_path / "b").write_bytes(bytes(10) + b"\x01" + bytes(53))
    assert run(capsys, "diff", tmp_path / "a", tmp_path / "b")[1].split() == ["00000A-00000A", "1"]


def test_shotcmp_exit_status(tmp_path, capsys):
    Image.new("RGB", (4, 4)).save(tmp_path / "a.png")
    Image.new("RGB", (4, 4), (9, 9, 9)).save(tmp_path / "b.png")
    assert run(capsys, "shotcmp", tmp_path / "a.png", tmp_path / "a.png")[0] == 0
    code, out = run(capsys, "shotcmp", tmp_path / "a.png", tmp_path / "b.png", "--crop", tmp_path / "c.png")
    assert code == 1 and "diff px=16" in out
    assert Image.open(tmp_path / "c.png").size == (4, 4)
    act, ref = tmp_path / "act", tmp_path / "ref"
    act.mkdir(); ref.mkdir()
    Image.new("RGB", (4, 4)).save(act / "x.png")
    Image.new("RGB", (4, 4)).save(ref / "x.png")
    assert run(capsys, "shotcmp", act, ref)[0] == 0
    Image.new("RGB", (4, 4)).save(ref / "y.png")
    code, out = run(capsys, "shotcmp", act, ref)
    assert code == 1 and "y.png: missing" in out
    (tmp_path / "e1").mkdir(); (tmp_path / "e2").mkdir()
    assert run(capsys, "shotcmp", tmp_path / "e1", tmp_path / "e2")[0] == 2


def test_glyph(tmp_path, capsys):
    store = tmp_path / "g.json"
    run(capsys, "glyph", "set", store, "가", "##..", "#...")
    run(capsys, "glyph", "set", store, "나", "..##", "...#")
    code, out = run(capsys, "glyph", "make", store, "다", "가", "x=나:0-1,2-3")
    assert out.splitlines()[1].startswith("####")
    code, out = run(capsys, "glyph", "show", store, "다")
    assert out.splitlines() == ["다", "####", "#..#"]
    code, out, err = run(capsys, "glyph", "show", store, "다라", err=True)
    assert code == 1 and out.splitlines()[0] == "다" and "라" in err


def test_run_rejects_bad_script(tmp_path, capsys):
    (tmp_path / "s.txt").write_text("10 jump 4\n20 end\n")
    code, out, err = run(capsys, "snes", "run", "nocore", "norom", tmp_path / "out", tmp_path / "s.txt", err=True)
    assert code == 2 and "unknown button" in err


def test_run_load_failed(tmp_path, capsys):
    (tmp_path / "s.txt").write_text("10 end\n")
    (tmp_path / "r.sfc").write_bytes(bytes(0x8000))
    code, out, err = run(capsys, "snes", "run", tmp_path / "missing_libretro.so", tmp_path / "r.sfc",
                         tmp_path / "out", tmp_path / "s.txt", err=True)
    assert code == 3 and err.startswith("LOAD FAILED") and out == ""


def test_errors_exit_2(tmp_path, capsys):
    code, out, err = run(capsys, "ips", "apply", tmp_path / "nope.sfc", tmp_path / "nope.ips", tmp_path / "o", err=True)
    assert code == 2 and err.startswith("krpatch: error:")
    (tmp_path / "bad.lz").write_bytes(b"\x05")
    code, out, err = run(capsys, "lzss", "decode", tmp_path / "bad.lz", "0", tmp_path / "o", err=True)
    assert code == 2 and "truncated" in err


def test_checksum_fix_refuses_unknown_header(tmp_path, capsys):
    p = tmp_path / "junk.bin"
    p.write_bytes(bytes(0x10000))
    code, out, err = run(capsys, "snes", "checksum", p, "--fix", err=True)
    assert code == 2 and "--mapper" in err
    assert p.read_bytes() == bytes(0x10000)
    assert run(capsys, "snes", "checksum", p, "--fix", "--mapper", "lorom")[0] == 0


def test_lua_dir(capsys):
    code, out = run(capsys, "snes", "lua")
    assert out.strip().endswith("lua")


def test_nds_unpack_pack(tmp_path, capsys):
    from test_nds import make_nds
    (tmp_path / "r.nds").write_bytes(make_nds())
    code, out = run(capsys, "nds", "info", tmp_path / "r.nds")
    assert code == 0 and "KRPT" in out and "files 4" in out
    code, out = run(capsys, "nds", "ls", tmp_path / "r.nds")
    assert "sub/b.bin" in out and "overlay9/overlay_0000.bin" in out
    run(capsys, "nds", "unpack", tmp_path / "r.nds", tmp_path / "x")
    (tmp_path / "x/data/sub/b.bin").write_bytes(b"new")
    code, out = run(capsys, "nds", "pack", tmp_path / "r.nds", tmp_path / "x", tmp_path / "o.nds")
    assert code == 0 and "sub/b.bin" in out and "1 files replaced" in out
    from kr_patch.nds.rom import Rom
    r = Rom((tmp_path / "o.nds").read_bytes())
    assert r.file(r.find("sub/b.bin")) == b"new"


def test_lz11_cli(tmp_path, capsys):
    (tmp_path / "a").write_bytes(b"abcabcabc" * 50)
    code, out = run(capsys, "lz11", "encode", tmp_path / "a", tmp_path / "a.lz")
    assert code == 0
    code, out = run(capsys, "lz11", "decode", tmp_path / "a.lz", tmp_path / "b")
    assert (tmp_path / "b").read_bytes() == b"abcabcabc" * 50
    code, out, err = run(capsys, "lz11", "decode", tmp_path / "a", tmp_path / "c", err=True)
    assert code == 2 and "LZ10/LZ11" in err


def test_linear_cli(tmp_path, capsys):
    (tmp_path / "f").write_bytes(bytes(range(64)))
    code, out = run(capsys, "linear", tmp_path / "f", tmp_path / "f.png", "--size", "8x8", "--bpp", "2",
                    "--order", "msb", "--cols", "4", "--scale", "1")
    assert code == 0
    assert Image.open(tmp_path / "f.png").size == (4 * 9 + 1, 9 + 1)
