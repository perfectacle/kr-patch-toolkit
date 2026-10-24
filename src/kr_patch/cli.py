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
        p = ips.make(base, patched, header=hdr, gap=a.gap, rle=a.rle)
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
    from .sfc.tiles import planar_to_sfc
    data, n = lzss.decompress(_read(a.file), a.offset)
    if a.planar:
        data = planar_to_sfc(data)
    Path(a.out).write_bytes(data)
    print(f"{len(data)} bytes from {n} compressed")


def cmd_lzss_encode(a):
    from . import lzss
    from .sfc.tiles import sfc_to_planar
    data = _read(a.file)
    if a.planar:
        data = sfc_to_planar(data)
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


def cmd_lz11_decode(a):
    from . import lz11
    data, n = lz11.decompress(_read(a.file), a.offset)
    Path(a.out).write_bytes(data)
    print(f"{len(data)} bytes from {n} compressed")


def cmd_lz11_encode(a):
    from . import lz11
    data = _read(a.file)
    out = lz11.compress(data, 0x10 if a.lz10 else 0x11, 2 if a.vram else 1)
    Path(a.out).write_bytes(out)
    print(f"{len(out)} bytes from {len(data)}")


def cmd_xdelta_make(a):
    from . import vcdiff
    n = vcdiff.make(a.base, a.patched, a.out, a.xdelta3, a.level)
    print(f"{a.out}: {n} bytes")


def cmd_xdelta_apply(a):
    from . import vcdiff
    Path(a.out).write_bytes(vcdiff.apply(_read(a.file), _read(a.patch)))


def cmd_linear(a):
    from . import linear
    w, h = (int(x) for x in a.size.lower().split("x"))
    data = _read(a.file)[a.offset:]
    img = linear.sheet(data, w, h, a.bpp, a.order, a.start, a.count, a.cols, a.scale)
    img.save(a.out)
    print(f"{a.out}: {img.width}x{img.height}")


# audio commands (numpy is imported only here, so other commands start fast)

def _span(s):
    a, b = s.split(":")
    return float(a), float(b)


def _positive(kind):
    def parse(s):
        v = kind(s)
        if not v > 0:
            raise argparse.ArgumentTypeError(f"must be positive, not {s}")
        return v
    parse.__name__ = kind.__name__
    return parse


_pos_int, _pos_float = _positive(int), _positive(float)


def _range(x, rate, start, end):
    """First and end sample of start..end seconds (end None = end of file)."""
    a, b = int(start * rate), len(x) if end is None else int(end * rate)
    if not 0 <= a < b <= len(x):
        raise ValueError(f"range {start}-{end} s is outside the {len(x) / rate:.3f} s recording")
    return a, b


def _json(v):
    """JSON number, or null for -inf and NaN, which JSON cannot hold."""
    import math
    return round(v, 2) if math.isfinite(v) else None


def cmd_segments(a):
    from .audio import analysis, wav
    x, rate = wav.read(a.wav)
    songs, gaps = analysis.segments(x, rate, a.window, a.threshold, a.min_gap)
    for s, e in gaps if a.gaps else songs:
        print(f"{s:9.2f} {e:9.2f} {e - s:9.2f}")


def cmd_period(a):
    from .audio import analysis, wav
    x, rate = wav.read(a.wav)
    lo, hi = _range(x, rate, a.start, a.end)
    cands = analysis.period_candidates(analysis.as_float(x[lo:hi]), rate, a.min_lag, a.range, a.top, a.fft, a.hop)
    for lag, score in cands:
        print(f"{lag / rate:10.3f} s {lag:10d} samples  sim={score:.4f}")
    print(f"resolution {a.hop} samples; a peak may be a multiple or a fraction of the true period, "
          "check it by ear or with `krpatch audio loop --period-range`", file=sys.stderr)


LOOP_DEFAULTS = {"fade_shape": "equal-gain", "tail_from": "seam", "seam_pick": "earliest"}
LOOP_LEGACY = {"fade_shape": "equal-power", "tail_from": "end", "seam_pick": "best"}


