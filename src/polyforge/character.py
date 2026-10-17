"""Text -> printable character/figure STL through a local image-to-3D pipeline.

PolyForge's templates only cover parametric parts. Characters, animals and whole scenes
("three Spider-Men pointing at each other") go through an external GPU pipeline instead:
a local LLM writes the image prompt, FLUX or SDXL-Turbo draws candidates, a local vision
model picks the most printable one, TripoSG lifts it to a mesh, and the mesh is repaired
and scaled to a target height. That pipeline lives outside this repo (it needs a ROCm/CUDA
torch environment and several GB of weights), so this module only runs it and reads back
what it wrote.

Configure with environment variables (defaults match the Madlab workstation):
  POLYFORGE_CHARACTER_PIPELINE  the pipeline script      (~/local-ai/tests/character.py)
  POLYFORGE_CHARACTER_PYTHON    python that can run it   (~/local-ai/venv-rocm/bin/python)
  POLYFORGE_CHARACTER_CWD       working directory        (~/local-ai/TripoSG)
"""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

QUALITY = {  # TripoSG steps, latent tokens, octree depth
    "fast": (30, 1024, 8),
    "full": (50, 2048, 9),
}


class CharacterError(RuntimeError):
    pass


@dataclass
class CharacterResult:
    stl: Path
    image: Path
    summary: str          # the pipeline's CHARACTER_OK line (time, faces, watertight, size, VRAM)
    anatomy_scores: str   # vision-model scores of the candidates, "" for a single candidate


def slug(text: str) -> str:
    """Same file stem the pipeline uses."""
    return "".join(ch if ch.isalnum() else "_" for ch in text)[:40].strip("_")


def _setting(name: str, default: str) -> Path:
    return Path(os.environ.get(name, default)).expanduser()


def pipeline_paths() -> tuple[Path, Path, Path]:
    return (_setting("POLYFORGE_CHARACTER_PIPELINE", "~/local-ai/tests/character.py"),
            _setting("POLYFORGE_CHARACTER_PYTHON", "~/local-ai/venv-rocm/bin/python"),
            _setting("POLYFORGE_CHARACTER_CWD", "~/local-ai/TripoSG"))


def available() -> tuple[bool, str]:
    script, python, cwd = pipeline_paths()
    for label, path in (("pipeline script", script), ("python", python), ("working directory", cwd)):
        if not path.exists():
            return False, f"character pipeline not set up: {label} {path} is missing"
    return True, "ok"


def generate(text: str, out_dir: Path, height_mm: float = 150.0, candidates: int = 4,
             image_model: str = "flux", quality: str = "full", style: str = "collectible", on_progress=None,
             timeout: float = 5400.0) -> CharacterResult:
    """Run the pipeline for one description. Blocks; `on_progress(done, total, label)` gets stage updates."""
    text = (text or "").strip()
    if not text:
        raise CharacterError("describe the character or scene to make")
    if quality not in QUALITY:
        raise CharacterError(f"quality must be one of {sorted(QUALITY)}")
    if image_model not in ("flux", "sdxl"):
        raise CharacterError("image_model must be flux or sdxl")
    ok, why = available()
    if not ok:
        raise CharacterError(why)
    script, python, cwd = pipeline_paths()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, CHAR_STYLE=style, CHAR_IMAGE_MODEL=image_model, CHAR_CANDIDATES=str(max(1, int(candidates))),
               HSA_OVERRIDE_GFX_VERSION=os.environ.get("HSA_OVERRIDE_GFX_VERSION", "10.3.0"),
               PYTORCH_HIP_ALLOC_CONF="expandable_segments:True")
    env["PYTHONPATH"] = os.pathsep.join(p for p in (str(Path.home() / "local-ai" / "stubs"), ".", env.get("PYTHONPATH", "")) if p)
    cmd = [str(python), str(script), text, str(out_dir), str(height_mm), *map(str, QUALITY[quality])]
    stages = [("prompt:", "image prompt written"), ("anatomy scores", "best candidate picked"),
              ("printable check", "mesh repaired"), ("CHARACTER_OK", "done")]
    lines: list[str] = []
    if on_progress:
        on_progress(0, len(stages), "writing the image prompt")
    env.setdefault("HSA_ENABLE_COREDUMP", "0")   # a GPU fault must not write a 10 GB dump
    for attempt in (1, 2):                         # ROCm on consumer cards hits random GPU page faults: retry once
        lines.clear()
        proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, stdin=subprocess.DEVNULL)
        try:
            for line in proc.stdout:
                lines.append(line.rstrip())
                for i, (marker, label) in enumerate(stages):
                    if marker in line and on_progress:
                        on_progress(i + 1, len(stages), label)
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            raise CharacterError(f"pipeline timed out after {timeout:.0f} s")
        gpu_fault = any("Memory access fault" in l or "page fault" in l for l in lines) or proc.returncode in (-6, -11, 134, 139)
        if not (gpu_fault and attempt == 1):
            break
        env["CHAR_SEED_OFFSET"] = "1000"             # Superman faulted twice on the same seeds: new seeds for the retry
        if on_progress:
            on_progress(0, len(stages), "GPU fault, retrying once with new seeds")
    ok_line = next((l for l in lines if l.startswith("CHARACTER_OK")), "")
    if proc.returncode != 0 or not ok_line:
        err = next((l for l in reversed(lines) if re.search(r"(Error|error|fault)[: ]", l) and "Token indices" not in l), lines[-1] if lines else "no output")
        raise CharacterError(f"pipeline failed: {err[:300]}")
    stem = slug(text)
    stl, image = out_dir / f"{stem}.stl", out_dir / f"{stem}_image.png"
    if not stl.exists():
        raise CharacterError(f"pipeline reported success but {stl} is missing")
    scores = next((l.split(":", 1)[1].strip() for l in lines if l.startswith("anatomy scores")), "")
    return CharacterResult(stl, image, ok_line[len("CHARACTER_OK"):].strip(), scores)
