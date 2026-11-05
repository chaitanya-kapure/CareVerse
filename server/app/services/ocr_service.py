"""Optical Character Recognition (OCR) Service.

Provides text extraction from scanned PDFs and medical document images
using RapidOCR (ONNX runtime) with optional pytesseract fallback.
"""

from __future__ import annotations

import base64
import io
import logging
import os
import shutil
from typing import Optional

import httpx
import numpy as np
from PIL import Image, ImageEnhance, ImageOps

from app.config import settings

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



def _get_gemini_api_key() -> Optional[str]:
    """Retrieve Gemini API key from settings or environment."""
    key = getattr(settings, "gemini_api_key", None) or settings.ai_api_key
    if key and key.strip():
        if getattr(settings, "ai_provider", "").lower() == "gemini" or key.strip().startswith("AIza"):
            return key.strip()
    # Check direct environment variables
    for env_var in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        val = os.environ.get(env_var)
        if val and val.strip():
            return val.strip()
    return None


def _preprocess_image_for_ocr(pil_img: Image.Image) -> Image.Image:
    """Enhance image contrast and dynamic range for improved OCR accuracy."""
    try:
        gray = pil_img.convert("L")
        contrast = ImageOps.autocontrast(gray, cutoff=2)
        sharp = ImageEnhance.Sharpness(contrast).enhance(1.4)
        return sharp.convert("RGB")
    except Exception:
        return pil_img


def _ocr_image_with_gemini(pil_img: Image.Image, api_key: str) -> Optional[str]:
    """Transcribe clinical documents and doctor handwriting using Gemini Multimodal Vision."""
    try:
        buf = io.BytesIO()
        pil_img.save(buf, format="JPEG", quality=90)
        img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        model_name = "gemini-1.5-flash"
        if getattr(settings, "ai_model", "") and "gemini" in settings.ai_model:
            model_name = settings.ai_model

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"

        prompt = (
            "You are an expert clinical document transcriber and medical pharmacist. "
            "Accurately transcribe all printed and handwritten text in this medical document exactly as written. "
            "Carefully decipher doctor cursive handwriting, prescriptions (medication names, dosages, formulations, frequencies, durations), "
            "patient demographics (name, age, sex, weight, date), and clinical examination notes. "
            "Preserve original layout, test names, and numbers. Do not invent or fabricate information. "
            "Return only the transcribed text without conversational commentary."
        )

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": img_b64,
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.0,
                "maxOutputTokens": 2048,
            },
        }

        with httpx.Client(timeout=35.0) as client:
            resp = client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    texts = [p.get("text", "") for p in parts if "text" in p]
                    result = "\n".join(texts).strip()
                    if result:
                        logger.info("Gemini Vision transcribed %d characters successfully", len(result))
                        return _clean_ocr_text(result)
            else:
                logger.warning("Gemini Vision request returned status %d: %s", resp.status_code, resp.text[:200])
    except Exception as exc:
        logger.warning("Gemini Vision transcription failed: %s", exc)

    return None

def ocr_image(img_input: np.ndarray | bytes | Image.Image) -> str:
    """Run OCR on a single image input (numpy array, raw bytes, or PIL Image).

    Returns extracted text string, or empty string on failure.
    """
    if img_input is None:
        return ""

    # Prepare PIL image and numpy array
    pil_img: Optional[Image.Image] = None
    if isinstance(img_input, Image.Image):
        pil_img = img_input.convert("RGB")
    elif isinstance(img_input, bytes):
        try:
            pil_img = Image.open(io.BytesIO(img_input)).convert("RGB")
        except Exception as exc:
            logger.warning("Failed to open image bytes for OCR: %s", exc)
            return ""
    elif isinstance(img_input, np.ndarray):
        try:
            pil_img = Image.fromarray(img_input).convert("RGB")
        except Exception:
            pass
    else:
        logger.warning("Unsupported image input type for OCR: %s", type(img_input))
        return ""

    # Strategy 1: High-accuracy Gemini Vision if configured
    gemini_key = _get_gemini_api_key()
    if gemini_key and pil_img is not None:
        gemini_text = _ocr_image_with_gemini(pil_img, gemini_key)
        if gemini_text:
            return gemini_text

    # Strategy 2: Preprocess and run local RapidOCR
    if pil_img is not None:
        processed_img = _preprocess_image_for_ocr(pil_img)
        img_arr = np.array(processed_img)
    elif isinstance(img_input, np.ndarray):
        img_arr = img_input
    else:
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
            # scale=2.5 (approx 144 DPI) gives optimal OCR accuracy and speed
            bitmap = page.render(scale=2.5)
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
