"""Export a board as a printable PDF (notes, practice, answer key).

Phones that cannot open the HTML page can still read a PDF. The picture is
drawn when ``svglib`` is installed; otherwise a short note points to the page.
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from xml.sax.saxutils import escape

from .schema import Board
from .store import BoardStore


def _p(text: str) -> str:
    return escape(text or "").replace("\n", "<br/>")


def _picture_flowable(svg: str, width: float):
    if not svg:
        return None
    try:
        from reportlab.graphics import renderPDF  # noqa: F401
        from svglib.svglib import svg2rlg
    except ImportError:
        return None
    try:
        drawing = svg2rlg(StringIO(svg))
    except Exception:
        return None
    if drawing is None or not drawing.width:
        return None
    scale = min(1.0, width / drawing.width)
    drawing.width *= scale
    drawing.height *= scale
    drawing.scale(scale, scale)
    return drawing


def build_pdf(board: Board, svg: str, out: Path) -> Path:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        KeepTogether,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
    )

    ss = getSampleStyleSheet()
    body = ParagraphStyle("b", parent=ss["BodyText"], fontSize=10.5, leading=14.5)
    small = ParagraphStyle("s", parent=body, fontSize=9, textColor=colors.HexColor("#555555"))
    mono = ParagraphStyle("m", parent=body, fontName="Courier", fontSize=9.5)
    h1, h2, h3 = ss["Title"], ss["Heading2"], ss["Heading3"]
    bullet = ParagraphStyle("bl", parent=body, leftIndent=12, bulletIndent=2)

    doc = SimpleDocTemplate(
        str(out),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"{board.topic} - {board.subject}",
        author="DeepTutor Learning Board",
    )
    width = A4[0] - 36 * mm
    s: list = [Paragraph(_p(board.topic), h1), Paragraph(_p(board.subject), small)]
    if board.review.status != "reviewed":
        s.append(
            Paragraph(
                "<b>DRAFT.</b> Not yet checked by a person. Check every note and answer "
                "against your guideline before studying from it.",
                body,
            )
        )
    s.append(Spacer(1, 6))

    # Picture
    s.append(Paragraph("Picture", h2))
    pic = _picture_flowable(svg, width)
    if pic is not None:
        s.append(pic)
    else:
        s.append(
            Paragraph(
                "The diagram is on the phone page (install svglib to include it here).", small
            )
        )
    if board.picture.caption:
        s.append(Paragraph(_p(board.picture.caption), small))

    # Notes
    n = board.notes
    s.append(Paragraph("Notes", h2))
    if n.summary:
        s.append(Paragraph(_p(n.summary), body))
    for sec in n.sections:
        block = [Paragraph(_p(sec.heading), h3)]
        block += [Paragraph(_p(pt), bullet, bulletText="•") for pt in sec.points]
        s.append(KeepTogether(block))
    if n.formulas:
        s.append(Paragraph("Formulas", h3))
        for f in n.formulas:
            s.append(Paragraph(f"<b>{_p(f.name)}</b>", body))
            s.append(Paragraph(_p(f.latex), mono))
            if f.explanation:
                s.append(Paragraph(_p(f.explanation), small))
    if n.key_terms:
        s.append(Paragraph("Key terms", h3))
        for k in n.key_terms:
            s.append(Paragraph(f"<b>{_p(k.term)}</b>: {_p(k.meaning)}", body))

    if board.explainers:
        s.append(Paragraph("Explain it to me", h2))
        for e in board.explainers:
            block = [Paragraph(_p(e.title), h3), Paragraph(_p(e.explanation), body)]
            if e.example:
                block.append(Paragraph(f"<b>On site:</b> {_p(e.example)}", body))
            if e.mistake:
                block.append(Paragraph(f"<b>Common mistake:</b> {_p(e.mistake)}", body))
            s.append(KeepTogether(block))

    # Practice
    qs = board.practice.questions
    s.append(PageBreak())
    s.append(Paragraph("Practice", h2))
    for i, q in enumerate(qs, 1):
        block = [Paragraph(f"<b>{i}.</b> {_p(q.question)} <font size=8>[{q.marks}]</font>", body)]
        for key, text in q.options.items():
            block.append(Paragraph(f"{_p(key)}. {_p(text)}", bullet))
        if q.type in ("fill_blank", "short_answer"):
            block.append(Paragraph("_" * 70, small))
        block.append(Spacer(1, 6))
        s.append(KeepTogether(block))

    # Answer key
    s.append(PageBreak())
    s.append(Paragraph("Answer key", h2))
    for i, q in enumerate(qs, 1):
        line = f"<b>{i}.</b> {_p(q.answer)}"
        if q.explanation:
            line += f" <font color='#555555'>{_p(q.explanation)}</font>"
        s.append(Paragraph(line, body))

    if board.explainers:
        s.append(Spacer(1, 6))
        s.append(Paragraph("Check questions from the explanations", h3))
        for e in board.explainers:
            q = e.check
            opts = " ".join(f"{k}. {v}" for k, v in q.options.items())
            line = (
                f"<b>{_p(e.title)}:</b> {_p(q.question)} {_p(opts)} <b>Answer: {_p(q.answer)}</b>"
            )
            s.append(Paragraph(line, body))

    # Progress
    p = board.progress
    s.append(Paragraph("Progress", h2))
    for m in p.mastery_path:
        s.append(Paragraph(f"[{m.status}] {_p(m.title)}", bullet, bulletText="•"))
    if p.weak_areas:
        s.append(Paragraph("Weak areas to revisit", h3))
        s += [Paragraph(_p(w), bullet, bulletText="•") for w in p.weak_areas]
    if board.warnings:
        s.append(Paragraph("Builder warnings", h3))
        s += [Paragraph(_p(w), small) for w in board.warnings]

    def footer(canvas, d):
        canvas.setFont("Helvetica", 8)
        canvas.drawString(18 * mm, 9 * mm, f"{board.topic} | {board.board_id}")
        canvas.drawRightString(A4[0] - 18 * mm, 9 * mm, f"Page {d.page}")

    doc.build(s, onFirstPage=footer, onLaterPages=footer)
    return out


def write_pdf(store: BoardStore, board_id: str, out: Path | str | None = None) -> Path:
    board = store.load(board_id)
    svg = store.read_asset(board)
    target = Path(out) if out else store.board_dir(board_id) / f"{board_id}.pdf"
    target.parent.mkdir(parents=True, exist_ok=True)
    return build_pdf(board, svg, target)
