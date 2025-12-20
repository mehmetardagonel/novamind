# voice_router.py
import os
import uuid
import asyncio
import logging
import re
from typing import Optional

import httpx
from fastapi import APIRouter, UploadFile, File, Header, HTTPException
from fastapi.responses import Response, JSONResponse

from session_store import chat_sessions, chat_session_locks
from chat_service import ChatService
from rag_service import rag_service

import io
import wave

router = APIRouter(prefix="/voice", tags=["voice"])

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")

VOICE_TTS_MODEL = os.getenv("VOICE_TTS_MODEL", "aura-asteria-en")
VOICE_TTS_ENCODING = os.getenv("VOICE_TTS_ENCODING", "linear16")  # easiest for browser playback
VOICE_TTS_SAMPLE_RATE = int(os.getenv("VOICE_TTS_SAMPLE_RATE", "24000"))

def _safe_header_value(value: Optional[str], max_len: int = 2000) -> str:
    if not value:
        return ""
    cleaned = re.sub(r"[\r\n]+", " ", str(value)).strip()
    cleaned = re.sub(r"[\x00-\x1F\x7F]", " ", cleaned)
    cleaned = cleaned.encode("latin-1", "ignore").decode("latin-1")
    return cleaned[:max_len]

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

async def _store_chat_embedding_background(
    user_id: str, session_id: str, role: str, content: str, message_id: str
) -> None:
    try:
        await rag_service.index_chat_message(
            user_id=user_id,
            session_id=session_id,
            role=role,
            content=content,
            message_id=message_id,
        )
    except Exception as e:
        logger.error(f"Background chat embedding failed for user {user_id}: {e}")


def _schedule_store_chat_embedding(
    user_id: str, session_id: str, role: str, content: str, message_id: str
) -> None:
    try:
        asyncio.create_task(
            _store_chat_embedding_background(
                user_id=user_id,
                session_id=session_id,
                role=role,
                content=content,
                message_id=message_id,
            )
        )
    except Exception as e:
        logger.error(f"Failed to schedule chat embedding for user {user_id}: {e}")

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
    session_key = f"{user_id}:{sid}"
    if session_key not in chat_sessions:
        chat_sessions[session_key] = ChatService(user_id=user_id)

    # Pull RAG context just like /chat
    context = ""
    try:
        context = await rag_service.get_combined_context(
            user_id=user_id,
            query=transcript,
            session_id=sid,
        )
    except Exception as e:
        logger.error(f"Failed to build RAG context for voice chat: {e}")

    context_message = ""
    if context:
        context_message = (
            f"{context}\n\n"
            f"Use the context above if it is relevant. "
            f"Do not mention it explicitly unless asked."
        )

    lock = chat_session_locks.get(session_key)
    if lock is None:
        lock = asyncio.Lock()
        chat_session_locks[session_key] = lock

    async with lock:
        response_text = await asyncio.to_thread(
            chat_sessions[session_key].chat,
            transcript,
            context_message,
        )

    # Store chat memory for RAG (best-effort)
    try:
        user_msg_id = str(uuid.uuid4())
        assistant_msg_id = str(uuid.uuid4())
        _schedule_store_chat_embedding(
            user_id=user_id,
            session_id=sid,
            role="user",
            content=transcript,
            message_id=user_msg_id,
        )

        assistant_clean = re.sub(r"```[\\s\\S]*?```", "", response_text or "").strip()
        _schedule_store_chat_embedding(
            user_id=user_id,
            session_id=sid,
            role="assistant",
            content=assistant_clean[:2000],
            message_id=assistant_msg_id,
        )
    except Exception as e:
        logger.error(f"Failed to schedule voice chat memory embeddings: {e}")

    audio_out, mime = await deepgram_tts(response_text)

    # Return audio for immediate playback + useful metadata in headers
    safe_transcript = _safe_header_value(transcript, max_len=200)
    safe_full_transcript = _safe_header_value(transcript, max_len=2000)
    safe_reply = _safe_header_value(response_text, max_len=2000)

    return Response(
        content=audio_out,
        media_type=mime,
        headers={
            "X-Session-Id": sid,
            "X-Transcript": safe_transcript,
            "X-User-Transcript": safe_full_transcript,
            "X-Assistant-Reply": safe_reply,
        },
    )
