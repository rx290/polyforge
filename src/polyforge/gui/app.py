"""Pure request/response logic for the local web GUI -- no HTTP framework,
no sockets, so this is directly unit-testable and reusable regardless of
what actually serves it (server.py's stdlib http.server today, something
else later if that ever needs to change).

Every function here takes plain dict-like input (already JSON-decoded) and
returns a plain JSON-serializable dict -- server.py's only job is decoding
the request body, calling one of these, and encoding the result.
"""

from __future__ import annotations

from pathlib import Path

from .. import render, templates
from ..geometry import preview_export
from ..nlu import ollama_client, template_matcher


def templates_json() -> list[dict]:
    return [
        {
            "key": t.key,
            "title": t.title,
            "description": t.description,
            "keywords": list(t.keywords),
            "backends": list(t.backends()),
            "params": [
                {"name": p.name, "default": p.default, "unit": p.unit, "description": p.description}
                for p in t.params
            ],
        }
        for t in templates.all_templates()
    ]


def ollama_status_json(base_url: str | None = None, auto_start: bool = False) -> dict:
    base_url = base_url or ollama_client.DEFAULT_BASE_URL
    try:
        status = ollama_client.ensure_server(base_url, auto_start=auto_start)
    except ollama_client.OllamaUnavailable as exc:
        return {"reachable": False, "error": str(exc), "base_url": base_url}
    return {
        "reachable": True,
        "base_url": status.base_url,
        "version": status.version,
        "started_by_us": status.started_by_us,
        "models": [
            {"name": m.name, "parameter_size": m.parameter_size, "quantization": m.quantization}
            for m in status.models
        ],
    }


class DesignError(Exception):
    """Raised for any request-level problem (unknown engine, bad template,
    bad backend) -- server.py turns this into a 400, not a 500."""


def design_json(payload: dict, workdir: Path, next_id: int) -> dict:
    text = (payload.get("text") or "").strip()
    if not text:
        raise DesignError("text is required")
    engine_name = payload.get("engine", "templates")
    backend = payload.get("backend", "openscad")
    overrides = payload.get("set") or {}

    if engine_name == "templates":
        try:
            result = template_matcher.match(text)
        except template_matcher.NoTemplateMatchError as exc:
            raise DesignError(str(exc)) from exc
    elif engine_name == "llm":
        from ..nlu import llm_backend

        try:
            result = llm_backend.match(
                text,
                base_url=payload.get("llm_url") or None,
                model=payload.get("llm_model") or None,
                auto_start=bool(payload.get("auto_start", True)),
            )
        except llm_backend.LLMBackendUnavailable as exc:
            raise DesignError(str(exc)) from exc
    else:
        raise DesignError(f"unknown engine: {engine_name!r}")

    params = {**result.params, **{k: float(v) for k, v in overrides.items()}}
    try:
        source, merged_params = render.render(result.template_key, params, backend=backend)
    except ValueError as exc:
        raise DesignError(str(exc)) from exc

    ext = render.BACKEND_EXTENSIONS[backend]
    filename = f"{result.template_key}_{next_id}{ext}"
    (workdir / filename).write_text(source)

    return {
        "template_key": result.template_key,
        "confidence": result.confidence,
        "notes": result.notes,
        "params": merged_params,
        "source": source,
        "filename": filename,
    }


def preview_json(filename: str, workdir: Path, imgsize: str = "800,600", on_progress=None) -> dict:
    scad = workdir / filename
    if scad.suffix.lower() != ".scad":
        raise DesignError("preview is only available for the OpenSCAD backend")
    try:
        views = preview_export.preview(scad, imgsize=imgsize, on_progress=on_progress)
    except Exception as exc:  # noqa: BLE001 - surfaced as a clean 400/500 message, not a stack trace
        raise DesignError(str(exc)) from exc
    return {"views": [{"name": v.stem, "path": str(v)} for v in views]}


def export_json(filename: str, workdir: Path, on_progress=None) -> dict:
    scad = workdir / filename
    if scad.suffix.lower() != ".scad":
        raise DesignError("export (STL) is only available for the OpenSCAD backend from the GUI")
    try:
        result = preview_export.export(scad, on_progress=on_progress)
    except Exception as exc:  # noqa: BLE001
        raise DesignError(str(exc)) from exc
    return {
        "stl": str(result["stl"]),
        "mesh_report": str(result["mesh_report"]),
        "spec": str(result["spec"]),
        "views": [{"name": v.stem, "path": str(v)} for v in result["views"]],
    }
