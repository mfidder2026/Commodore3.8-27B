"""Screen-code to text conversion for reading back emulator screen RAM."""

from __future__ import annotations


def screencode_to_char(code: int) -> str:
    """Map a screen code (uppercase/graphics charset) to a lowercase ASCII-ish char.

    Letters come out lowercase to match the lowercase .bas source convention.
    Reverse-video characters (bit 7) map to their normal counterpart; graphics
    characters without an ASCII equivalent become '?'.
    """
    code &= 0x7F
    if code == 0x00:
        return "@"
    if 0x01 <= code <= 0x1A:
        return chr(ord("a") + code - 1)
    if code == 0x1B:
        return "["
    if code == 0x1C:
        return "£"  # pound sign
    if code == 0x1D:
        return "]"
    if code == 0x1E:
        return "^"  # up arrow
    if code == 0x1F:
        return "<"  # left arrow
    if 0x20 <= code <= 0x3F:
        return chr(code)
    if code == 0x60:
        return " "  # shifted space
    return "?"


def screen_to_lines(data: bytes, columns: int) -> list[str]:
    """Split screen RAM into right-stripped text lines."""
    text = "".join(screencode_to_char(b) for b in data)
    return [text[i:i + columns].rstrip() for i in range(0, len(text), columns)]
