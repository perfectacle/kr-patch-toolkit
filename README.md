# kr-patch-toolkit

English | [한국어](README.ko.md)

Game-independent tools for building and testing translation patches. Some are
platform-independent (IPS patches, an LZSS codec, file diffs, screenshot
comparison, bitmap glyph tools with macOS OCR); the rest are for the SNES
(Super Famicom): cartridge mappers, header checksums, a 65c816 disassembler,
tile and BG rendering, a headless libretro test runner and Mesen 2 Lua scripts.
Other platforms (NDS first) are planned and will get their own `krpatch <platform>`
commands.

It is the shared part of several Korean translation patches. Anything specific
to one game (script formats, pointer tables, RAM addresses) stays in that
game's repository and is passed in as arguments.

No ROM data is included. The tests build tiny synthetic ROM images.

## Install

Python 3.15 or newer.

```sh
pip install git+https://github.com/perfectacle/kr-patch-toolkit@v0.1.0
```

This installs the `krpatch` command and the `kr_patch` package. Pin the tag in
a game project (`requirements.txt` or `pyproject.toml`) so its build output does
not change when the toolkit does.

## Commands

Run `krpatch <command> -h` (or `krpatch snes <command> -h`) for every option.
Addresses and offsets are hex unless stated otherwise.

| Command | Does |
| --- | --- |
| `krpatch ips make\|apply` | create and apply IPS patches |
| `krpatch lzss decode\|encode` | LZSS codec |
| `krpatch diff` | byte ranges where two files differ |
| `krpatch shotcmp` | compare screenshots as text |
| `krpatch contact` | contact sheet of screenshots |
| `krpatch glyph show\|make\|set` | bitmap glyphs in a JSON store |
| `krpatch ocr` | read glyphs with macOS Vision |
| `krpatch snes dis` | disassemble 65c816 code |
| `krpatch snes checksum` | check or fix the internal header checksum |
| `krpatch snes tiles` | render planar tiles |
| `krpatch snes bg`, `bgrefs` | BG layers from VRAM/CGRAM dumps |
| `krpatch snes run` | headless libretro runner |
| `krpatch snes lua` | path of the bundled Mesen 2 Lua scripts |

### `ips`: create and apply IPS patches

```sh
krpatch ips make original.sfc patched.sfc out.ips --headered out-headered.ips
krpatch ips apply original.sfc out.ips result.sfc
```

`make` checks that each patch reproduces the patched file before writing it.
`--headered` also writes a patch for SNES dumps with a 512-byte copier header.
`--gap N` sets how many equal bytes end a record (default 6). Patches made
with a different gap are equally valid but not byte-identical, so keep the
value a project has already shipped with. Files must stay below 16 MB, the
limit of IPS's 24-bit offsets.

### `lzss`: LZSS codec

The format: a u16 output size, then groups of eight items led by a flag byte
(LSB first); 1 = literal byte, 0 = u16 word with length `(w & 0xF) + 3` and
distance `w >> 4`. Positions before the start read as zero.

```sh
krpatch lzss decode game.sfc 0A8000 font.bin [--planar]
krpatch lzss encode font.bin font.lz [--planar]
```

`--planar` converts SNES 2bpp tiles stored as two planar halves to and from
SNES order. A truncated stream or a copy with distance 0 is an error.

### `diff`: byte ranges where two files differ

```sh
krpatch diff a.sfc b.sfc --gap 16
```

### `shotcmp`, `contact`: screenshots as text

```sh
krpatch shotcmp out/new-snes9x-v1 ref/new-snes9x-v1            # directories, matched by file name
krpatch shotcmp actual.png ref.png --box 0,160,256,64 --tol 8 --crop diff.png
krpatch shotcmp actual.png --box 0,160,256,64 --crop crop.png  # crop only
krpatch contact 'out/new-*/end.png' sheet.png --cols 8
```

