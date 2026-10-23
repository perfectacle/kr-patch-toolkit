# Changelog

English | [한국어](CHANGELOG.ko.md)

## Unreleased

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
