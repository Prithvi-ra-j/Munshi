import os
import httpx
from typing import Optional

WAHA_API_URL = os.getenv("WAHA_API_URL", "http://localhost:3000")
WAHA_SESSION = os.getenv("WAHA_SESSION", "default")


async def send_text_message(phone: str, text: str) -> bool:
    """Send a text message via WAHA."""
    api_url = os.getenv("WAHA_API_URL", "http://localhost:3000")
    session = os.getenv("WAHA_SESSION", "default")
    api_key = os.getenv("WAHA_API_KEY", "munshi-secret")
    url = f"{api_url}/api/sendText"
    clean_phone = phone.replace("@c.us", "").replace("@lid", "").replace("@s.whatsapp.net", "")
    payload = {"session": session, "chatId": f"{clean_phone}@c.us", "text": text}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload, headers={"X-Api-Key": api_key})
            return resp.status_code in (200, 201)
    except Exception:
        return False


async def download_media(media_url: str, dest_path: str) -> bool:
    """Download media file from WAHA to local path."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(media_url)
            if resp.status_code == 200:
                with open(dest_path, "wb") as f:
                    f.write(resp.content)
                return True
        return False
    except Exception:
        return False


async def get_session_status() -> Optional[str]:
    """Get WAHA session status."""
    api_url = os.getenv("WAHA_API_URL", "http://localhost:3000")
    session = os.getenv("WAHA_SESSION", "default")
    url = f"{api_url}/api/sessions/{session}"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("status", "unknown")
        return "disconnected"
    except Exception:
        return "disconnected"
