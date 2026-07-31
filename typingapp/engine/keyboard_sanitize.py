from __future__ import annotations

import unicodedata

# US-QWERTY-typeable ASCII: printable 0x20-0x7E plus common whitespace.
TYPEABLE_ASCII = frozenset(chr(c) for c in range(0x20, 0x7F)) | {"\n", "\t"}

# Each entry maps one non-typeable character to exactly one typeable replacement
# character. Every value here MUST be a single character — this file's sanitize
# function assumes a strict 1:1 character correspondence between input and output
# so that book-offset math elsewhere in the app (chunk_from_offset, page_info,
# LessonScreen._book_raw_offset) is never broken by sanitizing lesson text.
_EN_US_QWERTY_REPLACEMENTS: dict[str, str] = {
    chr(0x2018): "'",  # left single quotation mark
    chr(0x2019): "'",  # right single quotation mark / apostrophe
    chr(0x201A): ",",  # single low-9 quotation mark
    chr(0x201B): "'",  # single high-reversed-9 quotation mark
    chr(0x201C): '"',  # left double quotation mark
    chr(0x201D): '"',  # right double quotation mark
    chr(0x201E): '"',  # double low-9 quotation mark
    chr(0x201F): '"',  # double high-reversed-9 quotation mark
    chr(0x2013): "-",  # en dash
    chr(0x2014): "-",  # em dash
    chr(0x2212): "-",  # minus sign
    chr(0x2026): ".",  # horizontal ellipsis (single character) -> single period
    chr(0x00A0): " ",  # non-breaking space
    chr(0x2002): " ",  # en space
    chr(0x2003): " ",  # em space
    chr(0x2009): " ",  # thin space
    chr(0x200B): " ",  # zero-width space
    chr(0xFEFF): " ",  # BOM / zero-width no-break space
}

# Accented/special Latin letters that do NOT decompose into a base letter plus
# a combining mark under Unicode NFD normalization, so the NFD fallback in
# sanitize_for_keyboard can't resolve them. Each value is a single typeable
# ASCII character standing in for the accented original.
_NON_DECOMPOSING_REPLACEMENTS: dict[str, str] = {
    "ß": "s",  # German sharp s (eszett)
    "œ": "o",  # Latin small ligature oe
    "Œ": "O",  # Latin capital ligature OE
    "đ": "d",  # Latin small letter d with stroke
    "Đ": "D",  # Latin capital letter D with stroke
    "ł": "l",  # Latin small letter l with stroke
    "Ł": "L",  # Latin capital letter L with stroke
    "þ": "t",  # thorn
    "Þ": "T",  # capital thorn
    "ð": "d",  # eth
    "Ð": "D",  # capital eth
}

# Letters that are standard, directly-typeable characters on real Nordic
# keyboard layouts (e.g. Norwegian Bokmal treats ae/oe/aa as their own keys,
# not decorative accents on a Latin base letter) -- these pass through
# unchanged rather than being replaced with an ASCII lookalike, even though
# `layout` is still nominally "en-us-qwerty" here (this app doesn't yet model
# a distinct Nordic physical layout, but the *text* is legitimate target
# content for a Norwegian-language lesson and must not be mangled). Without
# this, ae/AE/oe/OE would hit _NON_DECOMPOSING_REPLACEMENTS (previously
# mapped them to plain "a"/"o") and aa/AA would decompose via NFD to "a"/"A"
# (dropping the combining ring above), silently turning Norwegian text into
# something else.
_NORDIC_PASSTHROUGH = frozenset({
    chr(0x00E6), chr(0x00C6),  # ae / AE (Latin small/capital ligature ae)
    chr(0x00F8), chr(0x00D8),  # oe / OE (Latin small/capital letter o with stroke)
    chr(0x00E5), chr(0x00C5),  # aa / AA (Latin small/capital letter a with ring above)
})

_LAYOUTS = {
    "en-us-qwerty": _EN_US_QWERTY_REPLACEMENTS,
}
_DEFAULT_LAYOUT = "en-us-qwerty"


def sanitize_for_keyboard(text: str, layout: str = "en-us-qwerty") -> str:
    """Replace every character not typeable on `layout` with a single-character
    ASCII equivalent, or a single space if there's no reasonable equivalent.
    Guarantees len(output) == len(input) always, so callers that track character
    offsets into the original text (book progress/page percent) stay correct."""
    replacements = _LAYOUTS.get(layout, _LAYOUTS[_DEFAULT_LAYOUT])
    out_chars = []
    for ch in text:
        if ch in TYPEABLE_ASCII:
            out_chars.append(ch)
        elif ch in _NORDIC_PASSTHROUGH:
            out_chars.append(ch)
        elif ch in replacements:
            out_chars.append(replacements[ch])
        elif ch in _NON_DECOMPOSING_REPLACEMENTS:
            out_chars.append(_NON_DECOMPOSING_REPLACEMENTS[ch])
        else:
            decomposed = unicodedata.normalize("NFD", ch)
            base = decomposed[0] if decomposed else ""
            if base and base in TYPEABLE_ASCII:
                out_chars.append(base)
            else:
                out_chars.append(" ")
    return "".join(out_chars)
