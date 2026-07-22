import os
import httpx
import json

api_key = os.environ.get("OPENROUTER_API_KEY")
print("API key set:", bool(api_key))
print("API key starts with:", api_key[:15] if api_key else "N/A")

prompt = """Extract entities from this industrial document chunk.
Return ONLY valid JSON, no markdown, no preamble.

Chunk (doc_type=worklog):
work_order_id: WO-1001, equipment_tag: PUMP-04B, work_type: Preventive
"""

resp = httpx.post(
    "https://openrouter.ai/api/v1/chat/completions",
    headers={"Authorization": f"Bearer {api_key}"},
    json={
        "model": "nousresearch/hermes-3-llama-3.1-405b",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
    },
    timeout=30,
)

print("\nStatus code:", resp.status_code)
print("\nFull response body:")
print(json.dumps(resp.json(), indent=2))