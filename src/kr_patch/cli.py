"""krpatch: command-line front end. Run `krpatch <command> -h` for each command."""
import argparse
import sys
from pathlib import Path

from . import __version__


def _hex(s):
    return int(s, 16)


def _int(s):
    return int(s, 0)


def _read(p):
    return Path(p).read_bytes()


# platform-independent commands

def cmd_ips_make(a):
    from . import ips
    base, patched = _read(a.base), _read(a.patched)
    jobs = [(a.out, False)] + ([(a.headered, True)] if a.headered else [])
    for path, hdr in jobs:
        p = ips.make(base, patched, header=hdr, gap=a.gap)
        pad = bytes(ips.COPIER) if hdr else b""
        if ips.apply(pad + base, p) != pad + patched:
            raise ValueError(f"{path}: does not reproduce the patched file")
        Path(path).write_bytes(p)
        print(f"{path}: {len(p)} bytes")


def cmd_ips_apply(a):
    from . import ips
    Path(a.out).write_bytes(ips.apply(_read(a.file), _read(a.patch)))


def cmd_diff(a):
    from .diff import ranges
    for s, e in ranges(_read(a.a), _read(a.b), a.gap):
        print("%06X-%06X %6d" % (s, e, e - s + 1))


def cmd_lzss_decode(a):
    from . import lzss
    from .snes.tiles import planar_to_snes
    data, n = lzss.decompress(_read(a.file), a.offset)
    if a.planar:
        data = planar_to_snes(data)
    Path(a.out).write_bytes(data)
    print(f"{len(data)} bytes from {n} compressed")


def cmd_lzss_encode(a):
    from . import lzss
    from .snes.tiles import snes_to_planar
    data = _read(a.file)
    if a.planar:
        data = snes_to_planar(data)
    out = lzss.compress(data)
    Path(a.out).write_bytes(out)
    print(f"{len(out)} bytes from {len(data)}")


def cmd_shotcmp(a):
    from PIL import Image
    from . import shots
    if not a.ref:
        if not (a.box and a.crop):
            raise ValueError("without REF, --box and --crop are required")
        shots.region(Image.open(a.actual), a.box).save(a.crop)
        print(f"cropped {a.box[2]}x{a.box[3]} -> {a.crop}")
        return
    ps = shots.pairs(a.actual, a.ref)
    failed = 0
    for x, y in ps:
        if not x.exists() or not y.exists():
            print(f"{x.name}: {'no reference' if x.exists() else 'missing'}")
            failed += 1
            continue
        bbox, msg = shots.compare(x, y, a.box, a.tol)
        print(f"{x.name}: {msg}")
        if msg != "same":
            failed += 1
        if bbox and a.crop and len(ps) == 1:
            Image.open(x).crop(bbox).save(a.crop)
    sys.exit(1 if failed else 0)


def cmd_contact(a):
    from . import shots
    print(shots.contact(a.pattern, a.out, a.cols))


def cmd_glyph(a):
    from .glyph import store as G
    store = G.load(a.store)

    def get(ch):
        if ch not in store:
            raise ValueError(f"{ch!r} is not in {a.store}")
        return store[ch]

    if a.op == "show":
        missing = [c for c in a.args[0] if c not in store]
        lines = G.side_by_side([(c, store[c]) for c in a.args[0] if c in store])
        if lines[0]:
            print("\n".join(lines))
        if missing:
            print(f"not in {a.store}: {''.join(missing)}", file=sys.stderr)
            sys.exit(1)
        return
    if a.op == "make":
        ch, base, specs = a.args[0], a.args[1], a.args[2:]
        g = get(base)
        for spec in specs:
            src, rows, cols = G.parse_spec(spec)
            g = G.transplant(g, get(src), rows, cols)
        store[ch] = g
        G.save(a.store, store)
        lines = G.side_by_side([(ch, g), (base, get(base))] + [(G.parse_spec(s)[0], get(G.parse_spec(s)[0])) for s in specs])
    else:   # set: rows given as '.#' or '01' strings
        ch = a.args[0]
        store[ch] = G.parse(a.args[1:])
        G.save(a.store, store)
        lines = G.side_by_side([(ch, store[ch])])
    print("\n".join(lines))


