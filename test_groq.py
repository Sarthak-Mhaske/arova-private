import requests
import json
import os

api_key = "placeholder" # Wait, I don't have the API key! The user's adapter pulls it from config.

def test():
    import sys
    sys.path.append("/home/sarthak/arova")
    from arova.core.config.manager import OSConfigManager
    cfg = OSConfigManager().load_providers()
    groq_keys = cfg.get("groq", {}).get("api_keys", [])
    if not groq_keys:
        print("No groq keys")
        return
    api_key = groq_keys[0]

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "openai/gpt-oss-120b",
        "messages": [{"role": "system", "content": "Return json."}, {"role": "user", "content": "Hi"}],
        "response_format": {"type": "json_object"}
    }
    res = requests.post(url, headers=headers, json=payload)
    print("Status:", res.status_code)
    print("Response:", res.text)

test()
