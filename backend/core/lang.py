"""Tiny language helpers (no heavy imports)."""
import re

_TAMIL = re.compile(r"[\u0B80-\u0BFF]")


def tamil_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    return len(_TAMIL.findall(text)) / len(letters)


def detect_language(text: str) -> str:
    """'ta' if the text is mostly Tamil script, else 'en'."""
    return "ta" if tamil_ratio(text) > 0.3 else "en"


def estimate_tokens(text: str) -> int:
    """Conservative token estimate: ~3.5 chars/token for ASCII, ~1 token per non-ASCII char."""
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    other = len(text) - ascii_chars
    return int(ascii_chars / 3.5 + other * 1.0) + 1
