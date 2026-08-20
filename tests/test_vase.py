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
        {"num_sides": 48, "facet_jitter": 0},  # near-smooth, not low-poly
        {"facet_jitter": 0},
        {"facet_jitter": 0.35},
        {"drainage_hole_d": 10},
        # every section forced to a plain cylinder (a straight tube)
        {"s1_type": 0, "s2_type": 0, "s3_type": 0, "s4_type": 0,
         "s1_end_d": 60, "s2_end_d": 60, "s3_end_d": 60, "s4_end_d": 60},
        # every section a straight cone (a simple uninterrupted taper)
        {"s1_type": 1, "s2_type": 1, "s3_type": 1, "s4_type": 1},
        # an hourglass waist via one bulge section (peak < both ends)
        {"s1_type": 3, "s1_end_d": 60, "s1_peak_d": 35},
        # a globe/bulb bulge (peak > both ends)
        {"s3_type": 3, "s3_end_d": 55, "s3_peak_d": 90},
        # uneven height fractions (don't need to sum to 1)
        {"s1_height_frac": 0.6, "s2_height_frac": 0.1, "s3_height_frac": 0.1, "s4_height_frac": 0.1},
        # holder ring enabled
        {"holder_ring_d": 6, "holder_ring_height_frac": 0.95},
        # textured base enabled
        {"base_texture_amplitude": 0.15, "base_texture_frequency": 12, "base_texture_height_frac": 0.3},
        # the combined "hourglass base, plain neck, bulb top, ring, texture" scenario
        {
            "s1_type": 3, "s1_end_d": 55, "s1_peak_d": 40, "s1_height_frac": 0.3,
            "s2_type": 0, "s2_end_d": 55, "s2_height_frac": 0.2,
            "s3_type": 3, "s3_end_d": 30, "s3_peak_d": 75, "s3_height_frac": 0.35,
            "s4_type": 0, "s4_end_d": 30, "s4_height_frac": 0.15,
            "holder_ring_d": 6, "holder_ring_height_frac": 0.98,
            "base_texture_amplitude": 0.1, "base_texture_frequency": 10, "base_texture_height_frac": 0.3,
            "num_sides": 32, "facet_jitter": 0, "total_twist_deg": 0,
        },
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
    source, _ = render.render("vase", {"s2_end_d": 10, "wall_thickness": 8})
    assert "wall_thickness is too large" in source


def test_vase_rejects_drainage_hole_bigger_than_interior():
    source, _ = render.render("vase", {"drainage_hole_d": 1000})
    assert "drainage_hole_d must be smaller" in source


def test_vase_rejects_zero_height_fraction():
    source, _ = render.render("vase", {"s2_height_frac": 0})
    assert "height_frac must be positive" in source


@pytest.mark.skipif(shutil.which("openscad") is None, reason="openscad CLI not installed")
def test_vase_is_genuinely_hollow_not_solid(tmp_path):
    """A real regression check, not just 'does it compile': a solid vase
    (wall_thickness effectively filling the whole profile) should be
    heavier than the actual hollow default at the same outer dimensions --
    catches an inner/outer cavity that silently failed to cut anything."""
    hollow_source, _ = render.render("vase", {})
    solid_source, _ = render.render("vase", {"wall_thickness": 20})  # thick wall, still under the assert's limit

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

    from polyforge.geometry import inspect as mesh_inspect

    hollow_vol = mesh_inspect.inspect(hollow_stl)["absolute_volume_mm3"]
    solid_vol = mesh_inspect.inspect(solid_stl)["absolute_volume_mm3"]
    assert hollow_vol < solid_vol * 0.5, (
        f"hollow vase ({hollow_vol:.0f}mm3) should be much smaller than the "
        f"thick-wall one ({solid_vol:.0f}mm3) -- the cavity may not be cutting"
    )


