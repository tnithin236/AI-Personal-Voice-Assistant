"""Upload -> extract -> chunk -> embed -> index. Blocking; call via asyncio.to_thread."""
import logging
import uuid
from pathlib import Path

from .chunking import chunk_text
from .pdf_reader import read_document

log = logging.getLogger(__name__)


class DocumentProcessor:
    def __init__(self, vectors_getter, repo, chunk_size: int, chunk_overlap: int):
        self._vectors = vectors_getter  # callable -> VectorStore (lazy)
        self.repo, self.size, self.overlap = repo, chunk_size, chunk_overlap

    def ingest(self, path: Path, filename: str) -> dict:
        pages = read_document(path)
        chunks = [{"page": p["page"], "text": t}
                  for p in pages for t in chunk_text(p["text"], self.size, self.overlap)]
        if not chunks:
            raise ValueError("No extractable text found (scanned PDFs need OCR, which is not included).")
        doc_id = uuid.uuid4().hex
        n = self._vectors().add_chunks(doc_id, filename, chunks)
        self.repo.add(doc_id, filename, str(path), n, len(pages) if path.suffix.lower() == ".pdf" else None,
                      path.stat().st_size)
        log.info("Indexed %s: %d chunks", filename, n)
        return self.repo.get(doc_id)

    def remove(self, doc_id: str) -> bool:
        doc = self.repo.get(doc_id)
        if not doc:
            return False
        self._vectors().delete_document(doc_id)
        self.repo.delete(doc_id)
        try:
            Path(doc["path"]).unlink(missing_ok=True)
        except OSError as e:
            log.warning("Could not delete %s: %s", doc["path"], e)
        return True
