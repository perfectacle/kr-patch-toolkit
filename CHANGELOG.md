# Changelog

## Unreleased

## 0.1.0

First release. Requires Python 3.15.

- `sfc_kr.rom`: LoROM, HiROM, ExHiROM and SA-1 mappers; header detection,
  checksum check and fix (with mirroring for non-power-of-two sizes); copier
  header handling; IPS make/apply with optional headered output and a
  configurable record gap; byte-range diff.
- `sfc_kr.disasm`: 65c816 disassembler with an injected mapper.
- `sfc_kr.codec.lzss`: LZSS codec (12-bit distance, 4-bit length) and planar
  2bpp tile conversion.
- `sfc_kr.gfx`: 1/2/4/8bpp tile decode/encode and sheets, BG layer rendering
  from VRAM/CGRAM dumps, tilemap VRAM references.
- `sfc_kr.font`: JSON glyph store and rectangle transplant, Hangul helpers,
  macOS Vision OCR with ㅁ/ㅇ correction.
- `sfc_kr.harness`: headless libretro runner (press, tap, shot, dump, poke,
  end; watched WRAM addresses as options; cheat fallback for cores without a
  WRAM pointer), screenshot comparison and contact sheets.
- `lua/`: Mesen 2 helpers, script replay compatible with `sfckr run`, and probes.
- `sfckr` command-line interface.
