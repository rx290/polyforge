"""PolyForge command-line entry point.

Runs fully standalone, no agent, no LLM required for the default `templates`
engine. See README.md for the full command reference.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import render, templates
from .geometry import blender_export
from .geometry import freecad_export
from .geometry import inspect as mesh_inspect
from .geometry import photogrammetry
from .geometry import preview_export
from .geometry import repair as mesh_repair
from .nlu import ollama_client, template_matcher

FREECAD_SUFFIXES = {".fcmacro", ".fcstd"}


def _backend_for(path: Path) -> str:
    name = path.name.lower()
    if name.endswith(".blender.py"):
        return "blender"
    if path.suffix.lower() in FREECAD_SUFFIXES:
        return "freecad"
    return "openscad"


def _cmd_list_templates(args) -> int:
    for t in templates.all_templates():
        print(f"{t.key}: {t.title}")
        print(f"  {t.description}")
        for p in t.params:
            print(f"    {p.name} = {p.default}{p.unit}  ({p.description})")
    return 0


def _load_engine(name: str):
    if name == "templates":
        return template_matcher
    if name == "llm":
        from .nlu import llm_backend

        return llm_backend
    raise ValueError(f"unknown engine: {name}")


def _cmd_design(args) -> int:
    engine = _load_engine(args.engine)
    try:
        if args.engine == "llm":
            llm_kwargs = {"base_url": args.llm_url, "model": args.llm_model, "auto_start": not args.no_auto_start}
            if args.llm_timeout is not None:
                llm_kwargs["timeout"] = args.llm_timeout
            result = engine.match(args.text, **llm_kwargs)
        else:
            result = engine.match(args.text)
    except Exception as exc:  # noqa: BLE001 - surfaced to the user as a clean CLI error
        print(f"error: {exc}", file=sys.stderr)
        return 1

    override_params = dict(item.split("=", 1) for item in args.set or [])
    override_params = {k: float(v) for k, v in override_params.items()}
    params = {**result.params, **override_params}

    try:
        source, merged_params = render.render(result.template_key, params, backend=args.backend)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    ext = render.BACKEND_EXTENSIONS[args.backend]
    out_path = args.out or Path(f"{result.template_key}{ext}")
    out_path.write_text(source)

    print(f"Template: {result.template_key} (confidence {result.confidence:.2f})")
    for note in result.notes:
        print(f"  - {note}")
    print("Parameters:")
    for name, value in merged_params.items():
        print(f"  {name} = {value}")
    print(f"Wrote {out_path}")
    return 0


def _cmd_preview(args) -> int:
    backend = _backend_for(args.source)
    if backend == "freecad":
        print("error: preview (multi-view PNG) isn't available for the FreeCAD backend yet. "
              "It needs FreeCAD's GUI/OpenGL stack, not just freecadcmd. Use `export` to get a "
              "validated STL/STEP instead.", file=sys.stderr)
        return 1
    if backend == "blender":
        print("error: preview (multi-view PNG) isn't available for the Blender backend yet. "
              "It needs Blender's GUI/OpenGL stack, not just --background. Use `export` to get a "
              "validated STL instead.", file=sys.stderr)
        return 1
    try:
        views = preview_export.preview(args.source, imgsize=args.imgsize, definitions=args.definitions)
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print("Generated views:")
    for view in views:
        print(f"  {view}")
    return 0


def _cmd_export(args) -> int:
    backend = _backend_for(args.source)
    try:
        if backend == "freecad":
            result = freecad_export.export(args.source)
        elif backend == "blender":
            result = blender_export.export(args.source)
        else:
            result = preview_export.export(args.source, imgsize=args.imgsize, definitions=args.definitions)
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if "views" in result:
        print("Generated views:")
        for view in result["views"]:
            print(f"  {view}")
    print(f"STL: {result['stl']}")
    if "step" in result:
        print(f"STEP: {result['step']}")
    print(f"Mesh report: {result['mesh_report']}")
    print(f"Specification: {result['spec']}")
    return 0


def _cmd_inspect(args) -> int:
    result = mesh_inspect.inspect(args.stl, tolerance=args.tolerance)
    print(json.dumps(result, indent=2))
    if args.json:
        args.json.write_text(json.dumps(result, indent=2) + "\n")
    if args.markdown:
        args.markdown.write_text(mesh_inspect.markdown(result))
    return 0


def _cmd_reconstruct_from_photos(args) -> int:
    try:
        result = photogrammetry.reconstruct(args.image_dir, args.out, camera_model=args.camera_model)
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"STL: {result['stl']}")
    print(f"Mesh report: {result['mesh_report']}")
    print(f"Specification: {result['spec']}")
    if result["submodel_count"] > 1:
        print(f"Warning: COLMAP fragmented this photo set into {result['submodel_count']} disconnected "
              f"reconstructions; used the largest ({result['submodel_image_count']} registered images). "
              "More overlap between shots would let it merge into one.")
    print("This mesh is reconstructed evidence, not editable parametric source -- "
          "measure it and rebuild important geometry parametrically before printing.")
    print("It also has NO absolute real-world scale: structure-from-motion recovers geometry "
          "only up to an arbitrary scale factor from photos alone. Measure a known real "
          "dimension on the physical object with calipers and rescale the mesh to match "
          "before trusting any of its measurements.")
    return 0


def _cmd_repair(args) -> int:
    try:
        report = mesh_repair.repair(args.input, args.output, mode=args.mode, max_size_change_mm=args.max_size_change_mm)
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2))
    return 0


def _cmd_ollama_status(args) -> int:
    base_url = args.llm_url or ollama_client.DEFAULT_BASE_URL
    try:
        status = ollama_client.ensure_server(base_url, auto_start=not args.no_auto_start)
    except ollama_client.OllamaUnavailable as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"Server: {status.base_url}")
    print(f"Reachable: yes{' (just started it)' if status.started_by_us else ''}")
    print(f"Version: {status.version or 'unknown (endpoint not supported on this build)'}")
    if not status.models:
        print("Models: none installed -- `ollama pull <model>` to add one")
    else:
        print("Models:")
        for m in status.models:
            details = " / ".join(v for v in (m.parameter_size, m.quantization) if v)
            print(f"  - {m.name}" + (f"  ({details})" if details else ""))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="polyforge", description="Offline parametric CAD generation and validation.")
    sub = parser.add_subparsers(dest="command", required=True)

    list_p = sub.add_parser("list-templates", help="list known part templates and their parameters")
    list_p.set_defaults(func=_cmd_list_templates)

    design_p = sub.add_parser("design", help="turn request text into a .scad or .FCMacro file")
    design_p.add_argument("text", help="what to build, e.g. 'a wall shelf 200x150x5mm with 2 M4 holes'")
    design_p.add_argument("--engine", choices=("templates", "llm"), default="templates")
    design_p.add_argument("--backend", choices=("openscad", "freecad", "blender"), default="openscad")
    design_p.add_argument("--out", type=Path, default=None)
    design_p.add_argument("--set", action="append", metavar="name=value", help="override a specific parameter")
    design_p.add_argument("--llm-url", default=None, help="local model server URL (engine=llm only)")
    design_p.add_argument("--llm-model", default=None, help="local model name (engine=llm only); default auto-picks an installed one")
    design_p.add_argument("--no-auto-start", action="store_true", help="don't launch `ollama serve` automatically if it's not running (engine=llm only)")
    design_p.add_argument("--llm-timeout", type=float, default=None, help="seconds to wait for the local model's response (engine=llm only, default 180s -- local generation, especially a 'thinking' model, can legitimately take over a minute)")
    design_p.set_defaults(func=_cmd_design)

    ollama_status_p = sub.add_parser("ollama-status", help="check/start the local Ollama server and list its installed models")
    ollama_status_p.add_argument("--llm-url", default=None, help="server URL (default http://localhost:11434)")
    ollama_status_p.add_argument("--no-auto-start", action="store_true", help="only report status; don't launch `ollama serve` if it's not running")
    ollama_status_p.set_defaults(func=_cmd_ollama_status)

    preview_p = sub.add_parser("preview", help="render seven labeled views of a .scad model (OpenSCAD only)")
    preview_p.add_argument("source", type=Path)
    preview_p.add_argument("-D", dest="definitions", action="append", default=[])
    preview_p.add_argument("--imgsize", default="1200,900")
    preview_p.set_defaults(func=_cmd_preview)

    export_p = sub.add_parser("export", help="export + validate a model; backend is chosen by file extension (.scad vs .FCMacro)")
    export_p.add_argument("source", type=Path)
    export_p.add_argument("-D", dest="definitions", action="append", default=[])
    export_p.add_argument("--imgsize", default="1200,900")
    export_p.set_defaults(func=_cmd_export)

    inspect_p = sub.add_parser("inspect", help="inspect an STL's geometry/topology")
    inspect_p.add_argument("stl", type=Path)
    inspect_p.add_argument("--tolerance", type=float, default=1e-5)
    inspect_p.add_argument("--json", type=Path, default=None)
    inspect_p.add_argument("--markdown", type=Path, default=None)
    inspect_p.set_defaults(func=_cmd_inspect)

    reconstruct_p = sub.add_parser(
        "reconstruct-from-photos",
        help="turn a directory of photos into an STL mesh (offline COLMAP + OpenMVS photogrammetry)",
    )
    reconstruct_p.add_argument("image_dir", type=Path, help="directory of photos of the object; shoot at least 3 elevation rings (not just one), ~10 azimuths each, ~30 photos minimum -- fewer rings fails outright regardless of photo count")
    reconstruct_p.add_argument("--out", type=Path, required=True, help="output workspace directory (STL, MESH_REPORT.md, MODEL_SPEC.md written here)")
    reconstruct_p.add_argument("--camera-model", default="SIMPLE_RADIAL", help="COLMAP camera model for images without usable EXIF calibration")
    reconstruct_p.set_defaults(func=_cmd_reconstruct_from_photos)

    repair_p = sub.add_parser("repair", help="conservative STL repair (requires trimesh)")
    repair_p.add_argument("input", type=Path)
    repair_p.add_argument("output", type=Path)
    repair_p.add_argument("--mode", choices=("safe", "aggressive"), default="safe")
    repair_p.add_argument("--max-size-change-mm", type=float, default=0.02)
    repair_p.set_defaults(func=_cmd_repair)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
