"""Detects, health-checks, and (if needed) starts a local Ollama server, and
lists the models actually installed on it -- so llm_backend (and, later, the
GUI's model picker) never has to guess a hardcoded model name that may not
exist on this machine.

Everything here talks to Ollama's plain HTTP API (`/api/version`, `/api/tags`,
`/api/generate`) with the standard library only, no ollama SDK dependency.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
import urllib.request
from dataclasses import dataclass, field

DEFAULT_BASE_URL = "http://localhost:11434"
STARTUP_TIMEOUT_S = 15.0
POLL_INTERVAL_S = 0.5
HEALTH_TIMEOUT_S = 2.0


class OllamaUnavailable(Exception):
    """Raised when Ollama can't be reached, isn't installed, or has no models."""


@dataclass
class ModelInfo:
    name: str
    parameter_size: str | None = None
    quantization: str | None = None
    family: str | None = None
    size_bytes: int | None = None


@dataclass
class ServerStatus:
    base_url: str
    running: bool
    version: str | None = None
    started_by_us: bool = False
    models: list[ModelInfo] = field(default_factory=list)


def _get(base_url: str, path: str, timeout: float) -> dict:
    request = urllib.request.Request(f"{base_url.rstrip('/')}{path}")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def is_running(base_url: str = DEFAULT_BASE_URL, timeout: float = HEALTH_TIMEOUT_S) -> bool:
    """A lightweight health check -- never raises, just reports reachability."""
    try:
        _get(base_url, "/api/tags", timeout)
        return True
    except Exception:  # noqa: BLE001 - any transport error means "not reachable"
        return False


def get_version(base_url: str = DEFAULT_BASE_URL, timeout: float = HEALTH_TIMEOUT_S) -> str | None:
    """The running server's reported version, or None if unreachable or the
    endpoint doesn't exist on this build (older Ollama versions predate it --
    absence of a version string isn't itself an error)."""
    try:
        return _get(base_url, "/api/version", timeout).get("version")
    except Exception:  # noqa: BLE001
        return None


def list_models(base_url: str = DEFAULT_BASE_URL, timeout: float = HEALTH_TIMEOUT_S) -> list[ModelInfo]:
    """Models actually pulled/available on the running server. Raises
    OllamaUnavailable if the server can't be reached -- callers that already
    know it's running (e.g. right after ensure_server) can let that surface;
    callers that don't should check is_running first."""
    try:
        body = _get(base_url, "/api/tags", timeout)
    except Exception as exc:  # noqa: BLE001
        raise OllamaUnavailable(f"Could not reach Ollama at {base_url} to list models: {exc}") from exc

    models = []
    for entry in body.get("models", []):
        details = entry.get("details", {}) or {}
        models.append(
            ModelInfo(
                name=entry.get("name") or entry.get("model", "unknown"),
                parameter_size=details.get("parameter_size"),
                quantization=details.get("quantization_level"),
                family=details.get("family"),
                size_bytes=entry.get("size"),
            )
        )
    return models


def find_ollama_binary() -> str | None:
    return shutil.which("ollama")


def ensure_server(
    base_url: str = DEFAULT_BASE_URL,
    auto_start: bool = True,
    startup_timeout: float = STARTUP_TIMEOUT_S,
    poll_interval: float = POLL_INTERVAL_S,
) -> ServerStatus:
    """Make sure a server is reachable at `base_url`, starting one if it
    isn't and `auto_start` is True. Raises OllamaUnavailable with a clear,
    actionable message (not installed / refused to start / no models) rather
    than letting a bare connection error surface -- this is the single choke
    point `llm_backend.match()` and the GUI's model picker both go through."""
    if is_running(base_url):
        return ServerStatus(base_url=base_url, running=True, version=get_version(base_url), models=list_models(base_url))

    if not auto_start:
        raise OllamaUnavailable(
            f"Ollama isn't running at {base_url} and auto_start is off. Start it yourself "
            "(`ollama serve`) or enable auto_start."
        )

    binary = find_ollama_binary()
    if binary is None:
        raise OllamaUnavailable(
            "Ollama isn't installed (no `ollama` binary on PATH). Install it from "
            "https://ollama.com/download, `ollama pull <model>`, then retry -- or use "
            "--engine templates instead, which needs no local model at all."
        )

    # Detached: outlives this process; stdout/stderr discarded rather than
    # piped, since nothing here reads them and an unread pipe can eventually
    # block the child on a full buffer.
    subprocess.Popen(
        [binary, "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    deadline = time.monotonic() + startup_timeout
    while time.monotonic() < deadline:
        if is_running(base_url):
            return ServerStatus(
                base_url=base_url, running=True, version=get_version(base_url),
                started_by_us=True, models=list_models(base_url),
            )
        time.sleep(poll_interval)

    raise OllamaUnavailable(
        f"Started `{binary} serve` but it never became reachable at {base_url} within "
        f"{startup_timeout:.0f}s. Check `ollama serve` manually for errors (a port conflict "
        "or GPU/driver issue are the usual causes)."
    )


def select_model(base_url: str = DEFAULT_BASE_URL, requested: str | None = None) -> str:
    """Resolve the model name llm_backend should actually use: the requested
    one if it's really installed (exact match, or matched ignoring a
    ":tag" suffix so "llama3.2" matches an installed "llama3.2:latest"),
    otherwise the first installed model -- never a hardcoded default that
    may not exist on this machine, which was the whole problem with the
    previous fixed `DEFAULT_MODEL = "llama3.2"`."""
    models = list_models(base_url)
    if not models:
        raise OllamaUnavailable(
            f"Ollama at {base_url} is running but has no models installed. "
            "`ollama pull llama3.2` (or any model you prefer), then retry."
        )

    if requested:
        for m in models:
            if m.name == requested or m.name.split(":")[0] == requested.split(":")[0]:
                return m.name
        available = ", ".join(m.name for m in models)
        raise OllamaUnavailable(
            f"Requested model {requested!r} isn't installed on {base_url}. "
            f"Available: {available}. `ollama pull {requested}` to add it, or drop "
            "--llm-model to auto-pick one of the available models."
        )

    return models[0].name
