"""Describe a functional part, get exact CAD: an LLM writes the model, we build and check it, and feed errors back.

For things whose sizes must be right (containers, organisers, brackets, mounts, enclosures, adapters). The model
writes OpenSCAD (default: free models are far more reliable at it) or build123d (also gives STEP). PolyForge builds
it, checks it is one closed solid sitting on Z=0 whose bounding box matches every overall size stated in the
request, and loops the problems back up to `rounds` times. Output: STL (+ STEP for build123d) + the editable script.

LLM endpoint: any OpenAI-compatible server. Defaults to the local FreeLLMAPI router with a fallback chain
(POLYFORGE_MAKE_URL, POLYFORGE_MAKE_MODEL as a comma list, key from POLYFORGE_MAKE_KEY_FILE).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

SYSTEM_SCAD = textwrap.dedent("""
    You write OpenSCAD for 3D-printable functional parts. Rules:
    - Millimetres. Z is up; the part sits on Z=0 (no negative Z). Use $fn=96 for round features.
    - Make every stated size exact: outer dimensions, wall/floor thickness, hole diameters and spacing, clearances
      (0.2-0.3 mm for parts that fit together). Minimum wall 1.2 mm. One single connected part.
    - Put the main sizes as variables at the top so they are easy to edit.
    - Reply with one ```openscad block and nothing else.
""").strip()

SYSTEM_B123D = textwrap.dedent("""
    You write build123d (Python CAD) scripts for 3D-printable functional parts. Rules:
    - `from build123d import *` and plain Python only. Millimetres. Z is up, the part sits on Z=0.
    - Algebra mode only: Box, Cylinder, Pos, Rot, `+` union, `-` cut. Prefer Box(..., align=(Align.MIN, Align.MIN, Align.MIN)).
    - Shapes have methods: `result.edges().filter_by(Axis.Z)`; fillet with `result = fillet(edges, radius=3)`.
      Never call edges()/faces() as bare functions (that needs a Builder context).
    - Make every stated size exact. 0.2-0.3 mm clearance for fits. Minimum wall 1.2 mm. Assign the final single solid to `result`.
    - Do not print, export or read files. Reply with one ```python block and nothing else.
    Example:
    ```python
    from build123d import *
    result = Box(60, 40, 20, align=(Align.MIN, Align.MIN, Align.MIN)) - Pos(2, 2, 2) * Box(56, 36, 18, align=(Align.MIN, Align.MIN, Align.MIN))
    result = fillet(result.edges().filter_by(Axis.Z), radius=2)
    ```
""").strip()

RUNNER = textwrap.dedent("""
    import json, sys
    src = open(sys.argv[1]).read()
    ns = {}
    try:
        exec(compile(src, "part.py", "exec"), ns)
    except Exception as exc:
        print(json.dumps({"error": f"{type(exc).__name__}: {exc}"})); sys.exit(0)
    r = ns.get("result")
    if r is None:
        print(json.dumps({"error": "the script did not assign the final solid to `result`"})); sys.exit(0)
    from build123d import export_step, export_stl
    bb = r.bounding_box()
    solids = len(r.solids()) if hasattr(r, "solids") else 1
    valid = r.is_valid() if callable(getattr(r, "is_valid", None)) else bool(getattr(r, "is_valid", True))
    export_step(r, sys.argv[2]); export_stl(r, sys.argv[3])
    print(json.dumps({"size": sorted([round(bb.size.X, 2), round(bb.size.Y, 2), round(bb.size.Z, 2)]),
                      "min_z": round(bb.min.Z, 2), "solids": solids, "valid": bool(valid)}))
