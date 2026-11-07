"""The tutor's own pictures: upload once, choose one for a board.

A picture is checked by its first bytes (not its file name), limited in size and
stored on this computer. When used, it is wrapped as an SVG that holds the image
as a data URI, so the board page still needs no network.
"""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path
import re
from typing import Any
import uuid

from .svg import UnsafeSvg, sanitize_svg

MAX_PICTURE_BYTES = 3 * 1024 * 1024
MAX_PICTURES = 60


class PictureError(ValueError):
    pass


def sniff(data: bytes) -> str:
    """Return png, jpeg, webp or svg from the file's own bytes."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    head = data[:2000].lstrip().lower()
    if head.startswith((b"<svg", b"<?xml")) and b"<svg" in data[:4000].lower():
        return "svg"
    raise PictureError("Upload a PNG, JPG, WEBP or SVG picture.")


def _size(data: bytes) -> tuple[int, int]:
    try:
        from PIL import Image

        with Image.open(io.BytesIO(data)) as im:
            return int(im.width), int(im.height)
    except Exception:
        return 800, 600


def wrap_as_svg(data: bytes, kind: str, label: str = "") -> str:
    """Return SVG text for the board page (raster pictures become an embedded image)."""
    if kind == "svg":
        try:
            return sanitize_svg(data.decode("utf-8", "replace"))
        except UnsafeSvg as exc:
            raise PictureError(f"That SVG is not safe to use: {exc}") from exc
    w, h = _size(data)
    mime = "jpeg" if kind == "jpeg" else kind
    b64 = base64.b64encode(data).decode("ascii")
    alt = re.sub(r"[<>&\"]", "", label)[:200]
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'viewBox="0 0 {w} {h}" role="img" aria-label="{alt}">'
        f'<image href="data:image/{mime};base64,{b64}" width="{w}" height="{h}"/></svg>'
    )


class PictureLibrary:
    def __init__(self, folder: Path | str) -> None:
        self.dir = Path(folder)
        self.dir.mkdir(parents=True, exist_ok=True)
        self._index = self.dir / "index.json"

    def list(self) -> list[dict[str, Any]]:
        try:
            data = json.loads(self._index.read_text("utf-8"))
        except (OSError, ValueError):
            return []
        return [d for d in data if isinstance(d, dict) and (self.dir / d.get("file", "")).is_file()]

    def add(self, filename: str, data: bytes, caption: str = "") -> dict[str, Any]:
        if not data or len(data) > MAX_PICTURE_BYTES:
            raise PictureError("That picture is empty or bigger than 3 MB.")
        kind = sniff(data)
        if kind == "svg":
            wrap_as_svg(data, kind)  # refuses unsafe svg now, not at build time
        items = self.list()
        if len(items) >= MAX_PICTURES:
            raise PictureError("Remove a picture first. The limit is 60.")
        pid = uuid.uuid4().hex[:12]
        file = f"{pid}.{kind}"
        (self.dir / file).write_bytes(data)
        name = Path(filename.replace("\\", "/")).name[:120] or file
        meta = {
            "id": pid,
            "file": file,
            "kind": kind,
            "name": name,
            "caption": " ".join(caption.split())[:300] or Path(name).stem.replace("-", " ")[:300],
        }
        self._index.write_text(json.dumps([*items, meta], indent=2), encoding="utf-8")
        return meta

    def get(self, pid: str) -> dict[str, Any] | None:
        return next((p for p in self.list() if p["id"] == pid), None)

    def svg_for(self, pid: str) -> tuple[str, dict[str, Any]]:
        meta = self.get(pid)
        if not meta:
            raise PictureError("That picture is no longer in your list.")
        data = (self.dir / meta["file"]).read_bytes()
        return wrap_as_svg(data, meta["kind"], meta["caption"]), meta

    def describe_inputs(self, pid: str) -> tuple[str, bytes | None, str]:
        """(kind, raster bytes or None, local text). SVG labels are read here, no network."""
        meta = self.get(pid)
        if not meta:
            return "", None, ""
        data = (self.dir / meta["file"]).read_bytes()
        if meta["kind"] == "svg":
            labels = re.findall(r"<text[^>]*>([^<]{1,80})</text>", data.decode("utf-8", "replace"))
            return "svg", None, "; ".join(dict.fromkeys(x.strip() for x in labels if x.strip()))[:600]
        return meta["kind"], data, ""

    def delete(self, pid: str) -> None:
        meta = self.get(pid)
        if not meta:
            return
        (self.dir / meta["file"]).unlink(missing_ok=True)
        keep = [p for p in self.list() if p["id"] != pid]
        self._index.write_text(json.dumps(keep, indent=2), encoding="utf-8")

    def raw(self, pid: str) -> tuple[bytes, str] | None:
        meta = self.get(pid)
        if not meta:
            return None
        mime = {"png": "image/png", "jpeg": "image/jpeg", "webp": "image/webp", "svg": "image/svg+xml"}
        return (self.dir / meta["file"]).read_bytes(), mime[meta["kind"]]
