"""Drawing kit for exact diagrams.

Code places every shape and label, so a diagram is right by construction. The
canvas refuses to finish if two labels overlap or a label leaves the picture.
"""

from __future__ import annotations

from html import escape

INK = "#1c1c22"
MUTED = "#5b5b66"
ACCENT = "#d9480f"
FILL = "#f1ece4"
FONT = "Arial, Helvetica, sans-serif"


class DiagramError(ValueError):
    """The inputs cannot make a correct diagram."""


def num(x: float, places: int = 2) -> str:
    """Trim trailing zeros: 1.50 -> 1.5, 2.0 -> 2."""
    text = f"{x:.{places}f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


class Canvas:
    def __init__(self, width: int = 640, height: int = 360, title: str = "") -> None:
        self.w, self.h, self.title = width, height, title
        self._parts: list[str] = []
        self._boxes: list[tuple[float, float, float, float, str]] = []
        self.labels: list[str] = []

    # -- primitives (all coordinates in canvas units)
    def line(self, x1, y1, x2, y2, *, color=INK, width=2, dash="", arrow=False, both=False):
        extra = f' stroke-dasharray="{dash}"' if dash else ""
        if arrow:
            extra += ' marker-end="url(#a)"'
        if both:
            extra += ' marker-start="url(#a)"'
        self._parts.append(
            f'<line x1="{num(x1)}" y1="{num(y1)}" x2="{num(x2)}" y2="{num(y2)}" '
            f'stroke="{color}" stroke-width="{width}"{extra}/>'
        )

    def rect(self, x, y, w, h, *, fill=FILL, stroke=INK, width=2):
        self._parts.append(
            f'<rect x="{num(x)}" y="{num(y)}" width="{num(w)}" height="{num(h)}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>'
        )

    def poly(self, points, *, fill=FILL, stroke=INK, width=2):
        pts = " ".join(f"{num(x)},{num(y)}" for x, y in points)
        self._parts.append(
            f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>'
        )

    def circle(self, cx, cy, r, *, fill="none", stroke=INK, width=2):
        self._parts.append(
            f'<circle cx="{num(cx)}" cy="{num(cy)}" r="{num(r)}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{width}"/>'
        )

    def path(self, d: str, *, fill="none", stroke=INK, width=2):
        self._parts.append(f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>')

    def text(self, x, y, s: str, *, size=15, anchor="middle", color=INK, bold=False, track=True):
        s = str(s)
        est = 0.56 * size * len(s)
        left = x - est / 2 if anchor == "middle" else x if anchor == "start" else x - est
        box = (left, y - size * 0.9, left + est, y + size * 0.25, s)
        if track:
            if box[0] < 0 or box[2] > self.w or box[1] < 0 or box[3] > self.h:
                raise DiagramError(f"label '{s}' does not fit inside the picture")
            for other in self._boxes:
                if box[0] < other[2] and other[0] < box[2] and box[1] < other[3] and other[1] < box[3]:
                    raise DiagramError(f"labels '{s}' and '{other[4]}' overlap")
            self._boxes.append(box)
            self.labels.append(s)
        weight = ' font-weight="700"' if bold else ""
        self._parts.append(
            f'<text x="{num(x)}" y="{num(y)}" font-family="{FONT}" font-size="{size}" '
            f'text-anchor="{anchor}" fill="{color}"{weight}>{escape(s)}</text>'
        )

    def dimension(self, x1, x2, y, label: str, *, size=14):
        """A dimension line with arrowheads and a centred label above it."""
        self.line(x1, y, x2, y, arrow=True, both=True, width=1.5, color=MUTED)
        self.line(x1, y - 7, x1, y + 7, width=1.5, color=MUTED)
        self.line(x2, y - 7, x2, y + 7, width=1.5, color=MUTED)
        self.text((x1 + x2) / 2, y - 8, label, size=size, color=MUTED)

    # -- output
    def svg(self) -> str:
        head = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" '
            f'role="img" aria-label="{escape(self.title)}">'
            f'<defs><marker id="a" markerWidth="8" markerHeight="8" refX="7" refY="4" '
            f'orient="auto-start-reverse"><path d="M0,0 L8,4 L0,8 z" fill="{INK}"/></marker></defs>'
            f'<rect width="{self.w}" height="{self.h}" fill="#ffffff"/>'
        )
        return head + "".join(self._parts) + "</svg>"


def check_labels(svg: str, expected: list[str]) -> list[str]:
    """Return the expected labels that are missing from the finished picture."""
    return [e for e in expected if f">{escape(e)}<" not in svg]
