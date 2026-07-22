"""
P&ID / engineering drawing parser — extracts text regions with bounding
box coordinates via OCR. Deliberately simple (label + coordinate, not
real symbol detection) per the build guide's guidance not to over-engineer
the CV here.
"""
import hashlib
from pdf2image import convert_from_path
from schemas import Chunk
from config import configure_tesseract, POPPLER_PATH

configure_tesseract()

import pytesseract


def parse_drawing(filepath: str, doc_type: str = "drawing") -> list[Chunk]:
    convert_kwargs = {"dpi": 300}
    if POPPLER_PATH:
        convert_kwargs["poppler_path"] = POPPLER_PATH

    images = convert_from_path(filepath, **convert_kwargs)
    chunks = []
    for page_num, img in enumerate(images):
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        for i, text in enumerate(data["text"]):
            if len(text.strip()) < 2:
                continue
            bbox = [data["left"][i], data["top"][i],
                    data["left"][i] + data["width"][i], data["top"][i] + data["height"][i]]
            chunk_id = hashlib.md5(f"{filepath}-{page_num}-{i}".encode()).hexdigest()[:12]
            chunks.append(Chunk(chunk_id=chunk_id, source_doc=filepath, doc_type=doc_type,
                                 content=text.strip(), bbox=[float(x) for x in bbox],
                                 page_number=page_num + 1))
    return chunks


def parse_drawing_image(filepath: str, doc_type: str = "drawing") -> list[Chunk]:
    """
    For plain image files (PNG/JPG) rather than PDF drawings — e.g. your
    pid_cropped.png. Skips the PDF-to-image conversion step entirely.

    P&ID instrument tags are small text inside thin circles — Tesseract's
    default settings detect almost nothing on this kind of image. Two
    fixes applied here, confirmed necessary through testing:
      1. Upscale 3x before OCR (small text needs more pixels to resolve)
      2. Use --psm 11 (sparse text mode — finds scattered text blocks
         rather than assuming a uniform paragraph layout, which is what
         the default PSM mode assumes and why it finds nothing on a
         diagram with scattered labels).
    """
    from PIL import Image
    img = Image.open(filepath).convert("L")  # grayscale improves OCR reliability
    w, h = img.size
    img_upscaled = img.resize((w * 3, h * 3), Image.LANCZOS)

    data = pytesseract.image_to_data(img_upscaled, output_type=pytesseract.Output.DICT,
                                      config="--psm 11")
    chunks = []
    for i, text in enumerate(data["text"]):
        if len(text.strip()) < 2:
            continue
        # bbox coordinates are in the 3x upscaled image — divide by 3 to
        # map back to original image pixel space
        bbox = [data["left"][i] / 3, data["top"][i] / 3,
                (data["left"][i] + data["width"][i]) / 3,
                (data["top"][i] + data["height"][i]) / 3]
        chunk_id = hashlib.md5(f"{filepath}-{i}".encode()).hexdigest()[:12]
        chunks.append(Chunk(chunk_id=chunk_id, source_doc=filepath, doc_type=doc_type,
                             content=text.strip(), bbox=[float(x) for x in bbox]))
    return chunks