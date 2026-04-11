import os
import time
import asyncio
from typing import Optional
from groq import AsyncGroq
from langsmith import traceable

_groq_client: Optional[AsyncGroq] = None


def get_groq_client() -> AsyncGroq:
    global _groq_client
    if _groq_client is None:
        _groq_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
    return _groq_client


@traceable(name="llm_call")
async def call_llm(
    prompt: str,
    system_prompt: str = "You are Munshi, a helpful AI assistant for Indian business owners.",
    model: str = "llama-3.3-70b-versatile",
    max_tokens: int = 500,
    temperature: float = 0.7,
) -> str:
    """Call Groq LLM with retry logic and LangSmith tracing."""
    client = get_groq_client()

    async def _call() -> str:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return response.choices[0].message.content or ""

    try:
        return await _call()
    except Exception:
        await asyncio.sleep(2)
        try:
            return await _call()
        except Exception:
            return "Kuch technical issue hai, thodi der mein try karein."


@traceable(name="whisper_transcribe")
async def transcribe_audio(audio_path: str) -> str:
    """Transcribe audio using Groq Whisper."""
    client = get_groq_client()
    try:
        with open(audio_path, "rb") as f:
            response = await client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=f,
                response_format="text",
            )
        return response if isinstance(response, str) else response.text
    except Exception:
        return ""
