import shutil

import pytest

from polyforge import cli


def test_design_writes_scad_file(tmp_path, capsys):
    out = tmp_path / "shelf.scad"
    rc = cli.main(["design", "a wall shelf 200x150x5mm with 2 M4 holes", "--out", str(out)])
    assert rc == 0
    assert out.exists()
    text = out.read_text()
    assert "shelf_width = 200" in text
    assert "hole_diameter = 4.5" in text


def test_design_set_override(tmp_path):
    out = tmp_path / "box.scad"
    rc = cli.main(["design", "a box", "--set", "width=123", "--out", str(out)])
    assert rc == 0
    assert "width = 123" in out.read_text()


def test_list_templates_runs(capsys):
    rc = cli.main(["list-templates"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "shelf_bracket" in captured.out


def test_design_freecad_backend_writes_fcmacro(tmp_path):
    out = tmp_path / "shelf.FCMacro"
    rc = cli.main(["design", "a wall shelf 200x150x60mm with 2 M4 holes", "--backend", "freecad", "--out", str(out)])
    assert rc == 0
    text = out.read_text()
    assert "shelf_width = 200" in text
    assert "import FreeCAD" in text


def test_preview_rejects_freecad_macro(tmp_path, capsys):
    macro = tmp_path / "shelf.FCMacro"
    macro.write_text("# not executed")
    rc = cli.main(["preview", str(macro)])
    assert rc == 1
    assert "FreeCAD" in capsys.readouterr().err


@pytest.mark.skipif(shutil.which("freecadcmd") is None, reason="freecadcmd not installed")
def test_export_dispatches_to_freecad_by_suffix(tmp_path):
    macro = tmp_path / "shelf.FCMacro"
    cli.main(["design", "a wall shelf 200x150x60mm with 2 M4 holes", "--backend", "freecad", "--out", str(macro)])
    rc = cli.main(["export", str(macro)])
    assert rc == 0
    assert (tmp_path / "output" / "shelf.stl").exists()
    assert (tmp_path / "output" / "shelf.step").exists()