def cmd_ocr(a):
    from .glyph import ocr
    from .glyph import store as G
    from .glyph.hangul import fix_mieum_ieung
    store = G.load(a.store)
    res = ocr.ocr_glyphs(store, a.outdir, a.per_row, a.scale, a.blur, a.lang)
    for k, ch in res.items():
        if ch and a.fix_mo:
            ch = fix_mieum_ieung(ch, store[k])
        print(f"{k}\t{ch or '?'}")


# SNES commands

def _mapper(name, rom):
    from .snes import header, mapper
    return header.detect(rom) if name == "auto" else mapper.get(name)


def cmd_dis(a):
    from .snes.dis65816 import disasm
    from .snes.header import strip_copier
    rom = strip_copier(_read(a.rom))
    print(disasm(rom, a.addr, a.count, not a.m16, not a.x16, _mapper(a.mapper, rom)))


def cmd_checksum(a):
    from .snes import header
    data = _read(a.rom)
    pre = data[:header.COPIER] if header.has_copier(data) else b""
    rom = data[len(pre):]
    mp = _mapper(a.mapper, rom)
    if a.fix and a.mapper == "auto":
        mp, score = header.detect_score(rom)
        if score < header.CONFIDENT:
            raise ValueError(f"no recognisable internal header (best guess {mp.name}, score {score}); "
                             "pass --mapper to fix it anyway")
    if a.fix:
        rom, s = header.fix(rom, mp)
        Path(a.rom).write_bytes(pre + rom)
        print(f"checksum {s:04X}")
        return
    comp, csum = header.stored(rom, mp)
    want = header.compute(rom, mp)
    ok = csum == want and comp == want ^ 0xFFFF
    print(f"{mp.name} title={header.title(rom, mp)!r} stored={csum:04X}/{comp:04X} computed={want:04X} {'ok' if ok else 'BAD'}")
    sys.exit(0 if ok else 1)


def cmd_tiles(a):
    from .snes.tiles import render
    data = _read(a.file)
    im = render(data, a.start, a.length // (a.stride or a.bpp * a.rows), a.bpp, rows=a.rows,
                stride=a.stride, cols=a.cols, scale=a.scale, tall=a.tall)
    im.save(a.out)
    print(a.out)


def cmd_bg(a):
    from .snes import bg
    bg.render(_read(a.vram), _read(a.cgram), a.map, a.chr, a.bpp, a.palbase, a.scale).save(a.out)


def cmd_bgrefs(a):
    from .snes import bg
    vram = _read(a.vram)
    lo, hi = (int(x, 16) for x in a.range.split("-"))
    for i, spec in enumerate(a.layer, 1):
        m, c, bpp = (_int(x) for x in spec.split(":"))
        h = bg.hits(vram, m, c, bpp, lo, hi + 1)
        print(f"BG{i} tiles->{lo:04X}-{hi:04X}: " + (f"{h[2]} {h[0]:04X}-{h[1]:04X}" if h else "0"))


def cmd_run(a):
    from .snes import libretro, script
    watches = [script.Watch.parse(w, a.watch_fmt) for w in a.watch]
    variables = dict(v.split("=", 1) for v in a.var)
    r = libretro.Runner(a.core, a.rom, a.out, script.load(a.script), a.srm, watches, variables,
                        verbose=a.verbose or None, cheat_hold=a.cheat_hold)
    try:
        n = r.run()
    except libretro.LoadError as e:
        print(e, file=sys.stderr)
        sys.exit(3)
    print("OK", n)


def lua_dir():
    return Path(__file__).resolve().parent / "snes" / "lua"


def cmd_lua(a):
    print(lua_dir())


