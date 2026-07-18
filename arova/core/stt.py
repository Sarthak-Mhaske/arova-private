from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import requests

from arova.core.config.loader import pick_groq_api_key

def contains_arabic_or_urdu_script(text: str) -> bool:
    """Check if the text contains characters from Arabic/Urdu Unicode blocks."""
    # Arabic block is \u0600-\u06FF, Arabic Supplement is \u0750-\u077F
    # Arabic Extended-A is \u08A0-\u08FF.
    pattern = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]')
    return bool(pattern.search(text))

def needs_translation(text: str) -> bool:
    """Check if the text likely needs translation (contains non-ASCII characters)."""
    try:
        text.encode('ascii')
        return False
    except UnicodeEncodeError:
        return True

def _groq_audio_request(endpoint: str, audio_path: str, config: dict[str, Any], model_key: str, language: str | None = None, prompt: str | None = None) -> dict[str, Any]:
    """Base helper for Groq audio API calls."""
    key = pick_groq_api_key(config)
    if not key:
        return {
            "ok": False,
            "text": "",
            "error": "No Groq API key configured.",
            "language_hint_used": language,
            "raw": None
        }

    path = Path(audio_path)
    if not path.exists():
        return {
            "ok": False,
            "text": "",
            "error": f"Audio file not found: {audio_path}",
            "language_hint_used": language,
            "raw": None
        }

    groq_cfg = config.get("groq", {})
    default_model = "whisper-large-v3" if model_key == "translation_model" else "whisper-large-v3-turbo"
    model = groq_cfg.get(model_key, default_model)
    
    # Strictly override in-memory configs that still have turbo for translation
    if model_key == "translation_model" and "turbo" in model:
        model = "whisper-large-v3"

    headers = {
        "Authorization": f"Bearer {key}"
    }

    data = {
        "model": model,
        "response_format": "json"
    }
    
    if language:
        data["language"] = language
        
    if prompt:
        data["prompt"] = prompt

    try:
        with open(path, "rb") as f:
            files = {"file": (path.name, f, "audio/mpeg")}  # Generic audio mime works fine for API 
            response = requests.post(endpoint, headers=headers, data=data, files=files, timeout=30.0)
            
        raw = response.json()
        
        if response.status_code == 200 and "text" in raw:
            return {
                "ok": True,
                "text": raw["text"].strip(),
                "error": None,
                "language_hint_used": language,
                "raw": raw
            }
        else:
            return {
                "ok": False,
                "text": "",
                "error": f"Groq API Error: {response.status_code} - {raw.get('error', {}).get('message', 'Unknown error')}",
                "language_hint_used": language,
                "raw": raw
            }
            
    except Exception as e:
        return {
            "ok": False,
            "text": "",
            "error": f"Request failed: {str(e)}",
            "language_hint_used": language,
            "raw": None
        }

def transcribe_audio_file(audio_path: str, config: dict[str, Any], language: str | None = None, prompt: str | None = None) -> dict[str, Any]:
    """Transcribe an audio file using Groq's whisper model."""
    endpoint = "https://api.groq.com/openai/v1/audio/transcriptions"
    return _groq_audio_request(endpoint, audio_path, config, "stt_model", language=language, prompt=prompt)

def translate_audio_file(audio_path: str, config: dict[str, Any]) -> dict[str, Any]:
    """Translate an audio file to English using Groq's whisper model."""
    endpoint = "https://api.groq.com/openai/v1/audio/translations"
    # The translations endpoint doesn't support the 'language' param as it always translates to English.
    return _groq_audio_request(endpoint, audio_path, config, "translation_model", language=None)

def transcribe_with_retry_for_indic(audio_path: str, config: dict[str, Any]) -> dict[str, Any]:
    """
    First transcribe normally with a prompt to heavily bias towards Devanagari script.
    If Arabic/Urdu script is still hallucinated, retry forcing specific Indic languages.
    """
    res = transcribe_audio_file(audio_path, config, prompt="मराठी, हिंदी")
    
    if res["ok"] and contains_arabic_or_urdu_script(res["text"]):
        # Often Whisper hallucinates Arabic for Marathi. Force Marathi first.
        retry_mr = transcribe_audio_file(audio_path, config, language="mr")
        if retry_mr["ok"] and not contains_arabic_or_urdu_script(retry_mr["text"]):
            return retry_mr
            
        # Fallback to Hindi
        retry_hi = transcribe_audio_file(audio_path, config, language="hi")
        if retry_hi["ok"]:
            return retry_hi
            
    return res
