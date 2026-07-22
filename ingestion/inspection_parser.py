import fitz
import re
import hashlib
from typing import List
def parse_inspection_report(filepath: str, doc_type: str = "inspection") -> List[dict]:
    doc = fitz.open(filepath)
    full_text = ""
    for page in doc:
        full_text += page.get_text("text") + "\n"
 
    # Split into per-unit blocks using the "Page 1 of N ... SN: xxxxx" header,
    # which reliably marks the start of each equipment unit's report — more
    # robust than the report title, which has inconsistent internal spacing.
    unit_blocks = re.split(r"(?=Page 1 of \d+\s+Compressor inspection)", full_text)
    unit_blocks = [b.strip() for b in unit_blocks if b.strip()]
 
    chunks = []
    for i, block in enumerate(unit_blocks):
        serial_match = re.search(r"Serial\s*nr\s*:\s*(\S+)", block, re.IGNORECASE)
        serial = serial_match.group(1) if serial_match else f"unit-{i}"
        chunk_id = hashlib.md5(f"{filepath}-{serial}".encode()).hexdigest()[:12]
        chunks.append({
            "chunk_id": chunk_id,
            "source_doc": filepath,
            "doc_type": doc_type,
            "content": block,
            "unit_ref": serial,
            "page_number": None
        })
    return chunks
 
 
if __name__ == "__main__":
    import json
    chunks = parse_inspection_report("sample_docs/3769_-_Mycom_200SUD-HE_rapport.pdf")
    print(f"Parsed {len(chunks)} equipment-unit chunks")
    for c in chunks:
        print(f"  - {c['unit_ref']}: {len(c['content'])} chars")
    with open("sample_docs/inspection_chunks.json", "w") as f:
        json.dump(chunks, f, indent=2)
    print("Saved to sample_docs/inspection_chunks.json")