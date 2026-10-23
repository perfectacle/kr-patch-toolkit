"""Minimal 65c816 disassembler. REP/SEP update the M/X width as decoding proceeds.

The cartridge map is injected as a mapper (see kr_patch.snes.mapper), so the same
decoder serves LoROM, HiROM and SA-1 images.
"""
from .mapper import LoROM

OPS = {}

_table = """
00 BRK imm8|01 ORA dpxi|02 COP imm8|03 ORA sr|04 TSB dp|05 ORA dp|06 ASL dp|07 ORA dpil|08 PHP imp|09 ORA immm|0A ASL acc|0B PHD imp|0C TSB abs|0D ORA abs|0E ASL abs|0F ORA long
10 BPL rel|11 ORA dpiy|12 ORA dpi|13 ORA sriy|14 TRB dp|15 ORA dpx|16 ASL dpx|17 ORA dpily|18 CLC imp|19 ORA absy|1A INC acc|1B TCS imp|1C TRB abs|1D ORA absx|1E ASL absx|1F ORA longx
20 JSR abs|21 AND dpxi|22 JSL long|23 AND sr|24 BIT dp|25 AND dp|26 ROL dp|27 AND dpil|28 PLP imp|29 AND immm|2A ROL acc|2B PLD imp|2C BIT abs|2D AND abs|2E ROL abs|2F AND long
30 BMI rel|31 AND dpiy|32 AND dpi|33 AND sriy|34 BIT dpx|35 AND dpx|36 ROL dpx|37 AND dpily|38 SEC imp|39 AND absy|3A DEC acc|3B TSC imp|3C BIT absx|3D AND absx|3E ROL absx|3F AND longx
40 RTI imp|41 EOR dpxi|42 WDM imm8|43 EOR sr|44 MVP mv|45 EOR dp|46 LSR dp|47 EOR dpil|48 PHA imp|49 EOR immm|4A LSR acc|4B PHK imp|4C JMP abs|4D EOR abs|4E LSR abs|4F EOR long
50 BVC rel|51 EOR dpiy|52 EOR dpi|53 EOR sriy|54 MVN mv|55 EOR dpx|56 LSR dpx|57 EOR dpily|58 CLI imp|59 EOR absy|5A PHY imp|5B TCD imp|5C JML long|5D EOR absx|5E LSR absx|5F EOR longx
60 RTS imp|61 ADC dpxi|62 PER rell|63 ADC sr|64 STZ dp|65 ADC dp|66 ROR dp|67 ADC dpil|68 PLA imp|69 ADC immm|6A ROR acc|6B RTL imp|6C JMP absi|6D ADC abs|6E ROR abs|6F ADC long
70 BVS rel|71 ADC dpiy|72 ADC dpi|73 ADC sriy|74 STZ dpx|75 ADC dpx|76 ROR dpx|77 ADC dpily|78 SEI imp|79 ADC absy|7A PLY imp|7B TDC imp|7C JMP absxi|7D ADC absx|7E ROR absx|7F ADC longx
80 BRA rel|81 STA dpxi|82 BRL rell|83 STA sr|84 STY dp|85 STA dp|86 STX dp|87 STA dpil|88 DEY imp|89 BIT immm|8A TXA imp|8B PHB imp|8C STY abs|8D STA abs|8E STX abs|8F STA long
90 BCC rel|91 STA dpiy|92 STA dpi|93 STA sriy|94 STY dpx|95 STA dpx|96 STX dpy|97 STA dpily|98 TYA imp|99 STA absy|9A TXS imp|9B TXY imp|9C STZ abs|9D STA absx|9E STZ absx|9F STA longx
A0 LDY immx|A1 LDA dpxi|A2 LDX immx|A3 LDA sr|A4 LDY dp|A5 LDA dp|A6 LDX dp|A7 LDA dpil|A8 TAY imp|A9 LDA immm|AA TAX imp|AB PLB imp|AC LDY abs|AD LDA abs|AE LDX abs|AF LDA long
B0 BCS rel|B1 LDA dpiy|B2 LDA dpi|B3 LDA sriy|B4 LDY dpx|B5 LDA dpx|B6 LDX dpy|B7 LDA dpily|B8 CLV imp|B9 LDA absy|BA TSX imp|BB TYX imp|BC LDY absx|BD LDA absx|BE LDX absy|BF LDA longx
C0 CPY immx|C1 CMP dpxi|C2 REP imm8|C3 CMP sr|C4 CPY dp|C5 CMP dp|C6 DEC dp|C7 CMP dpil|C8 INY imp|C9 CMP immm|CA DEX imp|CB WAI imp|CC CPY abs|CD CMP abs|CE DEC abs|CF CMP long
D0 BNE rel|D1 CMP dpiy|D2 CMP dpi|D3 CMP sriy|D4 PEI dpi|D5 CMP dpx|D6 DEC dpx|D7 CMP dpily|D8 CLD imp|D9 CMP absy|DA PHX imp|DB STP imp|DC JML absil|DD CMP absx|DE DEC absx|DF CMP longx
E0 CPX immx|E1 SBC dpxi|E2 SEP imm8|E3 SBC sr|E4 CPX dp|E5 SBC dp|E6 INC dp|E7 SBC dpil|E8 INX imp|E9 SBC immm|EA NOP imp|EB XBA imp|EC CPX abs|ED SBC abs|EE INC abs|EF SBC long
F0 BEQ rel|F1 SBC dpiy|F2 SBC dpi|F3 SBC sriy|F4 PEA abs|F5 SBC dpx|F6 INC dpx|F7 SBC dpily|F8 SED imp|F9 SBC absy|FA PLX imp|FB XCE imp|FC JSR absxi|FD SBC absx|FE INC absx|FF SBC longx
"""
for _line in _table.strip().splitlines():
    for _ent in _line.split('|'):
        _c, _mn, _md = _ent.split()
        OPS[int(_c, 16)] = (_mn, _md)

