#!/usr/bin/env python3
"""Render seven views and optionally export/document an OpenSCAD model."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


VIEWS = {
    "isometric": "55,0,25",
    "front": "90,0,0",
    "back": "90,0,180",
    "left": "90,0,-90",
    "right": "90,0,90",
    "top": "0,0,0",
    "bottom": "180,0,0",
}


def find_openscad():
    configured = os.environ.get("OPENSCAD_BIN")
    candidate = configured or shutil.which("openscad") or shutil.which("openscad-nightly")
    if not candidate:
        raise SystemExit("OpenSCAD CLI not found. Install OpenSCAD or set OPENSCAD_BIN.")
    return candidate


def run(command):
    completed = subprocess.run(command, text=True, capture_output=True)
    combined = (completed.stdout + "\n" + completed.stderr).strip()
    if completed.returncode:
        raise SystemExit(f"Command failed ({completed.returncode}): {' '.join(command)}\n{combined}")
    if "ERROR:" in combined or "Parser error" in combined:
        raise SystemExit(f"OpenSCAD reported an error:\n{combined}")
    return combined


def project_paths(scad):
    base = scad.parent.parent if scad.parent.name == "src" else scad.parent
    return base, base / "output", base / "previews"


def render_views(openscad, scad, preview_dir, imgsize, definitions):
    preview_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for name, rotation in VIEWS.items():
        out = preview_dir / f"{name}.png"
        cmd = [openscad, "--render", "--autocenter", "--viewall", "--projection=o", f"--camera=0,0,0,{rotation},0", f"--imgsize={imgsize}"]
        for definition in definitions:
            cmd.extend(["-D", definition])
        cmd.extend(["-o", str(out), str(scad)])
        run(cmd)
        if not out.exists() or out.stat().st_size == 0:
            raise SystemExit(f"OpenSCAD did not create a usable {name} image")
        outputs.append(out)
    return outputs


def locate_manifest(scad, base):
    candidates = [scad.with_suffix(".json"), base / "model-manifest.json", base / "MODEL_MANIFEST.json"]
    return next((p for p in candidates if p.exists()), None)


def write_spec(base, scad, stl, manifest_path, mesh_data):
    manifest = json.loads(manifest_path.read_text()) if manifest_path else {}
    size = mesh_data["bounds_mm"]["size"]
    lines = [
        f"# {manifest.get('name', scad.stem)} — model specification",
        "",
        f"- Revision: {manifest.get('revision', 'unspecified')}",
        f"- Purpose: {manifest.get('purpose', 'unspecified')}",
        f"- Units: {manifest.get('units', 'mm')}",
        f"- Editable source: `{scad.name}`",
        f"- Exported mesh: `{stl.name}`",
        f"- Measured overall size (X × Y × Z): {size[0]:.3f} × {size[1]:.3f} × {size[2]:.3f} mm",
        f"- Printer profile: {manifest.get('printer_profile', 'unspecified')}",
        f"- Nozzle: {manifest.get('nozzle_mm', 'unspecified')} mm",
        f"- Material: {manifest.get('material', 'unspecified')}",
        f"- Orientation: {manifest.get('orientation', 'unspecified')}",
        "",
        "## Parameters",
        "",
    ]
    for item in manifest.get("parameters", []):
        lines.append(f"- `{item.get('name')}` = {item.get('value')} ({item.get('kind', 'nominal')}): {item.get('description', '')}")
    lines.extend(["", "## Functional features", ""])
    for feature in manifest.get("features", []):
        details = ", ".join(f"{k}={v}" for k, v in feature.items() if k not in {"type", "description"})
        lines.append(f"- {feature.get('type', 'feature')}: {feature.get('description', '')}" + (f" ({details})" if details else ""))
    lines.extend(["", "## Assumptions", ""])
    lines.extend(f"- {v}" for v in manifest.get("assumptions", []))
    lines.extend(["", "## Warnings", ""])
    lines.extend(f"- {v}" for v in manifest.get("warnings", []))
    lines.extend(["", "## Validation", "", f"- Watertight by edge count: {'yes' if mesh_data['watertight_by_edge_count'] else 'no'}", f"- Boundary edges: {mesh_data['boundary_edges']}", f"- Non-manifold edges: {mesh_data['nonmanifold_edges']}", "- Seven orthographic/isometric images were generated; they still require visual inspection.", ""])
    (base / "MODEL_SPEC.md").write_text("\n".join(lines))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("preview", "export"))
    parser.add_argument("scad", type=Path)
    parser.add_argument("-D", dest="definitions", action="append", default=[])
    parser.add_argument("--imgsize", default="1200,900")
    args = parser.parse_args()
    scad = args.scad.resolve()
    if not scad.exists():
        parser.error(f"file not found: {scad}")
    openscad = find_openscad()
    base, output_dir, preview_dir = project_paths(scad)
    views = render_views(openscad, scad, preview_dir, args.imgsize, args.definitions)
    print("Generated views:")
    for view in views:
        print(view)
    if args.command == "preview":
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    stl = output_dir / f"{scad.stem}.stl"
    cmd = [openscad, "--render"]
    for definition in args.definitions:
        cmd.extend(["-D", definition])
    cmd.extend(["-o", str(stl), str(scad)])
    run(cmd)
    if not stl.exists() or stl.stat().st_size == 0:
        raise SystemExit("OpenSCAD did not create a usable STL")

    script_dir = Path(__file__).resolve().parent
    mesh_json = output_dir / f"{scad.stem}.mesh.json"
    mesh_md = base / "MESH_REPORT.md"
    inspect_cmd = [sys.executable, str(script_dir / "stl_inspect.py"), str(stl), "--json", str(mesh_json), "--markdown", str(mesh_md)]
    run(inspect_cmd)
    mesh_data = json.loads(mesh_json.read_text())
    write_spec(base, scad, stl, locate_manifest(scad, base), mesh_data)
    print(f"STL: {stl}\nSpecification: {base / 'MODEL_SPEC.md'}\nMesh report: {mesh_md}")


if __name__ == "__main__":
    main()
