# sfc-kr-toolkit

Game-independent tools for building and testing SNES (Super Famicom) translation
patches: cartridge mappers, header checksums, IPS patches, a 65c816
disassembler, an LZSS codec, tile and BG rendering, a headless libretro test
runner, screenshot comparison and Mesen 2 Lua probes.

It is the shared part of several Korean translation patches. Anything specific
to one game (script formats, pointer tables, hard-coded RAM addresses) stays in
that game's repository and is passed in as arguments.

No ROM data is included. The tests build tiny synthetic ROM images.

## Install

Python 3.15 or newer.

```sh
pip install git+https://github.com/perfectacle/sfc-kr-toolkit@v0.1.0
```

This installs the `sfckr` command and the `sfc_kr` package. Pin the tag in a
game project (`requirements.txt` or `pyproject.toml`) so its build output does
not change when the toolkit does.

## Commands

Run `sfckr <command> -h` for every option. Addresses and offsets are hex unless
stated otherwise.

### `dis`: disassemble 65c816 code

```sh
sfckr dis game.sfc 808000 40              # 40 instructions from $80:8000
sfckr dis game.sfc C08000 --mapper sa1    # lorom | hirom | exhirom | sa1 | auto (default)
sfckr dis game.sfc 808000 --m16 --x16     # start with 16-bit A and X/Y
```

`REP`/`SEP` update the register widths as decoding goes on. `auto` reads the
internal header to pick the mapper; a 512-byte copier header is skipped.

### `ips`: create and apply IPS patches

```sh
sfckr ips make original.sfc patched.sfc out.ips --headered out-headered.ips
sfckr ips apply original.sfc out.ips result.sfc
```

`make` checks that each patch reproduces the patched ROM before writing it.
`--headered` also writes a patch for dumps with a 512-byte copier header.
`--gap N` sets how many equal bytes end a record (default 6). Patches made
with a different gap are equally valid but not byte-identical, so keep the
value a project has already shipped with.

### `checksum`: check or fix the header checksum

```sh
sfckr checksum game.sfc          # prints mapper, title, stored and computed values; exit 1 if wrong
sfckr checksum game.sfc --fix    # rewrite complement and checksum in place
```

Non-power-of-two sizes are summed the way the cartridge mirrors them.

### `diff`: byte ranges where two files differ

```sh
sfckr diff a.sfc b.sfc --gap 16
```

### `tiles`: render planar tiles

```sh
sfckr tiles game.sfc 1C0000 2000 font.png --bpp 2
sfckr tiles game.sfc 1C0000 2000 font.png --bpp 2 --rows 12 --stride 20   # 8x12 glyphs in 0x20-byte slots
sfckr tiles vram.bin 4000 2000 vram.png --bpp 2 --tall                    # 8x16 glyphs from tile pairs
```

START and LENGTH are byte offsets into any file (ROM, VRAM dump, decompressed data).

### `bg`, `bgrefs`: BG layers from VRAM/CGRAM dumps

```sh
sfckr bg vram.bin cgram.bin 0 0x1000 4 bg1.png             # tilemap and CHR word addresses, bpp
sfckr bgrefs vram.bin --layer 0:4096:4 --layer 2048:12288:4 --layer 3072:20480:2 --range 6000-7FFF
```

`bgrefs` reports which part of a VRAM range each layer's tilemap uses, for
finding free VRAM for new glyphs.

### `lz`: LZSS codec

The format: a u16 output size, then groups of eight items led by a flag byte
(LSB first); 1 = literal byte, 0 = u16 word with length `(w & 0xF) + 3` and
distance `w >> 4`. Positions before the start read as zero.

```sh
sfckr lz decode game.sfc 0A8000 font.bin [--planar]
sfckr lz encode font.bin font.lz [--planar]
```

`--planar` converts 2bpp tiles stored as two planar halves to and from SNES order.

### `run`: headless libretro runner

```sh
sfckr run cores/snes9x_libretro.dylib game.sfc out/ s_new.txt [save.srm] --watch 7E0052:3
```

Plays an input script and writes `f<frame>.png` screenshots, `end.png`,
dumps, and `wram.log` (frame and watched WRAM values, one line per change) to
`out/`. Prints `OK <frames>`, or `LOAD FAILED` with exit status 3.

- `--watch ADDR[:SIZE]` (repeatable): WRAM offset or `$7E`/`$7F` address and size in bytes.
- `--watch-fmt SPEC`: Python format spec for watched values (default `0<2*SIZE>X`).
- `--var KEY=VALUE` or env `LRVARS="k=v,k=v"`: core options. `LRLOG=1` or `-v`: core log.
- `save.srm` is copied to the save RAM after loading and again after the first
  frame, and written to `out/<rom name>.srm` for cores that read it from disk.

Script format, one command per line, frames counted from power-on:

```
500 start 4             hold Start for 4 frames from frame 500
800 a+b 2               hold A and B
900 tap a 40 2000       4-frame A presses every 40 frames until frame 2000
1000 shot               screenshot f01000.png
1000 dump               wram_1000.bin and sram_1000.bin
1100 poke 029C 0123     16-bit WRAM write after frame 1100
3000 end                stop after frame 3000
```