`shotcmp` prints `same` or the number of differing pixels and their bounding
box, and exits 1 if any pair differs. A pixel differs when any colour channel
differs by more than `--tol`. With directories, a PNG present on only one side
counts as a difference, and two directories without PNGs are an error.

### `glyph`, `ocr`: bitmap glyphs

Glyphs are stored as JSON `{"가": ["0110...", ...]}`.

```sh
krpatch glyph show glyphs.json 각략
krpatch glyph make glyphs.json 갹 략 'ini=각:0-6,0-5'   # base glyph, then rows,cols copied from another glyph
krpatch glyph set glyphs.json 갹 '.##.' '#..#'
krpatch ocr glyphs.json ocr-rows/ --per-row 10 --fix-mo  # macOS only
```

`glyph show` exits 1 and names the characters that are not in the store.

`ocr` draws the glyphs in rows, reads each row with the macOS Vision framework
and prints `key<TAB>char` (`?` when the row length does not match). The Vision
helper (`ocr.swift`) is compiled with `xcrun swiftc` on first use into
`~/.cache/kr-patch-toolkit`. `--fix-mo` re-decides ㅁ/ㅇ from the glyph corners;
it suits pixel fonts that draw ㅁ with filled corners and ㅇ without, and can
turn correct results wrong on smooth fonts.

## SNES commands

### `snes dis`: disassemble 65c816 code

```sh
krpatch snes dis game.sfc 808000 40              # 40 instructions from $80:8000
krpatch snes dis game.sfc C08000 --mapper sa1    # lorom | hirom | exhirom | sa1 | auto (default)
krpatch snes dis game.sfc 808000 --m16 --x16     # start with 16-bit A and X/Y
```

`REP`/`SEP` update the register widths as decoding goes on. Block moves are
printed in assembler order, `MVN src,dst`. `auto` reads the internal header to
pick the mapper; a 512-byte copier header is skipped. SA-1 uses the power-on
Super MMC blocks (0-3); `kr_patch.snes.mapper.SA1(blocks=...)` takes others.

### `snes checksum`: check or fix the header checksum

```sh
krpatch snes checksum game.sfc          # prints mapper, title, stored and computed values; exit 1 if wrong
krpatch snes checksum game.sfc --fix    # rewrite complement and checksum in place
```

`--fix` refuses when no internal header is recognisable, unless `--mapper` is
given. Non-power-of-two sizes are summed the way the cartridge mirrors them.

### `snes tiles`: render planar tiles

```sh
krpatch snes tiles game.sfc 1C0000 2000 font.png --bpp 2
krpatch snes tiles game.sfc 1C0000 2000 font.png --bpp 2 --rows 12 --stride 20   # 8x12 glyphs in 0x20-byte slots
krpatch snes tiles vram.bin 4000 2000 vram.png --bpp 2 --tall                    # 8x16 glyphs from tile pairs
```

START and LENGTH are byte offsets into any file (ROM, VRAM dump, decompressed data).

### `snes bg`, `snes bgrefs`: BG layers from VRAM/CGRAM dumps

```sh
krpatch snes bg vram.bin cgram.bin 0 0x1000 4 bg1.png             # tilemap and CHR word addresses, bpp
krpatch snes bgrefs vram.bin --layer 0:0x1000:4 --layer 0x400:0x2000:4 --layer 0x800:0x3000:2 --range 6000-7FFF
```

`bgrefs` reports which part of a VRAM range each layer's tilemap uses, for
finding free VRAM for new glyphs.

### `snes run`: headless libretro runner

```sh
krpatch snes run cores/snes9x_libretro.dylib game.sfc out/ s_new.txt [save.srm] --watch 7E0010:2
```

Plays an input script and writes `f<frame>.png` screenshots, `end.png`,
dumps, and `wram.log` (frame and watched WRAM values, one line per change) to
`out/`. Prints `OK <frames>`. If the core cannot be loaded (missing file,
missing `retro_*` symbols, ROM rejected) it prints `LOAD FAILED: ...` to stderr
and exits with status 3. Run one script per process: cores keep global state.

