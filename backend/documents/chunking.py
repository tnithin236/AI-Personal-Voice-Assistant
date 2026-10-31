"""Paragraph-aware text chunking with overlap. Pure Python (no heavy imports)."""
import re

_SENT = re.compile(r"(?<=[.!?\u0964])\s+")


def _split_long(paragraph: str, size: int) -> list[str]:
    out, cur = [], ""
    for sent in _SENT.split(paragraph):
        while len(sent) > size:  # hard split very long sentences
            if cur:
                out.append(cur)
                cur = ""
            out.append(sent[:size])
            sent = sent[size:]
        if cur and len(cur) + len(sent) + 1 > size:
            out.append(cur)
            cur = sent
        else:
            cur = f"{cur} {sent}".strip()
    if cur:
        out.append(cur)
    return out


def chunk_text(text: str, size: int = 800, overlap: int = 120) -> list[str]:
    text = re.sub(r"[ \t]+", " ", text.replace("\r", ""))
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return []
    units: list[str] = []
    for p in (p.strip() for p in text.split("\n\n")):
        if p:
            units.extend([p] if len(p) <= size else _split_long(p, size))
    chunks, cur = [], ""
    for u in units:
        if cur and len(cur) + len(u) + 2 > size:
            chunks.append(cur)
            tail = cur[-overlap:] if overlap else ""
            sp = tail.find(" ")
            tail = tail[sp + 1:] if sp != -1 else tail
            cur = f"{tail}\n\n{u}".strip() if tail else u
        else:
            cur = f"{cur}\n\n{u}" if cur else u
    if cur:
        chunks.append(cur)
    return chunks