def cmd_loop(a):
    import json

    from .audio import analysis, loop, wav
    if a.period and a.period_range:
        raise ValueError("pass --period or --period-range, not both")
    for k, v in (LOOP_LEGACY if a.legacy else LOOP_DEFAULTS).items():
        if getattr(a, k) is None:
            setattr(a, k, v)
    x, rate = wav.read(a.wav)
    A, end = _range(x, rate, a.start, a.end)
    if a.end is None:
        songs = analysis.segments(x[A:end], rate)[0]
        if len(songs) > 1:
            print(f"warning: {len(songs)} songs separated by silence after --start (next at "
                  f"{a.start + songs[1][0]:.2f} s); pass --end to keep the search inside one song",
                  file=sys.stderr)
    win, coarse = int(a.window / 2 * rate), int(a.coarse_step * rate)
    P, pscore = a.period, None
    if not P:
        f = analysis.as_float(x)
        lag, _ = analysis.period_candidates(f[A:end], rate, a.min_lag, a.period_range, 1)[0]
        P, pscore = analysis.refine_period(f, rate, lag, A, end, a.refine_length)
        print(f"period {P} samples ({P / rate:.5f} s), waveform ncc {pscore:.4f}", file=sys.stderr)
    margin = win + coarse + a.snap
    if a.seam_range:
        t0, t1 = int(a.seam_range[0] * rate), int(a.seam_range[1] * rate)
    else:
        t0, t1 = A + margin, end - P - margin - a.snap_len
    if t0 < margin or t1 + P + margin + a.snap_len > end or t1 <= t0:
        raise ValueError("the seam range needs a full period plus the search window after it before --end "
                         "(or the end of the recording); record longer or narrow --seam-range")
    seam = loop.Seam(x, P, win, legacy=a.legacy)
    T = seam.find(t0, t1, coarse, a.fine_step, a.snap, a.snap_len,
                  None if a.seam_pick == "best" else a.seam_delta)
    tail, fade = int(a.tail * rate), int(a.fade_ms / 1000 * rate)
    E = T + P
    if (T if a.tail_from == "seam" else E) + tail > end:
        raise ValueError(f"--tail {a.tail} s does not fit before --end (or the end of the recording)")
    if T - fade < A:
        raise ValueError("the crossfade would reach before --start; lower --fade-ms or move the seam later")
    wav.write(a.out, loop.render(x, A, T, P, fade, tail, a.fade_shape, a.tail_from), rate)
    meta = {"loopStart": round((T - A) / rate, 6), "loopEnd": round((E - A) / rate, 6),
            "duration": round((E + tail - A) / rate, 6),
            "loopStartSample": T - A, "loopEndSample": E - A, "loopLengthSample": P,
            "durationSamples": E + tail - A, "sampleRate": rate, "period": P, "sourceStartSample": A,
            "seamScore": round(seam.score(T), 4)}
    if pscore is not None:
        meta["periodScore"] = round(pscore, 4)
    text = json.dumps(meta)
    if a.json:
        Path(a.json).write_text(text + "\n")
    print(text)


def cmd_seamcheck(a):
    import json

    from .audio import loop, wav
    y, rate = wav.read(a.wav)
    meta = json.loads(Path(a.json or Path(a.wav).with_suffix(".json")).read_text())

    def sample(key):
        if key + "Sample" in meta:
            return int(meta[key + "Sample"])
        if key in meta:
            return round(meta[key] * rate)
        raise ValueError(f"the loop JSON has neither {key} nor {key}Sample")

    s, e = sample("loopStart"), sample("loopEnd")
    if not 0 <= s < e <= len(y):
        raise ValueError(f"loop {s}-{e} is outside the {len(y)}-sample file")
    src = start = None
    if a.source:
        src, srate = wav.read(a.source)
        if srate != rate:
            raise ValueError(f"{a.source}: {srate} Hz, loop file {rate} Hz")
        start = int(a.source_start * rate) if a.source_start is not None else meta.get("sourceStartSample")
        if start is None:
            raise ValueError("--source needs --source-start when the loop JSON has no sourceStartSample")
    res, z = loop.check(y, rate, s, e, src, start, a.ratio)
    if a.render:
        wav.write(a.render, z, rate)
    print(json.dumps(res))
    sys.exit(0 if res["ok"] else 1)


