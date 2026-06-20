"""Terminal text alignment helpers that account for double-width CJK characters."""

import unicodedata


def display_width(s: str) -> int:
    """Count terminal columns, treating wide (CJK) characters as 2 columns each."""
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in s)


def pad(s: str, width: int, align: str = "<") -> str:
    """Pad `s` to `width` terminal columns, accounting for wide characters."""
    fill = " " * max(width - display_width(s), 0)
    return s + fill if align == "<" else fill + s
