import shutil
import subprocess

import pytest

from polyforge import render, templates


def test_vase_registered_with_expected_defaults():
    template = templates.get("vase")
    defaults = template.defaults()
    assert defaults["d_base"] == 70
    assert defaults["vase_height"] == 150
    assert defaults["num_sides"] == 7


def test_vase_generate_contains_all_params():
    template = templates.get("vase")
    source = template.generate(template.defaults())
    for param in template.params:
        assert param.name in source


@pytest.mark.skipif(shutil.which("openscad") is None, reason="openscad CLI not installed")
def test_vase_default_compiles_and_is_manifold(tmp_path):
    source, _ = render.render("vase", {})
    scad = tmp_path / "vase.scad"
    scad.write_text(source)
    stl = tmp_path / "vase.stl"
    result = subprocess.run(
        ["openscad", "--render", "-o", str(stl), str(scad)],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert stl.exists() and stl.stat().st_size > 0


@pytest.mark.skipif(shutil.which("openscad") is None, reason="openscad CLI not installed")
@pytest.mark.parametrize(
    "overrides",
    [
        {},
        {"total_twist_deg": 0},
        {"total_twist_deg": 360},
        {"num_sides": 3},
        {"num_sides": 24},
        {"facet_jitter": 0},
        {"facet_jitter": 0.35},
        {"drainage_hole_d": 10},
        {"d_base": 60, "d_q1": 60, "d_waist": 60, "d_q3": 60, "d_rim": 60},  # a plain cylinder
    ],
)
def test_vase_compiles_across_parameter_variations(tmp_path, overrides):
    source, _ = render.render("vase", overrides)
    scad = tmp_path / "vase.scad"
    scad.write_text(source)
    stl = tmp_path / "vase.stl"
    result = subprocess.run(
        ["openscad", "--render", "-o", str(stl), str(scad)],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert stl.exists() and stl.stat().st_size > 0


def test_vase_rejects_wall_thickness_too_large_for_narrow_profile():
    source, _ = render.render("vase", {"d_waist": 10, "wall_thickness": 8})
    assert "wall_thickness is too large" in source


def test_vase_rejects_drainage_hole_bigger_than_interior():
    source, _ = render.render("vase", {"drainage_hole_d": 1000})
    assert "drainage_hole_d must be smaller" in source


@pytest.mark.skipif(shutil.which("openscad") is None, reason="openscad CLI not installed")
def test_vase_is_genuinely_hollow_not_solid(tmp_path):
    """A real regression check, not just 'does it compile': a solid vase
    (wall_thickness effectively filling the whole profile) should be
    heavier than the actual hollow default at the same outer dimensions --
    catches an inner/outer cavity that silently failed to cut anything."""
    hollow_source, _ = render.render("vase", {})
    solid_source, _ = render.render("vase", {"wall_thickness": 20})  # thick wall, still under the assert's limit (< 22.5 here)

    hollow_scad, solid_scad = tmp_path / "hollow.scad", tmp_path / "solid.scad"
    hollow_stl, solid_stl = tmp_path / "hollow.stl", tmp_path / "solid.stl"
    hollow_scad.write_text(hollow_source)
    solid_scad.write_text(solid_source)

    for scad, stl in ((hollow_scad, hollow_stl), (solid_scad, solid_stl)):
        result = subprocess.run(
            ["openscad", "--render", "-o", str(stl), str(scad)],
            capture_output=True, text=True, timeout=120,
        )
        assert result.returncode == 0, result.stderr

    # polyforge's own mesh inspector already handles both ASCII and binary
    # STL (OpenSCAD's CLI defaults to ASCII) and computes a real signed
    # volume -- reuse it rather than hand-rolling STL parsing again.
    from polyforge.geometry import inspect as mesh_inspect

    hollow_vol = mesh_inspect.inspect(hollow_stl)["absolute_volume_mm3"]
    solid_vol = mesh_inspect.inspect(solid_stl)["absolute_volume_mm3"]
    assert hollow_vol < solid_vol * 0.5, (
        f"hollow vase ({hollow_vol:.0f}mm3) should be much smaller than the "
        f"near-solid one ({solid_vol:.0f}mm3) -- the cavity may not be cutting"
    )
