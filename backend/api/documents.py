import asyncio
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from backend.documents.pdf_reader import SUPPORTED
from backend.services import get_services

router = APIRouter(prefix="/api", tags=["documents"])


class SearchIn(BaseModel):
    query: str
    k: int = 4


@router.get("/documents")
def list_documents():
    return get_services().documents_repo.list()


@router.post("/documents")
async def upload_document(file: UploadFile = File(...)):
    s = get_services()
    original = Path(file.filename or "upload").name
    ext = Path(original).suffix.lower()
    if ext not in SUPPORTED:
        raise HTTPException(415, f"Unsupported file type '{ext}'. Supported: {', '.join(sorted(SUPPORTED))}")
    safe = re.sub(r"[^\w.\- ]", "_", original)
    dest = s.cfg.documents_dir / f"{uuid.uuid4().hex[:8]}_{safe}"
    limit, size = s.cfg.max_upload_mb * 2**20, 0
    with dest.open("wb") as f:
        while chunk := await file.read(1 << 20):
            size += len(chunk)
            if size > limit:
                f.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(413, f"File larger than {s.cfg.max_upload_mb} MB")
            f.write(chunk)
    try:
        return await asyncio.to_thread(s.documents.ingest, dest, original)
    except ValueError as e:
        dest.unlink(missing_ok=True)
        raise HTTPException(422, str(e))
    except Exception as e:  # noqa: BLE001
        dest.unlink(missing_ok=True)
        raise HTTPException(500, f"Indexing failed: {type(e).__name__}: {e}")


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    ok = await asyncio.to_thread(get_services().documents.remove, doc_id)
    if not ok:
        raise HTTPException(404, "Document not found")
    return {"ok": True}


@router.post("/documents/search")
async def search_documents(body: SearchIn):
    s = get_services()
    try:
        return await asyncio.to_thread(s.vectors.search_docs, body.query, body.k, 0.0)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(503, f"Vector store unavailable: {e}")
