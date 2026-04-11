import os
import tempfile
from app.state import MunshiState
from app.waha_client import download_media
from app.llm_client import transcribe_audio


async def transcription_agent(state: MunshiState) -> MunshiState:
    """Transcribe audio messages or pass through text messages."""
    if state["message_type"] != "audio":
        state["processed_text"] = state["raw_message"]
        return state

    audio_url = state.get("audio_url")
    if not audio_url:
        state["processed_text"] = state["raw_message"]
        state["agent_errors"].append("audio_url missing for audio message")
        return state

    # Download audio to temp file
    tmp_path = tempfile.mktemp(suffix=".ogg")
    downloaded = await download_media(audio_url, tmp_path)

    if not downloaded:
        state["processed_text"] = ""
        state["final_response"] = "Voice note ki samajh nahi aaya, please text karein"
        state["agent_errors"].append("Failed to download audio")
        return state

    try:
        transcribed = await transcribe_audio(tmp_path)
        if transcribed:
            state["transcribed_text"] = transcribed
            state["processed_text"] = transcribed
        else:
            state["final_response"] = "Voice note ki samajh nahi aaya, please text karein"
            state["agent_errors"].append("Transcription returned empty")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    return state
