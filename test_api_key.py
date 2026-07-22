import os
from dotenv import load_dotenv
import httpx

load_dotenv()

api_key = os.environ.get("OPENROUTER_API_KEY")
if not api_key:
    print("OPENROUTER_API_KEY is not set in this terminal session.")
    print("Run: $env:OPENROUTER_API_KEY = 'your_key_here'  then try again.")
else:
    resp = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": "nousresearch/hermes-3-llama-3.1-405b",
            "messages": [{"role": "user", "content": "Say hello in one word."}],
        },
    )
    print(resp.status_code)
    print(resp.json())