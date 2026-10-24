# Changelog

English | [한국어](CHANGELOG.ko.md)

## Unreleased

## 0.4.0

- **Breaking:** the Super Famicom tools are now called SFC everywhere. The
  `krpatch snes …` subcommand is `krpatch sfc …` (`dis`, `checksum`, `tiles`,
  `bg`, `bgrefs`, `run`, `lua`); the old name is not kept as an alias. The
  package `kr_patch.snes` is `kr_patch.sfc` (the Lua scripts are under
  `kr_patch/sfc/lua/`), `tiles.planar_to_snes`/`snes_to_planar` are
  `planar_to_sfc`/`sfc_to_planar`, and `examples/snes/` is `examples/sfc/`.
  Command output is unchanged.

## 0.3.0

- NDS: `krpatch nds info|ls|unpack|pack` and `kr_patch.nds.rom` read a DS ROM's
  header, name table, FAT and overlay tables, unpack the file system to a
  folder and rebuild a ROM with replaced files (in place when they fit, moved
  to the end otherwise; FAT, used size, device capacity and header CRC
  updated).
- `krpatch lz11 decode|encode` (`kr_patch.lz11`): Nintendo LZ10/LZ11 codec;
  `--vram` avoids distance-1 references for BIOS decompression to VRAM.
- `krpatch xdelta make|apply` (`kr_patch.vcdiff`): VCDIFF patches. `make` runs
  `xdelta3` without secondary compression or file names in the header;
  `apply` is a pure-Python decoder that checks each window's Adler-32.
- `krpatch linear` (`kr_patch.linear`): render linear 1/2/4/8bpp bitmaps with
  either pixel order in a byte.
- CI installs `xdelta3` so the `xdelta make` test runs.
- `examples/snes/run_all.sh`: `MESENCE` (save folder `MESENCE_SAVES`) also runs
  every scenario on MesenCE, the successor of the archived Mesen 2. `MESEN`
  runs Mesen 2 as before.
- The bundled Lua scripts (`krpatch snes lua`) were checked on Mesen 2.1.1 and
  MesenCE 2.2.1 and work unchanged on both.

## 0.2.0

Tools for recorded game music. Requires numpy 2.5.2 or newer.

- `audio` (`krpatch audio ...`), never mixing channels to mono:
  - `segments`: song boundaries from silence.
  - `period`: candidate loop periods by spectral self-similarity of one song.
  - `loop`: loop files with a sample-exact period and seam (earliest good
    seam by default), an equal-gain crossfade and a tail taken from after the
    seam; JSON output. `--legacy` reproduces files from the earlier
    `make_loop.py` script byte for byte.
  - `seamcheck`: spectral flux at the seam against the uncut recording on the
    same frame grid, or against the song's 99th percentile.
  - `loudness`: BS.1770 / EBU R128 integrated loudness of mono or stereo,
    `null` for silence.
  - WAV I/O uses the stdlib `wave`; unreadable or truncated files are errors.
- `snes run --wav`: record the core's audio as 16-bit stereo WAV at the core's
  sample rate, streamed to disk. Without the option nothing changes.
- `lua/probe/`: APU port writes (`apuports.lua`, `APUPORTS` port filter),
  S-DSP voice envelopes (`voices.lua`), and calls with their return address
  (`calls.lua`).
- The sdist includes the Korean README and changelog.

## 0.1.0

First release. Requires Python 3.15.

Platform-independent (`kr_patch`):

- `ips`: make/apply, RLE records and the truncation extension, optional
  output for 512-byte copier-headered dumps, configurable record gap.
- `lzss`: LZSS codec (12-bit distance, 4-bit length).
- `diff`: byte ranges where two files differ.
- `shots`: screenshot comparison (per-channel tolerance, crop, directory
  mode) and contact sheets.
- `glyph`: JSON glyph store with rectangle transplant, Hangul helpers, macOS
  Vision OCR with an optional ㅁ/ㅇ correction for pixel fonts.

SNES (`kr_patch.snes`):

- `mapper`: LoROM, HiROM, ExHiROM and SA-1 (Super MMC block registers).
- `header`: internal header detection, checksum check and fix (mirroring for
  non-power-of-two sizes), copier header handling.
- `dis65816`: 65c816 disassembler with an injected mapper.
- `tiles`, `bg`: 1/2/4/8bpp tiles, planar 2bpp conversion, BG layer rendering
  from VRAM/CGRAM dumps, tilemap VRAM references.
- `libretro`, `script`: headless libretro runner and its input script format
  (press, tap, shot, dump, poke, end; watched WRAM values; cheat fallback for
  cores without a WRAM pointer).
- `lua/`: Mesen 2 helpers, a script player that follows the same rules as the
  Python parser, and probes.

`krpatch` command-line interface with `krpatch snes ...` for SNES commands.
