"""Turn a template key + params into final OpenSCAD source."""

from __future__ import annotations

from . import templates


def render(template_key: str, params: dict) -> tuple[str, dict]:
    template = templates.get(template_key)
    merged = template.defaults()
    merged.update(params)
    return template.generate(merged), merged
