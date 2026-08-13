#!/usr/bin/env python3
"""Conservative STL repair with before/after dimensional safeguards."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def require_trimesh():
    try:
        import trimesh
    except ImportError as exc:
        raise SystemExit("mesh_repair.py requires trimesh: python3 -m pip install trimesh") from exc
    return trimesh


def facts(mesh):
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--mode", choices=("safe", "aggressive"), default="safe")
    parser.add_argument("--max-size-change-mm", type=float, default=0.02)
    args = parser.parse_args()
    trimesh = require_trimesh()
    loaded = trimesh.load_mesh(args.input, process=False)
    if not isinstance(loaded, trimesh.Trimesh):
        raise SystemExit("Input contains a scene or multiple unresolved meshes; inspect components before repair")
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
    if args.mode == "aggressive":
        trimesh.repair.fill_holes(mesh)
        mesh.process(validate=True)

    after = facts(mesh)
    deltas = [abs(a - b) for a, b in zip(before["extents_mm"], after["extents_mm"])]
    if max(deltas, default=0.0) > args.max_size_change_mm:
        raise SystemExit(f"Repair aborted: bounding-size change {deltas} mm exceeds limit")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(args.output)
    report = {
        "mode": args.mode,
        "input": str(args.input.resolve()),
        "output": str(args.output.resolve()),
        "before": before,
        "after": after,
        "extent_delta_mm": deltas,
    }
    report_path = args.output.with_suffix(".repair.json")
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
