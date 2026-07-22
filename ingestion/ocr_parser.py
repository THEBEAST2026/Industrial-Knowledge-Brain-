import pytesseract
from pdf2image import convert_from_path
from schemas import Chunk
import hashlib

def parse_scanned_pdf(filepath: str, doc_type: str) -> list[Chunk]:
    images = convert_from_path(filepath)
    chunks = []
    for page_num, img in enumerate(images):
        text = pytesseract.image_to_string(img)
        paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 30]
        for i, para in enumerate(paragraphs):
            chunk_id = hashlib.md5(f"{filepath}-ocr-{page_num}-{i}".encode()).hexdigest()[:12]
            chunks.append(Chunk(
                chunk_id=chunk_id, source_doc=filepath, doc_type=doc_type,
                content=para, page_number=page_num + 1
            ))
    return chunks