def _snes_parser(sub):
    snes = sub.add_parser("snes", help="SNES (Super Famicom) tools").add_subparsers(
        dest="snes_cmd", required=True, metavar="command")
    mappers = ["auto", "lorom", "hirom", "exhirom", "sa1"]

    p = snes.add_parser("dis", help="disassemble 65c816 code")
    p.add_argument("rom")
    p.add_argument("addr", type=_hex, help="CPU address in hex, e.g. 808000")
    p.add_argument("count", type=int, nargs="?", default=40)
    p.add_argument("--mapper", choices=mappers, default="auto")
    p.add_argument("--m16", action="store_true", help="start with a 16-bit accumulator")
    p.add_argument("--x16", action="store_true", help="start with 16-bit index registers")
    p.set_defaults(fn=cmd_dis)

    p = snes.add_parser("checksum", help="check or fix the internal header checksum")
    p.add_argument("rom")
    p.add_argument("--fix", action="store_true", help="rewrite the checksum in place")
    p.add_argument("--mapper", choices=mappers, default="auto")
    p.set_defaults(fn=cmd_checksum)

    p = snes.add_parser("tiles", help="render planar tiles to PNG")
    p.add_argument("file")
    p.add_argument("start", type=_hex, help="byte offset (hex)")
    p.add_argument("length", type=_hex, help="byte length (hex)")
    p.add_argument("out")
    p.add_argument("--bpp", type=int, choices=(1, 2, 4, 8), default=2)
    p.add_argument("--rows", type=int, default=8, help="rows per tile (e.g. 12 for 8x12 glyphs)")
    p.add_argument("--stride", type=_hex, help="bytes per tile (hex) when tiles are padded")
    p.add_argument("--cols", type=int, default=16)
    p.add_argument("--scale", type=int, default=2)
    p.add_argument("--tall", action="store_true", help="stack tile pairs into 8x16 glyphs")
    p.set_defaults(fn=cmd_tiles)

    p = snes.add_parser("bg", help="render a BG layer from VRAM and CGRAM dumps")
    p.add_argument("vram")
    p.add_argument("cgram")
    p.add_argument("map", type=_int, help="tilemap VRAM word address")
    p.add_argument("chr", type=_int, help="character VRAM word address")
    p.add_argument("bpp", type=int, choices=(2, 4, 8))
    p.add_argument("out")
    p.add_argument("--palbase", type=int, default=0)
    p.add_argument("--scale", type=int, default=3)
    p.set_defaults(fn=cmd_bg)

    p = snes.add_parser("bgrefs", help="which VRAM bytes each BG tilemap references")
    p.add_argument("vram")
    p.add_argument("--layer", action="append", required=True, metavar="MAP:CHR:BPP",
                   help="word addresses (decimal or 0x..), repeat per layer")
    p.add_argument("--range", default="0000-FFFF", help="VRAM byte range in hex, e.g. 6000-7FFF")
    p.set_defaults(fn=cmd_bgrefs)

    p = snes.add_parser("run", help="play an input script on a libretro core")
    p.add_argument("core", help="libretro core (.dylib/.so/.dll)")
    p.add_argument("rom")
    p.add_argument("out")
    p.add_argument("script")
    p.add_argument("srm", nargs="?", help="save RAM to load")
    p.add_argument("--watch", action="append", default=[], metavar="ADDR[:SIZE]",
                   help="WRAM value logged to wram.log on change (hex address, 1-4 bytes)")
    p.add_argument("--watch-fmt", default="", metavar="SPEC", help="format spec for watched values, e.g. 03x")
    p.add_argument("--var", action="append", default=[], metavar="KEY=VALUE", help="core option")
    p.add_argument("--cheat-hold", type=int, default=40,
                   help="frames a poke is held as a cheat on cores without a WRAM pointer")
    p.add_argument("-v", "--verbose", action="store_true", help="print core log and environment calls")
    p.set_defaults(fn=cmd_run)

    p = snes.add_parser("lua", help="print the directory of the bundled Mesen 2 Lua scripts")
    p.set_defaults(fn=cmd_lua)


