"""Turn a template key + params into final CAD source, for whichever backend."""

from __future__ import annotations

from . import templates

# Default output extension per backend, used by the CLI when --out isn't given.
BACKEND_EXTENSIONS = {"openscad": ".scad", "freecad": ".FCMacro", "blender": ".blender.py"}


def render(template_key: str, params: dict, backend: str = "openscad") -> tuple[str, dict]:
    template = templates.get(template_key)
    merged = template.defaults()
    merged.update(params)

    if backend == "openscad":
        return template.generate(merged), merged
    if backend == "freecad":
        if template.generate_freecad is None:
            raise ValueError(f"template {template_key!r} has no freecad backend yet")
        return template.generate_freecad(merged), merged
    if backend == "blender":
        if template.generate_blender is None:
            raise ValueError(f"template {template_key!r} has no blender backend yet")
        return template.generate_blender(merged), merged
    raise ValueError(f"unknown backend: {backend!r}. Known: {sorted(BACKEND_EXTENSIONS)}")
