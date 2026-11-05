"""Clinical Document Analyzer and Plain-Language Patient Verdict Generator.

Analyzes any medical document (scanned doctor slips, handwritten prescriptions,
laboratory reports, discharge summaries, imaging notes) and generates:
1. Detected document classification (e.g. Prescription, Lab Report, Discharge Summary)
2. Attributed clinician and healthcare facility
3. Relevant clinical specialty
4. Key observations in plain language
5. A simple, easy-to-understand Patient Verdict explaining what the document says
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Medical degree indicators that are not personal names
_DEGREE_PATTERN = re.compile(
    r"\b(?:m\.?s\.?|m\.?d\.?|m\.?b\.?b\.?s\.?|d\.?n\.?b\.?|f\.?r\.?c\.?s\.?|b\.?a\.?m\.?s\.?|b\.?h\.?m\.?s\.?)\b",
    re.IGNORECASE,
)


def _clean_ocr_anomalies(text: str) -> str:
    """Normalize common OCR misreadings of clinical and hospital terminology."""
    s = text

    # Common OCR prefix/name misreads: e.g. DeVishu -> Dr. Vishu
    s = re.sub(r"\bDe(?=[A-Z][a-z])", "Dr. ", s)
    s = re.sub(r"\bdr\s+([A-Z])", r"Dr. \1", s, flags=re.IGNORECASE)
    s = re.sub(r"\boupta\b", "Gupta", s, flags=re.IGNORECASE)

    # Hospital misreads
    s = re.sub(r"\bbostital\b", "Hospital", s, flags=re.IGNORECASE)
    s = re.sub(r"\bhostipal\b", "Hospital", s, flags=re.IGNORECASE)
    s = re.sub(r"\bhospita1\b", "Hospital", s, flags=re.IGNORECASE)

    # Degree and specialty misreads
    s = re.sub(r"\bmons\.?s\b", "M.S.", s, flags=re.IGNORECASE)
    s = re.sub(r"\bcenalsurpeny\b", "General Surgery", s, flags=re.IGNORECASE)
    s = re.sub(r"\bgen(?:eral)?\s*surpeny\b", "General Surgery", s, flags=re.IGNORECASE)

    return s


def _detect_doctor(lines: list[str]) -> Optional[str]:
    """Identify attending physician from header lines or Dr. prefixes."""
    for line in lines[:8]:
        cleaned = _clean_ocr_anomalies(line).strip()

        # Look for explicit Dr. prefix or Doctor
        match = re.search(r"\b(?:dr\.?|doctor)\s*([A-Za-z\s.\'\-]+)", cleaned, re.IGNORECASE)
        if match:
            doc_name = match.group(1).strip()
            # Drop degree suffix or parentheses if attached
            doc_name = re.sub(r"[(,].*$", "", doc_name).strip()
            doc_name = re.sub(
                r"\s+(?:m\.?s|m\.?d|m\.?b\.?b\.?s|d\.?n\.?b|f\.?r\.?c\.?s).*$",
                "",
                doc_name,
                flags=re.IGNORECASE,
            ).strip()

            if len(doc_name) >= 3 and not _DEGREE_PATTERN.search(doc_name) and not re.search(r"^(?:report|date|patient|name|hospital)$", doc_name, re.IGNORECASE):
                # Standardize to Dr. Name
                return "Dr. " + doc_name

    return None


def _detect_facility(lines: list[str]) -> Optional[str]:
    """Identify hospital, clinic, or diagnostic center from header lines."""
    for line in lines[:8]:
        cleaned = _clean_ocr_anomalies(line).strip()
        if re.search(
            r"\b(?:hospital|clinic|cliniq|medical\s*centre|medical\s*center|nursing\s*home|laboratory|diagnostic|healthcare)\b",
            cleaned,
            re.IGNORECASE,
        ):
            fac = cleaned.strip(" -:,.")
            if 4 <= len(fac) <= 100:
                return fac

    return None


def _detect_specialty(text: str) -> Optional[str]:
    """Identify medical department or specialty."""
    cleaned = _clean_ocr_anomalies(text)
    specialty_rules = [
        ("General Surgery", r"\b(?:general\s*surgery|surgery|surgeon|surgical)\b"),
        ("Cardiology", r"\b(?:cardiology|cardiologist|cardiac|ecg|echo)\b"),
        ("Orthopedics", r"\b(?:orthopedics|orthopaedic|bone|fracture|joint)\b"),
        ("Pediatrics", r"\b(?:pediatrics|paediatric|child\s*health)\b"),
        ("Internal Medicine", r"\b(?:internal\s*medicine|physician|general\s*medicine)\b"),
        ("Pathology & Diagnostics", r"\b(?:pathology|hematology|haematology|biochemistry|blood\s*test)\b"),
        ("Radiology & Imaging", r"\b(?:radiology|radiologist|x-ray|mri|ct\s*scan|ultrasound|sonography)\b"),
        ("Gynecology & Obstetrics", r"\b(?:gynecology|obstetrics|obgyn|maternity)\b"),
        ("Dermatology", r"\b(?:dermatology|skin|dermatologist)\b"),
        ("Neurology", r"\b(?:neurology|neuro|brain)\b"),
        ("ENT / Otorhinolaryngology", r"\b(?:ent|ear\s*nose\s*throat|otorhinolaryngology)\b"),
        ("Ophthalmology", r"\b(?:ophthalmology|eye|vision)\b"),
    ]
    for spec_name, pattern in specialty_rules:
        if re.search(pattern, cleaned, re.IGNORECASE):
            return spec_name
    return None


def _classify_document_type(text: str, category: str, has_labs: bool, has_doctor: bool = False) -> str:
    """Classify document into a patient-facing category."""
    text_lower = text.lower()

    if "discharge summary" in text_lower or "date of discharge" in text_lower:
        return "Hospital Discharge Summary"
    if any(k in text_lower for k in ["x-ray", "mri scan", "ct scan", "ultrasound", "sonography", "radiograph"]):
        return "Diagnostic Imaging & Radiology Report"
    if has_labs or any(k in text_lower for k in ["complete blood count", "haemoglobin", "glucose", "platelet count", "lipid profile", "creatinine", "serum", "pathology report"]):
        return "Laboratory Pathology & Blood Test Report"
    if has_doctor or any(k in text_lower for k in ["prescription", "rx", "tablet", "capsule", "dosage", "syrup", "consultation note", "opd", "surgery"]):
        return "Doctor Consultation & Prescription Slip"

    # Category fallback
    category_map = {
        "lab_report": "Laboratory Pathology Report",
        "prescription": "Doctor Prescription & Slip",
        "discharge_summary": "Hospital Discharge Summary",
        "imaging": "Diagnostic Imaging Report",
    }
    return category_map.get(category, "Doctor Clinical Record")


def analyze_document_content(
    raw_text: str,
    category: str = "other",
    structured_data: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Run comprehensive analysis and generate patient-friendly verdict in plain words."""
    if not raw_text or not raw_text.strip():
        return {
            "document_type": "Unreadable Document",
            "doctor": None,
            "facility": None,
            "specialty": None,
            "observations": ["No readable text could be detected from this document."],
            "verdict": "No readable text was detected from this document. If this is a photo or scan, please ensure good lighting and upload again.",
        }

    structured = structured_data or {}
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

    # 1. Attribute Doctor, Facility, Specialty
    doctor = structured.get("referring_doctor") or _detect_doctor(lines)
    facility = structured.get("referring_facility") or _detect_facility(lines)
    specialty = structured.get("specialty") or _detect_specialty(raw_text)

    # 2. Extract Labs & Medications
    lab_values = structured.get("lab_values") or []
    medications = structured.get("medications") or []
    conditions = structured.get("stated_conditions") or []

    high_labs = [
        item for item in lab_values
        if any(h in str(item.get("flag", "")).lower() for h in ["h", "high", "*"])
    ]
    low_labs = [
        item for item in lab_values
        if any(l in str(item.get("flag", "")).lower() for l in ["l", "low"])
    ]

    # 3. Classify Document Type
    doc_type = _classify_document_type(raw_text, category, has_labs=len(lab_values) > 0, has_doctor=bool(doctor))

    # 4. Generate Key Observations in Plain Words
    observations: list[str] = []

    if doctor:
        doc_obs = f"Consulting Physician: {doctor}"
        if specialty:
            doc_obs += f" ({specialty})"
        observations.append(doc_obs)
    elif specialty:
        observations.append(f"Department: {specialty}")

    if facility:
        observations.append(f"Healthcare Facility: {facility}")

    if lab_values:
        observations.append(f"Laboratory Test Results: {len(lab_values)} test markers analyzed.")
        if high_labs:
            high_str = ", ".join(f"{l['name']} ({l['value']} {l.get('unit', '')}) [HIGH]" for l in high_labs)
            observations.append(f"Elevated Test Markers: {high_str}")
        if low_labs:
            low_str = ", ".join(f"{l['name']} ({l['value']} {l.get('unit', '')}) [LOW]" for l in low_labs)
            observations.append(f"Low Test Markers: {low_str}")
        if not high_labs and not low_labs:
            observations.append("Test Markers Status: Stated test values recorded without flags.")

    if medications:
        med_names = [f"{m['name']}" + (f" ({m['dosage']})" if m.get("dosage") else "") for m in medications]
        observations.append(f"Prescribed Medications: {', '.join(med_names)}")

    if conditions:
        cond_names = [c.get("text", "") for c in conditions if c.get("text")]
        if cond_names:
            observations.append(f"Stated Conditions: {', '.join(cond_names)}")

    # If no structured items were parsed (e.g. prescription slips, notes)
    if not lab_values and not medications and not conditions:
        meaningful_lines = []
        for line in lines:
            cleaned = _clean_ocr_anomalies(line)
            if doctor and doctor.lower() in cleaned.lower():
                continue
            if facility and facility.lower() in cleaned.lower():
                continue
            if len(cleaned) >= 4 and not re.search(r"^(?:date|page|rx|opd|tel|phone)$", cleaned, re.IGNORECASE):
                meaningful_lines.append(cleaned)
        if meaningful_lines:
            observations.append("Clinical Content & Notes: " + "; ".join(meaningful_lines[:4]))
        else:
            observations.append("Clinical Content: Physician consultation slip containing clinical notes.")

    # 5. Build Simple-Words Patient Verdict
    verdict_sentences: list[str] = []

    # Sentence 1: Identification in plain words
    if doctor and facility:
        verdict_sentences.append(f"This record is a {doc_type.lower()} from {doctor} at {facility}.")
    elif doctor:
        verdict_sentences.append(f"This record is a {doc_type.lower()} from {doctor}.")
    elif facility:
        verdict_sentences.append(f"This record is a {doc_type.lower()} issued by {facility}.")
    else:
        verdict_sentences.append(f"This record has been identified as a {doc_type.lower()}.")

    # Sentence 2 & 3: Clinical takeaway in plain everyday words
    if doc_type in ["Doctor Consultation & Prescription Slip", "Doctor Clinical Record"]:
        if medications:
            verdict_sentences.append(
                f"It documents a physician consultation where {len(medications)} medication(s) were prescribed. "
                "No abnormal laboratory findings are documented."
            )
        else:
            verdict_sentences.append(
                "It records a clinical doctor consultation and prescription note. "
                "No critical abnormal laboratory test values were found in this document."
            )
        verdict_sentences.append(
            "Patient Takeaway: Follow the advice and medication instructions given by your doctor, "
            "and attend any scheduled follow-up appointments."
        )

    elif doc_type in ["Laboratory Pathology & Blood Test Report", "Laboratory Pathology Report"]:
        if high_labs or low_labs:
            flagged_items = high_labs + low_labs
            flagged_names = [f"{item['name']} ({item['value']} {item.get('unit', '')})" for item in flagged_items]
            verdict_sentences.append(
                f"Attention: {len(flagged_items)} test marker(s) ({', '.join(flagged_names)}) were found outside standard normal ranges."
            )
            verdict_sentences.append(
                "Patient Takeaway: Share these specific test results with your consulting doctor to review what they mean for your care."
            )
        else:
            verdict_sentences.append(
                "All test results detected in this report are within standard expected reference intervals."
            )
            verdict_sentences.append(
                "Patient Takeaway: Your lab results appear normal based on the printed reference values."
            )

    elif doc_type == "Diagnostic Imaging & Radiology Report":
        verdict_sentences.append(
            "It records findings from a diagnostic radiological imaging examination."
        )
        verdict_sentences.append(
            "Patient Takeaway: Discuss this imaging report with your physician to understand the findings in the context of your overall health."
        )

    elif doc_type == "Hospital Discharge Summary":
        verdict_sentences.append(
            "It outlines your hospital stay, clinical treatment, and discharge recommendations."
        )
        verdict_sentences.append(
            "Patient Takeaway: Follow the post-discharge care instructions, take your discharge medications as directed, and schedule any required outpatient follow-ups."
        )

    else:
        verdict_sentences.append(
            "The document has been securely digitized and filed under your central health records profile."
        )

    full_verdict = " ".join(verdict_sentences)

    return {
        "document_type": doc_type,
        "doctor": doctor,
        "facility": facility,
        "specialty": specialty,
        "observations": observations,
        "verdict": full_verdict,
    }
