"""Vboard v2 student page: sections carry their check question and explanation."""

import json
import re

from deeptutor.board.bundle import plan_layout, render_bundle
from deeptutor.board.schema import (
    Board, Explainer, NoteSection, Notes, Practice, Question,
)


def _board():
    q = lambda i, text, ans, opts: Question(id=i, type="single_choice", question=text, answer=ans, options=opts)
    return Board(
        board_id="demo", subject="Construction Planning", topic="Levelling",
        notes=Notes(sections=[
            NoteSection(heading="Setting up the level", points=["Set the level on its tripod roughly halfway between A and B."]),
            NoteSection(heading="The backsight", points=["The backsight is the first staff reading, taken on the known point."]),
            NoteSection(heading="Safety on site", points=["Wear boots and a hard hat."]),
        ]),
        practice=Practice(questions=[
            q("q1", "What is the first staff reading on the known point called?", "B", {"A": "Foresight", "B": "Backsight reading"}),
            q("q2", "Where is the level set up?", "A", {"A": "Roughly halfway between A and B", "B": "On A"}),
            q("q3", "Which unit is used for staff readings?", "A", {"A": "Metres", "B": "Litres"}),
        ]),
        explainers=[Explainer(
            kp_id="k1", title="Backsight", explanation="The backsight is the first staff reading on the known point.",
            check=Question(id="e-k1", type="true_false", question="The backsight comes first.", answer="true"),
        )],
    )


def test_each_section_gets_its_own_check_question_and_explanation():
    plan = plan_layout(_board())
    assert plan["sections"][0]["check"] == "q2"
    assert plan["sections"][1] == {"check": "q1", "explain": 0}
    assert plan["sections"][2] == {"check": None, "explain": None}  # no good match: read button instead
    assert plan["test"] == ["q1", "q2", "q3"]  # fewer than 3 unused, so the test has them all


def test_page_answers_the_first_glance_questions_and_has_accessibility_settings():
    page = render_bundle(_board(), "")
    data = json.loads(re.search(r'id="board-data">(.*?)</script>', page, re.S).group(1))
    assert data["_plan"]["sections"][1]["check"] == "q1"
    for marker in ('id="continue"', 'id="where"', 'id="weak"', 'id="glance"', 'href="#notes"',
                   'data-pref="size"', 'data-pref="theme"', 'data-pref="motion"', 'data-pref="simple"',
                   "speechSynthesis", 'class="skip"'):
        assert marker in page, marker
    assert "<animate" not in page  # the logo is shown still
    assert "Search topics" not in page and "Home" not in page  # no left menu, no search


def test_only_formulas_found_in_the_files_are_kept():
    from deeptutor.board.builder import formula_in_source

    src = "Height of instrument: HI = RL + BS. Reduced level: RL = HI - FS. Area A = l x b"
    assert formula_in_source(r"\mathrm{HI} = \mathrm{RL} + \mathrm{BS}", src)
    assert formula_in_source(r"A = l \times b", src)
    assert not formula_in_source(r"V = l \times b \times h", src)  # not in the files
    assert not formula_in_source(r"\mathrm{HC} = 2x", src)


def test_formulas_become_safe_mathml():
    from deeptutor.board.bundle import latex_to_mathml

    out = latex_to_mathml(r"\mathrm{RL}_B = \mathrm{HI} - \mathrm{FS}")
    assert out.startswith("<math") and "<msub>" in out
    hostile = latex_to_mathml(r"x </math><script>alert(1)</script>")
    assert "<script" not in hostile


def test_navigation_is_a_bottom_dock_not_a_top_bar():
    page = render_bundle(_board(), "")
    assert '<nav class="dock"' in page and 'class="tabs"' not in page
    assert "backdrop-filter" in page and "prefers-reduced-transparency" in page
