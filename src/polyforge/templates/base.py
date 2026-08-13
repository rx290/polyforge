"""Registry of parametric part templates.

Every template maps a bounded, known part shape (box, bracket, comb, ...) to a
function that renders valid parametric OpenSCAD from a params dict. This is the
shared vocabulary both NLU engines (template_matcher and llm_backend) fill in —
neither engine invents geometry outside this registry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class Param:
    name: str
    default: float
    unit: str = "mm"
    description: str = ""
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class Template:
    key: str
    title: str
    keywords: tuple[str, ...]
    params: list[Param]
    generate: Callable[[dict], str]
    description: str = ""

    def defaults(self) -> dict:
        return {p.name: p.default for p in self.params}


_REGISTRY: dict[str, Template] = {}


def register(template: Template) -> Template:
    if template.key in _REGISTRY:
        raise ValueError(f"template key already registered: {template.key}")
    _REGISTRY[template.key] = template
    return template


def get(key: str) -> Template:
    try:
        return _REGISTRY[key]
    except KeyError as exc:
        raise KeyError(f"unknown template: {key!r}. Known: {sorted(_REGISTRY)}") from exc


def all_templates() -> list[Template]:
    return list(_REGISTRY.values())