""")


@dataclass
class MakeResult:
    ok: bool
    rounds: int
    step: Path | None
    stl: Path | None
    script: Path | None
    report: dict


def requested_sizes(text: str) -> list[float]:
    """Overall sizes written as 150x100x60 / 150 x 100 x 60 mm; checked against the bounding box."""
    m = re.search(r"(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)(?:\s*[x×]\s*(\d+(?:\.\d+)?))?\s*mm", text, re.I)
    return sorted(float(v) for v in m.groups() if v) if m else []


def llm(messages, url=None, model=None, timeout=240):
    """OpenAI-compatible chat with a model fallback chain: free providers rate-limit (429) without warning."""
    url = url or os.environ.get("POLYFORGE_MAKE_URL", "http://127.0.0.1:3001/v1")
    chain = [model] if model else os.environ.get("POLYFORGE_MAKE_MODEL",
                                                 "mistral-large-3,devstral-2,qwen3.8-27b,gpt-oss-120b").split(",")
    key_file = Path(os.environ.get("POLYFORGE_MAKE_KEY_FILE", "~/.config/freellmapi-key")).expanduser()
    headers = {"Content-Type": "application/json"}
    if key_file.exists():
        headers["Authorization"] = "Bearer " + key_file.read_text().strip()
    last = None
    for _ in range(2):
        for m in chain:
            body = json.dumps({"model": m.strip(), "messages": messages, "temperature": 0.2}).encode()
            try:
                req = urllib.request.Request(f"{url}/chat/completions", body, headers)
                return json.load(urllib.request.urlopen(req, timeout=timeout))["choices"][0]["message"]["content"]
            except Exception as exc:   # 429 / 5xx / timeout: next model
                last = exc
        time.sleep(20)
    raise RuntimeError(f"no model answered ({last})")


def extract_code(reply: str) -> str:
    m = re.search(r"```(?:python|openscad|scad)?\s*\n(.*?)```", reply, re.S)
    return (m.group(1) if m else reply).strip()


def run_scad(script: Path, stl: Path) -> dict:
    exe = shutil.which("openscad") or "openscad"
    try:
        p = subprocess.run([exe, "--backend=manifold", "-o", str(stl), str(script)],
                           capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        return {"error": "OpenSCAD took longer than 300 s"}
    errs = [l for l in p.stderr.splitlines() if l.startswith(("ERROR", "Parser error"))]
    if p.returncode != 0 or not stl.exists() or errs:
        return {"error": "\n".join(errs) or p.stderr[-800:] or "OpenSCAD failed"}
    import trimesh
    m = trimesh.load(stl, force="mesh")
    if not len(m.faces):
        return {"error": "the model is empty"}
    bodies = m.split(only_watertight=False)
    voids = [b for b in bodies if b.is_watertight and b.volume < 0]
    return {"size": sorted(round(float(v), 2) for v in m.extents), "min_z": round(float(m.bounds[0, 2]), 2),
            "solids": len(bodies) - len(voids), "voids": [sorted(round(float(v), 2) for v in b.extents) for b in voids],
            "max_z": round(float(m.bounds[1, 2]), 3), "valid": bool(m.is_volume)}


def run_b123d(script: Path, step: Path, stl: Path, runner: Path) -> dict:
    try:
        p = subprocess.run([sys.executable, str(runner), str(script), str(step), str(stl)],
                           capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        return {"error": "the script took longer than 180 s"}
    last = (p.stdout.strip().splitlines() or [""])[-1]
    try:
        return json.loads(last) if last else {"error": p.stderr[-800:] or "no output"}
    except json.JSONDecodeError:
        return {"error": (p.stderr or p.stdout)[-800:]}


def check(run: dict, sizes: list[float], stl: Path) -> list[str]:
    if "error" in run:
        return [run["error"]]
    problems = []
    if not run.get("valid"):
        problems.append("the solid is not valid (open, self-intersecting or broken faces)")
    for v in run.get("voids", []):
        problems.append(f"there is a sealed hollow inside the part, size {v} mm: a cavity that should be open is closed by "
                        "a thin skin (often a shell a little taller than the cut, e.g. minkowski with h=0.01). "
                        "Make the cut go 1 mm past the top, and keep the outer height exact")
    if run.get("solids", 1) != 1:
        problems.append(f"the result is {run['solids']} separate solids; it must be one printable part")
    if abs(run.get("min_z", 0)) > 0.05:
        problems.append(f"the part must sit on Z=0, its lowest point is at Z={run['min_z']}")
    got = run.get("size", [])
    for want in sizes:                               # every stated overall size must match one bbox side
        if not any(abs(g - want) <= max(0.15, 0.003 * want) for g in got):
            problems.append(f"requested overall size {want} mm, bounding box is {got}")
    try:
        import trimesh
        if stl.exists() and not trimesh.load(stl, force="mesh").is_watertight:
            problems.append("the exported mesh is not watertight")
    except Exception:
        pass
    return problems


def make(text: str, out: Path, rounds: int = 4, on_progress=None, chat=llm, lang: str = "openscad") -> MakeResult:
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    sizes = requested_sizes(text)
    system = SYSTEM_SCAD if lang == "openscad" else SYSTEM_B123D
    fence = "openscad" if lang == "openscad" else "python"
    messages = [{"role": "system", "content": system}, {"role": "user", "content": text}]
    runner = out / "_run.py"; runner.write_text(RUNNER)
    script = out / ("part.scad" if lang == "openscad" else "part.py")
    stl, step = out / "part.stl", (None if lang == "openscad" else out / "part.step")
    history = []
    for i in range(1, rounds + 1):
        if on_progress:
            on_progress(i, rounds, f"round {i}: writing CAD")
        code = extract_code(chat(messages))
        script.write_text(code)
        stl.unlink(missing_ok=True)
        run = run_scad(script, stl) if lang == "openscad" else run_b123d(script, step, stl, runner)
        problems = check(run, sizes, stl)
        history.append({"round": i, "run": run, "problems": problems})
        if not problems:
            report = {"request": text, "rounds": i, "size_mm": run["size"], "lang": lang, "history": history}
            (out / "report.json").write_text(json.dumps(report, indent=1))
            return MakeResult(True, i, step, stl, script, report)
        messages += [{"role": "assistant", "content": f"```{fence}\n{code}\n```"},
                     {"role": "user", "content": "That does not work yet:\n- " + "\n- ".join(problems) +
                      "\nFix it and reply with the whole corrected script."}]
    report = {"request": text, "rounds": rounds, "lang": lang, "history": history}
    (out / "report.json").write_text(json.dumps(report, indent=1))
    return MakeResult(False, rounds, None, None, script, report)
