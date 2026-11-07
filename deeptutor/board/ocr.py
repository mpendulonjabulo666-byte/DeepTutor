"""Read a scanned PDF (photos of pages) with Gemini.

Used only when a PDF has no text layer. The pages are sent to Google using the
Gemini key already set for DeepTutor, ten pages at a time.
"""

from __future__ import annotations

import base64
import io
import time
from typing import Any, Callable

PAGES_PER_CALL = 10
MAX_PAGES = 120
_PROMPT = (
    "Transcribe all the text on these pages exactly as written. Keep headings, numbers, "
    "units, lists and tables as plain text, one line per row. Do not describe pictures. "
    "Do not add commentary. If a page has no text, write nothing for it."
)


class OcrUnavailable(RuntimeError):
    """OCR cannot run (not a Gemini setup, or the key is missing)."""


def _gemini_settings() -> tuple[str, str]:
    from deeptutor.services.llm.config import get_llm_config

    cfg = get_llm_config()
    name = f"{cfg.binding} {cfg.provider_name}".lower()
    if "gemini" not in name:
        raise OcrUnavailable("Reading scanned PDFs needs Gemini to be your configured model.")
    key = cfg.api_key[0] if isinstance(cfg.api_key, list) else cfg.api_key
    if not key:
        raise OcrUnavailable("No Gemini key is set. Set it and apply your settings again.")
    return cfg.model.removeprefix("models/"), key


def _split(data: bytes) -> list[bytes]:
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(io.BytesIO(data))
    pages = reader.pages
    if len(pages) > MAX_PAGES:
        raise OcrUnavailable(
            f"That PDF has {len(pages)} pages. The limit is {MAX_PAGES}; split it."
        )
    parts: list[bytes] = []
    for start in range(0, len(pages), PAGES_PER_CALL):
        writer = PdfWriter()
        for page in pages[start : start + PAGES_PER_CALL]:
            writer.add_page(page)
        buf = io.BytesIO()
        writer.write(buf)
        parts.append(buf.getvalue())
    return parts


def _call(
    model: str,
    key: str,
    pdf: bytes,
    post: Callable[..., Any],
    prompt: str = _PROMPT,
    mime: str = "application/pdf",
) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {
        "contents": [
            {
                "parts": [
                    {
                        "inline_data": {
                            "mime_type": mime,
                            "data": base64.b64encode(pdf).decode(),
                        }
                    },
                    {"text": prompt},
                ]
            }
        ],
        "generationConfig": {"temperature": 0},
    }
    last = ""
    for wait in (0, 5, 15, 30):
        if wait:
            time.sleep(wait)
        resp = post(url, headers={"x-goog-api-key": key}, json=body, timeout=180)
        if resp.status_code == 200:
            data = resp.json()
            parts = (data.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
            return "\n".join(str(p.get("text", "")) for p in parts)
        last = f"HTTP {resp.status_code}"
        if resp.status_code not in (429, 500, 503):
            try:
                last += ": " + str(resp.json()["error"]["message"])[:200]
            except Exception:
                pass
            break
    raise OcrUnavailable(f"Gemini could not read the pages ({last}). Try again in a minute.")


def ocr_pdf_with_gemini(data: bytes, post: Callable[..., Any] | None = None) -> str:
    """Return the text of a scanned PDF, or raise OcrUnavailable."""
    import httpx

    model, key = _gemini_settings()
    send = post or httpx.post
    return "\n\n".join(_call(model, key, part, send) for part in _split(data))


_PICTURE_PROMPT = (
    "This is a teaching picture chosen by a tutor. List the parts, labels and numbers you can "
    "actually see, as a short plain list (name: what it shows). Do not guess what is not visible. "
    "No introduction, no more than 120 words."
)


def describe_picture_with_gemini(data: bytes, mime: str, post: Callable[..., Any] | None = None) -> str:
    """Return a short list of what a picture shows, or raise OcrUnavailable."""
    import httpx

    model, key = _gemini_settings()
    return _call(model, key, data, post or httpx.post, _PICTURE_PROMPT, mime).strip()[:900]
