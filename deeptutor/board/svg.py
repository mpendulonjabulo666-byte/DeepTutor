"""Make model-written SVG safe to embed in an offline HTML page.

The picture is generated text, and it ends up inlined in a page that runs on a
phone. Scripts, event handlers, external references and embedded HTML are
removed so a bad generation cannot execute anything or load anything.
"""

from __future__ import annotations

import re
from xml.etree import ElementTree as StdET

import defusedxml.ElementTree as DefusedET

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
MAX_SVG_BYTES = 400_000

_DROP_TAGS = {
    "script",
    "foreignobject",
    "iframe",
    "object",
    "embed",
    "audio",
    "video",
    "canvas",
    "animate",
    "set",
    "animatetransform",
    "animatemotion",
    "handler",
    "listener",
}
_URL_REF = re.compile(r"url\(\s*(?!#)", re.IGNORECASE)


class UnsafeSvg(ValueError):
    pass


def _local(name: str) -> str:
    return name.rsplit("}", 1)[-1].lower() if "}" in name else name.lower()


def extract_svg(text: str) -> str:
    """Return the first ``<svg>...</svg>`` block from raw model output."""
    raw = text or ""
    match = re.search(r"<svg\b[\s\S]*?</svg\s*>", raw, re.IGNORECASE)
    if not match:
        raise UnsafeSvg("no <svg> element found")
    return match.group(0)


def _clean_attrs(el: StdET.Element) -> None:
    for key in list(el.attrib):
        name = _local(key)
        value = el.attrib[key]
        if name.startswith("on"):
            del el.attrib[key]
        elif name == "href" and not value.strip().startswith("#"):
            del el.attrib[key]
        elif name == "style" and (_URL_REF.search(value) or "expression(" in value.lower()):
            del el.attrib[key]
        elif _URL_REF.search(value):
            del el.attrib[key]


def _walk(el: StdET.Element) -> None:
    for child in list(el):
        if _local(child.tag) in _DROP_TAGS:
            el.remove(child)
            continue
        if _local(child.tag) == "style":
            css = child.text or ""
            if "@import" in css.lower() or _URL_REF.search(css):
                el.remove(child)
                continue
        _clean_attrs(child)
        _walk(child)


def sanitize_svg(text: str) -> str:
    """Parse, strip unsafe parts, and return a compact SVG string."""
    svg = extract_svg(text)
    if len(svg.encode("utf-8")) > MAX_SVG_BYTES:
        raise UnsafeSvg("svg is too large")
    try:
        root = DefusedET.fromstring(svg)
    except Exception as exc:  # defusedxml raises its own types for entities and bombs
        raise UnsafeSvg(f"svg could not be parsed safely: {exc}") from exc
    if _local(root.tag) != "svg":
        raise UnsafeSvg("root element is not svg")
    _clean_attrs(root)
    _walk(root)
    if not root.get("viewBox") and root.get("width") and root.get("height"):
        w = re.match(r"[\d.]+", root.get("width", ""))
        h = re.match(r"[\d.]+", root.get("height", ""))
        if w and h:
            root.set("viewBox", f"0 0 {w.group(0)} {h.group(0)}")
    for attr in ("width", "height"):
        root.attrib.pop(attr, None)
    StdET.register_namespace("", SVG_NS)
    StdET.register_namespace("xlink", XLINK_NS)
    out = StdET.tostring(root, encoding="unicode")
    if "<script" in out.lower():
        raise UnsafeSvg("script remained after cleaning")
    return out


__all__ = ["UnsafeSvg", "extract_svg", "sanitize_svg"]
