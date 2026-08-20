import shutil

import pytest

from polyforge import templates
from polyforge.geometry import blender_export
from polyforge.geometry import inspect as mesh_inspect

# Known-good sizes from the OpenSCAD backend (tests/test_templates.py) and
# confirmed identical on the FreeCAD backend (tests/test_freecad_backend.py),
# used here to assert the Blender backend produces the same geometry too.
EXPECTED_SIZE_MM = {
    "box": [60.0, 40.0, 30.0],
    "cable_comb": [80.0, 10.0, 20.0],
    "l_bracket": [40.0, 30.0, 30.0],
    "shelf_bracket": [200.0, 120.0, 60.0],
    "standoff_mount": [80.0, 60.0, 9.0],
    "vase": [67.46, 68.25, 150.0],
}

# See test_freecad_backend.py's matching comment: vase's facet jitter uses
# each backend's own native RNG, so its default params can't dimensionally
# cross-check exactly the way every other (fully deterministic) template's
# can. Checked with facet_jitter=0 instead and a small real tolerance --
# even jitter-free, a lofted/curved shape still comes out a fraction of a
# mm different between OpenSCAD's and Blender's own geometry/mesh kernels.
SIZE_TOLERANCE_MM = {"vase": 1.0}


def _size_check_params(template):
    if template.key == "vase":
        return {**template.defaults(), "facet_jitter": 0}
    return template.defaults()


def test_all_templates_have_a_blender_generator():
    for template in templates.all_templates():
        assert template.generate_blender is not None, f"{template.key} has no Blender backend"
        assert "blender" in template.backends()


def test_generate_blender_is_valid_python():
    for template in templates.all_templates():
        source = template.generate_blender(template.defaults())
        compile(source, f"{template.key}.blender.py", "exec")
        assert "result_obj" in source
        assert "POLYFORGE_SCRIPT_START" in source and "POLYFORGE_SCRIPT_END" in source


@pytest.mark.skipif(shutil.which("blender") is None, reason="blender not installed")
def test_generate_blender_exports_match_openscad_sizes(tmp_path):
    for template in templates.all_templates():
        macro_path = tmp_path / template.key / f"{template.key}.blender.py"
        macro_path.parent.mkdir(parents=True, exist_ok=True)
        macro_path.write_text(template.generate_blender(_size_check_params(template)))

        result = blender_export.export(macro_path)

        mesh_data = mesh_inspect.inspect(result["stl"])
        assert mesh_data["watertight_by_edge_count"], f"{template.key}: Blender export is not watertight"
        size = [round(v, 2) for v in mesh_data["bounds_mm"]["size"]]
        expected = EXPECTED_SIZE_MM[template.key]
        tol = SIZE_TOLERANCE_MM.get(template.key, 0.0)
        assert all(abs(s - e) <= tol for s, e in zip(size, expected)), (
            f"{template.key}: size {size} != expected {expected} (tolerance {tol}mm)"
        )


@pytest.mark.skipif(shutil.which("blender") is None, reason="blender not installed")
def test_invalid_params_fail_loudly_not_silently(tmp_path):
    # back_height == thickness violates shelf_bracket's own assert; Blender
    # exits 0 regardless, so this exercises the marker-bounded traceback
    # detection in geometry.blender_export.run rather than return code.
    template = templates.get("shelf_bracket")
    params = template.defaults()
    params["back_height"] = params["thickness"]
    macro_path = tmp_path / "shelf_bracket.blender.py"
    macro_path.write_text(template.generate_blender(params))

    # An assert failure in param_lines runs before the script's own final
    # print, so it's the "missing end marker" path (a crash mid-script) that
    # actually fires here, not the "traceback between markers" path -- that
    # second path only matters for a script that catches its own exception
    # and keeps going. Both are legitimate loud-failure signals.
    with pytest.raises(RuntimeError, match="Blender macro (raised an exception|did not run to completion)"):
        blender_export.export(macro_path)
    assert not (tmp_path / "output" / "shelf_bracket.stl").exists()


@pytest.mark.skipif(shutil.which("blender") is None, reason="blender not installed")
def test_benign_startup_shutdown_tracebacks_do_not_cause_false_failure(tmp_path):
    # Blender's own bl_pkg addon fails an optional import (missing 'cattrs')
    # on every headless invocation, both at startup and again during shutdown
    # teardown -- neither is our script's fault and neither should be treated
    # as a failure. A clean run (this one) must succeed despite that noise.
    template = templates.get("box")
    macro_path = tmp_path / "box.blender.py"
    macro_path.write_text(template.generate_blender(template.defaults()))
    result = blender_export.export(macro_path)
    assert result["stl"].exists()
