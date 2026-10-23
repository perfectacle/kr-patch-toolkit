"""Hangul syllable composition and an OCR correction for ㅁ/ㅇ."""

CHO_M, CHO_O = 6, 11        # initial ㅁ, ㅇ
JONG_M, JONG_O = 16, 21     # final ㅁ, ㅇ


def is_syllable(ch):
    return 0xAC00 <= ord(ch) <= 0xD7A3


def split(ch):
    n = ord(ch) - 0xAC00
    return n // 588, (n // 28) % 21, n % 28


def join(c, v, j):
    return chr(0xAC00 + c * 588 + v * 28 + j)


def fix_mieum_ieung(ch, g):
    """Re-decide ㅁ vs ㅇ from the glyph pixels.

    Small bitmap fonts draw ㅇ as a box with empty corners and ㅁ with filled ones,
    which Vision OCR mixes up. The initial consonant's top-left corner is checked
    on the first ink row, the final consonant's bottom-left on the last.
    """
    if not ch or not is_syllable(ch):
        return ch
    ink = [y for y, r in enumerate(g) if any(r)]
    if not ink:
        return ch
    c, v, j = split(ch)
    top, bot = ink[0], ink[-1]
    if c in (CHO_M, CHO_O):
        xs = [x for y in range(top, min(top + 3, len(g))) for x, p in enumerate(g[y]) if p]
        c = CHO_M if g[top][min(xs)] else CHO_O
    if j in (JONG_M, JONG_O):
        xs = [x for y in range(max(bot - 2, 0), bot + 1) for x, p in enumerate(g[y]) if p]
        j = JONG_M if g[bot][min(xs)] else JONG_O
    return join(c, v, j)
