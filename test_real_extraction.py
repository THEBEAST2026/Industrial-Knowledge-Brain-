import sys
import asyncio
import json
sys.path.insert(0, "ingestion")

from table_parser import parse_csv_xlsx
from entity_extractor import extract_entities

async def main():
    chunks = parse_csv_xlsx("sample_docs/maintenance_worklog.csv", "worklog")
    print(f"{len(chunks)} chunks parsed from worklog CSV")

    # Test on just the first 5 chunks first — cheap, fast, easy to eyeball
    test_chunks = chunks[:5]
    results = await asyncio.gather(*[extract_entities(c) for c in test_chunks])

    for r in results:
        print(f"\nChunk: {r.chunk_id}")
        print(f"  Entities found: {len(r.entities)}")
        for e in r.entities:
            print(f"    - {e.entity_type}: {e.value} -> {e.normalized_value} (conf: {e.confidence})")
        print(f"  Relationships: {r.relationships}")

    total_entities = sum(len(r.entities) for r in results)
    print(f"\nTotal: {len(test_chunks)} chunks -> {total_entities} entities extracted")

if __name__ == "__main__":
    asyncio.run(main())