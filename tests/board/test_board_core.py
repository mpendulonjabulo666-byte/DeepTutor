from __future__ import annotations

import json

from pydantic import ValidationError
import pytest

from deeptutor.board import BoardBuilder, BoardNotFound, BoardStore
from deeptutor.board.builder import NOTES_SYSTEM, PRACTICE_SYSTEM, PROGRESS_SYSTEM
from deeptutor.board.schema import Board, Question, slugify
from deeptutor.board.svg import UnsafeSvg, sanitize_svg

NOTES = {
    "summary": "Construction planning decides what is built, in what order, with what resources.",
    "sections": [{"heading": "Why plan", "points": ["Saves time.", "Saves money."]}],
    "formulas": [{"name": "Float", "latex": "LF - EF - D", "explanation": "Spare time."}],
    "key_terms": [{"term": "Critical path", "meaning": "Longest chain of tasks."}],
    "picture": {
        "title": "Bar chart",
        "what_to_draw": "Three bars",
        "caption": "A simple bar chart.",
        "alt": "Three tasks as bars",
    },
}
PROGRESS = {
    "mastery_path": [
        {"id": "kp1", "title": "Explain planning"},
        {"id": "kp2", "title": "Read a bar chart"},
    ]
}
PRACTICE = {
    "questions": [
        {
            "type": "single_choice",
            "question": "Best tool?",
            "options": {"A": "x", "B": "y"},
            "answer": "B",
            "marks": 1,
            "explanation": "Because.",
            "knowledge_point_id": "kp1",
        },
        {
            "type": "true_false",
            "question": "Planning is optional.",
            "answer": "false",
            "marks": 1,
            "knowledge_point_id": "kp9",
        },
        {"type": "single_choice", "question": "Bad one", "options": {"A": "x"}, "answer": "B"},
        {"type": "short_answer", "question": "Define float.", "answer": "Spare time.", "marks": 2},
    ]
}
GOOD_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="5" height="5"/><text x="1" y="9">A</text></svg>'


def fake_llm(fail: str | None = None):
    async def llm(prompt: str, system_prompt: str, **kw) -> str:
        if system_prompt == NOTES_SYSTEM and fail != "notes":
            return "```json\n" + json.dumps(NOTES) + "\n```"
        if system_prompt == PROGRESS_SYSTEM and fail != "progress":
            return json.dumps(PROGRESS)
        if system_prompt == PRACTICE_SYSTEM and fail != "practice":
            return json.dumps(PRACTICE)
        return "not json at all"

    return llm


async def good_picture(subject, topic, brief):
    return "Here you go:\n" + GOOD_SVG


async def no_context(kb, query):
    return "SOURCE TEXT about " + query


def builder(**kw):
    return BoardBuilder(
        llm=kw.pop("llm", fake_llm()),
        picture=kw.pop("picture", good_picture),
        context=kw.pop("context", no_context),
    )


def test_slugify():
    assert (
        slugify("Civil Engineering", "Construction Planning!")
        == "civil-engineering-construction-planning"
    )
    assert slugify("???") == "board"


def test_question_rules():
    ok = Question(
        id="q1",
        type="multi_choice",
        question="Pick",
        options={"A": "1", "B": "2", "C": "3"},
        answer="A,C",
    )
    assert ok.marks == 1
    with pytest.raises(ValidationError):
        Question(
            id="q1", type="single_choice", question="Pick", options={"A": "1", "B": "2"}, answer="Z"
        )
    with pytest.raises(ValidationError):
        Question(
            id="q1",
            type="single_choice",
            question="Pick",
            options={"A": "1", "B": "2"},
            answer="A,B",
        )
    with pytest.raises(ValidationError):
        Question(id="q1", type="true_false", question="x", answer="maybe")
    with pytest.raises(ValidationError):
        Question(id="q1", type="short_answer", question="x", answer="  ")


def test_board_rejects_bad_id_and_asset_paths():
    with pytest.raises(ValidationError):
        Board(board_id="Bad ID", subject="s", topic="t")
    with pytest.raises(ValidationError):
        Board(board_id="ok", subject="s", topic="t", picture={"asset": "../secret.svg"})
    with pytest.raises(ValidationError):
        Board(board_id="ok", subject="s", topic="t", picture={"asset": "/etc/passwd"})