def build_parser():
    ap = argparse.ArgumentParser(prog="krpatch", description="Translation patch tools")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True, metavar="command")

    p = sub.add_parser("ips", help="create or apply IPS patches")
    ips = p.add_subparsers(dest="op", required=True)
    q = ips.add_parser("make", help="patch from BASE to PATCHED, checked by re-applying it")
    q.add_argument("base")
    q.add_argument("patched")
    q.add_argument("out")
    q.add_argument("--headered", metavar="OUT", help="also write a patch for SNES dumps with a 512-byte copier header")
    q.add_argument("--gap", type=int, default=6, help="equal bytes that end a record (default 6)")
    q.set_defaults(fn=cmd_ips_make)
    q = ips.add_parser("apply")
    q.add_argument("file")
    q.add_argument("patch")
    q.add_argument("out")
    q.set_defaults(fn=cmd_ips_apply)

    p = sub.add_parser("lzss", help="LZSS (12-bit distance, 4-bit length) codec")
    lz = p.add_subparsers(dest="op", required=True)
    q = lz.add_parser("decode")
    q.add_argument("file")
    q.add_argument("offset", type=_hex)
    q.add_argument("out")
    q.add_argument("--planar", action="store_true", help="re-interleave planar SNES 2bpp halves to SNES order")
    q.set_defaults(fn=cmd_lzss_decode)
    q = lz.add_parser("encode")
    q.add_argument("file")
    q.add_argument("out")
    q.add_argument("--planar", action="store_true", help="split SNES 2bpp tiles into planar halves first")
    q.set_defaults(fn=cmd_lzss_encode)

    p = sub.add_parser("diff", help="list byte ranges where two files differ")
    p.add_argument("a")
    p.add_argument("b")
    p.add_argument("--gap", type=int, default=16, help="merge ranges closer than this")
    p.set_defaults(fn=cmd_diff)

    p = sub.add_parser("shotcmp", help="compare screenshots and print differing regions")
    p.add_argument("actual", help="PNG file or directory")
    p.add_argument("ref", nargs="?", help="PNG file or directory")
    p.add_argument("--box", type=lambda s: tuple(int(x) for x in s.split(",")), metavar="X,Y,W,H")
    p.add_argument("--tol", type=int, default=0, help="per-channel difference ignored as noise")
    p.add_argument("--crop", metavar="OUT.png", help="write the differing region (or --box without REF)")
    p.set_defaults(fn=cmd_shotcmp)

    p = sub.add_parser("contact", help="contact sheet of screenshots")
    p.add_argument("pattern", help="glob, quoted")
    p.add_argument("out")
    p.add_argument("--cols", type=int, default=10)
    p.set_defaults(fn=cmd_contact)

    p = sub.add_parser("glyph", help="show or build glyphs in a JSON glyph store")
    p.add_argument("op", choices=("show", "make", "set"))
    p.add_argument("store")
    p.add_argument("args", nargs="+", help="show CHARS | make CH BASE SRC:R0-R1,C0-C1... | set CH ROW...")
    p.set_defaults(fn=cmd_glyph)

    p = sub.add_parser("ocr", help="read glyphs of a JSON glyph store with macOS Vision")
    p.add_argument("store")
    p.add_argument("outdir", help="where row images are written")
    p.add_argument("--per-row", type=int, default=10)
    p.add_argument("--scale", type=int, default=8)
    p.add_argument("--blur", type=float, default=0.0)
    p.add_argument("--lang", default="ko-KR")
    p.add_argument("--fix-mo", action="store_true", help="re-decide ㅁ/ㅇ from glyph corners (pixel fonts only)")
    p.set_defaults(fn=cmd_ocr)

    _snes_parser(sub)
    return ap


def main(argv=None):
    ap = build_parser()
    a = ap.parse_args(argv)
    try:
        a.fn(a)
    except (ValueError, OSError, IndexError) as e:
        print(f"{ap.prog}: error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
