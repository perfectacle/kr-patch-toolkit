import os
import subprocess

import pytest
from test_lua import LUA
from test_lua import STUB as SFC_STUB

from kr_patch import cli
from kr_patch.fc import dis6502, ines

LUA_DIR = cli.fc_lua_dir()
# A probe and its input driver each add an endFrame callback, so keep all of them.
STUB = SFC_STUB.replace('if t == "endFrame" then cb = f end', 'if t == "endFrame" then cbs[#cbs + 1] = f end') \
    .replace("local cb\n", "local cbs = {}\n").replace("cb() end", "for _, f in ipairs(cbs) do f() end end")

# LDA #$01; STA $0300,X; BNE -5; JSR $C000; LDA ($10),Y; JMP ($FFFC); one unofficial opcode ($02); RTS
CODE = bytes.fromhex("A901 9D0003 D0FB 2000C0 B110 6CFCFF 02 60")


def make_ines(prg_banks=2, chr_banks=0, mapper=1, flags6=0x02, prg=b"", at=0, trainer=False, nes2=False, tail=b""):
    f6 = flags6 | (mapper & 0x0F) << 4 | (4 if trainer else 0)
    f7 = mapper & 0xF0 | (0x08 if nes2 else 0)
    head = bytearray(b"NES\x1a" + bytes([prg_banks, chr_banks, f6, f7]) + bytes(8))
    if nes2:
        head[8] = mapper >> 8 & 0x0F
    if tail:
        head[12:16] = tail
    body = bytearray(prg_banks * 0x4000)
    body[at:at + len(prg)] = prg
    return bytes(head) + (bytes(512) if trainer else b"") + bytes(body) + bytes(chr_banks * 0x2000)


def test_header():
    h = ines.parse(make_ines(32, 0, 1))
    assert (h.prg_size, h.chr_size, h.mapper, h.battery, h.trainer, h.nes2) == (0x80000, 0, 1, True, False, False)
    assert h.mirroring == "horizontal"
    h = ines.parse(make_ines(2, 1, 0x14A, flags6=1, nes2=True))
    assert (h.mapper, h.nes2, h.mirroring, h.chr_size) == (0x14A, True, "vertical", 0x2000)
    # text left in bytes 12-15 by old dumping tools: byte 7 is not trusted
    assert ines.parse(make_ines(2, 0, 0x41, tail=b"Dude")).mapper == 1
    with pytest.raises(ValueError):
        ines.parse(b"NOT A ROM" + bytes(16))


def test_prg_skips_trainer():
    data = make_ines(1, 1, prg=b"\xAA\xBB", trainer=True)
    p = ines.prg(data)
    assert len(p) == 0x4000 and p[:2] == b"\xAA\xBB"
    assert len(ines.chr_rom(data)) == 0x2000


def test_disasm():
    prg = bytes(0x4000) + CODE + bytes(0x4000 - len(CODE))
    out = dis6502.disasm(prg, 0x4000, 0xC000, 8).splitlines()
    assert out == [
        "01:C000  a9 01    LDA #$01",
        "01:C002  9d 00 03 STA $0300,X",
        "01:C005  d0 fb    BNE $C002",
        "01:C007  20 00 c0 JSR $C000",
        "01:C00A  b1 10    LDA ($10),Y",
        "01:C00C  6c fc ff JMP ($FFFC)",
        "01:C00F  02       .db $02",
        "01:C010  60       RTS",
    ]
    # 8 KB banks label the same offset as bank 02
    assert dis6502.disasm(prg, 0x4000, 0xC000, 1, bank_size=0x2000).startswith("02:C000")


def test_truncated_operand_is_a_byte():
    text, n = dis6502.decode(b"\xAD\x00", 0, 0x8000)
    assert text.endswith(".db $AD") and n == 1


def test_listing_marks_gaps():
    prg = CODE + bytes(0x4000 - len(CODE))
    rows = dis6502.read_cover(["00000 8000 3\n", "00002 8002 3", "", "00010 8010 1"])
    out = dis6502.listing(prg, rows).splitlines()
    assert out[0].startswith("00:8000  a9 01    LDA #$01") and out[0].endswith("; 3")
    assert out[2] == "" and out[3].startswith("00:8010  60       RTS")


