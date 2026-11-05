"""Optical Character Recognition (OCR) Service.

Provides text extraction from scanned PDFs and medical document images
using RapidOCR (ONNX runtime) with optional pytesseract fallback.
"""

from __future__ import annotations

import io
import logging
import os
import shutil
from typing import Optional

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Global cached instance of RapidOCR engine
_RAPID_OCR_ENGINE = None
_RAPID_OCR_AVAILABLE = True


def get_ocr_engine():
    """Lazily initialize and return the RapidOCR engine singleton."""
    global _RAPID_OCR_ENGINE, _RAPID_OCR_AVAILABLE
    if _RAPID_OCR_ENGINE is None and _RAPID_OCR_AVAILABLE:
        try:
            from rapidocr_onnxruntime import RapidOCR
            _RAPID_OCR_ENGINE = RapidOCR()
            logger.info("RapidOCR engine initialized successfully")
        except Exception as exc:
            _RAPID_OCR_AVAILABLE = False
            logger.warning("Could not initialize RapidOCR: %s", exc)
    return _RAPID_OCR_ENGINE


def _clean_ocr_text(text: str) -> str:
    """Normalize OCR text whitespace while preserving lines and medical content."""
    text = text.replace("\x00", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in text.split("\n")]
    return "\n".join(lines).strip()


def ocr_image(img_input: np.ndarray | bytes | Image.Image) -> str:
    """Run OCR on a single image input (numpy array, raw bytes, or PIL Image).

    Returns extracted text string, or empty string on failure.
    """
    if img_input is None:
        return ""

    # Convert PIL Image to numpy array if needed
    if isinstance(img_input, Image.Image):
        try:
            img_arr = np.array(img_input.convert("RGB"))
        except Exception as exc:
            logger.warning("Failed to convert PIL Image to numpy array: %s", exc)
            return ""
    elif isinstance(img_input, bytes):
        try:
            pil_img = Image.open(io.BytesIO(img_input)).convert("RGB")
            img_arr = np.array(pil_img)
        except Exception as exc:
            logger.warning("Failed to open image bytes for OCR: %s", exc)
            return ""
    elif isinstance(img_input, np.ndarray):
        img_arr = img_input
    else:
        logger.warning("Unsupported image input type for OCR: %s", type(img_input))
        return ""

    engine = get_ocr_engine()
    if engine is not None:
        try:
            results, _ = engine(img_arr)
            if results:
                # results is a list of [box_coords, text, confidence]
                extracted_lines = []
                for item in results:
                    if len(item) > 1 and item[1]:
                        cleaned = str(item[1]).strip()
                        if cleaned:
                            extracted_lines.append(cleaned)
                if extracted_lines:
                    return _clean_ocr_text("\n".join(extracted_lines))
        except Exception as exc:
            logger.warning("RapidOCR execution error: %s", exc)

    # Optional fallback: pytesseract if installed and binary present
    try:
        import pytesseract
        tesseract_cmd = shutil.which("tesseract") or (
            r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            if os.path.exists(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
            else None
        )
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
            pil_img = Image.fromarray(img_arr)
            text = pytesseract.image_to_string(pil_img)
            if text and text.strip():
                return _clean_ocr_text(text)
    except Exception:
        pass

    return ""


def ocr_pdf(content: bytes, max_pages: int = 50) -> tuple[str, int]:
    """Extract text from scanned PDF pages via rendering and OCR.

    Returns (combined_text, pages_processed).
    """
    if not content:
        return "", 0

    page_texts: list[str] = []
    pages_processed = 0

    # Primary strategy: render PDF pages to images using pypdfium2
    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(content)
        total_pages = len(pdf)
        pages_to_read = min(total_pages, max_pages)

        for i in range(pages_to_read):
            page = pdf[i]
            # scale=2.0 (approx 144 DPI) gives optimal OCR accuracy and speed
            bitmap = page.render(scale=2.0)
            img_arr = bitmap.to_numpy()
            text = ocr_image(img_arr)
            pages_processed += 1
            if text:
                page_texts.append(text)

        if page_texts:
            return _clean_ocr_text("\n\n".join(page_texts)), pages_processed
    except Exception as exc:
        logger.warning("pypdfium2 OCR extraction failed: %s", exc)

    # Secondary strategy: extract embedded images directly from pypdf
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(content))
        for page_idx, page in enumerate(reader.pages[:max_pages]):
            pages_processed = max(pages_processed, page_idx + 1)
            for img_file in page.images:
                try:
                    text = ocr_image(img_file.data)
                    if text:
                        page_texts.append(text)
                except Exception as img_exc:
                    logger.warning("Failed to OCR embedded image: %s", img_exc)

        if page_texts:
            return _clean_ocr_text("\n\n".join(page_texts)), pages_processed
    except Exception as exc:
        logger.warning("pypdf fallback image extraction failed: %s", exc)

    return _clean_ocr_text("\n\n".join(page_texts)), pages_processed
