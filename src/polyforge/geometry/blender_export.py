"""Run a generated Blender macro headlessly (blender --background --python) and
validate the result.

Mesh-only, unlike the FreeCAD backend: bpy has no B-rep kernel, so this writes
STL and nothing else. No preview either, for the same offscreen-GUI reason as
FreeCAD's freecadcmd.

Blender, like freecadcmd, exits 0 even when the script raises -- confirmed by
running a script with a deliberate uncaught exception and observing returncode
0 with a full traceback on stderr. Unlike freecadcmd, Blender ALSO prints a
benign traceback of its own on every single headless invocation (an unrelated
bl_pkg addon failing to import optional remote-asset-library dependencies),
before any of our script's code runs -- and, confirmed the same way, ANOTHER
one during Blender's own shutdown teardown, after our script has already
finished successfully. So a plain "Traceback" substring check, or even an
"everything after our start marker" check, would misfire. Every generated
macro (see templates.base.blender_macro) prints a "POLYFORGE_SCRIPT_START"
marker as its first line and a "POLYFORGE_SCRIPT_END" marker as its last;
failure detection only looks at the text strictly between those two markers.
If POLYFORGE_SCRIPT_END never appears, the script crashed before finishing --
treated as a failure regardless of what's in that trailing text.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from . import inspect as mesh_inspect
from . import spec as mesh_spec

START_MARKER = "POLYFORGE_SCRIPT_START"
END_MARKER = "POLYFORGE_SCRIPT_END"


def find_blender() -> str:
    configured = os.environ.get("BLENDER_BIN")
    candidate = configured or shutil.which("blender")
    if not candidate:
        raise RuntimeError("Blender CLI not found. Install Blender or set BLENDER_BIN to the blender binary.")
    return candidate


def run(command: list[str]) -> str:
    completed = subprocess.run(command, text=True, capture_output=True)
    combined = (completed.stdout + "\n" + completed.stderr).strip()
    if completed.returncode:
        raise RuntimeError(f"Command failed ({completed.returncode}): {' '.join(command)}\n{combined}")
    # Blender catches script exceptions internally and exits 0 regardless --
    # same gotcha as freecadcmd. Unlike freecadcmd, it also emits unrelated
    # benign tracebacks of its own around the script's run (one at startup
    # before the script begins, another during shutdown after it ends), so
    # only the text strictly between our own start/end markers is checked.
    if START_MARKER not in combined or END_MARKER not in combined:
        raise RuntimeError(f"Blender macro did not run to completion (missing start/end marker):\n{combined}")
    _, _, after_start = combined.partition(START_MARKER)
    script_output, _, _ = after_start.partition(END_MARKER)
    if "Traceback (most recent call last)" in script_output:
        raise RuntimeError(f"Blender macro raised an exception:\n{script_output}")
    return combined


def project_paths(macro: Path):
    base = macro.parent.parent if macro.parent.name == "src" else macro.parent
    return base, base / "output"


def export(macro: Path) -> dict:
    macro = macro.resolve()
    if not macro.exists():
        raise FileNotFoundError(f"file not found: {macro}")
    blender = find_blender()
    base, output_dir = project_paths(macro)

    run([blender, "--background", "--python", str(macro)])

    stem = macro.stem
    stl = output_dir / f"{stem}.stl"
    if not stl.exists() or stl.stat().st_size == 0:
        raise RuntimeError("Blender macro did not create a usable STL. Check the macro's own output dir convention.")

    mesh_data = mesh_inspect.inspect(stl)
    mesh_md = base / "MESH_REPORT.md"
    mesh_md.write_text(mesh_inspect.markdown(mesh_data))

    spec_path = mesh_spec.write_spec(base, macro, stl, mesh_spec.locate_manifest(macro, base), mesh_data)
    return {"stl": stl, "mesh_report": mesh_md, "spec": spec_path}
