import json
import queue
import sounddevice as sd
from vosk import Model, KaldiRecognizer
import httpx
import asyncio
import numpy as np
import os
from dotenv import load_dotenv

MODEL_PATH = "vosk-model-small-en-us-0.15"
SAMPLE_RATE = 16000

q = queue.Queue()

load_dotenv()
DG_API_KEY = os.getenv("DEEPGRAM_API_KEY")

async def tts_deepgram(text):
    url = "https://api.deepgram.com/v1/speak?model=aura-asteria-en&encoding=linear16&sample_rate=24000"

    headers = {
        "Authorization": f"Token {DG_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {"text": text}

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(url, headers=headers, json=payload)

    # ✅ BU ARTIK GERÇEK PCM16 AUDIO
    audio_bytes = r.content

    audio_np = np.frombuffer(audio_bytes, dtype=np.int16)

    sd.play(audio_np, samplerate=24000)
    sd.wait()


def callback(indata, frames, time, status):
    q.put(bytes(indata))

async def send_to_chatbot(text):
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.post(
            "http://localhost:8001/chat",
            json={"message": text}
        )
    return res.json()["response"]

if __name__ == "__main__":
    model = Model(MODEL_PATH)
    rec = KaldiRecognizer(model, SAMPLE_RATE)

    with sd.RawInputStream(
        samplerate=SAMPLE_RATE,
        blocksize=8000,
        dtype='int16',
        channels=1,
        callback=callback
    ):
        print("Start speaking:\n")
        while True:
            data = q.get()
            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                text = result.get("text", "")
                if text:
                    print("Prompt:", text)

                    reply = asyncio.run(send_to_chatbot(text))
                    print("\nResponse:", reply)
                    asyncio.run(tts_deepgram(reply))

