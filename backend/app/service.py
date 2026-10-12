from typing import Tuple
from .models import ParsedDocument, ItemizedCharge
from .extractor import extract_pages, is_pdf, png_to_b64
from . import llm as llm_mod
from .fallback import fallback_parse
from .config import settings
from .service_a import _coerce


def parse_one_pdf(pdf_bytes: bytes, filename: str) -> Tuple[ParsedDocument, str]:
    """Full pipeline for one PDF. Returns (doc, model_used). Raises ValueError."""
    if not is_pdf(pdf_bytes):
        raise ValueError(f"{filename}: not a PDF (magic bytes mismatch).")
    if len(pdf_bytes) > settings.max_upload_mb * 1024 * 1024:
        raise ValueError(f"{filename}: exceeds {settings.max_upload_mb} MB limit.")
    text, scanned_idx, scanned_pngs = extract_pages(pdf_bytes)
    method = "text+llm"
    if scanned_idx:
        vlm = llm_mod.pick_vision_model()
        if vlm is None:
            fb = fallback_parse(text)
            fb["warnings"] = (fb.get("warnings") or []) + [
                f"{len(scanned_idx)} scanned page(s) with no OCR/VLM available; "
                "text may be incomplete. Install tesseract or pull a vision model "
                "(e.g. `ollama pull moondream`)."]
            return _coerce(fb, filename, "regex-fallback", len(text)), settings.ollama_model
        ocr_bits = []
        for png in scanned_pngs:
            try:
                ocr_bits.append(llm_mod.vlm_ocr_page(png_to_b64(png), vlm))
            except Exception as e:
                ocr_bits.append(f"[VLM OCR failed: {e}]")
        text = text + "\n\n[VLM OCR of scanned pages]\n" + "\n".join(ocr_bits)
        method = f"vlm({vlm})+llm"
    try:
        data = llm_mod.llm_extract(text, filename)
    except Exception as e:
        fb = fallback_parse(text)
        fb["warnings"] = (fb.get("warnings") or []) + [f"LLM call failed ({e}); regex fallback."]
        return _coerce(fb, filename, "regex-fallback", len(text)), settings.ollama_model
    if "_parse_error" in data:
        fb = fallback_parse(text)
        fb["warnings"] = (fb.get("warnings") or []) + ["LLM JSON invalid; regex fallback."]
        return _coerce(fb, filename, "regex-fallback", len(text)), settings.ollama_model
    return _coerce(data, filename, method, len(text)), settings.ollama_model
