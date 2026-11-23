import asyncio
import io

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from backend.services import get_services
from backend.voice.audio_handler import list_input_devices, wav_bytes_to_audio
from backend.voice.tamil_tts import TTSUnavailable

router = APIRouter(prefix="/api", tags=["voice"])


class TTSIn(BaseModel):
    text: str
    language: str | None = None


@router.get("/voice/devices")
def devices():
    try:
        return list_input_devices()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(503, f"Cannot list audio devices: {e}")


@router.get("/voice/status")
async def voice_status():
    s = get_services()
    voice = s.settings.get("piper_voice")
    return {"whisper_loaded": s.stt.loaded_model, "piper": s.tts.piper.status(voice),
            "tamil": await asyncio.to_thread(s.tts.tamil.status)}


@router.post("/tts")
async def tts(body: TTSIn):
    s = get_services()
    try:
        audio, lang = await asyncio.to_thread(s.tts.synthesize, body.text, body.language)
    except TTSUnavailable as e:
        raise HTTPException(503, str(e))
    return Response(audio, media_type="audio/wav", headers={"X-Language": lang})


@router.post("/transcribe")
async def transcribe(file: UploadFile = File(...), language: str | None = Form(None)):
    """Postman-friendly: upload a short audio file (wav/mp3/m4a...) and get the transcript."""
    s = get_services()
    data = await file.read()
    lang = language if language in ("en", "ta") else None
    # Plain WAV files are decoded here, so they reach Whisper exactly like microphone audio. Other formats need PyAV.
    audio = wav_bytes_to_audio(data)
    source = audio if audio is not None else io.BytesIO(data)
    try:
        return await asyncio.to_thread(s.stt.transcribe, source, s.settings.get("whisper_model"), lang)
    except TypeError as e:
        if "metadata_errors" in str(e):
            raise HTTPException(415, "Decoding this audio format needs PyAV, and the installed PyAV version is "
                                     "incompatible with faster-whisper. Upload a 16-bit PCM WAV file instead.")
        raise HTTPException(500, f"Transcription failed: {type(e).__name__}: {e}")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"Transcription failed: {type(e).__name__}: {e}")
