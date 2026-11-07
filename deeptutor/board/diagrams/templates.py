"""Diagram templates. Each one validates its numbers, computes the answers and
draws to scale. Add a template by writing one function and registering it.

``courses`` says which NCV and NATED programmes it serves; the lists are used
only to offer the right templates, nothing is hard-wired to one course.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .core import ACCENT, FILL, INK, MUTED, Canvas, DiagramError, check_labels, num


@dataclass
class Template:
    name: str
    title: str
    courses: list[str]
    describe: str
    params: dict[str, str]
    draw: Callable[[dict[str, Any]], tuple[Canvas, list[str]]]
    needs_review: bool = True  # a teacher of the course should confirm it
    notes: list[str] = field(default_factory=list)


def _f(p: dict, key: str, lo: float, hi: float, default: float | None = None) -> float:
    try:
        v = float(p.get(key, default))
    except (TypeError, ValueError):
        raise DiagramError(f"'{key}' must be a number") from None
    if not lo <= v <= hi:
        raise DiagramError(f"'{key}' must be between {num(lo)} and {num(hi)}")
    return v


# ------------------------------------------------------------ levelling (civil)
def _levelling(p):
    rl_a = _f(p, "rl_a", -500, 5000, 100.0)
    bs = _f(p, "backsight", 0.05, 4.5, 1.5)
    fs = _f(p, "foresight", 0.05, 4.5, 2.1)
    hi = rl_a + bs
    rl_b = hi - fs
    c = Canvas(640, 360, "Levelling: instrument between two staves")
    gy = 300  # ground line level for A
    scale = 38.0  # px per metre
    diff = rl_b - rl_a  # ground under B relative to A
    gb = gy - diff * scale
    if not 120 < gb < 330:
        raise DiagramError("the levels are too far apart to draw to scale")
    ax, bx, ix = 110, 530, 320
    c.line(40, gy + 20, ax + 30, gy + 20, color=MUTED, width=1)  # ground stub
    c.poly([(30, gy), (ax + 40, gy), (ix, (gy + gb) / 2), (bx - 40, gb), (610, gb), (610, 340), (30, 340)],
           fill="#ece6db", stroke="#8a7f6d", width=1.5)
    # staves
    for x, g, top in ((ax, gy, gy - 4.2 * scale), (bx, gb, gb - 4.2 * scale)):
        c.rect(x - 8, max(top, 20), 16, g - max(top, 20), fill="#fff3bf", width=2)
    # instrument at HI
    hi_y = gy - bs * scale
    c.line(ix, hi_y, ix - 40, (gy + gb) / 2 + 6, width=2)
    c.line(ix, hi_y, ix + 40, (gy + gb) / 2 + 6, width=2)
    c.rect(ix - 16, hi_y - 12, 32, 24, fill="#dbe4ff", width=2)
    # line of collimation
    c.line(ax, hi_y, bx, hi_y, color=ACCENT, width=2, dash="8 5")
    # readings
    c.line(ax + 24, hi_y, ax + 24, gy, arrow=True, both=True, width=1.5)
    c.text(ax + 52, (hi_y + gy) / 2 + 5, f"BS {num(bs)} m", size=14, anchor="start")
    c.line(bx - 24, hi_y, bx - 24, gb, arrow=True, both=True, width=1.5)
    c.text(bx - 52, (hi_y + gb) / 2 + 5, f"FS {num(fs)} m", size=14, anchor="end")
    c.text(ax, 335, f"A  RL {num(rl_a)} m", size=15, bold=True)
    c.text(bx, 335 if abs(gb - 335) > 22 else 355, f"B  RL {num(rl_b)} m", size=15, bold=True)
    c.text(ix, 28, "Line of collimation (HI)", size=15, color=ACCENT)
    c.text(ix, 48, f"HI = {num(rl_a)} + {num(bs)} = {num(hi)} m", size=14, color=MUTED)
    c.text(ix, hi_y - 26, "Level", size=14)
    exp = [f"BS {num(bs)} m", f"FS {num(fs)} m", f"A  RL {num(rl_a)} m", f"B  RL {num(rl_b)} m"]
    return c, exp


# ------------------------------------------------------------ beam (civil, mechanics)
def _beam(p):
    span = _f(p, "span_m", 0.5, 30, 6.0)
    loads = p.get("point_loads") or []
    if not isinstance(loads, list) or len(loads) > 3:
        raise DiagramError("point_loads must be a list of up to three loads")
    pts = []
    for ld in loads:
        pos = _f(ld, "at_m", 0, span)
        kn = _f(ld, "kn", 0.1, 10000)
        pts.append((pos, kn))
    w = _f(p, "udl_kn_per_m", 0, 1000, 0.0)
    if not pts and w == 0:
        raise DiagramError("the beam needs a load")
    total = sum(k for _, k in pts) + w * span
    rb = (sum(k * a for a, k in pts) + w * span * span / 2) / span
    ra = total - rb
    c = Canvas(640, 300, "Simply supported beam with loads")
    x0, x1, by = 80, 560, 170
    sx = (x1 - x0) / span
    c.rect(x0, by - 8, x1 - x0, 16, fill="#cfd8dc", width=2)
    # pin support at A, roller at B
    c.poly([(x0, by + 8), (x0 - 16, by + 40), (x0 + 16, by + 40)], fill="#dbe4ff")
    c.line(x0 - 24, by + 40, x0 + 24, by + 40, width=3)
    c.poly([(x1, by + 8), (x1 - 16, by + 36), (x1 + 16, by + 36)], fill="#dbe4ff")
    c.circle(x1 - 8, by + 44, 6, fill="#fff")
    c.circle(x1 + 8, by + 44, 6, fill="#fff")
    c.line(x1 - 24, by + 52, x1 + 24, by + 52, width=3)
    exp = []
    for a, k in sorted(pts):
        x = x0 + a * sx
        c.line(x, by - 70, x, by - 10, arrow=True, color=ACCENT, width=3)
        label = f"{num(k)} kN"
        c.text(x, by - 78, label, size=14, color=ACCENT, bold=True)
        exp.append(label)
    if w:
        for i in range(9):
            x = x0 + 10 + i * (x1 - x0 - 20) / 8
            c.line(x, by - 46, x, by - 10, arrow=True, color=ACCENT, width=1.5)
        c.line(x0 + 10, by - 46, x1 - 10, by - 46, color=ACCENT, width=2)
        label = f"{num(w)} kN/m"
        c.text(x0 + 70 if pts else (x0 + x1) / 2, by - 54, label, size=14, color=ACCENT, bold=True)
        exp.append(label)
    c.dimension(x0, x1, by + 92, f"{num(span)} m")
    exp.append(f"{num(span)} m")
    c.text(x0, by + 124, f"A  R = {num(ra)} kN", size=15, bold=True)
    c.text(x1, by + 124, f"B  R = {num(rb)} kN", size=15, bold=True)
    exp += [f"A  R = {num(ra)} kN", f"B  R = {num(rb)} kN"]
    return c, exp


# ------------------------------------------------------------ weld joints (welding)
_JOINTS = {
    "butt": "Butt joint",
    "lap": "Lap joint",
    "tee": "T joint",
    "corner": "Corner joint",
}


def _weld(p):
    kind = str(p.get("joint", "butt")).lower()
    if kind not in _JOINTS:
        raise DiagramError(f"joint must be one of {', '.join(_JOINTS)}")
    c = Canvas(640, 300, f"{_JOINTS[kind]}")
    plate, bead = "#cfd8dc", "#ffa94d"
    if kind == "butt":
        c.rect(70, 130, 240, 40, fill=plate)
        c.rect(330, 130, 240, 40, fill=plate)
        c.poly([(310, 130), (330, 130), (320, 120)], fill=bead, width=1.5)
        c.text(190, 200, "Plate 1", size=15)
        c.text(450, 200, "Plate 2", size=15)
        c.text(320, 90, "Weld", size=15, color=ACCENT, bold=True)
        c.line(320, 98, 320, 116, arrow=True, color=ACCENT)
    elif kind == "lap":
        c.rect(70, 150, 320, 36, fill=plate)
        c.rect(250, 114, 320, 36, fill=plate)
        c.poly([(250, 150), (250, 150), (234, 150), (250, 134)], fill=bead, width=1.5)
        c.poly([(390, 150), (390, 186), (410, 186)], fill=bead, width=1.5)
        c.text(150, 220, "Plate 1", size=15)
        c.text(480, 100, "Plate 2", size=15)
        c.text(450, 230, "Fillet weld", size=15, color=ACCENT, bold=True)
        c.line(430, 218, 405, 192, arrow=True, color=ACCENT)
    elif kind == "tee":
        c.rect(70, 190, 500, 36, fill=plate)
        c.rect(302, 60, 36, 130, fill=plate)
        c.poly([(302, 190), (302, 160), (278, 190)], fill=bead, width=1.5)
        c.poly([(338, 190), (338, 160), (362, 190)], fill=bead, width=1.5)
        c.text(150, 260, "Base plate", size=15)
        c.text(450, 110, "Upright plate", size=15)
        c.text(160, 140, "Fillet weld", size=15, color=ACCENT, bold=True)
        c.line(215, 132, 276, 180, arrow=True, color=ACCENT)
    else:  # corner
        c.rect(130, 190, 300, 36, fill=plate)
        c.rect(130, 60, 36, 130, fill=plate)
        c.poly([(166, 190), (166, 166), (190, 190)], fill=bead, width=1.5)
        c.text(330, 260, "Plate 1", size=15)
        c.text(300, 110, "Plate 2", size=15)
        c.text(410, 160, "Fillet weld", size=15, color=ACCENT, bold=True)
        c.line(398, 164, 196, 184, arrow=True, color=ACCENT)
    exp = [t for t in ("Plate 1", "Plate 2", "Weld", "Fillet weld", "Base plate", "Upright plate")
           if f">{t}<" in c.svg()]
    return c, exp


# ------------------------------------------------------------ series circuit (electrical)
def _circuit(p):
    volts = _f(p, "volts", 0.1, 1000, 12.0)
    rs = p.get("resistors_ohm", [100, 200])
    if not isinstance(rs, list) or not 1 <= len(rs) <= 4:
        raise DiagramError("resistors_ohm must list one to four resistors")
    vals = [_f({"r": r}, "r", 0.1, 1e7) for r in rs]
    total = sum(vals)
    amps = volts / total
    c = Canvas(640, 320, "Series circuit")
    top, bot, l, r = 90, 250, 90, 550
    c.line(l, top, r, top)
    c.line(r, top, r, bot)
    c.line(r, bot, l, bot)
    # battery on the left side
    c.line(l, top, l, 150)
    c.line(l, 200, l, bot)
    c.line(l - 22, 150, l + 22, 150, width=3)
    c.line(l - 12, 164, l + 12, 164, width=5)
    c.line(l, 164, l, 200)
    c.text(l - 34, 160, "+", size=18, anchor="end", bold=True)
    c.text(l - 12, 205, f"{num(volts)} V", size=15, anchor="end", bold=True)
    # resistors along the top
    n = len(vals)
    span = r - l - 80
    names = []
    for i, v in enumerate(vals):
        cx = l + 80 + span * (i + 0.5) / n
        c.rect(cx - 36, top - 14, 72, 28, fill="#fff", width=2)
        lab = f"R{i + 1} = {num(v)} ohm"
        c.text(cx, top - 26, lab, size=13)
        names.append(lab)
    c.text(320, 290, f"R total = {num(total)} ohm", size=15, bold=True)
    c.text(320, 312, f"I = {num(amps, 3)} A", size=15, bold=True, color=ACCENT)
    exp = [f"{num(volts)} V", *names, f"R total = {num(total)} ohm", f"I = {num(amps, 3)} A"]
    return c, exp


REGISTRY: dict[str, Template] = {
    t.name: t
    for t in [
        Template(
            "levelling", "Levelling: backsight and foresight",
            ["Civil Engineering", "Building and Structural Construction", "Surveying"],
            "Level instrument between two staves; computes HI and the reduced level of B.",
            {"rl_a": "reduced level of A in m", "backsight": "staff reading at A in m",
             "foresight": "staff reading at B in m"},
            _levelling,
        ),
        Template(
            "beam", "Simply supported beam",
            ["Civil Engineering", "Mechanical Engineering", "Engineering and Related Design"],
            "Beam with pin and roller, up to three point loads and an optional UDL; computes reactions.",
            {"span_m": "span in m", "point_loads": "list of {at_m, kn}", "udl_kn_per_m": "UDL in kN/m (optional)"},
            _beam,
        ),
        Template(
            "weld_joint", "Basic weld joints",
            ["Welding", "Fitting and Turning", "Boilermaking"],
            "Butt, lap, T or corner joint with plates and weld labelled.",
            {"joint": "butt | lap | tee | corner"},
            _weld,
        ),
        Template(
            "series_circuit", "Series circuit",
            ["Electrical Infrastructure Construction", "Electronic Control and Digital Electronics", "Process Instrumentation"],
            "Battery with one to four resistors in series; computes total R and current.",
            {"volts": "supply voltage in V", "resistors_ohm": "list of resistances in ohm"},
            _circuit,
        ),
    ]
}


def render(name: str, params: dict[str, Any]) -> tuple[str, Template]:
    """Draw a template. Raises DiagramError when the numbers cannot give a correct picture."""
    tpl = REGISTRY.get(name)
    if tpl is None:
        raise DiagramError(f"no template called {name!r}")
    canvas, expected = tpl.draw(params or {})
    svg = canvas.svg()
    missing = check_labels(svg, expected)
    if missing:
        raise DiagramError(f"labels missing from the picture: {', '.join(missing)}")
    return svg, tpl


def catalogue() -> str:
    """The list shown to the AI so it can pick a template and fill the numbers."""
    return "\n".join(
        f'- "{t.name}": {t.describe} params: ' + "; ".join(f"{k} ({v})" for k, v in t.params.items())
        for t in REGISTRY.values()
    )
