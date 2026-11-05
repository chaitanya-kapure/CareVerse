"""HTTP response helpers shared by more than one controller."""

from urllib.parse import quote

from fastapi.responses import Response


def pdf_response(content: bytes, mime: str, filename: str) -> Response:
    """Return stored PDF bytes for display in the browser."""
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
