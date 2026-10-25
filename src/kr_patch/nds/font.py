"""NDS bitmap fonts (NFTR, the `RTFN` files of the Nitro SDK).

Blocks read: FINF (font info), CGLP (glyph bitmaps), CWDH (widths, optional)
and CMAP (character code to glyph index; types 0, 1 and 2). Multi-byte fields
are little-endian. A glyph bitmap is cell width x cell height pixels of `bpp`
bits each, packed row by row with no padding between rows, most significant
bit first; each glyph takes `glyph_size` bytes.

Only reading; codes are whatever the font's encoding uses (`encoding` in
FINF: 0 UTF-8, 1 UTF-16, 2 Shift JIS, 3 CP1252).
"""
import struct

ENCODINGS = {0: "utf-8", 1: "utf-16", 2: "shift-jis", 3: "cp1252"}


class Font:
    """A parsed NFTR. Raises ValueError on a file that is not one or whose
    blocks run past the end."""

    def __init__(self, data):
        self.data = bytes(data)
        if self.data[:4] != b"RTFN":
            raise ValueError("not an NFTR font (no RTFN magic)")
        try:
            self._parse()
        except (struct.error, IndexError):
            raise ValueError("malformed NFTR: a block runs past the end of the file") from None

    def _parse(self):
        d = self.data
        hsize, nblocks = struct.unpack_from("<HH", d, 0x0C)
        self.blocks = {}
        o = hsize
        for _ in range(nblocks):
            tag = d[o:o + 4][::-1].decode("ascii", "replace")
            size = struct.unpack_from("<I", d, o + 4)[0]
            if size < 8 or o + size > len(d):
                raise ValueError(f"malformed NFTR: block {tag!r} at {o:#x} has size {size:#x}")
            self.blocks.setdefault(tag, []).append(o)
            o += size
        for tag in ("FINF", "CGLP", "CMAP"):
            if tag not in self.blocks:
                raise ValueError(f"malformed NFTR: no {tag} block")

        f = self.blocks["FINF"][0]
        self.line_height = d[f + 9]
        self.error_glyph = struct.unpack_from("<H", d, f + 10)[0]
        self.default_width = tuple(d[f + 12:f + 15])
        self.encoding = d[f + 15]

        g = self.blocks["CGLP"][0]
        (self.cell_w, self.cell_h, self.glyph_size, self.baseline,
         self.max_w, self.bpp, _rotation) = struct.unpack_from("<BBHBBBB", d, g + 8)
        if self.bpp not in (1, 2, 4, 8) or self.glyph_size == 0:
            raise ValueError(f"malformed NFTR: {self.bpp} bits per pixel, {self.glyph_size} bytes per glyph")
        if self.cell_w * self.cell_h * self.bpp > self.glyph_size * 8:
            raise ValueError("malformed NFTR: a glyph cell does not fit in its bytes")
        self._glyphs = g + 16
        self.count = (struct.unpack_from("<I", d, g + 4)[0] - 16) // self.glyph_size

        self.widths = {}
        for c in self.blocks.get("CWDH", []):
            first, last = struct.unpack_from("<HH", d, c + 8)
            for i in range(first, last + 1):
                p = c + 16 + 3 * (i - first)
                if p + 3 > len(d):
                    raise IndexError
                self.widths[i] = tuple(d[p:p + 3])

        self.cmap = {}
        for c in self.blocks["CMAP"]:
            first, last, kind = struct.unpack_from("<HHH", d, c + 8)
            p = c + 20
            if kind == 0:
                base = struct.unpack_from("<H", d, p)[0]
                for code in range(first, last + 1):
                    self.cmap[code] = base + code - first
            elif kind == 1:
                for code in range(first, last + 1):
                    gi = struct.unpack_from("<H", d, p + 2 * (code - first))[0]
                    if gi != 0xFFFF:
                        self.cmap[code] = gi
            elif kind == 2:
                n = struct.unpack_from("<H", d, p)[0]
                for k in range(n):
                    code, gi = struct.unpack_from("<HH", d, p + 2 + 4 * k)
                    self.cmap[code] = gi
            else:
                raise ValueError(f"malformed NFTR: CMAP type {kind} at {c:#x}")

    def glyph_bytes(self, index):
        """The raw bytes of glyph `index`."""
        if not 0 <= index < self.count:
            raise ValueError(f"glyph {index} out of range (font has {self.count})")
        o = self._glyphs + index * self.glyph_size
        return self.data[o:o + self.glyph_size]

    def glyph(self, index):
        """Glyph `index` as rows of pixel values (0 = blank, up to 2**bpp - 1)."""
        bits = int.from_bytes(self.glyph_bytes(index), "big")
        total, mask = self.glyph_size * 8, (1 << self.bpp) - 1
        rows = []
        i = 0
        for _y in range(self.cell_h):
            row = []
            for _x in range(self.cell_w):
                i += self.bpp
                row.append(bits >> (total - i) & mask)
            rows.append(row)
        return rows

    def width(self, index):
        """(left offset, glyph width, advance) of glyph `index`; FINF's
        default when CWDH does not cover it."""
        return self.widths.get(index, self.default_width)

    def code_glyph(self, code):
        """Glyph index of character `code`, or None when the font lacks it."""
        return self.cmap.get(code)


def sheet(font, codes, cols=32, scale=2):
    """A Pillow image of the glyphs of `codes` that the font has, in rows of
    `cols` cells with a 1-pixel border: ink is dark, blank pixels light and
    the borders gray."""
    from PIL import Image
    codes = [c for c in codes if c in font.cmap]
    w, h = font.cell_w + 1, font.cell_h + 1
    rows = (len(codes) + cols - 1) // cols
    img = Image.new("L", (cols * w, max(1, rows) * h), 60)
    mask = (1 << font.bpp) - 1
    for k, code in enumerate(codes):
        ox, oy = k % cols * w, k // cols * h
        for y, row in enumerate(font.glyph(font.cmap[code])):
            for x, v in enumerate(row):
                img.putpixel((ox + x, oy + y), 255 - v * 255 // mask if v else 230)
    return img.resize((img.width * scale, img.height * scale), Image.NEAREST)
