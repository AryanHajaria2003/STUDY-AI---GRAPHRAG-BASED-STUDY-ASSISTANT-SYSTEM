
import pymupdf
import pytesseract
import re

from PIL import Image
from io import BytesIO
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4

pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)


def clean_text(text):
    text = text.replace("\x00", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_metadata(filename, total_pages, title=None):
    return {
        "document_id": str(uuid4()),
        "filename": filename,
        "title": title or filename,
        "total_pages": total_pages,
        "processed_at": datetime.now(timezone.utc).isoformat()
    }


def process_document(file_path):
    file_path = Path(file_path)
    extension = file_path.suffix.lower()
    pages = []
    title = file_path.name

    if extension == ".pdf":
        doc = pymupdf.open(str(file_path))
        title = doc.metadata.get("title") or file_path.name

        for number, page in enumerate(doc, start=1):
            text = page.get_text("text")

            if len(text.strip()) < 30:
                pix = page.get_pixmap(dpi=200)
                image = Image.open(BytesIO(pix.tobytes("png")))
                text = pytesseract.image_to_string(image)

            pages.append({
                "page_number": number,
                "text": clean_text(text)
            })

        total_pages = len(doc)
        doc.close()

    elif extension in [".png", ".jpg", ".jpeg"]:
        image = Image.open(file_path).convert("RGB")
        text = pytesseract.image_to_string(image)

        pages.append({
            "page_number": 1,
            "text": clean_text(text)
        })

        total_pages = 1

    else:
        raise ValueError("Unsupported file format.")

    metadata = extract_metadata(
        file_path.name,
        total_pages,
        title
    )

    return {
        "metadata": metadata,
        "pages": pages
    }


# Keep compatibility with the previous PDF function.
def process_pdf(pdf_path):
    return process_document(pdf_path)
