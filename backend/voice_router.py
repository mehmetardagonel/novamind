# voice_router.py
import os
import uuid
import asyncio
import logging
import re
import json
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

VOICE_RESPONSE_CACHE: dict[str, dict] = {}
VOICE_RESPONSE_CACHE_MAX = 200

def _safe_header_value(value: Optional[str], max_len: int = 2000) -> str:
    if not value:
        return ""
    cleaned = re.sub(r"[\r\n]+", " ", str(value)).strip()
    cleaned = re.sub(r"[\x00-\x1F\x7F]", " ", cleaned)
    cleaned = cleaned.encode("latin-1", "ignore").decode("latin-1")
    return cleaned[:max_len]

def _normalize_transcript(text: str) -> str:
    if not text:
        return ""
    lowered = text.lower()
    if any(k in lowered for k in ["mail", "email", "inbox", "account", "outlook", "gmail"]):
        text = re.sub(r"\bout\\s+look\\b", "outlook", text, flags=re.IGNORECASE)
        text = re.sub(r"\bout\\s+lock\\b", "outlook", text, flags=re.IGNORECASE)
        text = re.sub(r"\bout\\s+put\\b", "outlook", text, flags=re.IGNORECASE)
        text = re.sub(r"\boutput\\b", "outlook", text, flags=re.IGNORECASE)
        text = re.sub(r"\bg\\s+mail\\b", "gmail", text, flags=re.IGNORECASE)
    return text

