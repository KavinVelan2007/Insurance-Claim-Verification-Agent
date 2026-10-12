"""PDF text extraction with PyMuPDF + scanned-page detection.

Strategy (accuracy/speed):
- PyMuPDF text extraction is ~100x faster than a VLM and near-perfect on
  digital PDFs, so it is ALWAYS tried first.
- A page with < 50 text chars is treated as scanned/image-only.
- Scanned pages are rendered to PNG and sent to a LOCAL Ollama VLM
  (moondream/llava/qwen2.5vl…) ONLY if one is installed; otherwise the page
  is flagged so the API can fail gracefully instead of hallucinating.
"""
import base64
import io
from typing import Tuple, List

try:
    import pymupdf as fitz  # PyMuPDF (modern import; `import fitz` is deprecated)
    _HAS_FITZ = True
except ImportError:
    try:
        import fitz  # type: ignore # fallback for older installs
        _HAS_FITZ = True
    except ImportError:  # allow API import before PyMuPDF install finishes
        fitz = None  # type: ignore
        _HAS_FITZ = False

SCANNED_CHAR_THRESHOLD = 50


def extract_pages(pdf_bytes: bytes) -> Tuple[str, List[int], List[bytes]]:
    """Return (full_text, scanned_page_numbers, scanned_page_pngs)."""
    if not _HAS_FITZ:
        raise RuntimeError("PyMuPDF not installed yet — install with `pip install PyMuPDF`.")
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    texts: List[str] = []
    scanned_idx: List[int] = []
    scanned_pngs: List[bytes] = []
    for i, page in enumerate(doc):
        t = page.get_text("text") or ""
        texts.append(t)
        if len(t.strip()) < SCANNED_CHAR_THRESHOLD:
            scanned_idx.append(i)
            pix = page.get_pixmap(dpi=150)
            scanned_pngs.append(pix.tobytes("png"))
    doc.close()
    return "\n\n".join(texts), scanned_idx, scanned_pngs


def png_to_b64(png: bytes) -> str:
    return base64.b64encode(png).decode("ascii")


def is_pdf(pdf_bytes: bytes) -> bool:
    return pdf_bytes[:5] == b"%PDF-"
