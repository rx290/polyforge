import shutil

import pytest

from polyforge import templates
from polyforge.gui import app as gui_app


def test_templates_json_matches_the_real_registry():
    data = gui_app.templates_json()
    keys = {t["key"] for t in data}
    assert keys == {t.key for t in templates.all_templates()}
    for entry in data:
        assert entry["params"]
        assert "openscad" in entry["backends"]


def test_ollama_status_json_never_raises_when_unreachable():
    result = gui_app.ollama_status_json(base_url="http://localhost:18453", auto_start=False)
    assert result["reachable"] is False
    assert "error" in result


def test_design_json_with_templates_engine_writes_a_file(tmp_path):
    result = gui_app.design_json({"text": "a wall shelf 200x150x5mm with 2 M4 holes"}, tmp_path, 1)
    assert result["template_key"] == "shelf_bracket"
    assert (tmp_path / result["filename"]).exists()
    assert "shelf_width = 200" in result["source"]


def test_design_json_applies_set_overrides(tmp_path):
    result = gui_app.design_json({"text": "a box", "set": {"width": "123"}}, tmp_path, 1)
    assert result["params"]["width"] == 123.0


def test_design_json_empty_text_raises_design_error(tmp_path):
    with pytest.raises(gui_app.DesignError, match="text is required"):
        gui_app.design_json({"text": "  "}, tmp_path, 1)


def test_design_json_unknown_engine_raises_design_error(tmp_path):
    with pytest.raises(gui_app.DesignError, match="unknown engine"):
        gui_app.design_json({"text": "a box", "engine": "magic"}, tmp_path, 1)


def test_design_json_freecad_backend(tmp_path):
    result = gui_app.design_json(
        {"text": "a wall shelf 200x150x60mm with 2 M4 holes", "backend": "freecad"}, tmp_path, 1
    )
    assert result["filename"].endswith(".FCMacro")
    assert "import FreeCAD" in result["source"]


def test_preview_json_rejects_non_scad_backend(tmp_path):
    (tmp_path / "thing.FCMacro").write_text("# not openscad")
    with pytest.raises(gui_app.DesignError, match="OpenSCAD"):
        gui_app.preview_json("thing.FCMacro", tmp_path)


@pytest.mark.skipif(shutil.which("openscad") is None, reason="openscad not installed")
def test_preview_json_against_real_openscad(tmp_path):
    design = gui_app.design_json({"text": "a box"}, tmp_path, 1)
    result = gui_app.preview_json(design["filename"], tmp_path, imgsize="200,150")
    names = {v["name"] for v in result["views"]}
    assert names == {"isometric", "front", "back", "left", "right", "top", "bottom"}


@pytest.mark.skipif(shutil.which("openscad") is None, reason="openscad not installed")
def test_export_json_against_real_openscad(tmp_path):
    design = gui_app.design_json({"text": "a box"}, tmp_path, 1)
    result = gui_app.export_json(design["filename"], tmp_path)
    assert result["stl"].endswith(".stl")
