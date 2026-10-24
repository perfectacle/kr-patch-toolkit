"""Minimal 6502 disassembler for FC PRG ROM (official opcodes; others print as `.db`).

Code is addressed by PRG ROM offset and the CPU address it runs at, because a
mapper can put the same bank at different addresses. Lines are labelled
`BB:AAAA`: the PRG bank of `bank_size` bytes the offset falls in, and the CPU
address.
"""

OPS = {}

_table = """
00 BRK imp|01 ORA izx|05 ORA zp|06 ASL zp|08 PHP imp|09 ORA imm|0A ASL acc|0D ORA abs|0E ASL abs
10 BPL rel|11 ORA izy|15 ORA zpx|16 ASL zpx|18 CLC imp|19 ORA aby|1D ORA abx|1E ASL abx
20 JSR abs|21 AND izx|24 BIT zp|25 AND zp|26 ROL zp|28 PLP imp|29 AND imm|2A ROL acc|2C BIT abs|2D AND abs|2E ROL abs
30 BMI rel|31 AND izy|35 AND zpx|36 ROL zpx|38 SEC imp|39 AND aby|3D AND abx|3E ROL abx
40 RTI imp|41 EOR izx|45 EOR zp|46 LSR zp|48 PHA imp|49 EOR imm|4A LSR acc|4C JMP abs|4D EOR abs|4E LSR abs
50 BVC rel|51 EOR izy|55 EOR zpx|56 LSR zpx|58 CLI imp|59 EOR aby|5D EOR abx|5E LSR abx
60 RTS imp|61 ADC izx|65 ADC zp|66 ROR zp|68 PLA imp|69 ADC imm|6A ROR acc|6C JMP ind|6D ADC abs|6E ROR abs
70 BVS rel|71 ADC izy|75 ADC zpx|76 ROR zpx|78 SEI imp|79 ADC aby|7D ADC abx|7E ROR abx
81 STA izx|84 STY zp|85 STA zp|86 STX zp|88 DEY imp|8A TXA imp|8C STY abs|8D STA abs|8E STX abs
90 BCC rel|91 STA izy|94 STY zpx|95 STA zpx|96 STX zpy|98 TYA imp|99 STA aby|9A TXS imp|9D STA abx
A0 LDY imm|A1 LDA izx|A2 LDX imm|A4 LDY zp|A5 LDA zp|A6 LDX zp|A8 TAY imp|A9 LDA imm|AA TAX imp|AC LDY abs|AD LDA abs|AE LDX abs
B0 BCS rel|B1 LDA izy|B4 LDY zpx|B5 LDA zpx|B6 LDX zpy|B8 CLV imp|B9 LDA aby|BA TSX imp|BC LDY abx|BD LDA abx|BE LDX aby
C0 CPY imm|C1 CMP izx|C4 CPY zp|C5 CMP zp|C6 DEC zp|C8 INY imp|C9 CMP imm|CA DEX imp|CC CPY abs|CD CMP abs|CE DEC abs
D0 BNE rel|D1 CMP izy|D5 CMP zpx|D6 DEC zpx|D8 CLD imp|D9 CMP aby|DD CMP abx|DE DEC abx
E0 CPX imm|E1 SBC izx|E4 CPX zp|E5 SBC zp|E6 INC zp|E8 INX imp|E9 SBC imm|EA NOP imp|EC CPX abs|ED SBC abs|EE INC abs
F0 BEQ rel|F1 SBC izy|F5 SBC zpx|F6 INC zpx|F8 SED imp|F9 SBC aby|FD SBC abx|FE INC abx
"""
for _line in _table.strip().splitlines():
    for _ent in _line.split('|'):
        _c, _mn, _md = _ent.split()
        OPS[int(_c, 16)] = (_mn, _md)

FMT = {
    'imp': '', 'acc': 'A', 'imm': '#${:02X}', 'zp': '${:02X}', 'zpx': '${:02X},X', 'zpy': '${:02X},Y',
    'izx': '(${:02X},X)', 'izy': '(${:02X}),Y', 'abs': '${:04X}', 'abx': '${:04X},X', 'aby': '${:04X},Y',
    'ind': '(${:04X})',
}
SIZE = {'imp': 0, 'acc': 0, 'imm': 1, 'zp': 1, 'zpx': 1, 'zpy': 1, 'izx': 1, 'izy': 1, 'rel': 1,
        'abs': 2, 'abx': 2, 'aby': 2, 'ind': 2}


def label(off, addr, bank_size=0x4000):
    return '{:02X}:{:04X}'.format(off // bank_size, addr & 0xFFFF)


def decode(prg, off, addr, bank_size=0x4000):
    """One instruction at PRG offset `off`, running at CPU `addr`: (text, length)."""
    op = OPS.get(prg[off])
    n = SIZE[op[1]] if op else 0
    if op is None or off + 1 + n > len(prg):
        op, n = ('.db', 'imm'), 0
        s = '${:02X}'.format(prg[off])
    else:
        mn, md = op
        arg = int.from_bytes(prg[off + 1:off + 1 + n], 'little')
        if md == 'rel':
            s = '${:04X}'.format((addr + 2 + (arg - 256 if arg & 0x80 else arg)) & 0xFFFF)
        else:
            s = FMT[md].format(arg) if FMT[md] else ''
    raw = prg[off:off + 1 + n].hex(' ')
    text = '{}  {:<8} {} {}'.format(label(off, addr, bank_size), raw, op[0], s).rstrip()
    return text, 1 + n


def disasm(prg, off, addr, count, bank_size=0x4000):
    out = []
    for _ in range(count):
        if off >= len(prg):
            break
        text, n = decode(prg, off, addr, bank_size)
        out.append(text)
        off, addr = off + n, (addr + n) & 0xFFFF
    return '\n'.join(out)


def listing(prg, rows, bank_size=0x4000):
    """Disassemble executed instructions only. `rows` are (offset, cpu address, count)
    from `probe/cover.lua`; a gap between runs prints as a blank line."""
    out, prev_end = [], None
    for off, addr, cnt in sorted(rows):
        text, n = decode(prg, off, addr, bank_size)
        if prev_end is not None and off > prev_end:
            out.append('')
        out.append(f'{text:<34} ; {cnt}')
        prev_end = max(prev_end or 0, off + n)
    return '\n'.join(out)


def read_cover(lines):
    """Rows of a cover.txt: `OFFSET ADDR COUNT` (hex, hex, decimal)."""
    rows = []
    for line in lines:
        if line.strip():
            off, addr, cnt = line.split()
            rows.append((int(off, 16), int(addr, 16), int(cnt)))
    return rows
