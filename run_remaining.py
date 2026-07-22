import sys
import asyncio
import json
import os
sys.path.insert(0, "ingestion")

from table_parser import parse_csv_xlsx
from drawing_parser import parse_drawing_image
from inspection_parser import parse_inspection_report
from entity_extractor import extract_entities
from schemas import Chunk


async def extract_and_save(chunks, label, out_path):
    print(f"\n[{label}] Extracting entities from {len(chunks)} chunks...")
    results = await asyncio.gather(*[extract_entities(c) for c in chunks])
    total_entities = sum(len(r.entities) for r in results)
    print(f"[{label}] Done: {total_entities} entities extracted -> {out_path}")
    os.makedirs("sample_docs/extracted", exist_ok=True)
    with open(out_path, "w") as f:
        json.dump([r.model_dump() for r in results], f, indent=2)
    return results


async def main():
    # 1. Worklog CSV — CRITICAL, has the TANK-01 patch for cross-doc demo
    worklog_chunks = parse_csv_xlsx("sample_docs/maintenance_worklog.csv", "worklog")
    await extract_and_save(worklog_chunks, "worklog",
                            "sample_docs/extracted/output_worklog_maintenance_worklog.json")

    # 2. P&ID drawing
    pid_chunks = parse_drawing_image("sample_docs/pid_cropped.png")
    await extract_and_save(pid_chunks, "drawing",
                            "sample_docs/extracted/output_drawing_pid_cropped.json")

    # 3. Inspection report (different chunk shape — convert to Chunk objects)
    raw_chunks = parse_inspection_report("sample_docs/3769_-_Mycom_200SUD-HE_rapport.pdf")
    inspection_chunks = [Chunk(chunk_id=c["chunk_id"], source_doc=c["source_doc"],
                                doc_type="inspection", content=c["content"]) for c in raw_chunks]
    await extract_and_save(inspection_chunks, "inspection",
                            "sample_docs/extracted/output_inspection_live.json")

    print("\nALL 3 REMAINING DOCUMENTS PROCESSED.")


if __name__ == "__main__":
    asyncio.run(main())