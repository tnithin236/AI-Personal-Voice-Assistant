import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services import get_services

router = APIRouter(prefix="/api", tags=["memory"])


class MemoryIn(BaseModel):
    text: str


def _vec():
    try:
        return get_services().vectors
    except Exception as e:  # noqa: BLE001
        raise HTTPException(503, f"Vector store unavailable: {e}")


@router.get("/memories")
async def list_memories():
    return await asyncio.to_thread(_vec().list_memories)


@router.post("/memories")
async def add_memory(body: MemoryIn):
    text = body.text.strip()
    if len(text) < 3:
        raise HTTPException(400, "Memory text is too short")
    return await asyncio.to_thread(_vec().add_memory, text, "user")


@router.get("/memories/search")
async def search_memories(q: str, k: int = 5):
    return await asyncio.to_thread(_vec().search_memories, q, k, 0.0)


@router.delete("/memories/{memory_id}")
async def delete_memory(memory_id: str):
    await asyncio.to_thread(_vec().delete_memory, memory_id)
    return {"ok": True}


@router.delete("/memories")
async def clear_memories():
    await asyncio.to_thread(_vec().clear_memories)
    return {"ok": True}
