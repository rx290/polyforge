import pytest

from polyforge.nlu import template_matcher
from polyforge.nlu.template_matcher import NoTemplateMatchError, match


def test_shelf_with_dimensions_and_screw_and_count():
    result = match("a wall shelf 200x150x5mm with 2 M4 holes")
    assert result.template_key == "shelf_bracket"
    assert result.params["shelf_width"] == 200
    assert result.params["shelf_depth"] == 150
    assert result.params["back_height"] == 5
    assert result.params["hole_diameter"] == 4.5
    assert result.params["hole_count"] == 2


def test_cable_comb_with_word_number_count():
    result = match("make me a cable comb with six slots")
    assert result.template_key == "cable_comb"
    assert result.params["slot_count"] == 6


def test_corner_bracket_with_triple_dimensions():
    result = match("a 40x30x30 corner bracket")
    assert result.template_key == "l_bracket"
    assert result.params["width"] == 40
    assert result.params["flange_a"] == 30
    assert result.params["flange_b"] == 30


def test_box_keyword():
    result = match("box 60x40x30")
    assert result.template_key == "box"
    assert result.params["width"] == 60
    assert result.params["depth"] == 40
    assert result.params["height"] == 30


def test_standoff_mount_keyword():
    result = match("I need a standoff mount plate for my board")
    assert result.template_key == "standoff_mount"


def test_cm_unit_converted_to_mm():
    result = match("box 6x4x3cm")
    assert result.params["width"] == 60
    assert result.params["depth"] == 40
    assert result.params["height"] == 30


def test_fuzzy_typo_fallback():
    result = match("I want a shelv for my wall")
    assert result.template_key == "shelf_bracket"
    assert result.confidence < 0.7


def test_empty_text_raises():
    with pytest.raises(NoTemplateMatchError):
        match("")


def test_gibberish_raises():
    with pytest.raises(NoTemplateMatchError):
        match("xqzvbn plonk fribble wozzit")