def cmd_loudness(a):
    import json

    from .audio import loudness, wav
    x, rate = wav.read(a.wav)
    lo, hi = _range(x, rate, a.start, a.end)
    f = x[lo:hi] / 32768
    lufs = loudness.integrated(f, rate)
    res = {"integrated": _json(lufs), "samplePeak": _json(loudness.sample_peak(f))}
    if a.target is not None and res["integrated"] is not None:
        res["gain"] = round(a.target - lufs, 2)
    print(json.dumps(res))


def _audio_parser(sub):
    au = sub.add_parser("audio", help="analyse recordings and make seamless loops (16-bit WAV)").add_subparsers(
        dest="audio_cmd", required=True, metavar="command")

    p = au.add_parser("segments", help="songs separated by silence: start, end, length in seconds")
    p.add_argument("wav")
    p.add_argument("--window", type=_pos_float, default=0.05, help="RMS window in seconds (default 0.05)")
    p.add_argument("--threshold", type=float, default=30,
                   help="RMS over all channels below this (int16 units) is quiet (default 30)")
    p.add_argument("--min-gap", type=_pos_float, default=0.3, help="seconds of quiet that separate songs (default 0.3)")
    p.add_argument("--gaps", action="store_true", help="print the quiet gaps instead of the songs")
    p.set_defaults(fn=cmd_segments)

    p = au.add_parser("period", help="candidate loop periods by spectral self-similarity",
                      description="Candidate loop periods by spectral self-similarity. Give one song's range "
                                  "(--start/--end, e.g. from `krpatch audio segments`): over several songs "
                                  "or the silence after one, long lags that span them win.")
    p.add_argument("wav")
    p.add_argument("--start", type=float, default=0.0, help="song start in seconds")
    p.add_argument("--end", type=_pos_float, help="song end in seconds (default: end of file)")
    p.add_argument("--min-lag", type=_pos_float, default=5.0, help="shortest lag and overlap in seconds (default 5)")
    p.add_argument("--range", type=_span, metavar="LO:HI", help="only lags within LO..HI seconds")
    p.add_argument("--top", type=_pos_int, default=6)
    p.add_argument("--fft", type=_pos_int, default=2048, help="FFT size (default 2048)")
    p.add_argument("--hop", type=_pos_int, default=512, help="frame step in samples (default 512)")
    p.set_defaults(fn=cmd_period)

    p = au.add_parser("loop", help="find the seam and write a loop file; prints JSON")
    p.add_argument("wav")
    p.add_argument("out", help="loop WAV to write")
    p.add_argument("--start", type=float, default=0.0, help="song start in seconds; the file begins here")
    p.add_argument("--end", type=_pos_float, help="end of the song in seconds (default: end of file)")
    p.add_argument("--period", type=_pos_int, help="known period in samples (skips the period search)")
    p.add_argument("--period-range", type=_span, metavar="LO:HI", help="search the period within LO..HI seconds")
    p.add_argument("--min-lag", type=_pos_float, default=5.0, help="shortest period searched, seconds (default 5)")
    p.add_argument("--refine-length", type=_pos_float, default=3.0,
                   help="seconds of waveform matched to refine the period (default 3)")
    p.add_argument("--seam-range", type=_span, metavar="FROM:TO",
                   help="search the seam between these seconds of the recording (default: all that fits)")
    p.add_argument("--seam-pick", choices=("earliest", "best"),
                   help="earliest position within --seam-delta of the best score (default), or the best")
    p.add_argument("--seam-delta", type=_pos_float, default=0.003, help="score margin for earliest (default 0.003)")
    p.add_argument("--window", type=_pos_float, default=0.5, help="seam match window in seconds (default 0.5)")
    p.add_argument("--coarse-step", type=_pos_float, default=0.05, help="coarse seam step in seconds (default 0.05)")
    p.add_argument("--fine-step", type=_pos_int, default=16, help="fine seam step in samples (default 16)")
    p.add_argument("--snap", type=_pos_int, default=200, help="final search +- samples (default 200)")
    p.add_argument("--snap-len", type=_pos_int, default=64, help="samples compared in the final search (default 64)")
    p.add_argument("--fade-ms", type=_pos_float, default=60, help="crossfade before loopEnd (default 60)")
    p.add_argument("--fade-shape", choices=("equal-gain", "equal-power"),
                   help="equal-gain (sin^2, default) suits a seam whose sides match; equal-power (sin/cos) "
                        "is 3 dB louder mid-fade on such audio")
    p.add_argument("--tail", type=float, default=0.5, help="seconds kept after loopEnd (default 0.5)")
    p.add_argument("--tail-from", choices=("seam", "end"),
                   help="tail is the audio after the seam, as heard after the jump (default), "
                        "or what followed loopEnd in the recording")
    p.add_argument("--legacy", action="store_true",
                   help="behave like the make_loop.py script: equal-power fade, tail from the end, best seam, "
                        "seam score on the channel sum")
    p.add_argument("--json", metavar="PATH", help="also write the JSON here")
    p.set_defaults(fn=cmd_loop)

    p = au.add_parser("seamcheck",
                      help="spectral flux at the loop jump vs the uncut recording or the song; exit 1 if louder")
    p.add_argument("wav", help="loop WAV")
    p.add_argument("--json", metavar="PATH", help="loop JSON (default: WAV path with .json)")
    p.add_argument("--source", metavar="WAV", help="original recording, to measure the uncut continuation")
    p.add_argument("--source-start", type=float, help="seconds where the loop file starts in --source "
                                                      "(default: sourceStartSample from the JSON)")
    p.add_argument("--ratio", type=_pos_float, default=1.25,
                   help="pass while the seam flux is at most this times the reference (default 1.25)")
    p.add_argument("--render", metavar="OUT.wav", help="write the intro and the loop three times (two jumps)")
    p.set_defaults(fn=cmd_seamcheck)

    p = au.add_parser("loudness", help="integrated loudness (BS.1770 / EBU R128) and sample peak; prints JSON")
    p.add_argument("wav")
    p.add_argument("--start", type=float, default=0.0, help="seconds")
    p.add_argument("--end", type=_pos_float, help="seconds (default: end of file)")
    p.add_argument("--target", type=float, metavar="LUFS", help="also print the gain in dB to reach this")
    p.set_defaults(fn=cmd_loudness)


