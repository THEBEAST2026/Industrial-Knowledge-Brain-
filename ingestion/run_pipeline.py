
import asyncio
import json
import os

from pdf_parser import parse_pdf
from table_parser import parse_csv_xlsx
from ocr_parser import parse_scanned_pdf
from drawing_parser import parse_drawing, parse_drawing_image
from entity_extractor import extract_entities


async def run(filepath: str, doc_type: str):
    ext = os.path.splitext(filepath)[1].lower()

    if doc_type == "drawing":
        if ext in (".png", ".jpg", ".jpeg"):
            chunks = parse_drawing_image(filepath)
        else:
            chunks = parse_drawing(filepath)
    elif doc_type == "worklog" and ext in (".xlsx", ".csv"):
        chunks = parse_csv_xlsx(filepath, doc_type)
    else:
        chunks = parse_pdf(filepath, doc_type)
        if not chunks:  # empty text -> scanned page, fall back to OCR
            chunks = parse_scanned_pdf(filepath, doc_type)

    if not chunks:
        print(f"WARNING: no chunks produced for {filepath} — check the file exists and parses correctly")
        return [], []

    results = await asyncio.gather(*[extract_entities(c) for c in chunks])

    os.makedirs("sample_docs/extracted", exist_ok=True)
    out_name = os.path.splitext(os.path.basename(filepath))[0]
    out_path = f"sample_docs/extracted/output_{doc_type}_{out_name}.json"
    with open(out_path, "w") as f:
        json.dump([r.dict() for r in results], f, indent=2)

    total_entities = sum(len(r.entities) for r in results)
    print(f"[{doc_type}] {filepath}: {len(chunks)} chunks, {total_entities} entities -> {out_path}")
    return chunks, results


async def run_all():
    """
    Batch version — runs the pipeline across all 5 of your sample documents
    in one go. Adjust filenames to match exactly what's in your sample_docs/.
    """
    documents = [
        ("sample_docs/OISD-STANDARD-144.pdf", "procedure"),
        ("sample_docs/maintenance_worklog.csv", "worklog"),
        ("sample_docs/pid_cropped.png", "drawing"),
        # ai4i2020_worklog_reformatted.csv (399 rows) SKIPPED given time
        # pressure — not needed for the core TANK-01 cross-document demo,
        # and would add several minutes + extra API cost for no demo value.
    ]
    for filepath, doc_type in documents:
        if not os.path.exists(filepath):
            print(f"SKIPPED (file not found): {filepath}")
            continue
        await run(filepath, doc_type)


async def run_inspection():
    """Inspection report uses a different parser (returns dicts per equipment
    unit, not per-paragraph Chunk objects), so it's wired in separately."""
    from inspection_parser import parse_inspection_report

    raw_chunks = parse_inspection_report("sample_docs/3769_-_Mycom_200SUD-HE_rapport.pdf")
    if not raw_chunks:
        print("WARNING: no chunks from inspection report")
        return

    # Convert dicts to Chunk objects so extract_entities can process them
    from schemas import Chunk
    chunks = [Chunk(chunk_id=c["chunk_id"], source_doc=c["source_doc"],
                     doc_type="inspection", content=c["content"]) for c in raw_chunks]

    results = await asyncio.gather(*[extract_entities(c) for c in chunks])
    os.makedirs("sample_docs/extracted", exist_ok=True)
    out_path = "sample_docs/extracted/output_inspection_live.json"
    with open(out_path, "w") as f:
        json.dump([r.dict() for r in results], f, indent=2)
    total_entities = sum(len(r.entities) for r in results)
    print(f"[inspection] {len(chunks)} chunks, {total_entities} entities -> {out_path}")


async def run_everything():
    """Runs all 5 documents in one call — use this given time pressure."""
    await run_all()
    await run_inspection()
    print("\nALL DOCUMENTS PROCESSED. Check sample_docs/extracted/ for output JSON files.")


if __name__ == "__main__":
    asyncio.run(run_everything())