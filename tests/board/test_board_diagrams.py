import asyncio

import pytest

from deeptutor.board.builder import engine_picture
from deeptutor.board.diagrams import DiagramError, render
from deeptutor.board.diagrams.core import Canvas
from deeptutor.board.svg import count_shapes, sanitize_svg


def test_levelling_numbers_are_computed_by_code():
    svg, _ = render("levelling", {"rl_a": 100, "backsight": 1.5, "foresight": 2.1})
    assert "HI = 100 + 1.5 = 101.5 m" in svg and "B  RL 99.4 m" in svg


def test_beam_reactions():
    svg, _ = render("beam", {"span_m": 6, "point_loads": [{"at_m": 2, "kn": 10}], "udl_kn_per_m": 5})
    assert "A  R = 21.67 kN" in svg and "B  R = 18.33 kN" in svg


def test_every_template_survives_the_sanitizer():
    for name, params in [
        ("levelling", {}), ("beam", {"span_m": 4, "udl_kn_per_m": 2}),
        ("weld_joint", {"joint": "tee"}), ("series_circuit", {"volts": 9, "resistors_ohm": [10, 20]}),
    ]:
        svg, _ = render(name, params)
        assert count_shapes(sanitize_svg(svg)) >= 3


@pytest.mark.parametrize("name,params", [
    ("beam", {"span_m": 6}),                      # no load
    ("levelling", {"backsight": 99}),             # out of range
    ("weld_joint", {"joint": "spiral"}),
    ("series_circuit", {"resistors_ohm": []}),
    ("nope", {}),
])
def test_bad_inputs_are_refused_not_drawn_wrong(name, params):
    with pytest.raises(DiagramError):
        render(name, params)


def test_overlapping_labels_are_caught():
    c = Canvas(200, 100)
    c.text(100, 50, "Same place")
    with pytest.raises(DiagramError):
        c.text(100, 50, "Other text")


def test_engine_picture_uses_ai_choice_and_falls_back():
    async def good(prompt, system_prompt=""):
        return '{"template": "weld_joint", "params": {"joint": "lap"}}'

    async def none(prompt, system_prompt=""):
        return '{"template": "none"}'

    async def bad(prompt, system_prompt=""):
        return '{"template": "beam", "params": {"span_m": 6}}'

    assert "Fillet weld" in asyncio.run(engine_picture("Welding", "Joints", "lap", good))
    assert asyncio.run(engine_picture("S", "T", "x", none)) is None
    assert asyncio.run(engine_picture("S", "T", "x", bad)) is None