Buttons: `a b x y l r start select up down left right`. Lines starting with `#`
are comments. On cores without a WRAM pointer (bsnes, Supafaust) a poke is
applied as a Pro Action Replay cheat for `--cheat-hold` frames (default 40).

`examples/run_all.sh` runs every scenario on every core (and Mesen 2) and
collects one result line per run.

### `shotcmp`, `contact`: screenshots as text

```sh
sfckr shotcmp out/new-snes9x-v11 ref/new-snes9x-v11          # directories, matched by file name
sfckr shotcmp actual.png ref.png --box 0,160,256,64 --tol 8 --crop diff.png
sfckr shotcmp actual.png --box 0,160,256,64 --crop crop.png  # crop only
sfckr contact 'out/new-*/end.png' sheet.png --cols 8
```

`shotcmp` prints `same` or the number of differing pixels and their bounding
box, and exits 1 if any pair differs.

### `glyph`, `ocr`: bitmap glyphs

Glyphs are stored as JSON `{"가": ["0110...", ...]}`.

```sh
sfckr glyph show glyphs.json 각략
sfckr glyph make glyphs.json 갹 략 'ini=각:0-6,0-5'   # base glyph, then rows,cols copied from another glyph
sfckr glyph set glyphs.json 갹 '.##.' '#..#'
sfckr ocr glyphs.json ocr-rows/ --per-row 10 --fix-mo  # macOS only
```

`ocr` draws the glyphs in rows, reads each row with the macOS Vision framework
and prints `key<TAB>char` (`?` when the row length does not match). The Vision
helper (`ocr.swift`) is compiled with `xcrun swiftc` on first use into
`~/.cache/sfc-kr-toolkit`. `--fix-mo` re-decides ㅁ/ㅇ from the glyph corners; it
suits pixel fonts that draw ㅁ with filled corners and ㅇ without, and can turn
correct results wrong on smooth fonts.

### `lua`: Mesen 2 scripts

```sh
sfckr lua    # prints the directory of the bundled Lua scripts
```

Run them with `Mesen --testrunner rom.sfc <script>` and `LIBDIR=$(sfckr lua)`:

| Script | Does |
| --- | --- |
| `lib.lua` | shared helpers: screenshots, savestates, memory dumps, input |
| `boot.lua` | power on, periodic taps (`TAP`, `PERIOD`, `TAPUNTIL`), presses (`SEQ="start@400:3"`), screenshots every `EVERY` frames until `MAXF` |
| `script.lua` | plays an `sfckr run` script (`SCRIPT`, `SRM`, `WATCH_WRAM`, `WATCH_FMT`) |
| `seq.lua` | replays `SEQ="btn:frames,wait:frames"` from a savestate with `POKE`/`WATCH` |
| `poke_state.lua` | loads `STATE`, writes `POKE` once, saves to `OUT` |
| `dumpsrm.lua` | writes the save RAM of a savestate to `save.srm` |
| `probe/*.lua` | `watch`, `peek`, `wtrace`, `wdump`, `wrange`, `swatch`, `cgram`, `trace`, `regs`, `ppu`; each lists its env variables in its first lines and runs `boot.lua` for input |

All write their output files to `SHOT_DIR`. Use `WATCH_WRAM`, not `WATCH`, for
`script.lua`: zsh treats `WATCH` and `WATCHFMT` as its own parameters.

## Python API

```python
from sfc_kr.rom import header, ips
from sfc_kr.disasm import disasm

rom = open("game.sfc", "rb").read()
mp = header.detect(rom)                 # LoROM / HiROM / ExHiROM / SA1
print(disasm(rom, 0x808000, 20, mapper=mp))
fixed, csum = header.fix(rom, mp)
patch = ips.make(rom, fixed)
```

## Planned: `game.toml`

Game projects will describe their mapper, watched RAM, emulator matrix and
scenarios in a `game.toml`, so `sfckr` commands need fewer arguments. Not
implemented yet.

## Development

```sh
uv venv -p 3.15.0 .venv && uv pip install -p .venv -e '.[test]'
.venv/bin/python -m pytest
```

## License

MIT. See [LICENSE](LICENSE).

## 한국어 요약

슈퍼패미컴 한글 패치를 만들고 검증할 때 게임마다 복사해 쓰던 공통 도구를 한
패키지로 모았습니다. 매퍼 주소 변환(LoROM·HiROM·ExHiROM·SA-1), 헤더
체크섬, IPS 생성·적용, 65c816 디스어셈블러, LZSS 압축, 타일·BG 렌더링,
libretro 헤드리스 실행기, 스크린샷 비교, 글리프 편집과 macOS Vision OCR,
Mesen 2 Lua 스크립트가 들어 있습니다.

- 설치: `pip install git+https://github.com/perfectacle/sfc-kr-toolkit@v0.1.0`
- 명령: `sfckr dis | ips | checksum | diff | tiles | bg | bgrefs | lz | run | shotcmp | contact | glyph | ocr | lua`
- 게임마다 다른 값(주소, 감시할 RAM 등)은 인자로 넘깁니다. 게임 저장소의 `game.toml` 로 받는 방식은 계획 중입니다.
- 롬 데이터와 대본은 들어 있지 않습니다. 테스트는 직접 만든 작은 합성 롬으로 돌립니다.
