# voice_router.py
import os
import uuid
from typing import Optional

import httpx
from fastapi import APIRouter, UploadFile, File, Header, HTTPException
from fastapi.responses import Response, JSONResponse

from session_store import chat_sessions
from chat_service import ChatService

import io
import wave
import logging

router = APIRouter(prefix="/voice", tags=["voice"])

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

VOICE_TTS_MODEL = os.getenv("VOICE_TTS_MODEL", "aura-asteria-en")
VOICE_TTS_ENCODING = os.getenv("VOICE_TTS_ENCODING", "linear16")  # easiest for browser playback
VOICE_TTS_SAMPLE_RATE = int(os.getenv("VOICE_TTS_SAMPLE_RATE", "24000"))

async def deepgram_stt(audio_bytes: bytes, content_type: str) -> str:
    if not DEEPGRAM_API_KEY:
        raise HTTPException(status_code=500, detail="DEEPGRAM_API_KEY is not set")

    url = "https://api.deepgram.com/v1/listen"
    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": content_type or "application/octet-stream",
    }
    params = {
        "smart_format": "true",
        "punctuate": "true",
        # Keep it simple for now. Later you can pass language from frontend ("tr"/"en").
        "language": "en",
    }

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(url, params=params, headers=headers, content=audio_bytes)
        r.raise_for_status()
        data = r.json()

    try:
        transcript = data["results"]["channels"][0]["alternatives"][0]["transcript"]
    except Exception:
        transcript = ""

    return transcript.strip()

logger = logging.getLogger(__name__)

def pcm16_to_wav(pcm_bytes: bytes, sample_rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)         # mono
        wf.setsampwidth(2)         # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()

async def deepgram_tts(text: str) -> tuple[bytes, str]:
    if not DEEPGRAM_API_KEY:
        raise HTTPException(status_code=500, detail="DEEPGRAM_API_KEY is not set")

    url = "https://api.deepgram.com/v1/speak"
    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": "application/json",
    }

    params = {
        "model": VOICE_TTS_MODEL,
        "encoding": "linear16",
        "sample_rate": str(VOICE_TTS_SAMPLE_RATE),
    }

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(url, params=params, headers=headers, json={"text": text})

    if r.status_code >= 400:
        # Deepgram bazen JSON hata döndürüyor; log’da görünsün
        logger.error("Deepgram TTS error %s: %s", r.status_code, r.text)
        raise HTTPException(status_code=502, detail=f"Deepgram TTS failed: {r.text}")

    wav_bytes = pcm16_to_wav(r.content, VOICE_TTS_SAMPLE_RATE)
    return wav_bytes, "audio/wav"

@router.post("/chat")
async def voice_chat(
    file: UploadFile = File(...),
    session_id: Optional[str] = None,
    user_id: str = Header(..., alias="X-User-Id"),
):
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    transcript = await deepgram_stt(audio_bytes, file.content_type or "application/octet-stream")
    if not transcript:
        return JSONResponse({"transcript": "", "response_text": "", "session_id": session_id})

    # Reuse the SAME session mechanism as /chat
    sid = session_id or str(uuid.uuid4())
    if sid not in chat_sessions:
        chat_sessions[sid] = ChatService(user_id=user_id)

    response_text = chat_sessions[sid].chat(transcript)

    audio_out, mime = await deepgram_tts(response_text)

    # Return audio for immediate playback + useful metadata in headers
    return Response(
        content=audio_out,
        media_type=mime,
        headers={
            "X-Session-Id": sid,
            "X-Transcript": transcript[:200],
        },
    )
