"""PolyForge command-line entry point.

Runs fully standalone, no agent, no LLM required for the default `templates`
engine. See README.md for the full command reference.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from . import hardware, render, templates
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
    template = templates.get(result.template_key)
    if template.printability_check is not None:
        for note in template.printability_check(merged_params):
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


def _cmd_hardware_scan(args) -> int:
    gpu = hardware.detect_gpu()
    rec = hardware.recommend_model(gpu)

    if gpu.vendor == "none":
        print("GPU: none detected (or nvidia-smi/rocm-smi not found on PATH)")
    else:
        print(f"GPU: {gpu.name or gpu.vendor} ({gpu.vendor}, via {gpu.detected_via})")
        print(f"VRAM: {gpu.vram_mb} MB" if gpu.vram_mb is not None else "VRAM: unknown")

    print(f"Recommended model: {rec.model}  [{rec.tier}]")
    print(f"Reason: {rec.reason}")
    print(
        "This is a rule of thumb (~1GB VRAM per 1B parameters at Q4 quantization, plus "
        "headroom) -- not a guarantee. A model that fits can still run slowly, and actual "
        "context length used matters too."
    )

    if args.pull:
        from .nlu import ollama_client

        try:
            ollama_client.ensure_server(auto_start=True)
        except ollama_client.OllamaUnavailable as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(f"Pulling {rec.model} ...")
        binary = ollama_client.find_ollama_binary()
        completed = subprocess.run([binary, "pull", rec.model])
        return completed.returncode
    return 0


def _cmd_gui(args) -> int:
    from .gui import server as gui_server

    workdir = args.workdir or Path(tempfile.mkdtemp(prefix="polyforge_gui_"))
    gui_server.serve(workdir, port=args.port, open_browser=not args.no_browser)
    return 0


def _cmd_character(args) -> int:
    from . import character

    def progress(done, total, label):
        print(f"[{done}/{total}] {label}", flush=True)

    try:
        res = character.generate(args.text, args.out, height_mm=args.height, candidates=args.candidates,
                                 image_model=args.image_model, quality=args.quality, style=args.style, on_progress=progress)
    except character.CharacterError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"STL:   {res.stl}")
    print(f"image: {res.image}")
    print(f"check: {res.summary}")
    if res.anatomy_scores:
        print(f"candidate scores: {res.anatomy_scores}")
    return 0


def _cmd_robot(args) -> int:
    import json as _json
    from .robot.builder import build
    from .robot import catalog
    if args.list_parts:
        for k in catalog.keys():
            p = catalog.get(k)
            print(f"{k:28s} {p['category']:10s} {p['label']}{'' if p.get('verified') else '  (unverified: measure)'}")
        return 0
    if args.mounts:
        from .robot import mounts as M
        k = args.mounts
        cat = catalog.get(k)["category"]
        if cat == "servo":
            parts = {f"cradle_{k}": M.servo_cradle(k, hollow_axis=args.hollow), f"u_bracket_{k}": M.servo_u_bracket(k, hollow_axis=args.hollow),
                     f"horn_coupler_{k}": M.horn_coupler(k), f"l_joint_{k}": M.servo_l_joint(k)}
            if args.hollow:
                parts[f"hollow_pivot_{k}"] = M.hollow_pivot(k)
        elif cat == "stepper":
            parts = {f"mount_{k}": M.byj_mount(k) if "28byj" in k else M.nema_mount(k)}
        elif cat in ("gear_motor", "dc_motor"):
            parts = {f"mount_{k}": M.gear_motor_mount(k)}
        elif cat == "battery":
            parts = {f"tray_{k}": M.battery_tray(k)}
        else:
            base, lid, meta = M.enclosure(k)
            parts = {f"tray_{k}": M.board_tray(k), f"enclosure_{k}": (base, meta), f"enclosure_{k}_lid": (lid, {})}
        res = M.export_checked(parts, args.out, sheet_title=f"mounts for {k}")
        for n, r in res.items():
            print(f"{'ok ' if r['check']['ok'] else 'FAIL'} {n}.stl {'; '.join(r['check']['problems'])}")
        print(f"contact sheet: {args.out / 'contact_sheet.png'}")
        return 0 if all(r["check"]["ok"] for r in res.values()) else 1
    if not args.spec:
        print("error: give a spec JSON (see polyforge/robot/builder.py) or --list-parts", file=sys.stderr)
        return 1
    spec = _json.loads(args.spec.read_text())
    if spec.get("type") == "quadruped":             # 12-servo SpotMicro-like walker
        from .robot.quadruped import build_quadruped
        r = build_quadruped(spec, args.out)
        print(f"body {r['body_mm']} mm, femur {r['femur']} mm, tibia {r['tibia']} mm")
        for k, ok in r["print_checks"].items():
            print(f"{'ok ' if ok else 'FAIL'} print check {k} (x{r['print_counts'].get(k, 1)})")
        for c in r["clashes"]:
            print(f"FAIL clash {c['a']} / {c['b']} {c['mm3']} mm3")
        print(f"files: {args.out}/print/*.stl, assembly.png, BOM.md, ASSEMBLY.md"); [print("check:", w) for w in r["warnings"]]
        return 0 if all(r["print_checks"].values()) and not r["clashes"] else 1
    if spec.get("type") == "biped":                 # 4-servo walker / roller
        from .robot.biped import build_biped
        r = build_biped(spec, args.out)
        print(f"body {r['body_mm']} mm, inner {r['inner_mm']} mm")
        for k, ok in r["fits"].items():
            print(f"{'ok ' if ok else 'FAIL'} {k}")
        print("files:", ", ".join(r["files"])); [print("check:", w) for w in r["warnings"]]
        return 0 if all(r["fits"].values()) and all(r.get("print_checks", {}).values()) else 1
    try:
        r = build(spec, args.out)
    except (KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"deck {r['deck_mm'][0]} x {r['deck_mm'][1]} mm, wheels {r['wheel_d']} mm")
    print("files:", ", ".join(f"{f}.stl/.step" for f in r["files"]))
    print("screws:", ", ".join(f"{n} x {k}" for k, n in r["screws"].items()))
    for w in r["warnings"]:
        print("check:", w)
    return 0


def _cmd_make(args) -> int:
    from .make import make

    res = make(args.text, args.out, rounds=args.rounds, lang=args.lang, on_progress=lambda d, t, l: print(f"[{d}/{t}] {l}", flush=True))
    last = res.report["history"][-1]
    if not res.ok:
        print("error: no valid part after", res.rounds, "rounds; last problems:", "; ".join(last["problems"]), file=sys.stderr)
        print("script kept at", res.script, file=sys.stderr)
        return 1
    print(f"OK in {res.rounds} round(s): {res.report['size_mm']} mm")
    print(f"STEP: {res.step}\nSTL:  {res.stl}\nscript (editable): {res.script}")
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

    hw_p = sub.add_parser("hardware-scan", help="detect GPU/VRAM (NVIDIA/CUDA or AMD/ROCm) and recommend an Ollama model size to match")
    hw_p.add_argument("--pull", action="store_true", help="also `ollama pull` the recommended model (starts the server first if needed)")
    hw_p.set_defaults(func=_cmd_hardware_scan)

    char_p = sub.add_parser("character", help="describe any character, figure or scene -> printable STL (local GPU image-to-3D pipeline)")
    char_p.add_argument("text", help="e.g. 'three Spider-Man figures pointing at each other' or 'a six-winged angel with a halo'")
    char_p.add_argument("--out", type=Path, default=Path("characters"), help="output folder (default ./characters)")
    char_p.add_argument("--height", type=float, default=150.0, help="figure height in mm (default 150)")
    char_p.add_argument("--candidates", type=int, default=4, help="images to draw; a local vision model keeps the most printable (default 4)")
    char_p.add_argument("--image-model", choices=("flux", "sdxl"), default="flux", help="flux: better hands/faces, slower; sdxl: fast draft")
    char_p.add_argument("--style", choices=("collectible", "anime", "manga", "comic", "chibi", "realistic"), default="collectible")
    char_p.add_argument("--quality", choices=("full", "fast"), default="full", help="3D detail (fast uses less VRAM)")
    char_p.set_defaults(func=_cmd_character)

    robot_p = sub.add_parser("robot", help="printable robot chassis sized around real boards and motors (STEP + STL + BOM)")
    robot_p.add_argument("spec", type=Path, nargs="?", help="robot spec JSON")
    robot_p.add_argument("--out", type=Path, default=Path("robot"))
    robot_p.add_argument("--list-parts", action="store_true", help="list the component library")
    robot_p.add_argument("--mounts", metavar="PART", help="print-checked mounts for one library part (board, servo, motor, battery)")
    robot_p.add_argument("--hollow", action="store_true", help="with --mounts on a servo: hollow-axis joint for wires")
    robot_p.set_defaults(func=_cmd_robot)

    make_p = sub.add_parser("make", help="describe a functional part with exact sizes, get checked CAD (STEP + STL + script)")
    make_p.add_argument("text", help="e.g. 'a storage box 120x80x50 mm, 2 mm walls, open top, 3 equal dividers'")
    make_p.add_argument("--out", type=Path, default=Path("made"))
    make_p.add_argument("--rounds", type=int, default=4, help="fix-and-retry rounds (default 4)")
    make_p.add_argument("--lang", choices=("openscad", "build123d"), default="openscad", help="openscad: most reliable with free models; build123d: also writes STEP")
    make_p.set_defaults(func=_cmd_make)

    gui_p = sub.add_parser("gui", help="start the local web GUI (stdlib http.server, no extra dependencies)")
    gui_p.add_argument("--port", type=int, default=8420)
    gui_p.add_argument("--workdir", type=Path, default=None, help="where generated files go (default: a fresh temp directory)")
    gui_p.add_argument("--no-browser", action="store_true", help="don't automatically open a browser tab")
    gui_p.set_defaults(func=_cmd_gui)

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
