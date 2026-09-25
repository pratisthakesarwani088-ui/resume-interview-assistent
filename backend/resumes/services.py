"""
PDF text extraction for uploaded resumes, using PyMuPDF (imported as `fitz`).
Kept as a small standalone function so it's easy to test and to swap out later.
"""

import fitz  # PyMuPDF


class PDFExtractionError(Exception):
    """Raised when a file that passed upload validation still can't be parsed."""


def extract_text_from_pdf(file_path):
    """
    Open the PDF at `file_path` and return (text, page_count).
    Raises PDFExtractionError for corrupt/unreadable/encrypted files.
    """
    try:
        doc = fitz.open(file_path)
    except Exception as exc:  # PyMuPDF raises its own exception types
        raise PDFExtractionError(f"Could not open PDF: {exc}") from exc

    try:
        if doc.is_encrypted:
            raise PDFExtractionError("PDF is password-protected.")

        page_count = doc.page_count
        text_parts = [page.get_text() for page in doc]
    finally:
        doc.close()

    text = "\n\n".join(part.strip() for part in text_parts).strip()

    if not text:
        raise PDFExtractionError(
            "No extractable text found in this PDF (it may be a scanned image)."
        )

    return text, page_count
