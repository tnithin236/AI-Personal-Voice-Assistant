"""Text extraction for PDF / TXT / MD files. Returns a list of pages: [{"page": int|None, "text": str}]."""
import codecs
from pathlib import Path

SUPPORTED = {".pdf", ".txt", ".md"}


def read_pdf(path: Path) -> list[dict]:
    import pymupdf
    pages = []
    with pymupdf.open(str(path)) as doc:
        for i, page in enumerate(doc, 1):
            text = page.get_text("text").strip()
            if text:
                pages.append({"page": i, "text": text})
    return pages


def read_text(path: Path) -> list[dict]:
    raw = path.read_bytes()
    if raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return [{"page": None, "text": raw.decode("utf-16")}]
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return [{"page": None, "text": raw.decode(enc)}]
        except UnicodeError:
            continue
    return [{"page": None, "text": raw.decode("utf-8", errors="replace")}]


def read_document(path: Path) -> list[dict]:
    ext = path.suffix.lower()
    if ext == ".pdf":
        return read_pdf(path)
    if ext in (".txt", ".md"):
        return read_text(path)
    raise ValueError(f"Unsupported file type '{ext}'. Supported: {', '.join(sorted(SUPPORTED))}")