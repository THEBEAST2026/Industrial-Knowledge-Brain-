"""
Entity extraction via Hermes (OpenRouter). Includes the error handling and
concurrency control the build guide called for — a single failed/rate-
limited request returns an empty result instead of crashing the whole batch.
"""
import os
import json
import asyncio
import httpx
from dotenv import load_dotenv
from schemas import Chunk, ExtractionResult

load_dotenv()  # reads OPENROUTER_API_KEY from a .env file in the project root,
                # so you don't need to re-run $env:OPENROUTER_API_KEY every
                # time you open a new terminal

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "nousresearch/hermes-3-llama-3.1-405b"

EXTRACTION_PROMPT = """Extract entities from this industrial document chunk.
Return ONLY valid JSON, no markdown, no preamble.

Schema:
{{
  "entities": [
    {{"entity_type": "Equipment|Permit|Person|Regulation|Incident|Parameter|Date",
      "value": "as written", "normalized_value": "standardized form", "confidence": 0.0-1.0}}
  ],
  "relationships": [
    {{"from": "entity value", "to": "entity value", "type": "MAINTAINED_BY|LOCATED_IN|REFERENCES|FAILED_ON"}}
  ]
}}

Example:
Text: "Permit HW-2291 issued for hot work near TK-102 on 14 March 2026, approved by Shift Engineer R. Nair."
Output: {{"entities": [
  {{"entity_type":"Permit","value":"HW-2291","normalized_value":"HW-2291","confidence":0.95}},
  {{"entity_type":"Equipment","value":"TK-102","normalized_value":"TK-102","confidence":0.95}},
  {{"entity_type":"Date","value":"14 March 2026","normalized_value":"2026-03-14","confidence":0.9}},
  {{"entity_type":"Person","value":"R. Nair","normalized_value":"R. NAIR","confidence":0.85}}
], "relationships": [{{"from":"HW-2291","to":"TK-102","type":"REFERENCES"}}]}}

Now extract from this chunk (doc_type={doc_type}):
{content}
"""


_semaphore = asyncio.Semaphore(3)


async def extract_entities(chunk: Chunk) -> ExtractionResult:
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        print(f"  [{chunk.chunk_id}] SKIPPED — OPENROUTER_API_KEY not set")
        return ExtractionResult(chunk_id=chunk.chunk_id, entities=[], relationships=[])

    prompt = EXTRACTION_PROMPT.format(doc_type=chunk.doc_type, content=chunk.content)

    async with _semaphore:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    OPENROUTER_URL,
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1,
                        "max_tokens": 800,
                    },
                )

            body = resp.json()

           
            if resp.status_code != 200 or "choices" not in body:
                error_info = body.get("error", body)
                print(f"  [{chunk.chunk_id}] API ERROR (status {resp.status_code}): {error_info}")
                return ExtractionResult(chunk_id=chunk.chunk_id, entities=[], relationships=[])

            raw = body["choices"][0]["message"]["content"]
            clean = raw.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(clean)

           
            raw_entities = parsed.get("entities", [])
            entities = []
            for e in raw_entities:
                e["value"] = str(e.get("value", ""))
                e["normalized_value"] = str(e.get("normalized_value", ""))
                e["chunk_id"] = chunk.chunk_id
                entities.append(e)

            relationships = parsed.get("relationships", [])

            return ExtractionResult(chunk_id=chunk.chunk_id, entities=entities, relationships=relationships)

        except json.JSONDecodeError as e:
            print(f"  [{chunk.chunk_id}] JSON parse failed: {e} — raw content was: {raw[:200] if 'raw' in dir() else 'N/A'}")
            return ExtractionResult(chunk_id=chunk.chunk_id, entities=[], relationships=[])
        except httpx.TimeoutException:
            print(f"  [{chunk.chunk_id}] Request timed out")
            return ExtractionResult(chunk_id=chunk.chunk_id, entities=[], relationships=[])
        except Exception as e:
            print(f"  [{chunk.chunk_id}] Unexpected error: {type(e).__name__}: {e}")
            return ExtractionResult(chunk_id=chunk.chunk_id, entities=[], relationships=[])