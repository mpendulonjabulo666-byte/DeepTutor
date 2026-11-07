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
