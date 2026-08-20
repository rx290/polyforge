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


# ---- vase free-text extraction -----------------------------------------
# Regression coverage for a real reported bug: free-text vase requests like
# "300mm height and 200mm width" produced no param overrides at all (the
# old extractor only understood WxDxH triples/pairs joined by "x"/"by"),
# so every vase request rendered identically regardless of what was typed.

def test_vase_named_dimensions_and_texture_keyword_from_free_text():
    result = match("a square vase with wave ripples 300mm height and 200mm width")
    assert result.template_key == "vase"
    assert result.params["vase_height"] == 300
    assert result.params["d_base"] == 200
    assert result.params["base_texture_amplitude"] == 0.12


def test_vase_dimension_word_before_the_number_also_works():
    result = match("a vase, height 250mm, diameter 90mm")
    assert result.params["vase_height"] == 250
    assert result.params["d_base"] == 90


def test_vase_hourglass_keyword_sets_a_bulge_section_narrower_than_its_ends():
    result = match("an hourglass vase")
    assert result.params["s1_type"] == 3
    assert result.params["s1_peak_d"] < result.params["s1_end_d"]


def test_vase_bulb_holder_sets_both_a_globe_bulge_and_a_holder_ring():
    result = match("a vase with a bulb holder on top")
    assert result.params["s4_type"] == 3
    assert result.params["s4_peak_d"] > result.params["s4_end_d"]
    assert result.params["holder_ring_d"] > 0


def test_vase_twist_keyword_sets_total_twist_deg():
    result = match("a spiral twisted vase")
    assert result.params["total_twist_deg"] == 360


def test_vase_low_poly_vs_smooth_keywords_pick_opposite_facet_settings():
    low_poly = match("a low poly vase")
    assert low_poly.params["num_sides"] <= 8
    assert low_poly.params["facet_jitter"] > 0

    smooth = match("a smooth vase")
    assert smooth.params["num_sides"] >= 40
    assert smooth.params["facet_jitter"] == 0


def test_vase_numeric_dimension_extraction_takes_priority_over_keyword_nudges():
    # An explicit number should never be clobbered by a same-named keyword
    # nudge -- there's no overlap today, but this guards the "already in
    # params" precedence check in extract_params directly.
    result = match("a vase 500mm height")
    assert result.params["vase_height"] == 500


def test_vase_detailed_keyword_bumps_profile_slices():
    result = match("a detailed vase")
    assert result.params["profile_slices"] == 64


def _merged_diameters(template, params):
    from polyforge.nlu.template_matcher import _VASE_DIAMETER_CHAIN
    merged = template.defaults()
    merged.update(params)
    return [merged[name] for name in _VASE_DIAMETER_CHAIN]


def test_vase_without_support_disables_a_bulge_that_was_just_requested():
    from polyforge import templates
    result = match("an hourglass vase that prints without support")
    assert result.params["s1_type"] == 2  # bulge (3) forced back to taper
    diameters = _merged_diameters(templates.get("vase"), result.params)
    assert all(a >= b for a, b in zip(diameters, diameters[1:])), diameters


def test_vase_without_support_clamps_a_flaring_default_profile():
    from polyforge import templates
    result = match("a vase that prints without support")
    diameters = _merged_diameters(templates.get("vase"), result.params)
    assert all(a >= b for a, b in zip(diameters, diameters[1:])), diameters


def test_vase_detailed_smooth_without_support_all_combine():
    from polyforge import templates
    result = match("a detailed vase with smooth texture and it should print without support")
    assert result.params["profile_slices"] == 64
    assert result.params["num_sides"] == 48
    assert result.params["facet_jitter"] == 0
    diameters = _merged_diameters(templates.get("vase"), result.params)
    assert all(a >= b for a, b in zip(diameters, diameters[1:])), diameters
