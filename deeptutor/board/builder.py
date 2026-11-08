"""Build a topic board from one request.

Order of work:

1. Notes (from the knowledge base when one is given), including a brief for the picture.
2. Progress (the mastery path) and Picture, in parallel.
3. Practice, tied to the mastery path items.

Each section is isolated. If one fails, the board is still saved with that
section empty and a warning, so one bad generation does not lose the rest.
The model calls are injectable so tests run without a network or a key.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import re
from typing import Any, Awaitable, Callable

from pydantic import ValidationError

from deeptutor.utils.json_parser import parse_json_response

from .schema import (
    MAX_QUESTIONS,
    Board,
    Explainer,
    MasteryItem,
    Notes,
    Picture,
    Practice,
    Progress,
    Question,
    Source,
    slugify,
)
from .svg import UnsafeSvg, count_shapes, sanitize_svg

logger = logging.getLogger(__name__)

LLMFn = Callable[..., Awaitable[str]]
PictureFn = Callable[[str, str, str], Awaitable[str]]
ContextFn = Callable[[str, str], Awaitable[str]]

MAX_CONTEXT_CHARS = 12_000

_STYLE = (
    "Write for students at a South African TVET college. Use plain English, short sentences "
    "and everyday words. Explain technical terms the first time they appear. "
    "Use only facts that appear in SOURCE when SOURCE is given. When SOURCE is empty, use only "
    "well-established general knowledge. Never invent figures, standards, regulations or clause "
    "numbers. If you are unsure of a value, leave it out. Teach only what the topic itself covers "
    "(its outcomes, instruments, methods, calculations). Do not write about marks, weights, ICASS, "
    "portfolios of evidence or pass rules unless the topic is about them. "
    "Reply with one JSON object and nothing else."
)

_CMD_WORD = re.compile(r"\\(?:mathrm|text|textrm|operatorname)\{([^{}]*)\}")


def _compact(text: str) -> str:
    text = text.replace("\\times", "x").replace("\\cdot", "x").replace("×", "x").replace("·", "x")
    text = text.replace("−", "-").replace("\\left", "").replace("\\right", "")
    text = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"\1/\2", text)
    text = re.sub(r"\\[a-zA-Z]+", "", text)
    return re.sub(r"[\s{}_^*]", "", text).lower()


def formula_in_source(latex: str, source: str) -> bool:
    """True when a formula can be traced to the uploaded files.

    Symbols of two or more letters (HI, RL, FS) must all appear in the source as
    written. A formula made only of single letters must appear in the source in
    the same compact form (``A=lxb``), because single letters prove nothing alone.
    """
    words = [w for grp in _CMD_WORD.findall(latex) for w in re.findall(r"[A-Za-z]{2,}", grp)]
    plain = _CMD_WORD.sub(" ", latex)
    plain = re.sub(r"\\[a-zA-Z]+", " ", plain)
    words += re.findall(r"(?<![A-Za-z])[A-Za-z]{2,}(?![A-Za-z])", plain)
    if words:
        return all(re.search(rf"(?<![A-Za-z]){re.escape(w)}(?![A-Za-z])", source) for w in words)
    return bool(_compact(latex)) and _compact(latex) in _compact(source)


NOTES_SYSTEM = (
    "You write exam-ready study notes.\n" + _STYLE + "\n\n"
    "JSON keys:\n"
    '- "summary": 2 to 3 sentences.\n'
    '- "sections": 3 to 10 items of {"heading": str, "points": [3 to 8 short strings]}. '
    "Cover EVERY subtopic and outcome the SOURCE lists for this topic, in the order the guideline "
    "gives them, with headings in the guideline's own words. Nothing in the syllabus is left out. "
    "Write points the way a memo answer is written: one fact per point, so a student can write it "
    "straight into an exam answer. When the source lists items (instruments, materials, steps, "
    "types), give the complete list, every item the source names, with one plain line each, so a "
    "question such as 'list five' can always be answered.\n"
    '- "formulas": items of {"name": str, "latex": str, "explanation": str}. Copy each formula '
    "exactly as the SOURCE writes it (same letters, symbols and units, as used in the exam papers "
    "and formula sheets). Write a symbol of several letters as \\mathrm{HI}. Never make up or "
    "rewrite a formula. Empty list when the SOURCE has none.\n"
    '- "key_terms": 6 to 12 items of {"term": str, "meaning": str}.\n'
    '- "picture": {"title": str, "what_to_draw": str, "caption": str, "alt": str}. '
    "One diagram that would help a student understand the topic. "
    '"what_to_draw" lists the exact shapes and labels.'
)

PROGRESS_SYSTEM = (
    "You design a mastery path: the ordered skills a student must master for a topic.\n"
    + _STYLE
    + "\n\n"
    'JSON key "mastery_path": 4 to 6 items of {"id": "kp1", "title": str}, ids kp1, kp2 and so on, '
    "in the order a student should learn them. Titles start with a verb such as Identify, Explain, Calculate."
)

PRACTICE_SYSTEM = (
    "You write exam practice questions with a marking guide.\n" + _STYLE + "\n\n"
    'JSON key "questions": a list. Each item:\n'
    '- "type": one of single_choice, multi_choice, true_false, fill_blank, short_answer.\n'
    '- "question": str.\n'
    '- "options": {"A": str, "B": str, "C": str, "D": str} for single_choice and multi_choice, otherwise {}.\n'
    '- "answer": for single_choice the key such as "B"; for multi_choice keys such as "A,C"; '
    'for true_false exactly "true" or "false"; otherwise the model answer text.\n'
    '- "marks": integer 1 to 6, higher for longer answers.\n'
    '- "explanation": 1 to 2 sentences on why the answer is right.\n'
    '- "difficulty": easy, medium or hard.\n'
    '- "knowledge_point_id": one of the mastery path ids given.\n'
    "Mix the types. Most should be single_choice or short_answer. Cover every mastery path item. "
    "Questions must be answerable from the notes given."
)


EXPLAIN_SYSTEM = (
    "You are a patient tutor. For each skill on the mastery path, explain it the way a good "
    "teacher would to a student who got it wrong.\n" + _STYLE + "\n\n"
    'JSON key "explainers": one item per mastery path id. Each item:\n'
    '- "kp_id": the mastery path id.\n'
    '- "title": the skill, in a few words.\n'
    '- "explanation": 3 to 6 short sentences in plain English. Say what it is, then why, then how.\n'
    '- "example": a simple everyday example from a South African building site or a house '
    "(bricks, cement, a trench, a tape measure). No invented numbers or standards.\n"
    '- "mistake": the most common mistake students make, in one sentence.\n'
    '- "check": a NEW question on the same idea (not one already asked) with keys '
    '"type" (single_choice or true_false), "question", "options" ({"A","B","C"} for single_choice, '
    'otherwise {}), "answer" (key like "B", or "true"/"false"), "marks" 1, "explanation" (one sentence).'
)


def kp_ids_ok(board: Board) -> bool:
    return bool(board.progress.mastery_path)


@dataclass
class BuildResult:
    board: Board
    svg: str | None


def _trim(text: str, limit: int = MAX_CONTEXT_CHARS) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit] + "\n[truncated]"


async def default_llm(prompt: str, system_prompt: str, **kwargs: Any) -> str:
    from deeptutor.services.llm import complete

    return await complete(prompt, system_prompt=system_prompt, **kwargs)


async def default_context(kb: str, query: str) -> str:
    from deeptutor.services.rag.service import RAGService

    result = await RAGService().search(query=query, kb_name=kb)
    return str(result.get("content") or result.get("answer") or "")


SVG_SYSTEM = (
    "You draw one clear teaching diagram as an SVG for a student's phone. "
    "Reply with the SVG only, starting with <svg and ending with </svg>.\n"
    "Rules:\n"
    '- viewBox="0 0 800 500". Plain white background rectangle first.\n'
    "- Draw the actual shapes with <rect>, <line>, <path>, <polygon>, <circle>. A diagram made "
    "only of text is wrong.\n"
    '- Give EVERY shape explicit fill and stroke attributes, for example fill="#dbeafe" '
    'stroke="#1e3a8a" stroke-width="3". Do not use CSS classes or a <style> element.\n'
    "- Labels are <text> with font-size 18 to 22, font-family sans-serif, placed beside or inside "
    "the shape they name, never overlapping another label. Use short labels.\n"
    '- Arrows: define <marker id="a"> in <defs> and use marker-end="url(#a)".\n'
    "- Draw only what the brief asks for. Do not invent dimensions, standards or numbers. "
    "No scripts, no images, no external links, no animation."
)


ENGINE_SYSTEM = (
    "You choose a drawing template for a study diagram and fill in its numbers. "
    "Reply with JSON only: {\"template\": name, \"params\": {...}} or {\"template\": \"none\"} "
    "when no template fits the brief. Use only the templates listed. Use numbers that appear in the "
    "source or brief; if none are given, use simple realistic example values."
)


async def engine_picture(subject: str, topic: str, brief: str, llm=None) -> str | None:
    """Pick a template and draw it with code, so the labels and numbers are exact.

    Returns None when no template fits or the numbers cannot make a correct picture.
    """
    from .diagrams import DiagramError, catalogue, render

    ask = llm or default_llm
    try:
        raw = await ask(
            f"Subject: {subject}\nTopic: {topic}\nBrief: {brief}\n\nTEMPLATES:\n{catalogue()}",
            ENGINE_SYSTEM,
        )
        data = parse_json_response(raw, fallback=None)
        if not isinstance(data, dict):
            return None
        name = str(data.get("template", "none"))
        if name == "none":
            return None
        svg, _tpl = render(name, data.get("params") or {})
        return svg
    except (DiagramError, ValueError, TypeError, AttributeError) as exc:
        logger.info("Diagram engine skipped: %s", exc)
        return None


async def default_picture(subject: str, topic: str, brief: str) -> str:
    """Exact drawing from a template when one fits; otherwise one direct SVG request."""
    drawn = await engine_picture(subject, topic, brief)
    if drawn:
        return drawn
    prompt = (
        f"Subject: {subject}\nTopic: {topic}\nDraw this: {brief}\n"
        "Keep it simple: 4 to 10 labelled parts."
    )
    return await default_llm(prompt, SVG_SYSTEM)


class BoardBuilder:
    def __init__(
        self,
        *,
        llm: LLMFn | None = None,
        picture: PictureFn | None = None,
        context: ContextFn | None = None,
    ) -> None:
        self._llm = llm or default_llm
        self._picture = picture or default_picture
        self._context = context or default_context

    async def _json(self, system: str, prompt: str) -> dict[str, Any]:
        """Ask for JSON, with one retry that restates the format."""
        last = ""
        for attempt in range(2):
            ask = (
                prompt
                if attempt == 0
                else prompt
                + "\n\nYour last reply was not valid JSON. Reply with the JSON object only."
            )
            last = await self._llm(ask, system_prompt=system)
            data = parse_json_response(last, fallback=None)
            if isinstance(data, dict) and data:
                return data
        raise ValueError("model did not return a JSON object")

    async def _explainers(
        self, who: str, notes_text: str, notes_ctx: str, board: Board, warnings: list[str]
    ) -> list[Explainer]:
        path = board.progress.mastery_path
        ids = [m.id for m in path]
        asked = "\n".join(f"- {q.question}" for q in board.practice.questions)
        prompt = (
            f"{who}\n\nMASTERY PATH:\n"
            + "\n".join(f"{m.id}: {m.title}" for m in path)
            + f"\n\nNOTES:\n{notes_text or '(none)'}\n\nSOURCE:\n{_trim(notes_ctx, 6000) or '(none)'}"
            + f"\n\nQUESTIONS ALREADY ASKED (do not repeat):\n{asked or '(none)'}"
        )
        data = await self._json(EXPLAIN_SYSTEM, prompt)
        out: list[Explainer] = []
        seen: set[str] = set()
        dropped = 0
        for raw in data.get("explainers", []):
            try:
                kp = str(raw.get("kp_id", ""))
                if kp not in ids or kp in seen:
                    raise ValueError("unknown or repeated kp_id")
                chk = {**raw.get("check", {}), "id": f"e-{kp}", "knowledge_point_id": kp}
                out.append(Explainer.model_validate({**raw, "check": chk}))
                seen.add(kp)
            except (ValidationError, AttributeError, TypeError, ValueError):
                dropped += 1
        if dropped:
            warnings.append(f"{dropped} generated explanation(s) were invalid and left out.")
        if not out:
            warnings.append("No valid explanations were generated.")
        return out

    async def build(
        self,
        *,
        subject: str,
        topic: str,
        kb: str | None = None,
        level: str = "",
        questions: int = 10,
        with_picture: bool = True,
        board_id: str | None = None,
        focus: str = "",
    ) -> BuildResult:
        questions = max(1, min(int(questions), MAX_QUESTIONS))
        board = Board(
            board_id=board_id or slugify(subject, topic),
            subject=subject,
            topic=topic,
            level=level if 0 < len(level) <= 40 else "",
        )
        warnings: list[str] = []
        who = f"Subject: {subject}\nTopic: {topic}" + (f"\nLevel: {level}" if level else "")
        focus = " ".join(str(focus or "").split())[:1000]
        if focus:
            who += (
                "\nTutor instructions (follow them for emphasis, depth and wording; "
                f"never add facts that are not in the source): {focus}"
            )

        notes_ctx = questions_ctx = ""
        if kb:
            board.sources.append(Source(kind="other", name=f"Knowledge base: {kb}"))
            try:
                notes_ctx, questions_ctx = await asyncio.gather(
                    self._context(kb, f"{subject} {topic}"),
                    self._context(kb, f"{topic} exam questions memorandum marks"),
                )
            except Exception as exc:
                logger.warning("Knowledge base search failed: %s", exc)
                warnings.append(f"Knowledge base '{kb}' could not be searched: {exc}")
        if not notes_ctx.strip():
            warnings.append(
                "No source material was used. Content comes from general knowledge and must be checked against your guideline."
            )

        # 1. Notes
        brief = ""
        try:
            data = await self._json(
                NOTES_SYSTEM, f"{who}\n\nSOURCE:\n{_trim(notes_ctx) or '(none)'}"
            )
            pic = data.pop("picture", None) or {}
            board.notes = Notes.model_validate(data)
            if notes_ctx.strip() and board.notes.formulas:
                kept = [f for f in board.notes.formulas if formula_in_source(f.latex, notes_ctx)]
                for f in board.notes.formulas:
                    if f not in kept:
                        warnings.append(
                            f"Formula '{f.name}' was left out because it is not in your files. "
                            "Add it from the exam formula sheet if it belongs."
                        )
                board.notes.formulas = kept
            board.picture = Picture(
                title=str(pic.get("title", "")),
                alt=str(pic.get("alt", "")),
                caption=str(pic.get("caption", "")),
            )
            brief = str(pic.get("what_to_draw", ""))
        except Exception as exc:
            logger.warning("Notes failed: %s", exc)
            warnings.append(f"Notes could not be generated: {exc}")

        notes_text = board.notes.model_dump_json() if board.notes.sections else ""

        # 2. Progress and Picture in parallel
        async def progress_task() -> Progress:
            data = await self._json(PROGRESS_SYSTEM, f"{who}\n\nNOTES:\n{notes_text or '(none)'}")
            items = [
                MasteryItem.model_validate({**i, "status": "new"})
                for i in data.get("mastery_path", [])
            ]
            if not items:
                raise ValueError("empty mastery path")
            return Progress(mastery_path=items)

        async def picture_task() -> str:
            what = brief or board.picture.title
            for attempt in range(2):
                ask = what
                if attempt:
                    ask += (
                        "\nIMPORTANT: your last picture had no drawn shapes. Use <rect>, <line> "
                        "and <path> elements with explicit fill and stroke attributes."
                    )
                svg_text = sanitize_svg(await self._picture(subject, topic, ask))
                if count_shapes(svg_text) >= 3:
                    return svg_text
            raise UnsafeSvg("the picture had no drawn shapes, only text")

        tasks: list[Awaitable[Any]] = [progress_task()]
        if with_picture:
            tasks.append(picture_task())
        results = await asyncio.gather(*tasks, return_exceptions=True)

        if isinstance(results[0], BaseException):
            logger.warning("Progress failed: %s", results[0])
            warnings.append(f"Mastery path could not be generated: {results[0]}")
        else:
            board.progress = results[0]

        svg: str | None = None
        if with_picture:
            if isinstance(results[1], BaseException):
                kind = "unsafe or unreadable" if isinstance(results[1], UnsafeSvg) else "failed"
                warnings.append(f"Picture {kind}: {results[1]}")
                logger.warning("Picture failed: %s", results[1])
            else:
                svg = results[1]
                board.picture.kind = "svg"
                board.picture.asset = "assets/picture.svg"
                if not board.picture.alt:
                    board.picture.alt = board.picture.title or f"Diagram for {topic}"

        # 3. Practice
        try:
            kp_ids = [m.id for m in board.progress.mastery_path]
            prompt = (
                f"{who}\n\nWrite {questions} questions.\n"
                f"MASTERY PATH IDS: {', '.join(kp_ids) or '(none)'}\n\n"
                f"NOTES:\n{notes_text or '(none)'}\n\n"
                f"PAST PAPER SOURCE (style and mark guide):\n{_trim(questions_ctx) or '(none)'}"
            )
            data = await self._json(PRACTICE_SYSTEM, prompt)
            kept: list[Question] = []
            dropped = 0
            for raw_q in data.get("questions", []):
                try:
                    q = Question.model_validate({**raw_q, "id": f"q{len(kept) + 1}"})
                except (ValidationError, AttributeError, TypeError):
                    dropped += 1
                    continue
                if q.knowledge_point_id not in kp_ids:
                    q.knowledge_point_id = ""
                kept.append(q)
            board.practice = Practice(questions=kept[:questions])
            if dropped:
                warnings.append(f"{dropped} generated question(s) were invalid and left out.")
            if not kept:
                warnings.append("No valid practice questions were generated.")
        except Exception as exc:
            logger.warning("Practice failed: %s", exc)
            warnings.append(f"Practice questions could not be generated: {exc}")

        # 4. Explainers: plain words plus a fresh check question for each skill
        if kp_ids_ok(board):
            try:
                board.explainers = await self._explainers(
                    who, notes_text, notes_ctx, board, warnings
                )
            except Exception as exc:
                logger.warning("Explainers failed: %s", exc)
                warnings.append(f"Explanations could not be generated: {exc}")

        board.warnings = warnings
        return BuildResult(board=board, svg=svg)


__all__ = ["BoardBuilder", "BuildResult"]
