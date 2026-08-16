import shutil
from pathlib import Path

import pytest

from polyforge.geometry import inspect as mesh_inspect
from polyforge.geometry import photogrammetry

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "photogrammetry_box"

# 36 synthetic orbit photos (rendered from PolyForge's own box template via
# Blender/EEVEE with a noise-textured material and a checkered ground plane
# -- a flat untextured render is close to a worst case for SIFT feature
# matching; see photogrammetry.py's module docstring and project_polyforge
# memory for how that was discovered). Committed as a fixture rather than
# re-rendered per test run: deterministic, no Blender dependency for this
# test, and this exact photo set is already confirmed to reconstruct cleanly.
_HAVE_TOOLS = shutil.which("colmap") is not None and shutil.which("InterfaceCOLMAP") is not None and shutil.which("DensifyPointCloud") is not None and shutil.which("ReconstructMesh") is not None


def test_reconstruct_rejects_empty_directory(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(FileNotFoundError):
        photogrammetry.reconstruct(empty, tmp_path / "out")


def test_reconstruct_rejects_missing_directory(tmp_path):
    with pytest.raises(FileNotFoundError):
        photogrammetry.reconstruct(tmp_path / "does_not_exist", tmp_path / "out")


@pytest.mark.skipif(not _HAVE_TOOLS, reason="colmap and/or openmvs not installed")
def test_reconstruct_produces_a_real_mesh(tmp_path):
    result = photogrammetry.reconstruct(FIXTURE_DIR, tmp_path / "out")

    assert result["stl"].exists() and result["stl"].stat().st_size > 0
    assert result["mesh_report"].exists()
    assert result["spec"].exists()
    assert result["submodel_count"] >= 1
    assert result["submodel_image_count"] >= 1

    mesh_data = mesh_inspect.inspect(result["stl"])
    assert mesh_data["triangles"] > 0
    assert mesh_data["degenerate_triangles"] == 0
    # Not asserting watertightness here: a photogrammetry reconstruction only
    # covers what the cameras actually saw, so an open bottom surface (the
    # camera orbit never looked underneath the object) is expected, correct
    # behavior, not a bug -- unlike the generative template backends, which
    # must be watertight since they fully control the geometry.
