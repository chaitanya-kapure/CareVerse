"""HTTP response helpers shared by more than one controller.

The PDF response lives here rather than inside the patient document controller
because Phase 3 serves the same bytes to an authorized doctor. Two copies of
this would be two places where a security header could be added on one path
and forgotten on the other, and the file endpoint is exactly the route where
that difference would be silent.
"""

from urllib.parse import quote

from fastapi.responses import Response


def pdf_response(content: bytes, mime: str, filename: str) -> Response:
    """Return stored PDF bytes for display in the browser.

    The headers are not decoration:

    * `nosniff` stops a browser from re-interpreting the bytes as something
      other than the type we declared.
    * The CSP confines any active content inside the PDF. A patient-supplied
      file is untrusted input, and rendering it against our own origin is the
      one way a PDF could reach the rest of the application.
    * `no-store` keeps a patient's medical document out of shared caches and
      out of the browser's disk cache, so it cannot outlive the session that
      was allowed to read it.
    """
    ascii_fallback = "".join(
        char if 32 <= ord(char) < 127 and char not in '"\\' else "_"
        for char in filename
    ) or "document.pdf"

    return Response(
        content=content,
        media_type=mime,
        headers={
            "Content-Disposition": (
                f'inline; filename="{ascii_fallback}"; '
                f"filename*=UTF-8''{quote(filename, safe='')}"
            ),
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; object-src 'self'",
            "Cache-Control": "private, no-store",
        },
    )
