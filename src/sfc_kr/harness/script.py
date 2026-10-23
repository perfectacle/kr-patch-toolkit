"""Input scripts shared by the libretro runner and lua/script.lua (Mesen 2).

One command per line, frames counted from power-on (1 = after the first frame):

    F button[+button] LEN       hold buttons for LEN frames
    F tap button PERIOD UNTIL   4-frame presses every PERIOD frames until frame UNTIL
    F shot                      screenshot f<F>.png
    F dump                      WRAM and SRAM to wram_<F>.bin / sram_<F>.bin
    F poke ADDR VALUE           16-bit little-endian WRAM write after frame F (hex)
    F end                       stop after frame F

ADDR is a WRAM offset ($0000-$1FFFF) or a full $7E/$7F address.
Blank lines and lines starting with # are ignored.
"""
from dataclasses import dataclass, field

BUTTONS = {"b": 0, "y": 1, "select": 2, "start": 3, "up": 4, "down": 5, "left": 6, "right": 7,
           "a": 8, "x": 9, "l": 10, "r": 11}
TAP_LEN = 4


@dataclass
class Script:
    presses: list = field(default_factory=list)   # (first, stop, {button id})
    shots: set = field(default_factory=set)
    dumps: set = field(default_factory=set)
    pokes: dict = field(default_factory=dict)     # frame -> [(wram offset, value)]
    end: int = 0

    def held(self, frame):
        s = set()
        for a, b, btn in self.presses:
            if a <= frame < b:
                s |= btn
        return s


def wram_offset(a):
    if 0x7E0000 <= a <= 0x7FFFFF:
        return a - 0x7E0000
    if a > 0x1FFFF:
        raise ValueError(f"${a:06X} is not in WRAM")
    return a


def _buttons(spec, n):
    try:
        return {BUTTONS[b] for b in spec.lower().split("+")}
    except KeyError as e:
        raise ValueError(f"line {n}: unknown button {e.args[0]!r}") from None


def parse(lines):
    sc = Script()
    for n, line in enumerate(lines, 1):
        p = line.split()
        if not p or p[0].startswith("#"):
            continue
        if len(p) < 2:
            raise ValueError(f"line {n}: expected 'frame command ...': {line.strip()!r}")
        f, cmd = int(p[0]), p[1]
        try:
            if cmd == "shot":
                sc.shots.add(f)
            elif cmd == "dump":
                sc.dumps.add(f)
            elif cmd == "end":
                sc.end = f
            elif cmd == "tap":
                btn = _buttons(p[2], n)
                for t in range(f, int(p[4]), int(p[3])):
                    sc.presses.append((t, t + TAP_LEN, btn))
            elif cmd == "poke":
                sc.pokes.setdefault(f, []).append((wram_offset(int(p[2], 16)), int(p[3], 16) & 0xFFFF))
            else:
                sc.presses.append((f, f + int(p[2]), _buttons(cmd, n)))
        except IndexError:
            raise ValueError(f"line {n}: missing argument for {cmd!r}") from None
    return sc


def load(path):
    with open(path, encoding="utf-8") as fp:
        return parse(fp)


def par_codes(offset, value):
    """Pro Action Replay codes writing a 16-bit value at a WRAM offset, one byte each."""
    return [f"{0x7E0000 + offset + k:06X}{b:02X}" for k, b in enumerate((value & 0xFF, value >> 8))]


@dataclass
class Watch:
    """A WRAM value logged to wram.log whenever it changes."""
    offset: int
    size: int = 1
    fmt: str = ""

    @classmethod
    def parse(cls, spec, fmt=""):
        """'ADDR[:SIZE]' with ADDR in hex."""
        a, _, n = spec.partition(":")
        return cls(wram_offset(int(a, 16)), int(n) if n else 1, fmt)

    def format(self, v):
        return format(v, self.fmt or f"0{self.size * 2}X")