- `--watch ADDR[:SIZE]` (repeatable): WRAM offset or `$7E`/`$7F` address and size, 1-4 bytes.
- `--watch-fmt SPEC`: Python format spec for watched values (default `0<2*SIZE>X`).
- `--var KEY=VALUE` or env `LRVARS="k=v,k=v"`: core options. `LRLOG=1` or `-v`:
  core log (the core's format strings are printed without their arguments).
- `save.srm` is copied to the save RAM after loading and again after the first
  frame, and written to `out/<rom name>.srm` for cores that read it from disk.

Script format, one command per line, frames counted from power-on:

```
500 start 4             hold Start for 4 frames from frame 500
800 a+b 2               hold A and B
900 tap a 40 2000       4-frame A presses every 40 frames until frame 2000
1000 shot               screenshot f01000.png
1000 dump               wram_1000.bin and sram_1000.bin
1100 poke 0010 1234     16-bit WRAM write after frame 1100
3000 end                stop after frame 3000
```

Buttons (any case): `a b x y l r start select up down left right`. Lines
starting with `#` are comments. `end` is required, and a command after the end
frame is an error. Pokes and watches must lie inside the 128 KB of WRAM (and
inside what the core exposes). On cores without a WRAM pointer (bsnes,
Supafaust) each poke is applied as Pro Action Replay cheats for `--cheat-hold`
frames (default 40); overlapping pokes get their own cheat slots.

`examples/snes/run_all.sh` runs every scenario on every core (and Mesen 2) and
collects one result line per run.

### `snes lua`: Mesen 2 scripts

```sh
krpatch snes lua    # prints the directory of the bundled Lua scripts
```

Run them with `Mesen --testrunner rom.sfc <script>` and `LIBDIR=$(krpatch snes lua)`:

| Script | Does |
| --- | --- |
| `lib.lua` | shared helpers: screenshots, savestates, memory dumps, input |
| `boot.lua` | power on, periodic taps (`TAP`, `PERIOD`, `TAPUNTIL`), presses (`SEQ="start@400:3"`), screenshots every `EVERY` frames until `MAXF` |
| `script.lua` | plays a `krpatch snes run` script (`SCRIPT`, `SRM`, `WATCH_WRAM`, `WATCH_FMT`) with the same parsing rules |
| `seq.lua` | replays `SEQ="btn:frames,wait:frames"` from a savestate with `POKE`/`WATCH` |
| `poke_state.lua` | loads `STATE`, writes `POKE` once, saves to `OUT` |
| `dumpsrm.lua` | writes the save RAM of a savestate to `save.srm` |
| `probe/*.lua` | `watch`, `peek`, `wtrace`, `wdump`, `wrange`, `swatch`, `cgram`, `trace`, `regs`, `ppu`; each lists its env variables in its first lines and runs `boot.lua` for input |

All write their output files to `SHOT_DIR`. Use `WATCH_WRAM`, not `WATCH`, for
`script.lua`: zsh treats `WATCH` and `WATCHFMT` as its own parameters.

## Python API

```python
from kr_patch import ips
from kr_patch.snes import header
from kr_patch.snes.dis65816 import disasm

rom = open("game.sfc", "rb").read()
mp = header.detect(rom)                 # LoROM / HiROM / ExHiROM / SA1
print(disasm(rom, 0x808000, 20, mapper=mp))
fixed, csum = header.fix(rom, mp)
patch = ips.make(rom, fixed)
```

## Planned

- NDS support under `kr_patch.nds` and `krpatch nds ...`.
- `game.toml`: game projects describe their mapper, watched RAM, emulator
  matrix and scenarios in one file, so commands need fewer arguments.

## Development

```sh
uv venv -p 3.15.0 .venv && uv pip install -p .venv -e '.[test]'
.venv/bin/python -m pytest
```

## License

MIT. See [LICENSE](LICENSE).