# SFC commands

def _mapper(name, rom):
    from .sfc import header, mapper
    return header.detect(rom) if name == "auto" else mapper.get(name)


def cmd_dis(a):
    from .sfc.dis65816 import disasm
    from .sfc.header import strip_copier
    rom = strip_copier(_read(a.rom))
    print(disasm(rom, a.addr, a.count, not a.m16, not a.x16, _mapper(a.mapper, rom)))


def cmd_checksum(a):
    from .sfc import header
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
    from .sfc.tiles import render
    data = _read(a.file)
    im = render(data, a.start, a.length // (a.stride or a.bpp * a.rows), a.bpp, rows=a.rows,
                stride=a.stride, cols=a.cols, scale=a.scale, tall=a.tall)
    im.save(a.out)
    print(a.out)


def cmd_bg(a):
    from .sfc import bg
    bg.render(_read(a.vram), _read(a.cgram), a.map, a.chr, a.bpp, a.palbase, a.scale).save(a.out)


def cmd_bgrefs(a):
    from .sfc import bg
    vram = _read(a.vram)
    lo, hi = (int(x, 16) for x in a.range.split("-"))
    for i, spec in enumerate(a.layer, 1):
        m, c, bpp = (_int(x) for x in spec.split(":"))
        h = bg.hits(vram, m, c, bpp, lo, hi + 1)
        print(f"BG{i} tiles->{lo:04X}-{hi:04X}: " + (f"{h[2]} {h[0]:04X}-{h[1]:04X}" if h else "0"))


def cmd_run(a):
    from .sfc import libretro, script
    watches = [script.Watch.parse(w, a.watch_fmt) for w in a.watch]
    variables = dict(v.split("=", 1) for v in a.var)
    r = libretro.Runner(a.core, a.rom, a.out, script.load(a.script), a.srm, watches, variables,
                        verbose=a.verbose or None, cheat_hold=a.cheat_hold, wav=a.wav)
    try:
        n = r.run()
    except libretro.LoadError as e:
        print(e, file=sys.stderr)
        sys.exit(3)
    print("OK", n)


