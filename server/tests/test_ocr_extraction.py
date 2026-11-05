"""Unit tests for OCR service and scanned document text extraction."""

import io
import pytest
import numpy as np
from PIL import Image, ImageDraw

from app.services import extraction_service, ocr_service
from app.services.structured_extraction import extract_structured


def _create_test_scanned_pdf(lines: list[str]) -> bytes:
    """Create a synthesized PDF that contains an image with rendered text."""
    img = Image.new("RGB", (900, 450), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    y = 30
    for line in lines:
        d.text((30, y), line, fill=(0, 0, 0))
        y += 45

    buf = io.BytesIO()
    img.save(buf, format="PDF")
    return buf.getvalue()


def test_ocr_extracts_text_from_scanned_pdf():
    """A PDF that contains only an image should have its text extracted by OCR."""
    pdf_bytes = _create_test_scanned_pdf([
        "Report: Complete Blood Count",
        "Report Date: 2025-11-02",
        "Haemoglobin: 14.2 g/dL",
        "Glucose: 126 mg/dL (70-99) H",
        "Metformin 500 mg twice daily",
    ])

    outcome = extraction_service.extract_text(pdf_bytes)

    assert outcome["extraction_status"] == "completed"
    assert outcome["extracted_text"] is not None
    text = outcome["extracted_text"]
    assert "Glucose" in text or "126" in text or "Metformin" in text or "Blood" in text
    assert outcome["character_count"] > 10

    # Verify structured extraction runs cleanly on the OCR output
    structured = extract_structured(text)
    assert structured is not None
    # We should have at least lab_values, medications, or document metadata
    has_extracted_data = (
        bool(structured.get("lab_values"))
        or bool(structured.get("medications"))
        or bool(structured.get("document_date"))
        or bool(structured.get("report_title"))
    )
    assert has_extracted_data


def test_ocr_extracts_text_from_image_bytes():
    """Direct image bytes should be readable by OCR service."""
    img = Image.new("RGB", (800, 200), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((30, 40), "Prescription: Amoxicillin 500 mg TID", fill=(0, 0, 0))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    text = ocr_service.ocr_image(buf.getvalue())

    assert "Amoxicillin" in text or "500" in text or "Prescription" in text


def test_blank_pdf_still_reports_needs_ocr():
    """A truly blank PDF with no text and no image text should return needs_ocr."""
    img = Image.new("RGB", (300, 300), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PDF")
    blank_pdf_bytes = buf.getvalue()

    outcome = extraction_service.extract_text(blank_pdf_bytes)
    assert outcome["extraction_status"] == "needs_ocr"
    assert outcome["extracted_text"] is None


def test_clinical_analyzer_extracts_verdict_for_non_numeric_prescription_slip():
    """A clinic slip with no numeric values must still generate doctor, facility, specialty, and plain-English verdict."""
    from app.services.clinical_analyzer import analyze_document_content

    slip_text = (
        "DeVishu Oupta\n"
        "VY BOSTITAL\n"
        "Mons.s(CenalSurpeny)\n"
        "Calssh\n"
        "Paruhsy\n"
    )

    result = analyze_document_content(slip_text, category="prescription")

    assert result["document_type"] == "Doctor Consultation & Prescription Slip"
    assert result["doctor"] == "Dr. Vishu Gupta"
    assert result["facility"] == "VY Hospital"
    assert result["specialty"] == "General Surgery"
    assert "verdict" in result
    assert "Dr. Vishu Gupta" in result["verdict"]
    assert "VY Hospital" in result["verdict"]
    assert len(result["observations"]) > 0


def test_clinical_analyzer_extracts_verdict_for_lab_report():
    """A lab report must produce plain-English verdict with high/low flags highlighted."""
    from app.services.clinical_analyzer import analyze_document_content

    lab_text = (
        "City General Hospital\n"
        "Complete Blood Count\n"
        "Glucose 126 mg/dL (70-99) H\n"
        "Haemoglobin 14.2 g/dL\n"
    )
    structured = {
        "lab_values": [
            {"name": "Glucose", "value": "126", "unit": "mg/dL", "flag": "high"},
            {"name": "Haemoglobin", "value": "14.2", "unit": "g/dL", "flag": "normal"},
        ]
    }

    result = analyze_document_content(lab_text, category="lab_report", structured_data=structured)

    assert result["document_type"] == "Laboratory Pathology & Blood Test Report"
    assert "Attention" in result["verdict"] or "Glucose" in result["verdict"]
    assert len(result["observations"]) > 0
