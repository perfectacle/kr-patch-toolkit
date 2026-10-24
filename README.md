# kr-patch-toolkit

English | [한국어](README.ko.md)

Game-independent tools for building and testing translation patches. Some are
platform-independent (IPS patches, an LZSS codec, file diffs, screenshot
comparison, bitmap glyph tools with macOS OCR, seamless music loops cut from
recordings); the rest are for the SNES
(Super Famicom): cartridge mappers, header checksums, a 65c816 disassembler,
tile and BG rendering, a headless libretro test runner and Lua scripts for
Mesen 2 and MesenCE.
Other platforms (NDS first) are planned and will get their own `krpatch <platform>`
commands.

It is the shared part of several Korean translation patches. Anything specific
to one game (script formats, pointer tables, RAM addresses) stays in that
game's repository and is passed in as arguments.

No ROM data is included. The tests build tiny synthetic ROM images.

## Install

Python 3.15 or newer.

```sh
pip install git+https://github.com/perfectacle/kr-patch-toolkit@v0.2.0
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
| `krpatch audio segments\|period\|loop\|seamcheck\|loudness` | song boundaries, loop period, loop files, loudness |
| `krpatch snes dis` | disassemble 65c816 code |
| `krpatch snes checksum` | check or fix the internal header checksum |
| `krpatch snes tiles` | render planar tiles |
| `krpatch snes bg`, `bgrefs` | BG layers from VRAM/CGRAM dumps |
| `krpatch snes run` | headless libretro runner |
| `krpatch snes lua` | path of the bundled Lua scripts for Mesen 2 and MesenCE |

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

### `audio`: seamless loops from recordings

For game music recorded from an emulator, e.g. with `krpatch snes run --wav`.
Input is 16-bit PCM WAV; times are in seconds unless stated otherwise.
Channels are never mixed to mono, so a voice panned in anti-phase still
counts.

```sh
krpatch audio segments rec.wav                                   # songs: start, end, length
krpatch audio period rec.wav --start 36.4 --end 250.25           # candidate periods of one song
krpatch audio loop rec.wav song.wav --start 36.4 --end 250.25 --period-range 100:115 --json song.json
krpatch audio loop rec.wav song.wav --start 36.4 --end 250.25 --period 5136108 --seam-range 40:70
krpatch audio seamcheck song.wav --source rec.wav --render check.wav
krpatch audio loudness song.wav --target -20
```

`segments` splits the recording at silence: 50 ms windows (`--window`) whose
RMS over all channels is below 30 (`--threshold`, in int16 units) for at least
0.3 s (`--min-gap`). `--gaps` prints the silent stretches instead of the songs.

`period` compares the log spectrum (2048-point FFT every 512 samples) of the
range with itself shifted by every lag of at least `--min-lag` (5 s), averaged
over channels, and prints the best lags. Give it one song's range from
`segments`: over several songs, or a song and the silence after it, long lags
that span them win. It tolerates repeats whose waveforms differ, but its
resolution is one hop (about 11 ms at 48 kHz), and a peak can be a multiple or
a fraction of the true period when the music repeats a phrase inside its loop.
Pick by ear, then pass `--range` or `loop --period-range`.

`loop` writes the song from `--start` to loopEnd plus a tail, and prints:

```json
{"loopStart": 6.651625, "loopEnd": 113.653875, "duration": 114.153875,
 "loopStartSample": 319278, "loopEndSample": 5455386, "loopLengthSample": 5136108,
 "durationSamples": 5479386, "sampleRate": 48000, "period": 5136108,
 "sourceStartSample": 1747200, "seamScore": 0.9983}
