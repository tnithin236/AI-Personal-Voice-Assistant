"""Embedded (local, on-disk) Qdrant. Two collections: memories and document chunks."""
import logging
import time
import uuid
from pathlib import Path

from qdrant_client import QdrantClient, models

from .embeddings import DIM, Embedder

log = logging.getLogger(__name__)
MEM, DOC = "memories", "documents"


class VectorStore:
    def __init__(self, path: Path, embedder: Embedder):
        path.mkdir(parents=True, exist_ok=True)
        self.client = QdrantClient(path=str(path))
        self.embedder = embedder
        for name in (MEM, DOC):
            if not self.client.collection_exists(name):
                self.client.create_collection(
                    name, vectors_config=models.VectorParams(size=DIM, distance=models.Distance.COSINE))
        log.info("Qdrant ready at %s", path)

    # ---- memories -------------------------------------------------------
    def add_memory(self, text: str, source: str = "auto", conversation_id: str | None = None) -> dict:
        pid = str(uuid.uuid4())
        payload = {"text": text.strip(), "source": source, "conversation_id": conversation_id,
                   "created_at": time.time()}
        vec = self.embedder.embed([text])[0]
        self.client.upsert(MEM, points=[models.PointStruct(id=pid, vector=vec, payload=payload)])
        return {"id": pid, **payload}

    def search_memories(self, query: str, k: int = 4, min_score: float = 0.35,
                        source: str | None = None) -> list[dict]:
        flt = None
        if source:
            flt = models.Filter(must=[models.FieldCondition(key="source", match=models.MatchValue(value=source))])
        vec = self.embedder.embed([query])[0]
        res = self.client.query_points(MEM, query=vec, limit=k, score_threshold=min_score,
                                       query_filter=flt, with_payload=True).points
        return [{"id": str(p.id), "score": p.score, **p.payload} for p in res]

    def list_memories(self, limit: int = 1000) -> list[dict]:
        points, _ = self.client.scroll(MEM, limit=limit, with_payload=True, with_vectors=False)
        items = [{"id": str(p.id), **p.payload} for p in points]
        return sorted(items, key=lambda m: m.get("created_at", 0), reverse=True)

    def delete_memory(self, memory_id: str) -> None:
        self.client.delete(MEM, points_selector=models.PointIdsList(points=[memory_id]))

    def clear_memories(self) -> None:
        self.client.delete_collection(MEM)
        self.client.create_collection(
            MEM, vectors_config=models.VectorParams(size=DIM, distance=models.Distance.COSINE))

    # ---- documents ------------------------------------------------------
    def add_chunks(self, doc_id: str, filename: str, chunks: list[dict]) -> int:
        vecs = self.embedder.embed([c["text"] for c in chunks])
        points = [models.PointStruct(
            id=str(uuid.uuid4()), vector=v,
            payload={"doc_id": doc_id, "filename": filename, "page": c.get("page"),
                     "chunk_index": i, "text": c["text"]})
            for i, (c, v) in enumerate(zip(chunks, vecs))]
        for i in range(0, len(points), 64):
            self.client.upsert(DOC, points=points[i:i + 64])
        return len(points)

    def search_docs(self, query: str, k: int = 4, min_score: float = 0.3,
                    doc_ids: list[str] | None = None) -> list[dict]:
        flt = None
        if doc_ids:
            flt = models.Filter(must=[models.FieldCondition(key="doc_id", match=models.MatchAny(any=doc_ids))])
        vec = self.embedder.embed([query])[0]
        res = self.client.query_points(DOC, query=vec, limit=k, score_threshold=min_score,
                                       query_filter=flt, with_payload=True).points
        return [{"score": p.score, **p.payload} for p in res]

    def delete_document(self, doc_id: str) -> None:
        self.client.delete(DOC, points_selector=models.FilterSelector(
            filter=models.Filter(must=[models.FieldCondition(key="doc_id", match=models.MatchValue(value=doc_id))])))

    def close(self) -> None:
        self.client.close()