def _cli(capsys, *args):
    code = 0
    try:
        cli.main([str(a) for a in args])
    except SystemExit as e:
        code = e.code
    return code, capsys.readouterr()


def test_cli(tmp_path, capsys):
    rom = tmp_path / "t.nes"
    rom.write_bytes(make_ines(4, 0, 1, prg=CODE, at=3 * 0x4000))
    code, o = _cli(capsys, "fc", "info", rom)
    assert code == 0 and o.out.strip() == ("iNES mapper=1 prg=64K chr=0 (CHR-RAM) mirroring=horizontal "
                                           "battery=yes trainer=no")
    # no --bank: the last bank, where the fixed $C000 bank of most mappers comes from
    _, o = _cli(capsys, "fc", "dis", rom, "C000", "1")
    assert o.out.strip() == "03:C000  a9 01    LDA #$01"
    _, o = _cli(capsys, "fc", "dis", rom, "8000", "1", "--bank", "3")
    assert o.out.strip() == "03:8000  a9 01    LDA #$01"
    _, o = _cli(capsys, "fc", "dis", rom, "8000", "1", "--offset", "C002")
    assert o.out.strip() == "03:8000  9d 00 03 STA $0300,X"
    code, o = _cli(capsys, "fc", "dis", rom, "8000", "1", "--bank", "4")
    assert code == 2 and "outside" in o.err
    (tmp_path / "cover.txt").write_text("0C000 C000 2\n00000 8000 1\n")
    _, o = _cli(capsys, "fc", "listing", rom, tmp_path / "cover.txt", "--range", "C000-FFFF")
    assert o.out.strip() == "03:C000  a9 01    LDA #$01         ; 2"
    _, o = _cli(capsys, "fc", "lua")
    assert (LUA_DIR / "lib.lua").exists() and o.out.strip() == str(LUA_DIR)


needs_lua = pytest.mark.skipif(LUA is None, reason="needs a Lua 5.3+ interpreter")


def _lua(tmp_path, script, **env):
    (tmp_path / "stub.lua").write_text(STUB)
    out = tmp_path / "out"
    out.mkdir(exist_ok=True)
    e = dict(os.environ, LIBDIR=str(LUA_DIR), SHOT_DIR=str(out), **env)
    r = subprocess.run([LUA, str(tmp_path / "stub.lua"), str(LUA_DIR / script)], capture_output=True, text=True, env=e)
    assert r.returncode == 0, r.stderr
    return out


@needs_lua
def test_boot(tmp_path):
    out = _lua(tmp_path, "boot.lua", MAXF="120", EVERY="60")
    assert sorted(p.name for p in out.iterdir()) == ["f00060.png", "f00120.png"]


@needs_lua
def test_seq_from_state(tmp_path):
    (tmp_path / "s.mss").write_bytes(b"")
    out = _lua(tmp_path, "seq.lua", STATE=str(tmp_path / "s.mss"), SEQ="a:3,wait:5", EVERY="0", TAIL="4",
               POKE="0044=12", WATCH="x=0044;y=0045:2")
    assert (out / "watch.txt").read_text() == "end x=12 y=0000\n"
    # the stub reports every memory as 16 bytes; savestates need an exec callback it never fires
    assert {p.name for p in out.iterdir()} >= {"end.png", "end.ram", "end.wram", "end.oam"}


@needs_lua
def test_probe_driver(tmp_path):
    (tmp_path / "s.mss").write_bytes(b"")
    out = _lua(tmp_path, "probe/watch.lua", DRIVER=str(LUA_DIR / "seq.lua"), STATE=str(tmp_path / "s.mss"),
               SEQ="wait:20", EVERY="0", TAIL="1", WF="1", WT="10", WATCH="0044,0045:2")
    assert (out / "watch.txt").read_text() == "1 0044=00 0045=0000\n"
