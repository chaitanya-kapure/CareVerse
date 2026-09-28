"""PDF byte fixtures built in-process.

No PDF is committed to this repository. The suite is public and a real
medical document must never enter git -- even as a "sample", even as a
screenshot, even stripped of names. Every PDF the tests use is therefore
synthesised here from PDF primitives, containing only the string the test
passed in.

Two shapes are needed:

  * `text_pdf()`  -- a digitally generated PDF whose content stream carries
                     real extractable text, which is the `completed` path.
  * `blank_pdf()` -- a valid, well-formed PDF with no text at all, which is
                     the scanned-document `needs_ocr` path.

`corrupt_pdf()` covers the third: something that announces itself as a PDF
but cannot be parsed, for the `failed` path.
"""

from __future__ import annotations

# Escape rules for a literal string inside a PDF content stream. Only the
# two characters that PDF string syntax actually cares about are needed,
# because the fixtures never emit parentheses or backslashes themselves.
_PDF_ESCAPES = {"\\": r"\\", "(": r"\(", ")": r"\)"}


def _escape(text: str) -> str:
    return "".join(_PDF_ESCAPES.get(char, char) for char in text)


def _assemble(objects: list[str]) -> bytes:
    """Lay out PDF objects with a correct xref table.

    pypdf will read a file with a broken xref by rebuilding it, but a fixture
    that only works because the parser is forgiving would stop catching real
    regressions. Offsets are computed as the bytes are written, so the
    document is exactly what a viewer expects.
    """
    header = b"%PDF-1.4\n"
    body = bytearray()
    offsets: list[int] = []

    for number, obj in enumerate(objects, start=1):
        offsets.append(len(header) + len(body))
        body += f"{number} 0 obj\n{obj}\nendobj\n".encode("latin-1")

    xref_offset = len(header) + len(body)
    xref = f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"
    for offset in offsets:
        xref += f"{offset:010d} 00000 n \n"

    trailer = (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    )
    return header + bytes(body) + xref.encode("latin-1") + trailer.encode("latin-1")


def text_pdf(text: str = "Complete Blood Count  Haemoglobin 14.2 g/dL") -> bytes:
    """A one-page PDF with `text` drawn as extractable text."""
    # Every PDF string literal must not contain raw newlines; join with
    # spaces and draw each line separately so extraction still reads them.
    lines = [line for line in text.splitlines() if line.strip()] or [""]

    content_parts = ["BT", "/F1 12 Tf", "72 720 Td", "14 TL"]
    for index, line in enumerate(lines):
        if index:
            content_parts.append("T*")
        content_parts.append(f"({_escape(line)}) Tj")
    content_parts.append("ET")
    content_stream = "\n".join(content_parts)

    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            "/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"
        ),
        f"<< /Length {len(content_stream)} >>\nstream\n{content_stream}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    return _assemble(objects)


def blank_pdf(pages: int = 1) -> bytes:
    """A valid PDF with `pages` pages and no content on any of them.

    This is what a scan looks like to the extractor: the file opens, the page
    tree is well formed, and there is simply nothing written down.
    """
    page_ids = [3 + index * 2 for index in range(pages)]

    objects = ["<< /Type /Catalog /Pages 2 0 R >>"]
    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {pages} >>")

    # One Page object followed by its (empty) Contents object per page.
    for page_id in page_ids:
        contents_id = page_id + 1
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Contents {contents_id} 0 R >>"
        )
        objects.append("<< /Length 0 >>\nstream\nendstream")

    return _assemble(objects)


def corrupt_pdf() -> bytes:
    """Starts with the magic bytes, then falls apart.

    Used to prove that a file passing the type check can still fail during
    extraction, and that this degrades the document rather than the request.
    """
    return b"%PDF-1.4\nthis is not a pdf object graph at all\n%%EOF\n"


def oversized_pdf(padding_mb: int = 16) -> bytes:
    """A genuine PDF pushed past `MAX_UPLOAD_MB`.

    The padding is a PDF comment, which a parser reads to end-of-line and
    ignores, so the file stays valid throughout and the size cap is what
    rejects it -- not the type check getting there first and masking it.
    """
    base = text_pdf("Padding for the size limit test")
    body = b"%" + b"A" * (padding_mb * 1024 * 1024)
    # Splice before the final %%EOF so the trailer still terminates the file.
    return base[: base.rfind(b"%%EOF")] + body + b"\n%%EOF\n"