def _find_balanced_json(text: str, start_index: int, open_char: str, close_char: str) -> Optional[str]:
    depth = 0
    in_string = False
    escape = False
    for i in range(start_index, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == "\"":
                in_string = False
            continue
        if ch == "\"":
            in_string = True
            continue
        if ch == open_char:
            depth += 1
        elif ch == close_char:
            depth -= 1
            if depth == 0:
                return text[start_index : i + 1]
    return None

def _first_balanced_json(text: str, open_char: str, close_char: str) -> Optional[tuple[str, int]]:
    idx = text.find(open_char)
    while idx != -1:
        candidate = _find_balanced_json(text, idx, open_char, close_char)
        if candidate:
            return candidate, idx
        idx = text.find(open_char, idx + 1)
    return None

def _normalize_emails_payload(parsed) -> Optional[dict]:
    if isinstance(parsed, list):
        return {"emails": parsed, "insights": None}
    if isinstance(parsed, dict):
        emails = parsed.get("emails")
        if isinstance(emails, list):
            insights = parsed.get("insights") or parsed.get("summary") or parsed.get("message")
            return {
                "emails": emails,
                "insights": insights if isinstance(insights, str) else None,
            }
    return None

def _extract_emails_payload(text: str) -> dict:
    result = {"emails": None, "insights": None, "text_before": ""}
    if not text:
        return result

    fence_regex = re.compile(r"```\s*json\s*([\s\S]*?)\s*```", re.IGNORECASE)
    for match in fence_regex.finditer(text):
        candidate = (match.group(1) or "").strip()
        try:
            payload = _normalize_emails_payload(json.loads(candidate))
        except Exception:
            payload = None
        if payload:
            result.update(payload)
            result["text_before"] = text[: match.start()].strip()
            return result

    any_fence = re.compile(r"```\s*([\s\S]*?)\s*```")
    for match in any_fence.finditer(text):
        candidate = (match.group(1) or "").strip()
        try:
            payload = _normalize_emails_payload(json.loads(candidate))
        except Exception:
            payload = None
        if payload:
            result.update(payload)
            result["text_before"] = text[: match.start()].strip()
            return result

    try:
        payload = _normalize_emails_payload(json.loads(text.strip()))
    except Exception:
        payload = None
    if payload:
        result.update(payload)
        return result

    array_match = _first_balanced_json(text, "[", "]")
    if array_match:
        candidate, idx = array_match
        try:
            payload = _normalize_emails_payload(json.loads(candidate))
        except Exception:
            payload = None
        if payload:
            result.update(payload)
            result["text_before"] = text[:idx].strip()
            return result

    obj_match = _first_balanced_json(text, "{", "}")
    if obj_match:
        candidate, idx = obj_match
        try:
            payload = _normalize_emails_payload(json.loads(candidate))
        except Exception:
            payload = None
        if payload:
            result.update(payload)
            result["text_before"] = text[:idx].strip()
            return result

    result["text_before"] = text.strip()
    return result

def _store_voice_response(user_id: str, response_text: str) -> str:
    payload = _extract_emails_payload(response_text or "")
    response_id = str(uuid.uuid4())
    VOICE_RESPONSE_CACHE[response_id] = {
        "user_id": user_id,
        "response_text": response_text or "",
        "emails": payload.get("emails"),
        "insights": payload.get("insights"),
        "text_before": payload.get("text_before") or "",
    }
    logger.info(
        "Stored voice response %s (emails=%s).",
        response_id,
        len(payload.get("emails") or []) if isinstance(payload.get("emails"), list) else "none",
    )
    if len(VOICE_RESPONSE_CACHE) > VOICE_RESPONSE_CACHE_MAX:
        oldest_key = next(iter(VOICE_RESPONSE_CACHE))
        VOICE_RESPONSE_CACHE.pop(oldest_key, None)
    return response_id

def _is_email_heavy_response(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    if "```json" in lowered:
        return True
    if "📧" in text:
        return True
    keyword_hits = sum(k in lowered for k in ["from:", "subject:", "date:"])
    if keyword_hits >= 2:
        return True
    if "here are your" in lowered and "email" in lowered:
        return True
    if "emails about" in lowered and "date:" in lowered:
        return True
    return False

def _build_voice_summary(text: str) -> str:
    if not text:
        return ""
    lowered = text.lower()
    provider = None
    if "outlook" in lowered:
        provider = "Outlook"
    elif "gmail" in lowered:
        provider = "Gmail"

    provider_phrase = f" from your {provider} account" if provider else ""

    if "didn't find" in lowered or "no emails" in lowered or "couldn't find" in lowered:
        first = re.split(r"[\n\.]", text.strip(), 1)[0].strip()
        return first or "I didn't find any emails."
    if "here are" in lowered and "email" in lowered:
        return f"Here are your emails{provider_phrase} on the screen."
    if "i found" in lowered and "email" in lowered:
        return f"I found some emails{provider_phrase}. They're shown on the screen."
    return f"Here are your emails{provider_phrase} on the screen."

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

    logger.info("STT transcript=%r", transcript)
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
    logger.info("TTS reply_text=%r, bytes=%d", text, len(wav_bytes))
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

    normalized_transcript = _normalize_transcript(transcript)
    if normalized_transcript != transcript:
        logger.info(
            "Voice STT normalized transcript (%s chars): %s",
            len(normalized_transcript),
            normalized_transcript[:200],
        )
    else:
        logger.info("Voice STT transcript (%s chars): %s", len(transcript), transcript[:200])

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
            normalized_transcript,
            context_message,
        )
    logger.info("Voice response (%s chars).", len(response_text or ""))

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

    tts_text = response_text or ""
    if _is_email_heavy_response(response_text):
        first_line = ""
        for line in (response_text or "").splitlines():
            if line.strip():
                first_line = line.strip()
                break
        if first_line and not first_line.lstrip().startswith("```") and not first_line.lstrip().startswith("["):
            tts_text = first_line
        else:
            tts_text = _build_voice_summary(response_text)
    logger.info("Voice TTS text (%s chars): %s", len(tts_text or ""), tts_text[:200])

    response_id = _store_voice_response(user_id, response_text)

    if not tts_text:
        return JSONResponse(
            {
                "transcript": transcript,
                "response_text": response_text or "",
                "session_id": sid,
            }
        )

    audio_out, mime = await deepgram_tts(tts_text)
    logger.info("Voice TTS audio bytes: %s", len(audio_out))

    # Return audio for immediate playback + useful metadata in headers
    safe_transcript = _safe_header_value(normalized_transcript, max_len=200)
    safe_full_transcript = _safe_header_value(normalized_transcript, max_len=2000)
    safe_reply = _safe_header_value(response_text, max_len=2000)
    safe_tts = _safe_header_value(tts_text, max_len=2000)

    return Response(
        content=audio_out,
        media_type=mime,
        headers={
            "X-Session-Id": sid,
            "X-Transcript": safe_transcript,
            "X-User-Transcript": safe_full_transcript,
            "X-Assistant-Reply": safe_reply,
            "X-Assistant-Tts": safe_tts,
            "X-Voice-Response-Id": response_id,
        },
    )

@router.get("/response/{response_id}")
async def get_voice_response(
    response_id: str, user_id: str = Header(..., alias="X-User-Id")
):
    payload = VOICE_RESPONSE_CACHE.get(response_id)
    if not payload or payload.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="Voice response not found")
    return JSONResponse(
        {
            "response_text": payload.get("response_text", ""),
            "emails": payload.get("emails"),
            "insights": payload.get("insights"),
            "text_before": payload.get("text_before", ""),
        }
    )
