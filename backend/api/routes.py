import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.core import monitor
from backend.services import get_services

from . import chat, documents, memory, tools, voice, websocket

router = APIRouter()
router.include_router(chat.router)
router.include_router(voice.router)
router.include_router(memory.router)
router.include_router(documents.router)
router.include_router(tools.router)
router.include_router(websocket.router)


class SettingsIn(BaseModel):
    values: dict


@router.get("/api/health")
async def health():
    s = get_services()
    llm, tamil = await asyncio.gather(s.llm.health(), asyncio.to_thread(s.tts.tamil.status))
    return {"llm": llm, "tamil_tts": tamil, "piper": s.tts.piper.status(s.settings.get("piper_voice")),
            "whisper_loaded": s.stt.loaded_model, "embedder_loaded": s.embedder.loaded,
            "qdrant_open": s.vectors_open, "documents": s.documents_repo.count()}


@router.get("/api/system")
async def system():
    s = get_services()
    snap = monitor.snapshot()
    try:
        snap["ollama_loaded"] = [{"name": m["name"], "size_mb": round(m["size"] / 2**20),
                                  "vram_mb": round(m.get("size_vram", 0) / 2**20)} for m in await s.llm.running()]
    except Exception:  # noqa: BLE001
        snap["ollama_loaded"] = []
    return snap


@router.get("/api/settings")
def get_settings():
    return get_services().settings.all()


@router.put("/api/settings")
def put_settings(body: SettingsIn):
    try:
        return get_services().settings.update(body.values)
    except KeyError as e:
        raise HTTPException(400, str(e.args[0]))


@router.post("/api/settings/reset")
def reset_settings():
    return get_services().settings.reset()


@router.get("/api/llm/models")
async def llm_models():
    try:
        return await get_services().llm.models()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(503, f"Cannot reach Ollama: {e}")