```

Positions are relative to the written file; `loopEndSample` is exclusive, so
the loop is samples `loopStartSample` to `loopEndSample - 1`, and
`loopLengthSample` is the period. `sourceStartSample` is where the file starts
in the recording.

- Period: `--period` (samples), or the best `period` lag within
  `--period-range` (or from `--min-lag` up), refined to the sample by matching
  3 s of waveform (`--refine-length`) one period later at seven places in the
  range; `periodScore` is that match.
- Seam T: where 0.5 s around T (`--window`) best matches 0.5 s around T +
  period, all channels together. First in 50 ms steps over `--seam-range`
  (default: everything in the recording that fits before `--end`), then in
  16-sample steps, then the sample within ±200 where 64 samples on both sides
  differ least. The coarse pick is the earliest position scoring within 0.003
  of the best (`--seam-delta`), since any seam inside the repeating part loops
  cleanly and an early one keeps the file short; `--seam-pick best` takes the
  best instead. `seamScore` is the match at T: close to 1 when repeats are
  nearly identical, lower (around 0.9) when voices differ slightly between
  repeats.
- Crossfade: the 60 ms before loopEnd (`--fade-ms`) fade into the 60 ms before
  T, so the jump lands in audio that already sounds like what follows T. The
  default `--fade-shape equal-gain` (sin² in, 1 − sin² out) keeps the level
  when both sides match, as they do at a good seam; `equal-power` (sin/cos) is
  up to 3 dB louder mid-fade on such audio.
- Tail: 0.5 s (`--tail`) of what follows T, i.e. what a player hears after the
  jump. It keeps a lossy encoder's padding out of the loop, so players must
  loop on `loopStart`/`loopEnd`, not on the file end. `--tail-from end` takes
  what followed loopEnd in the recording instead.
- Without `--end`, `loop` warns when `segments` finds more than one song after
  `--start`.
- `--legacy` behaves like the script these commands replace: equal-power fade,
  tail from the end, best seam, and the seam score on the channel sum. It
  reproduces loop files made with that script byte for byte.

`seamcheck` plays the intro and the loop three times, i.e. two jumps, the way
a player would (`--render` writes it), and measures spectral flux, i.e. how
sharply the sound rises, at the first jump. With `--source` it also measures
the uncut recording over the same frames, where the song simply continues past
loopEnd (the file's start comes from `sourceStartSample` in the JSON, or
`--source-start`); both use the same frame grid, so an exact loop measures the
same as its source. It prints JSON and exits 1 when the seam is above 1.25
times (`--ratio`) that continuation, or, without a source, above 1.25 times the
song's 99th percentile. A loop that starts on a drum hit is loud at the seam
either way, so prefer `--source`.

`loudness` prints integrated loudness by ITU-R BS.1770-4 / EBU R128
(K-weighting, 400 ms blocks, -70 LUFS absolute and -10 LU relative gates) for
mono or stereo, and the sample peak; `--target LUFS` adds the gain that reaches
it. Silence prints `null` for both and no gain. True peak is not measured: use
`ffmpeg -i song.wav -af ebur128=peak=true -f null -`.

Unreadable or truncated WAV files are an error (exit 2).

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
- `--wav OUT.wav`: record the core's audio output, 16-bit stereo at the sample
  rate the core reports (bsnes 48000 Hz; snes9x reports 32040.5 Hz, which the
  WAV header rounds to an integer). Samples are written as they arrive, so long
  recordings do not stay in memory.

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

`examples/snes/run_all.sh` runs every scenario on every core (and on Mesen 2
with `MESEN`, MesenCE with `MESENCE`) and collects one result line per run.

### `snes lua`: Mesen 2 and MesenCE scripts

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
| `probe/*.lua` | `watch`, `peek`, `wtrace`, `wdump`, `wrange`, `swatch`, `cgram`, `trace`, `regs`, `ppu`, `apuports`, `voices`, `calls`; each lists its env variables in its first lines and runs `boot.lua` for input |
| `probe/apuports.lua` | writes to the APU ports `$2140-$2143` that change a value, with frame and PC: song and sound effect commands; `APUPORTS="1,3"` logs only those ports |
| `probe/voices.lua` | envelope level of the eight S-DSP voices every `VSTEP` frames |
| `probe/calls.lua` | each call of the `CALLS` addresses with A, X, Y and the return address |

All write their output files to `SHOT_DIR`. Use `WATCH_WRAM`, not `WATCH`, for
`script.lua`: zsh treats `WATCH` and `WATCHFMT` as its own parameters.

Mesen 2 ended at 2.1.1, and its repository (SourMesen/Mesen2) was archived in
June 2026. MesenCE (nesdev-org/MesenCE) continues it; its executable is still
`Mesen`, so the command above works with either. MesenCE keeps its data in a
`MesenCE` folder (`~/Library/Application Support/MesenCE` on macOS) when that
folder exists and falls back to the `Mesen2` folder otherwise; saves are in
`Saves` inside it. Every script here was run on a test ROM with Mesen 2.1.1
and MesenCE 2.2.1 with power-on RAM set to zeros
(`--snes.ramPowerOnState=AllZeros`): screenshots, memory dumps and logs were
the same in both, apart from the run-to-run differences each version shows on
its own. Only the save state files are not byte for byte the same.

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

from kr_patch.audio import loudness, wav

x, rate = wav.read("song.wav")          # int16, shape (frames, channels)
print(loudness.integrated(x / 32768, rate))
```

## Planned

- NDS support under `kr_patch.nds` and `krpatch nds ...`.
- `game.toml`: game projects describe their mapper, watched RAM, emulator
  matrix and scenarios in one file, so commands need fewer arguments.

## Development

```sh
uv sync --locked
uv run pytest
uv run ruff check .
```

`uv.lock` pins the development and CI environment and only takes releases at
least seven days old. Coding agents start from [AGENTS.md](AGENTS.md).

## License

MIT. See [LICENSE](LICENSE).