def lua_dir():
    return Path(__file__).resolve().parent / "sfc" / "lua"


def cmd_lua(a):
    print(lua_dir())


def _sfc_parser(sub):
    sfc = sub.add_parser("sfc", help="SFC (Super Famicom) tools").add_subparsers(
        dest="sfc_cmd", required=True, metavar="command")
    mappers = ["auto", "lorom", "hirom", "exhirom", "sa1"]

    p = sfc.add_parser("dis", help="disassemble 65c816 code")
    p.add_argument("rom")
    p.add_argument("addr", type=_hex, help="CPU address in hex, e.g. 808000")
    p.add_argument("count", type=int, nargs="?", default=40)
    p.add_argument("--mapper", choices=mappers, default="auto")
    p.add_argument("--m16", action="store_true", help="start with a 16-bit accumulator")
    p.add_argument("--x16", action="store_true", help="start with 16-bit index registers")
    p.set_defaults(fn=cmd_dis)

    p = sfc.add_parser("checksum", help="check or fix the internal header checksum")
    p.add_argument("rom")
    p.add_argument("--fix", action="store_true", help="rewrite the checksum in place")
    p.add_argument("--mapper", choices=mappers, default="auto")
    p.set_defaults(fn=cmd_checksum)

    p = sfc.add_parser("tiles", help="render planar tiles to PNG")
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

    p = sfc.add_parser("bg", help="render a BG layer from VRAM and CGRAM dumps")
    p.add_argument("vram")
    p.add_argument("cgram")
    p.add_argument("map", type=_int, help="tilemap VRAM word address")
    p.add_argument("chr", type=_int, help="character VRAM word address")
    p.add_argument("bpp", type=int, choices=(2, 4, 8))
    p.add_argument("out")
    p.add_argument("--palbase", type=int, default=0)
    p.add_argument("--scale", type=int, default=3)
    p.set_defaults(fn=cmd_bg)

    p = sfc.add_parser("bgrefs", help="which VRAM bytes each BG tilemap references")
    p.add_argument("vram")
    p.add_argument("--layer", action="append", required=True, metavar="MAP:CHR:BPP",
                   help="word addresses (decimal or 0x..), repeat per layer")
    p.add_argument("--range", default="0000-FFFF", help="VRAM byte range in hex, e.g. 6000-7FFF")
    p.set_defaults(fn=cmd_bgrefs)

    p = sfc.add_parser("run", help="play an input script on a libretro core")
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
    p.add_argument("--wav", metavar="OUT.wav", help="record the core's audio (16-bit stereo, the core's sample rate)")
    p.add_argument("-v", "--verbose", action="store_true", help="print core log and environment calls")
    p.set_defaults(fn=cmd_run)

    p = sfc.add_parser("lua", help="print the directory of the bundled Mesen 2 / MesenCE Lua scripts")
    p.set_defaults(fn=cmd_lua)


# FC commands

def _fc_prg(path):
    from .fc import ines
    data = _read(path)
    return ines.parse(data), ines.prg(data)


def cmd_fc_info(a):
    h, _ = _fc_prg(a.rom)
    chr_ = f"{h.chr_size // 1024}K" if h.chr_size else "0 (CHR-RAM)"
    sub = f".{h.submapper}" if h.nes2 else ""
    print(f"{'NES 2.0' if h.nes2 else 'iNES'} mapper={h.mapper}{sub} prg={h.prg_size // 1024}K chr={chr_} "
          f"mirroring={h.mirroring} battery={'yes' if h.battery else 'no'} trainer={'yes' if h.trainer else 'no'}")


def _bank_size(s):
    kb = int(s)
    if kb not in (8, 16, 32):
        raise argparse.ArgumentTypeError("bank size is 8, 16 or 32 (KB)")
    return kb * 1024


