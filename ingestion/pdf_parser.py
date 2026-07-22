import fitz  # PyMuPDF
from schemas import Chunk
import hashlib

def parse_pdf(filepath: str, doc_type: str) -> list[Chunk]:
    doc = fitz.open(filepath)
    chunks = []
    for page_num, page in enumerate(doc):
        text = page.get_text("text")
        if not text.strip():
            continue  # likely scanned — route to OCR
        paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 30]
        for i, para in enumerate(paragraphs):
            chunk_id = hashlib.md5(f"{filepath}-{page_num}-{i}".encode()).hexdigest()[:12]
            chunks.append(Chunk(
                chunk_id=chunk_id,
                source_doc=filepath,
                doc_type=doc_type,
                content=para,
                page_number=page_num + 1
            ))
    return chunks