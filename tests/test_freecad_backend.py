import shutil
import subprocess

import pytest

from polyforge import templates
from polyforge.geometry import inspect as mesh_inspect

# Known-good sizes from the OpenSCAD backend (tests/test_templates.py), used
# here to assert the two backends produce dimensionally identical geometry
# for the same template + default params.
EXPECTED_SIZE_MM = {
    "box": [60.0, 40.0, 30.0],
    "cable_comb": [80.0, 10.0, 20.0],
    "l_bracket": [40.0, 30.0, 30.0],
    "shelf_bracket": [200.0, 120.0, 60.0],
    "standoff_mount": [80.0, 60.0, 9.0],
}


def test_all_templates_have_a_freecad_generator():
    for template in templates.all_templates():
        assert template.generate_freecad is not None, f"{template.key} has no FreeCAD backend"
        assert "freecad" in template.backends()


def test_generate_freecad_is_valid_python():
    for template in templates.all_templates():
        source = template.generate_freecad(template.defaults())
        compile(source, f"{template.key}.FCMacro", "exec")
        assert "Part.makeBox" in source or "Part.makeCylinder" in source
        assert "shape" in source


@pytest.mark.skipif(shutil.which("freecadcmd") is None, reason="freecadcmd not installed")
def test_generate_freecad_exports_match_openscad_sizes(tmp_path):
    for template in templates.all_templates():
        macro_path = tmp_path / f"{template.key}.FCMacro"
        macro_path.write_text(template.generate_freecad(template.defaults()))
        result = subprocess.run(["freecadcmd", str(macro_path)], capture_output=True, text=True, timeout=120)
        combined = result.stdout + result.stderr
        assert result.returncode == 0 and "Exception while processing file" not in combined, combined

        stl_path = tmp_path / "output" / f"{template.key}.stl"
        assert stl_path.exists() and stl_path.stat().st_size > 0

        mesh_data = mesh_inspect.inspect(stl_path)
        assert mesh_data["watertight_by_edge_count"], f"{template.key}: FreeCAD export is not watertight"
        size = [round(v, 2) for v in mesh_data["bounds_mm"]["size"]]
        assert size == EXPECTED_SIZE_MM[template.key], f"{template.key}: size {size} != OpenSCAD backend's {EXPECTED_SIZE_MM[template.key]}"


@pytest.mark.skipif(shutil.which("freecadcmd") is None, reason="freecadcmd not installed")
def test_invalid_params_fail_loudly_not_silently(tmp_path):
    # back_height == thickness violates shelf_bracket's own assert; freecadcmd
    # exits 0 regardless, so this exercises the "Exception while processing
    # file" detection in geometry.freecad_export.run rather than return code.
    template = templates.get("shelf_bracket")
    params = template.defaults()
    params["back_height"] = params["thickness"]
    macro_path = tmp_path / "shelf_bracket.FCMacro"
    macro_path.write_text(template.generate_freecad(params))

    result = subprocess.run(["freecadcmd", str(macro_path)], capture_output=True, text=True, timeout=120)
    combined = result.stdout + result.stderr
    assert "Exception while processing file" in combined
    assert not (tmp_path / "output" / "shelf_bracket.stl").exists()
