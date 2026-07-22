

# Update this to match your Tesseract install path
TESSERACT_CMD_PATH = r'C:\Users\Admin\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'

# Update this to match your extracted Poppler folder's Library\bin subfolder
POPPLER_PATH = r'C:\Users\Admin\Downloads\Release-26.02.0-0.zip\poppler-26.02.0\Library\bin'


def configure_tesseract():
    """Call this once at the top of any script that uses pytesseract."""
    import pytesseract
    import os
    if TESSERACT_CMD_PATH and os.path.exists(TESSERACT_CMD_PATH):
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD_PATH
    elif TESSERACT_CMD_PATH:
        print(f"WARNING: Tesseract not found at {TESSERACT_CMD_PATH} — "
              f"check your install path in ingestion/config.py")