def cmd_fc_dis(a):
    from .fc.dis6502 import disasm
    _, prg = _fc_prg(a.rom)
    if a.offset is not None:
        off = a.offset
    else:
        bank = a.bank if a.bank is not None else len(prg) // a.bank_size - 1
        off = bank * a.bank_size + a.addr % a.bank_size
    if not 0 <= off < len(prg):
        raise ValueError(f"PRG offset {off:X} outside the {len(prg):X}-byte PRG ROM")
    print(disasm(prg, off, a.addr, a.count, a.bank_size))


def cmd_fc_listing(a):
    from .fc.dis6502 import listing, read_cover
    _, prg = _fc_prg(a.rom)
    lo, hi = (int(x, 16) for x in a.range.split("-"))
    rows = [r for r in read_cover(Path(a.cover).read_text().splitlines()) if lo <= r[0] <= hi]
    print(listing(prg, rows, a.bank_size))


def fc_lua_dir():
    return Path(__file__).resolve().parent / "fc" / "lua"


def cmd_fc_lua(a):
    print(fc_lua_dir())


def _fc_parser(sub):
    fc = sub.add_parser("fc", help="FC (Famicom) tools").add_subparsers(
        dest="fc_cmd", required=True, metavar="command")

    p = fc.add_parser("info", help="iNES / NES 2.0 header: mapper, PRG and CHR sizes, mirroring, battery")
    p.add_argument("rom")
    p.set_defaults(fn=cmd_fc_info)

    p = fc.add_parser("dis", help="disassemble 6502 code")
    p.add_argument("rom")
    p.add_argument("addr", type=_hex, help="CPU address in hex, e.g. C000")
    p.add_argument("count", type=int, nargs="?", default=40)
    p.add_argument("--bank", type=_hex, help="PRG bank mapped at ADDR (hex; default: the last bank)")
    p.add_argument("--bank-size", type=_bank_size, default=0x4000, metavar="KB",
                   help="PRG bank size in KB: 8, 16 (default) or 32")
    p.add_argument("--offset", type=_hex, help="PRG ROM offset (hex) instead of --bank")
    p.set_defaults(fn=cmd_fc_dis)

    p = fc.add_parser("listing", help="disassemble the instructions a cover.lua run executed")
    p.add_argument("rom")
    p.add_argument("cover", help="cover.txt from probe/cover.lua")
    p.add_argument("--range", default="0-FFFFFF", help="PRG offset range in hex, e.g. 3C000-3FFFF")
    p.add_argument("--bank-size", type=_bank_size, default=0x4000, metavar="KB",
                   help="PRG bank size in KB for the BB:AAAA labels (default 16)")
    p.set_defaults(fn=cmd_fc_listing)

    p = fc.add_parser("lua", help="print the directory of the bundled MesenCE Lua scripts for FC")
    p.set_defaults(fn=cmd_fc_lua)


# NDS commands

def _nds(path):
    from .nds.rom import Rom
    return Rom(_read(path))


def cmd_nds_info(a):
    r = _nds(a.rom)
    print(f"title {r.title}  code {r.code}  size {len(r.data):#x}  used {r.used:#x}")
    for name, (off, size) in (("arm9", r.arm9), ("arm7", r.arm7), ("fnt", r.fnt), ("fat", r.fat),
                              ("ovt9", r.ovt9), ("ovt7", r.ovt7)):
        print(f"{name:5} {off:#010x} {size:#x}")
    print(f"files {len(r.entries)}  named {len(r.names)}  overlays {len(r.overlays['9'])}+{len(r.overlays['7'])}")


def cmd_nds_ls(a):
    r = _nds(a.rom)
    rows = [(fid, n) for fid, n in r.names.items()] + [(fid, p) for p, fid in r.overlay_files().items()]
    for fid, name in sorted(rows):
        s, e = r.entries[fid]
        print(f"{fid:5d} {s:#010x} {e - s:10d}  {name}")


def cmd_nds_unpack(a):
    from .nds.rom import unpack
    print(f"{unpack(_nds(a.rom), a.out)} files -> {a.out}")


def cmd_nds_pack(a):
    from .nds.rom import pack
    out, changed = pack(_nds(a.rom), a.dir)
    Path(a.out).write_bytes(out)
    for p in changed:
        print(p)
    print(f"{len(changed)} files replaced -> {a.out} ({len(out)} bytes)")