FMT = {
    'imp': '', 'acc': 'A', 'imm8': '#${:02X}', 'dp': '${:02X}', 'dpx': '${:02X},X', 'dpy': '${:02X},Y',
    'dpi': '(${:02X})', 'dpxi': '(${:02X},X)', 'dpiy': '(${:02X}),Y', 'dpil': '[${:02X}]', 'dpily': '[${:02X}],Y',
    'sr': '${:02X},S', 'sriy': '(${:02X},S),Y', 'abs': '${:04X}', 'absx': '${:04X},X', 'absy': '${:04X},Y',
    'absi': '(${:04X})', 'absxi': '(${:04X},X)', 'absil': '[${:04X}]', 'long': '${:06X}', 'longx': '${:06X},X',
}
SIZE = {'imp': 0, 'acc': 0, 'imm8': 1, 'dp': 1, 'dpx': 1, 'dpy': 1, 'dpi': 1, 'dpxi': 1, 'dpiy': 1, 'dpil': 1,
        'dpily': 1, 'sr': 1, 'sriy': 1, 'abs': 2, 'absx': 2, 'absy': 2, 'absi': 2, 'absxi': 2, 'absil': 2,
        'long': 3, 'longx': 3, 'rel': 1, 'rell': 2, 'mv': 2}


def decode(rom, addr, m8=True, x8=True, mapper=None):
    """One instruction at CPU `addr`: (text, length, m8, x8) with flags after it."""
    o = (mapper or LoROM()).to_offset(addr)
    mn, md = OPS[rom[o]]
    if md == 'immm':
        n = 1 if m8 else 2
    elif md == 'immx':
        n = 1 if x8 else 2
    else:
        n = SIZE[md]
    arg = int.from_bytes(rom[o + 1:o + 1 + n], 'little')
    raw = rom[o:o + 1 + n].hex(' ')
    if md in ('immm', 'immx'):
        s = ('#${:0%dX}' % (n * 2)).format(arg)
    elif md == 'rel':
        t = (addr + 2 + (arg - 256 if arg & 0x80 else arg)) & 0xFFFF | (addr & 0xFF0000)
        s = '${:06X}'.format(t)
    elif md == 'rell':
        t = (addr + 3 + (arg - 65536 if arg & 0x8000 else arg)) & 0xFFFF | (addr & 0xFF0000)
        s = '${:06X}'.format(t)
    elif md == 'mv':
        # encoded as opcode, destination bank, source bank; written as source,destination
        s = '${:02X},${:02X}'.format(arg >> 8, arg & 0xFF)
    else:
        s = FMT[md].format(arg) if FMT[md] else ''
    if mn == 'REP':
        if arg & 0x20: m8 = False
        if arg & 0x10: x8 = False
    elif mn == 'SEP':
        if arg & 0x20: m8 = True
        if arg & 0x10: x8 = True
    text = '{:02X}:{:04X}  {:<12} {} {}'.format(addr >> 16, addr & 0xFFFF, raw, mn, s).rstrip()
    return text, 1 + n, m8, x8


def disasm(rom, addr, count, m8=True, x8=True, mapper=None):
    mapper = mapper or LoROM()
    out = []
    for _ in range(count):
        text, n, m8, x8 = decode(rom, addr, m8, x8, mapper)
        out.append(text)
        addr = (addr & 0xFF0000) | ((addr + n) & 0xFFFF)
    return '\n'.join(out)