@pytest.mark.skipif(shutil.which("openscad") is None, reason="openscad CLI not installed")
def test_holder_ring_actually_adds_material(tmp_path):
    without_ring, _ = render.render("vase", {"holder_ring_d": 0})
    with_ring, _ = render.render("vase", {"holder_ring_d": 8, "holder_ring_height_frac": 0.9})

    without_scad, with_scad = tmp_path / "without.scad", tmp_path / "with.scad"
    without_stl, with_stl = tmp_path / "without.stl", tmp_path / "with.stl"
    without_scad.write_text(without_ring)
    with_scad.write_text(with_ring)
    for scad, stl in ((without_scad, without_stl), (with_scad, with_stl)):
        result = subprocess.run(
            ["openscad", "--render", "-o", str(stl), str(scad)],
            capture_output=True, text=True, timeout=120,
        )
        assert result.returncode == 0, result.stderr

    from polyforge.geometry import inspect as mesh_inspect

    vol_without = mesh_inspect.inspect(without_stl)["absolute_volume_mm3"]
    vol_with = mesh_inspect.inspect(with_stl)["absolute_volume_mm3"]
    assert vol_with > vol_without, "enabling holder_ring_d should add real material, not be a no-op"


@pytest.mark.skipif(shutil.which("openscad") is None, reason="openscad CLI not installed")
def test_textured_base_changes_the_surface_area(tmp_path):
    flat_source, _ = render.render("vase", {"base_texture_amplitude": 0})
    textured_source, _ = render.render(
        "vase", {"base_texture_amplitude": 0.15, "base_texture_frequency": 10, "base_texture_height_frac": 0.3}
    )
    flat_scad, textured_scad = tmp_path / "flat.scad", tmp_path / "textured.scad"
    flat_stl, textured_stl = tmp_path / "flat.stl", tmp_path / "textured.stl"
    flat_scad.write_text(flat_source)
    textured_scad.write_text(textured_source)
    for scad, stl in ((flat_scad, flat_stl), (textured_scad, textured_stl)):
        result = subprocess.run(
            ["openscad", "--render", "-o", str(stl), str(scad)],
            capture_output=True, text=True, timeout=120,
        )
        assert result.returncode == 0, result.stderr

    from polyforge.geometry import inspect as mesh_inspect

    flat_area = mesh_inspect.inspect(flat_stl)["surface_area_mm2"]
    textured_area = mesh_inspect.inspect(textured_stl)["surface_area_mm2"]
    assert textured_area > flat_area * 1.02, "a wavy textured surface should measurably increase surface area"


@pytest.mark.skipif(shutil.which("freecadcmd") is None, reason="freecadcmd not installed")
def test_holder_ring_is_watertight_on_freecad_backend(tmp_path):
    """Regression check for a real bug: a separately-built torus unioned
    onto the shell afterward produced non-manifold edges once the vase's
    own faceted/jittered surface met it unevenly around the circumference
    -- fixed by baking the ring in as a radius bump on the same profile
    instead of a boolean union. FreeCAD's own boolean happened to tolerate
    the old torus-union approach fine, so this is here mainly so a future
    regression back to a separate-torus design gets caught by whichever
    backend is actually sensitive to it, not just visually."""
    source, _ = render.render("vase", {"holder_ring_d": 6, "holder_ring_height_frac": 0.95}, backend="freecad")
    macro = tmp_path / "vase.FCMacro"
    macro.write_text(source)
    result = subprocess.run(["freecadcmd", str(macro)], capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr

    from polyforge.geometry import inspect as mesh_inspect

    stl = tmp_path / "output" / "vase.stl"
    assert stl.exists()
    mesh_data = mesh_inspect.inspect(stl)
    assert mesh_data["watertight_by_edge_count"], mesh_data


@pytest.mark.skipif(shutil.which("blender") is None, reason="blender not installed")
def test_holder_ring_is_watertight_on_blender_backend(tmp_path):
    """Same regression check as the FreeCAD test above, but this is the
    backend where the bug actually surfaced live: a separately-built torus,
    even carefully positioned to stay embedded in the wall, still produced
    a handful of non-manifold edges once unioned via Blender's bmesh
    boolean modifier specifically -- confirmed by exporting the torus mesh
    alone first (genuinely watertight on its own) before finding the defect
    only appeared post-union. Fixed by baking the ring in as a radius bump
    on the profile instead, which needs no boolean for this feature at all."""
    from polyforge.geometry import blender_export
    from polyforge.geometry import inspect as mesh_inspect

    source, _ = render.render("vase", {"holder_ring_d": 6, "holder_ring_height_frac": 0.95}, backend="blender")
    macro = tmp_path / "vase.blender.py"
    macro.write_text(source)
    result = blender_export.export(macro)

    mesh_data = mesh_inspect.inspect(result["stl"])
    assert mesh_data["watertight_by_edge_count"], mesh_data
