"""Detect the local GPU (NVIDIA/CUDA via `nvidia-smi`, AMD/ROCm via
`rocm-smi`), and recommend an Ollama model size to match -- both installer
scripts (scripts/install.sh, scripts/install.ps1) call into this through
`polyforge hardware-scan` rather than duplicating detection logic in two
shell languages. `nvidia-smi`/`rocm-smi` are themselves cross-platform (both
ship Windows builds), so one implementation covers both installers.

The model recommendation is a rule-of-thumb sized on VRAM only (roughly
1GB of VRAM per 1B parameters at Q4 quantization, plus headroom) -- it is
not a guarantee, doesn't account for actual context length used, and a
model that "fits" can still be slow. Said explicitly wherever this surfaces,
not oversold.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass


@dataclass
class GpuInfo:
    vendor: str  # "nvidia", "amd", or "none"
    name: str | None = None
    vram_mb: int | None = None
    detected_via: str | None = None  # which tool found it, for transparency


def _run(cmd: list[str], timeout: float = 10.0) -> str | None:
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout


def _detect_nvidia() -> GpuInfo | None:
    if shutil.which("nvidia-smi") is None:
        return None
    output = _run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"])
    if not output:
        return None
    line = output.strip().splitlines()[0] if output.strip() else ""
    parts = [p.strip() for p in line.split(",")]
    if len(parts) < 2:
        return GpuInfo(vendor="nvidia", detected_via="nvidia-smi")
    name = parts[0]
    match = re.search(r"(\d+)", parts[1])
    vram_mb = int(match.group(1)) if match else None
    return GpuInfo(vendor="nvidia", name=name, vram_mb=vram_mb, detected_via="nvidia-smi")


def _detect_amd() -> GpuInfo | None:
    if shutil.which("rocm-smi") is None:
        return None
    # --showproductname and --showmeminfo vram are separate queries in
    # rocm-smi's own CLI; --json is more reliably parseable across versions
    # than scraping its human-readable table output.
    output = _run(["rocm-smi", "--showproductname", "--showmeminfo", "vram", "--json"])
    if not output:
        return GpuInfo(vendor="amd", detected_via="rocm-smi")
    name = None
    vram_mb = None
    name_match = re.search(r'"Card series"\s*:\s*"([^"]+)"', output)
    if name_match:
        name = name_match.group(1)
    vram_match = re.search(r'"VRAM Total Memory \(B\)"\s*:\s*"(\d+)"', output)
    if vram_match:
        vram_mb = int(vram_match.group(1)) // (1024 * 1024)
    return GpuInfo(vendor="amd", name=name, vram_mb=vram_mb, detected_via="rocm-smi")


def detect_gpu() -> GpuInfo:
    """NVIDIA is checked first only because `nvidia-smi` is far more common
    in practice; a machine can't sensibly have both drivers reporting a
    primary compute GPU at once, so this isn't a real preference judgment."""
    return _detect_nvidia() or _detect_amd() or GpuInfo(vendor="none")


@dataclass
class ModelRecommendation:
    model: str
    tier: str
    reason: str


# (max_vram_mb_exclusive_upper_bound, model_tag, tier_label) -- checked in
# order, first match wins. The top entry (no real GPU, or nothing detected)
# covers CPU-only inference, which is legitimately usable for the small end
# of this table, just slow.
_TIERS: list[tuple[int, str, str]] = [
    (4096, "llama3.2:1b", "tiny (CPU-friendly, <4GB VRAM or none)"),
    (6144, "llama3.2:3b", "small (4-6GB VRAM)"),
    (10240, "llama3.1:8b", "medium (6-10GB VRAM)"),
    (16384, "qwen2.5:14b", "large (10-16GB VRAM)"),
]
_TOP_TIER = ("qwen2.5:32b", "extra-large (16GB+ VRAM)")


def recommend_model(gpu: GpuInfo) -> ModelRecommendation:
    vram = gpu.vram_mb
    if gpu.vendor == "none" or vram is None:
        model, tier = _TIERS[0][1], _TIERS[0][2]
        reason = (
            "no GPU detected (or VRAM unreadable) -- recommending a small model that's "
            "still reasonably usable on CPU alone"
        )
        return ModelRecommendation(model=model, tier=tier, reason=reason)

    for ceiling, model, tier in _TIERS:
        if vram < ceiling:
            reason = f"{gpu.name or gpu.vendor} has ~{vram}MB VRAM, fits the {tier} tier"
            return ModelRecommendation(model=model, tier=tier, reason=reason)

    model, tier = _TOP_TIER
    reason = f"{gpu.name or gpu.vendor} has ~{vram}MB VRAM, comfortably fits the {tier} tier"
    return ModelRecommendation(model=model, tier=tier, reason=reason)