def _nds_parser(sub):
    nds = sub.add_parser("nds", help="Nintendo DS tools").add_subparsers(
        dest="nds_cmd", required=True, metavar="command")

    p = nds.add_parser("info", help="header, table offsets and file counts")
    p.add_argument("rom")
    p.set_defaults(fn=cmd_nds_info)

    p = nds.add_parser("ls", help="list files: id, offset, size, path")
    p.add_argument("rom")
    p.set_defaults(fn=cmd_nds_ls)

    p = nds.add_parser("unpack", help="write header, ARM binaries, overlays and data/ to a folder")
    p.add_argument("rom")
    p.add_argument("out")
    p.set_defaults(fn=cmd_nds_unpack)

    p = nds.add_parser("pack", help="rebuild ROM with the files under DIR (data/, overlay9/, overlay7/) that differ")
    p.add_argument("rom")
    p.add_argument("dir")
    p.add_argument("out")
    p.set_defaults(fn=cmd_nds_pack)


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
    q.add_argument("--headered", metavar="OUT", help="also write a patch for SFC dumps with a 512-byte copier header")
    q.add_argument("--gap", type=int, default=6, help="equal bytes that end a record (default 6)")
    q.add_argument("--rle", action="store_true", help="write long runs of one byte as RLE records (changes the output)")
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
    q.add_argument("--planar", action="store_true", help="re-interleave planar SFC 2bpp halves to SFC order")
    q.set_defaults(fn=cmd_lzss_decode)
    q = lz.add_parser("encode")
    q.add_argument("file")
    q.add_argument("out")
    q.add_argument("--planar", action="store_true", help="split SFC 2bpp tiles into planar halves first")
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

    p = sub.add_parser("lz11", help="Nintendo LZ10/LZ11 (GBA/DS BIOS) codec")
    lz = p.add_subparsers(dest="op", required=True)
    q = lz.add_parser("decode")
    q.add_argument("file")
    q.add_argument("out")
    q.add_argument("--offset", type=_hex, default=0, help="stream start in FILE (hex)")
    q.set_defaults(fn=cmd_lz11_decode)
    q = lz.add_parser("encode")
    q.add_argument("file")
    q.add_argument("out")
    q.add_argument("--lz10", action="store_true", help="write LZ10 (type 0x10) instead of LZ11")
    q.add_argument("--vram", action="store_true", help="no distance-1 references (safe for BIOS decompression to VRAM)")
    q.set_defaults(fn=cmd_lz11_encode)

    p = sub.add_parser("xdelta", help="create or apply VCDIFF (xdelta3) patches")
    xd = p.add_subparsers(dest="op", required=True)
    q = xd.add_parser("make", help="patch from BASE to PATCHED with xdelta3, checked by decoding it")
    q.add_argument("base")
    q.add_argument("patched")
    q.add_argument("out")
    q.add_argument("--xdelta3", default="xdelta3", help="xdelta3 command (default: from PATH)")
    q.add_argument("--level", type=int, default=9, choices=range(10), metavar="0-9")
    q.set_defaults(fn=cmd_xdelta_make)
    q = xd.add_parser("apply", help="apply a patch without secondary compression")
    q.add_argument("file")
    q.add_argument("patch")
    q.add_argument("out")
    q.set_defaults(fn=cmd_xdelta_apply)

    p = sub.add_parser("linear", help="render linear (row-packed) bitmaps such as DS fonts to PNG")
    p.add_argument("file")
    p.add_argument("out")
    p.add_argument("--size", required=True, metavar="WxH")
    p.add_argument("--bpp", type=int, required=True, choices=(1, 2, 4, 8))
    p.add_argument("--order", choices=("lsb", "msb"), default="lsb", help="first pixel in the low (lsb) or high bits")
    p.add_argument("--offset", type=_hex, default=0, help="data start in FILE (hex)")
    p.add_argument("--start", type=int, default=0, help="first bitmap index")
    p.add_argument("--count", type=int)
    p.add_argument("--cols", type=int, default=16)
    p.add_argument("--scale", type=int, default=2)
    p.set_defaults(fn=cmd_linear)

    _audio_parser(sub)
    _sfc_parser(sub)
    _fc_parser(sub)
    _nds_parser(sub)
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
