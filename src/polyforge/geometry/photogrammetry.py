"""Offline multi-photo-to-mesh reconstruction: COLMAP (sparse SfM) handed off
to OpenMVS (CPU-capable dense reconstruction and meshing).

COLMAP's own dense multi-view-stereo (`patch_match_stereo`) requires CUDA
with no CPU fallback in the mainline binary -- confirmed directly by running
it without a GPU present ("Dense stereo reconstruction requires CUDA, which
is not available on your system", followed by an abort). So this uses COLMAP
only for its CPU-capable sparse pipeline (feature extraction, matching,
incremental SfM), then hands the sparse result to OpenMVS -- whose densify
and mesh stages build CPU-only by default -- for the part COLMAP itself
can't do without a GPU.

Unlike freecadcmd/blender, both colmap and the OpenMVS binaries give proper
nonzero exit codes on real failures (verified directly by deliberately
breaking each), so failure detection here is the ordinary kind: no
output-text scanning or start/end markers needed.

COLMAP's incremental mapper can register images into more than one
disconnected sub-model when the photo set doesn't give it enough overlap to
merge everything into one reconstruction. This picks whichever sub-model
registered the most images (via `colmap model_analyzer`, not a guess) as the
one to carry forward -- a photo set that fragments into several small
sub-models produced too little overlap for a good reconstruction regardless
of which fragment is chosen, so this doesn't try to be clever about it.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from . import inspect as mesh_inspect
from . import ply as ply_convert
from . import spec as mesh_spec


def find_colmap() -> str:
    configured = os.environ.get("COLMAP_BIN")
    candidate = configured or shutil.which("colmap")
    if not candidate:
        raise RuntimeError("COLMAP not found. Install colmap or set COLMAP_BIN to its binary.")
    return candidate


def find_openmvs_bin(name: str) -> str:
    env_key = f"OPENMVS_{name.upper()}_BIN"
    configured = os.environ.get(env_key)
    candidate = configured or shutil.which(name)
    if not candidate:
        raise RuntimeError(f"OpenMVS's {name} not found. Install openmvs or set {env_key} to its binary.")
    return candidate


def run(command: list[str], cwd: Path | None = None) -> str:
    completed = subprocess.run(command, text=True, capture_output=True, cwd=cwd)
    combined = (completed.stdout + "\n" + completed.stderr).strip()
    if completed.returncode:
        raise RuntimeError(f"Command failed ({completed.returncode}): {' '.join(command)}\n{combined}")
    return combined


def _registered_image_count(colmap: str, submodel: Path) -> int:
    output = run([colmap, "model_analyzer", "--path", str(submodel)])
    match = re.search(r"Registered images:\s*(\d+)", output)
    if not match:
        raise RuntimeError(f"could not parse registered image count from model_analyzer output:\n{output}")
    return int(match.group(1))


def _best_submodel(colmap: str, sparse_dir: Path) -> Path:
    candidates = [p for p in sorted(sparse_dir.iterdir()) if p.is_dir() and (p / "images.bin").exists()]
    if not candidates:
        raise RuntimeError(f"COLMAP produced no registered sparse model under {sparse_dir}")
    return max(candidates, key=lambda p: _registered_image_count(colmap, p))


def reconstruct(image_dir: Path, output_dir: Path, camera_model: str = "SIMPLE_RADIAL") -> dict:
    """Run the full sparse SfM (COLMAP) -> dense + mesh (OpenMVS) pipeline on
    a directory of photos, producing an STL plus the same validation
    artifacts (MESH_REPORT.md, MODEL_SPEC.md) the other backends write.

    The resulting mesh is reconstructed geometry, not editable parametric
    source -- treat it as evidence to measure and rebuild from, the same way
    the existing STL-reconstruct workflow already treats a scanned/damaged
    STL (see SKILL.md's "Reconstruct" guidance), not as a file to hand-edit.

    It also has no absolute real-world scale: structure-from-motion from
    photos alone recovers geometry only up to an arbitrary scale factor
    (confirmed directly -- a 60x40x30mm test box reconstructed at
    3.6x2.3x1.2mm, a consistent ~1/16.6 scale in every dimension, not noise).
    Measure a known real dimension on the physical object and rescale the
    mesh to match before trusting any of its measurements.
    """
    image_dir = Path(image_dir).resolve()
    if not image_dir.is_dir() or not any(image_dir.iterdir()):
        raise FileNotFoundError(f"no images found in {image_dir}")
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    colmap = find_colmap()
    database_path = output_dir / "database.db"
    sparse_dir = output_dir / "sparse"
    sparse_dir.mkdir(exist_ok=True)

    run([colmap, "feature_extractor",
         "--database_path", str(database_path),
         "--image_path", str(image_dir),
         "--ImageReader.single_camera", "1",
         "--ImageReader.camera_model", camera_model])
    run([colmap, "exhaustive_matcher", "--database_path", str(database_path)])
    run([colmap, "mapper",
         "--database_path", str(database_path),
         "--image_path", str(image_dir),
         "--output_path", str(sparse_dir)])

    submodel = _best_submodel(colmap, sparse_dir)

    undistorted_dir = output_dir / "undistorted"
    run([colmap, "image_undistorter",
         "--image_path", str(image_dir),
         "--input_path", str(submodel),
         "--output_path", str(undistorted_dir),
         "--output_type", "COLMAP"])

    interface_colmap = find_openmvs_bin("InterfaceCOLMAP")
    run([interface_colmap, "-i", ".", "-o", "scene.mvs"], cwd=undistorted_dir)

    densify = find_openmvs_bin("DensifyPointCloud")
    run([densify, "scene.mvs"], cwd=undistorted_dir)

    reconstruct_mesh = find_openmvs_bin("ReconstructMesh")
    run([reconstruct_mesh, "scene_dense.mvs"], cwd=undistorted_dir)
    mesh_ply = undistorted_dir / "scene_dense_mesh.ply"
    if not mesh_ply.exists():
        raise RuntimeError(
            "OpenMVS did not produce a mesh (scene_dense_mesh.ply missing). This usually means "
            "the photo set didn't give enough view overlap/coverage for a reconstructable surface -- "
            "retake with more photos and more overlap between consecutive shots."
        )

    stl_path = output_dir / f"{image_dir.name}.stl"
    try:
        ply_convert.convert(mesh_ply, stl_path)
    except ValueError as exc:
        raise RuntimeError(
            f"{exc}. The mesh-cleaning pass removed all geometry -- the photo set's view coverage "
            "was too thin for a usable surface. Retake with more photos, more overlap, and full "
            "coverage around the object."
        ) from exc

    mesh_data = mesh_inspect.inspect(stl_path)
    mesh_md = output_dir / "MESH_REPORT.md"
    mesh_md.write_text(mesh_inspect.markdown(mesh_data))

    spec_path = mesh_spec.write_spec(output_dir, image_dir, stl_path, mesh_spec.locate_manifest(image_dir, output_dir), mesh_data)
    return {"stl": stl_path, "mesh_report": mesh_md, "spec": spec_path}
