import site
import sys
sys.path.insert(0, "/home/sarthak/arova")
import requests
import json
import logging

original_post = requests.post

def intercept_post(url, *args, **kwargs):
    if "api.groq.com" in url:
        if "json" in kwargs:
            with open("/home/sarthak/arova/last_groq_payload.json", "w") as f:
                json.dump(kwargs["json"], f, indent=2)
    return original_post(url, *args, **kwargs)

requests.post = intercept_post

# Now we need to trigger a chat stream.
# But we can't easily trigger the whole daemon from a script.
# Instead, let's just patch it in the actual daemon.
