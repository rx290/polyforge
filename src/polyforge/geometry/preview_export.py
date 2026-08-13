"""Render seven labeled views of an OpenSCAD model, and export+validate an STL from it."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from . import inspect as mesh_inspect
from . import spec as mesh_spec

VIEWS = {
    "isometric": "55,0,25",
    "front": "90,0,0",
    "back": "90,0,180",
    "left": "90,0,-90",
    "right": "90,0,90",
    "top": "0,0,0",
    "bottom": "180,0,0",
}


def find_openscad() -> str:
    configured = os.environ.get("OPENSCAD_BIN")
    candidate = configured or shutil.which("openscad") or shutil.which("openscad-nightly")
    if not candidate:
        raise RuntimeError("OpenSCAD CLI not found. Install OpenSCAD or set OPENSCAD_BIN.")
    return candidate


def run(command: list[str]) -> str:
    completed = subprocess.run(command, text=True, capture_output=True)
    combined = (completed.stdout + "\n" + completed.stderr).strip()
    if completed.returncode:
        raise RuntimeError(f"Command failed ({completed.returncode}): {' '.join(command)}\n{combined}")
    if "ERROR:" in combined or "Parser error" in combined:
        raise RuntimeError(f"OpenSCAD reported an error:\n{combined}")
    return combined


def project_paths(scad: Path):
    base = scad.parent.parent if scad.parent.name == "src" else scad.parent
    return base, base / "output", base / "previews"


def render_views(openscad: str, scad: Path, preview_dir: Path, imgsize: str, definitions: list[str]) -> list[Path]:
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
            raise RuntimeError(f"OpenSCAD did not create a usable {name} image")
        outputs.append(out)
    return outputs


def preview(scad: Path, imgsize: str = "1200,900", definitions: list[str] | None = None) -> list[Path]:
    scad = scad.resolve()
    if not scad.exists():
        raise FileNotFoundError(f"file not found: {scad}")
    openscad = find_openscad()
    _, _, preview_dir = project_paths(scad)
    return render_views(openscad, scad, preview_dir, imgsize, definitions or [])


def export(scad: Path, imgsize: str = "1200,900", definitions: list[str] | None = None) -> dict:
    scad = scad.resolve()
    if not scad.exists():
        raise FileNotFoundError(f"file not found: {scad}")
    definitions = definitions or []
    openscad = find_openscad()
    base, output_dir, preview_dir = project_paths(scad)
    views = render_views(openscad, scad, preview_dir, imgsize, definitions)

    output_dir.mkdir(parents=True, exist_ok=True)
    stl = output_dir / f"{scad.stem}.stl"
    cmd = [openscad, "--render"]
    for definition in definitions:
        cmd.extend(["-D", definition])
    cmd.extend(["-o", str(stl), str(scad)])
    run(cmd)
    if not stl.exists() or stl.stat().st_size == 0:
        raise RuntimeError("OpenSCAD did not create a usable STL")

    mesh_data = mesh_inspect.inspect(stl)
    mesh_json = output_dir / f"{scad.stem}.mesh.json"
    mesh_json.write_text(json.dumps(mesh_data, indent=2) + "\n")
    mesh_md = base / "MESH_REPORT.md"
    mesh_md.write_text(mesh_inspect.markdown(mesh_data))

    spec_path = mesh_spec.write_spec(base, scad, stl, mesh_spec.locate_manifest(scad, base), mesh_data)
    return {"views": views, "stl": stl, "mesh_report": mesh_md, "spec": spec_path}
