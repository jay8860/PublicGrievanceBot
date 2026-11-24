"""Shared OpenRouter client (vision + text) for backend features.

``bot.py`` keeps its own copy for the citizen flow so the bot stays independently
deployable; the backend needs the same primitives for before/after verification
and must not import a Telegram module to get them.
"""
import base64
import io
import json
import logging
from typing import Iterable, Optional

import requests
from PIL import Image

from config import get_env

logger = logging.getLogger(__name__)

API_KEY = get_env("OPENROUTER_API_KEY")
MODEL = get_env("OPENROUTER_MODEL", "google/gemini-2.0-flash-001")
BASE_URL = get_env("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/")
TIMEOUT = int(get_env("OPENROUTER_TIMEOUT_SECONDS", "60"))
MAX_IMAGE_PX = 1024


def image_to_data_url(image_bytes: bytes, max_px: int = MAX_IMAGE_PX) -> str:
    """Normalise any upload to a small RGB JPEG data URL."""
    image = Image.open(io.BytesIO(image_bytes))
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    image.thumbnail((max_px, max_px))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def extract_json(text: str) -> dict:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else ""
        if cleaned.rstrip().endswith("```"):
            cleaned = cleaned.rstrip()[:-3]
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        raise ValueError(f"model did not return JSON: {text!r}")
    return json.loads(cleaned[start:end + 1])


def chat(messages: list, *, model: Optional[str] = None, max_tokens: int = 900,
         temperature: float = 0.1) -> str:
    if not API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not set")
    resp = requests.post(
        f"{BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json",
                 "X-Title": "District Grievance Platform"},
        json={"model": model or MODEL, "messages": messages, "max_tokens": max_tokens,
              "temperature": temperature},
        timeout=TIMEOUT,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"OpenRouter HTTP {resp.status_code}: {resp.text[:300]}")
    payload = resp.json()
    choices = payload.get("choices") or []
    if not choices:
        raise RuntimeError(f"OpenRouter returned no choices: {str(payload)[:300]}")
    content = (choices[0].get("message") or {}).get("content")
    if isinstance(content, list):
        content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
    return content or ""


def vision_prompt(prompt: str, images: Iterable[bytes]) -> list:
    """Build an OpenAI-style multimodal user message."""
    content = [{"type": "text", "text": prompt}]
    for raw in images:
        content.append({"type": "image_url", "image_url": {"url": image_to_data_url(raw)}})
    return [{"role": "user", "content": content}]
