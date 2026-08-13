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
