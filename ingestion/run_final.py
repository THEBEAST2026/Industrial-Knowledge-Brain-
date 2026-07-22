import sys
import asyncio
import json
import os
sys.path.insert(0, "ingestion")

from table_parser import parse_csv_xlsx
from pdf_parser import parse_pdf
from drawing_parser import parse_drawing_image
from entity_extractor import extract_entities


async def extract_and_save(chunks, label, out_path):
    print(f"\n[{label}] Extracting entities from {len(chunks)} chunks...")
    results = await asyncio.gather(*[extract_entities(c) for c in chunks])
    total_entities = sum(len(r.entities) for r in results)
    print(f"[{label}] Done: {total_entities} entities extracted -> {out_path}")

    os.makedirs("sample_docs/extracted", exist_ok=True)
    with open(out_path, "w") as f:
        json.dump([r.dict() for r in results], f, indent=2)
    return results


async def main():
    # 1. Worklog CSV (41 chunks — you already tested this works)
    worklog_chunks = parse_csv_xlsx("sample_docs/maintenance_worklog.csv", "worklog")
    await extract_and_save(worklog_chunks, "worklog",
                            "sample_docs/extracted/worklog_entities_live.json")

    # 2. Procedure PDF (267 chunks from your earlier test)
    procedure_chunks = parse_pdf("sample_docs/OISD-STANDARD-144.pdf", "procedure")
    await extract_and_save(procedure_chunks, "procedure",
                            "sample_docs/extracted/procedure_entities_live.json")

    # Note: ai4i2020 worklog (399 rows) and P&ID/inspection are handled
    # separately below since they need different treatment — see comments.

    print("\nDone with worklog + procedure. Run the ai4i2020 CSV separately")
    print("(it's large — 399 rows — so it costs more; test worklog quality first).")


if __name__ == "__main__":
    asyncio.run(main())