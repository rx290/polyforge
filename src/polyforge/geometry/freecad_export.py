"""Run a generated FreeCAD macro headlessly (freecadcmd) and validate the result.

No multi-view preview here (unlike the OpenSCAD backend): FreeCAD's offscreen
rendering needs its GUI/OpenGL stack (Xvfb + freecad, not freecadcmd), which is
a heavier dependency this phase doesn't take on. Export + mesh validation only.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from . import inspect as mesh_inspect
from . import spec as mesh_spec


def find_freecadcmd() -> str:
    configured = os.environ.get("FREECAD_BIN")
    candidate = (
        configured
        or shutil.which("freecadcmd")
        or shutil.which("FreeCADCmd")
        or shutil.which("freecadcmd-nightly")
    )
    if not candidate:
        raise RuntimeError("FreeCAD console CLI not found. Install FreeCAD or set FREECAD_BIN to freecadcmd/FreeCADCmd.")
    return candidate


def run(command: list[str]) -> str:
    completed = subprocess.run(command, text=True, capture_output=True)
    combined = (completed.stdout + "\n" + completed.stderr).strip()
    if completed.returncode:
        raise RuntimeError(f"Command failed ({completed.returncode}): {' '.join(command)}\n{combined}")
    # freecadcmd catches macro exceptions internally and exits 0 regardless --
    # the only signal is this line in its output, so check for it explicitly.
    if "Traceback (most recent call last)" in combined or "Exception while processing file" in combined:
        raise RuntimeError(f"FreeCAD macro raised an exception:\n{combined}")
    return combined


def project_paths(macro: Path):
    base = macro.parent.parent if macro.parent.name == "src" else macro.parent
    return base, base / "output"


def export(macro: Path) -> dict:
    macro = macro.resolve()
    if not macro.exists():
        raise FileNotFoundError(f"file not found: {macro}")
    freecadcmd = find_freecadcmd()
    base, output_dir = project_paths(macro)

    run([freecadcmd, str(macro)])

    stem = macro.stem
    stl = output_dir / f"{stem}.stl"
    step = output_dir / f"{stem}.step"
    if not stl.exists() or stl.stat().st_size == 0:
        raise RuntimeError("FreeCAD macro did not create a usable STL. Check the macro's own output dir convention.")
    if not step.exists() or step.stat().st_size == 0:
        raise RuntimeError("FreeCAD macro did not create a usable STEP file.")

    mesh_data = mesh_inspect.inspect(stl)
    mesh_md = base / "MESH_REPORT.md"
    mesh_md.write_text(mesh_inspect.markdown(mesh_data))

    spec_path = mesh_spec.write_spec(base, macro, stl, mesh_spec.locate_manifest(macro, base), mesh_data)
    return {"stl": stl, "step": step, "mesh_report": mesh_md, "spec": spec_path}