def test_svg_sanitizer_removes_active_content():
    dirty = (
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="100" height="50">'
        '<script>alert(1)</script><rect onclick="evil()" width="5" height="5" fill="url(http://x.test/a)"/>'
        '<a xlink:href="http://evil.test"><text>hi</text></a><foreignObject><div>x</div></foreignObject>'
        '<animate attributeName="x"/><use href="#ok"/></svg>'
    )
    clean = sanitize_svg("junk " + dirty + " more")
    low = clean.lower()
    for bad in ("script", "onclick", "evil.test", "foreignobject", "animate", "http://x.test"):
        assert bad not in low
    assert "viewbox" in low
    assert 'width="100"' not in clean
    assert "#ok" in clean


def test_svg_sanitizer_rejects_non_svg_and_entities():
    with pytest.raises(UnsafeSvg):
        sanitize_svg("no diagram here")
    bomb = '<?xml version="1.0"?><!DOCTYPE s [<!ENTITY a "aaaa">]><svg xmlns="http://www.w3.org/2000/svg">&a;</svg>'
    with pytest.raises(UnsafeSvg):
        sanitize_svg(bomb)


@pytest.mark.asyncio
async def test_full_build_and_storage(tmp_path):
    result = await builder().build(
        subject="Civil Engineering", topic="Construction Planning", kb="mat", questions=10
    )
    board = result.board
    assert board.board_id == "civil-engineering-construction-planning"
    assert board.notes.summary.startswith("Construction planning")
    assert [m.id for m in board.progress.mastery_path] == ["kp1", "kp2"]
    # one invalid question dropped, ids renumbered, unknown kp id cleared
    assert [q.id for q in board.practice.questions] == ["q1", "q2", "q3"]
    assert board.practice.questions[1].knowledge_point_id == ""
    assert any("invalid" in w for w in board.warnings)
    assert board.picture.asset == "assets/picture.svg" and result.svg
    assert board.review.status == "draft"
    assert board.sources[0].name == "Knowledge base: mat"

    store = BoardStore(tmp_path)
    store.save(board, result.svg)
    loaded = store.load(board.board_id)
    assert loaded.model_dump() == board.model_dump()
    assert "<rect" in store.read_asset(loaded)
    assert store.list()[0].board_id == board.board_id
    assert store.mark_reviewed(board.board_id).review.status == "reviewed"
    store.delete(board.board_id)
    assert not store.exists(board.board_id)
    with pytest.raises(BoardNotFound):
        store.load(board.board_id)


@pytest.mark.asyncio
@pytest.mark.parametrize("failing", ["notes", "progress", "practice"])
async def test_one_failed_section_does_not_lose_the_board(failing):
    result = await builder(llm=fake_llm(failing)).build(subject="S", topic="T", kb="k")
    board = result.board
    assert any("could not be generated" in w for w in board.warnings)
    if failing != "notes":
        assert board.notes.sections
    if failing != "progress":
        assert board.progress.mastery_path
    if failing != "practice":
        assert board.practice.questions
    Board.model_validate(board.model_dump())


@pytest.mark.asyncio
async def test_unsafe_or_missing_picture_is_a_warning_not_a_crash():
    async def bad_picture(*a):
        return "the model refused"

    result = await builder(picture=bad_picture).build(subject="S", topic="T")
    assert result.svg is None
    assert result.board.picture.asset == ""
    assert any(w.startswith("Picture") for w in result.board.warnings)


@pytest.mark.asyncio
async def test_without_kb_warns_that_content_is_unsourced():
    result = await builder().build(subject="S", topic="T")
    assert any("No source material" in w for w in result.board.warnings)
    assert result.board.sources == []


@pytest.mark.asyncio
async def test_kb_search_failure_is_reported_and_build_continues():
    async def broken(kb, q):
        raise RuntimeError("index missing")

    result = await builder(context=broken).build(subject="S", topic="T", kb="k")
    assert any("could not be searched" in w for w in result.board.warnings)
    assert result.board.notes.sections


def test_store_rejects_path_traversal(tmp_path):
    store = BoardStore(tmp_path)
    with pytest.raises(BoardNotFound):
        store.board_dir("../etc")
    assert store.exists("../etc") is False
