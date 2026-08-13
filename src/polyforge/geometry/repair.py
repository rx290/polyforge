"""Conservative STL repair with before/after dimensional safeguards."""

from __future__ import annotations

from pathlib import Path


class RepairAborted(Exception):
    """Raised when a repair would change bounding-box size beyond the allowed limit."""


def require_trimesh():
    try:
        import trimesh
    except ImportError as exc:
        raise RuntimeError("mesh repair requires trimesh: python3 -m pip install trimesh") from exc
    return trimesh


def facts(mesh) -> dict:
    return {
        "vertices": int(len(mesh.vertices)),
        "faces": int(len(mesh.faces)),
        "bounds_mm": mesh.bounds.tolist(),
        "extents_mm": mesh.extents.tolist(),
        "watertight": bool(mesh.is_watertight),
        "winding_consistent": bool(mesh.is_winding_consistent),
        "volume_mm3": float(mesh.volume),
        "area_mm2": float(mesh.area),
    }


def repair(input_path: Path, output_path: Path, mode: str = "safe", max_size_change_mm: float = 0.02) -> dict:
    trimesh = require_trimesh()
    loaded = trimesh.load_mesh(input_path, process=False)
    if not isinstance(loaded, trimesh.Trimesh):
        raise ValueError("Input contains a scene or multiple unresolved meshes; inspect components before repair")
    before = facts(loaded)

    mesh = loaded.copy()
    mesh.merge_vertices()
    if hasattr(mesh, "unique_faces"):
        mesh.update_faces(mesh.unique_faces())
    if hasattr(mesh, "nondegenerate_faces"):
        mesh.update_faces(mesh.nondegenerate_faces())
    mesh.remove_unreferenced_vertices()
    trimesh.repair.fix_winding(mesh)
    trimesh.repair.fix_normals(mesh)
    if mode == "aggressive":
        trimesh.repair.fill_holes(mesh)
        mesh.process(validate=True)

    after = facts(mesh)
    deltas = [abs(a - b) for a, b in zip(before["extents_mm"], after["extents_mm"])]
    if max(deltas, default=0.0) > max_size_change_mm:
        raise RepairAborted(f"Repair aborted: bounding-size change {deltas} mm exceeds limit {max_size_change_mm} mm")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(output_path)
    return {
        "mode": mode,
        "input": str(input_path.resolve()),
        "output": str(output_path.resolve()),
        "before": before,
        "after": after,
        "extent_delta_mm": deltas,
    }
