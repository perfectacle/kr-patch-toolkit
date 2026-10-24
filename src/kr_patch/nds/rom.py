"""NDS ROM: header, file name table (FNT), file allocation table (FAT), overlay
tables, and rebuilding a ROM with replaced files.

Rebuilding keeps the layout of the base ROM: a replaced file that fits in its
old slot (up to the start of the next region) stays where it was, the rest of
the slot is filled with 0xFF when the byte after the slot is 0xFF and with 0x00
otherwise; a file that does not fit, or whose bytes another FAT entry shares,
moves to the end, aligned to ALIGN, after any non-padding data that follows
the last file (such as a Download Play signature). Only the FAT, the used-size field (when the
files end later than before), the device capacity and the header CRC change in
the header area. The same base and the same replacements always give the same
bytes, and no replacements give the base back.
"""
import bisect
import struct
from pathlib import Path

ALIGN = 0x200
BANNER_SIZES = {1: 0x840, 2: 0x940, 3: 0xA40, 0x103: 0x23C0}


def crc16(data, crc=0xFFFF):
    """CRC-16/MODBUS, as used for the header (0x000-0x15D) and the logo."""
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def _u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


class Rom:
    def __init__(self, data):
        self.data = bytes(data)
        d = self.data
        if len(d) < 0x200:
            raise ValueError("too small for an NDS header")
        try:
            self._parse()
        except (struct.error, IndexError):
            raise ValueError("malformed NDS ROM: a table points past the end of the file") from None

    def _parse(self):
        d = self.data
        self.title = d[0:12].rstrip(b"\0").decode("ascii", "replace")
        self.code = d[12:16].decode("ascii", "replace")
        self.arm9 = (_u32(d, 0x20), _u32(d, 0x2C))
        self.arm7 = (_u32(d, 0x30), _u32(d, 0x3C))
        self.fnt = (_u32(d, 0x40), _u32(d, 0x44))
        self.fat = (_u32(d, 0x48), _u32(d, 0x4C))
        self.ovt9 = (_u32(d, 0x50), _u32(d, 0x54))
        self.ovt7 = (_u32(d, 0x58), _u32(d, 0x5C))
        self.banner = _u32(d, 0x68)
        self.used = _u32(d, 0x80)
        self.entries = [struct.unpack_from("<II", d, self.fat[0] + i * 8) for i in range(self.fat[1] // 8)]
        self.names = self._names()
        self.overlays = {"9": self._ovt(self.ovt9), "7": self._ovt(self.ovt7)}

    def _ovt(self, table):
        off, size = table
        return [struct.unpack_from("<8I", self.data, off + i * 32) for i in range(size // 32)]

    def _names(self):
        base, d, names = self.fnt[0], self.data, {}
        if not self.fnt[1]:
            return names

        def walk(dir_id, prefix, depth):
            if depth > 64:
                raise ValueError("FNT directories nest too deep")
            sub_off, fid = struct.unpack_from("<IH", d, base + (dir_id & 0xFFF) * 8)
            p = base + sub_off
            while (t := d[p]) != 0:
                n = t & 0x7F
                name = d[p + 1:p + 1 + n].decode("shift_jis", "replace")
                p += 1 + n
                # names become paths in unpack, so nothing may climb out of the folder
                if name in ("", ".", "..") or "/" in name or "\\" in name:
                    raise ValueError(f"FNT name {name!r} is not a plain file name")
                if t & 0x80:
                    sub = struct.unpack_from("<H", d, p)[0]; p += 2
                    walk(sub, prefix + name + "/", depth + 1)
                else:
                    names[fid] = prefix + name
                    fid += 1

        walk(0xF000, "", 0)
        return names

    def file(self, fid):
        s, e = self.entries[fid]
        return self.data[s:e]

    def find(self, path):
        for fid, name in self.names.items():
            if name == path:
                return fid
        raise ValueError(f"no file {path!r} in the ROM")

    def overlay_files(self):
        """{'overlay9/overlay_0000.bin': file id, ...}"""
        return {f"overlay{cpu}/overlay_{ov[0]:04d}.bin": ov[6] for cpu, ovs in self.overlays.items() for ov in ovs}

    def banner_size(self):
        if not self.banner:
            return 0
        return BANNER_SIZES.get(struct.unpack_from("<H", self.data, self.banner)[0], 0x840)

    def regions(self):
        """Start offsets of everything in the ROM image, for slot sizes."""
        starts = [s for s, e in self.entries if e > s]
        starts += [self.arm9[0], self.arm7[0], self.fnt[0], self.fat[0]]
        starts += [t[0] for t in (self.ovt9, self.ovt7) if t[1]]
        if self.banner:
            starts.append(self.banner)
        return sorted(set(starts))


def unpack(rom, out):
    """Write every part of the ROM under `out`: header.bin, arm9.bin, arm7.bin,
    y9.bin and y7.bin (overlay tables), banner.bin, overlay9/ and overlay7/, and
    the file system under data/. Returns the number of files written."""
    out = Path(out)
    d = rom.data
    parts = {"header.bin": d[:0x200], "arm9.bin": d[rom.arm9[0]:sum(rom.arm9)], "arm7.bin": d[rom.arm7[0]:sum(rom.arm7)],
             "y9.bin": d[rom.ovt9[0]:sum(rom.ovt9)], "y7.bin": d[rom.ovt7[0]:sum(rom.ovt7)]}
    if rom.banner:
        parts["banner.bin"] = d[rom.banner:rom.banner + rom.banner_size()]
    for path, fid in rom.overlay_files().items():
        parts[path] = rom.file(fid)
    for fid, name in rom.names.items():
        parts["data/" + name] = rom.file(fid)
    seen = {}
    for path in parts:
        if path.lower() in seen:
            raise ValueError(f"{seen[path.lower()]} and {path} differ only in case; they would overwrite each other "
                             "on a case-insensitive file system")
        seen[path.lower()] = path
    for path, blob in parts.items():
        p = out / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(blob)
    return len(parts)


def rebuild(rom, files):
    """New ROM bytes with `files` ({file id: bytes}) replaced. Overlays may only
    be replaced by data of the same size, since the overlay tables are kept."""
    if rom.data[0x12] & 2:
        raise ValueError("DSi-enhanced ROMs (unit code bit 1) are not supported: the TWL area is not tracked")
    out = bytearray(rom.data)
    entries = list(rom.entries)
    regions = rom.regions()
    end = max([rom.used] + [e for s, e in entries])
    # data after the last file that is not padding (e.g. the Download Play signature) stays put
    tail = rom.data[end:].rstrip(b"\xFF\x00")
    if tail:
        bisect.insort(regions, end)
        end += len(tail)
    overlay_ids = set(rom.overlay_files().values())
    for fid in sorted(files):
        if not 0 <= fid < len(entries):
            raise ValueError(f"file id {fid} is not in the FAT ({len(entries)} entries)")
        blob = files[fid]
        s, e = entries[fid]
        if fid in overlay_ids and len(blob) != e - s:
            raise ValueError(f"overlay file {fid} changes size ({e - s} -> {len(blob)}); the overlay table is not updated")
        nxt = next((r for r in regions if r > s), None)
        new_e = max(e, s + len(blob))
        # other FAT entries may share these bytes; never write over them
        shared = any(j != fid and a < new_e and s < b for j, (a, b) in enumerate(entries) if b > a)
        # the last region in the image can grow where it is
        if e > s and not shared and (nxt is None or len(blob) <= nxt - s):
            pad = 0xFF if e < len(out) and out[e] == 0xFF else 0x00
            out[s:s + len(blob)] = blob
            if len(blob) < e - s:
                out[s + len(blob):e] = bytes([pad]) * (e - s - len(blob))
            entries[fid] = (s, s + len(blob))
            end = max(end, s + len(blob))
        else:
            s = -(-end // ALIGN) * ALIGN
            if len(out) < s:
                out += b"\xFF" * (s - len(out))
            out[s:s + len(blob)] = blob
            entries[fid] = (s, s + len(blob))
            end = s + len(blob)
            bisect.insort(regions, s)
    for i, (s, e) in enumerate(entries):
        struct.pack_into("<II", out, rom.fat[0] + i * 8, s, e)
    # some tools leave the used-size field below the real end; keep it unless the files reach further
    if max(e for s, e in entries) > max([rom.used] + [e for s, e in rom.entries]):
        struct.pack_into("<I", out, 0x80, max(e for s, e in entries))
    cap = out[0x14]
    while (0x20000 << cap) < len(out):
        cap += 1
    out[0x14] = cap
    struct.pack_into("<H", out, 0x15E, crc16(out[:0x15E]))
    return bytes(out)


def pack(rom, folder):
    """Rebuild with every file under `folder` (as written by unpack: data/...,
    overlay9/..., overlay7/...) that differs from the ROM. Returns (bytes,
    list of changed paths). Other parts (arm9, header, banner) are not read."""
    folder = Path(folder)
    paths = {"data/" + n: fid for fid, n in rom.names.items()}
    paths.update(rom.overlay_files())
    files, changed = {}, []
    for path, fid in sorted(paths.items()):
        p = folder / path
        if p.is_file():
            blob = p.read_bytes()
            if blob != rom.file(fid):
                files[fid] = blob
                changed.append(path)
    return rebuild(rom, files), changed
