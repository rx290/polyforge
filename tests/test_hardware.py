import shutil

import pytest

from polyforge import hardware


def test_detect_gpu_never_raises():
    gpu = hardware.detect_gpu()
    assert gpu.vendor in {"nvidia", "amd", "none"}


def test_recommend_model_for_no_gpu():
    rec = hardware.recommend_model(hardware.GpuInfo(vendor="none"))
    assert rec.model == "llama3.2:1b"
    assert "no GPU" in rec.reason


@pytest.mark.parametrize(
    "vram_mb,expected_model",
    [
        (2048, "llama3.2:1b"),
        (4096, "llama3.2:3b"),
        (6144, "llama3.1:8b"),
        (10240, "qwen2.5:14b"),
        (24576, "qwen2.5:32b"),
    ],
)
def test_recommend_model_tiers_scale_with_vram(vram_mb, expected_model):
    rec = hardware.recommend_model(hardware.GpuInfo(vendor="nvidia", name="Test GPU", vram_mb=vram_mb))
    assert rec.model == expected_model


def test_recommend_model_handles_unknown_vram_on_a_real_gpu():
    # A GPU was detected but VRAM couldn't be read (parsing failure, unusual
    # driver output) -- should fall back to the safe tiny tier, not crash.
    rec = hardware.recommend_model(hardware.GpuInfo(vendor="nvidia", name="Mystery GPU", vram_mb=None))
    assert rec.model == "llama3.2:1b"


@pytest.mark.skipif(shutil.which("nvidia-smi") is None, reason="no NVIDIA GPU/driver on this machine")
def test_detect_gpu_against_the_real_nvidia_smi():
    gpu = hardware.detect_gpu()
    assert gpu.vendor == "nvidia"
    assert gpu.detected_via == "nvidia-smi"
    assert gpu.vram_mb is not None and gpu.vram_mb > 0
