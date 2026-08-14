"""MODEL_SPEC.md generation, shared by every export backend."""

from __future__ import annotations

import json
from pathlib import Path


def locate_manifest(source: Path, base: Path):
    candidates = [source.with_suffix(".json"), base / "model-manifest.json", base / "MODEL_MANIFEST.json"]
    return next((p for p in candidates if p.exists()), None)


def write_spec(base: Path, source: Path, artifact: Path, manifest_path, mesh_data: dict) -> Path:
    manifest = json.loads(manifest_path.read_text()) if manifest_path else {}
    size = mesh_data["bounds_mm"]["size"]
    lines = [
        f"# {manifest.get('name', source.stem)}: model specification",
        "",
        f"- Revision: {manifest.get('revision', 'unspecified')}",
        f"- Purpose: {manifest.get('purpose', 'unspecified')}",
        f"- Units: {manifest.get('units', 'mm')}",
        f"- Editable source: `{source.name}`",
        f"- Exported mesh: `{artifact.name}`",
        f"- Measured overall size (X × Y × Z): {size[0]:.3f} × {size[1]:.3f} × {size[2]:.3f} mm",
        f"- Printer profile: {manifest.get('printer_profile', 'unspecified')}",
        f"- Nozzle: {manifest.get('nozzle_mm', 'unspecified')} mm",
        f"- Material: {manifest.get('material', 'unspecified')}",
        f"- Orientation: {manifest.get('orientation', 'unspecified')}",
        "",
        "## Parameters",
        "",
    ]
    for item in manifest.get("parameters", []):
        lines.append(f"- `{item.get('name')}` = {item.get('value')} ({item.get('kind', 'nominal')}): {item.get('description', '')}")
    lines.extend(["", "## Functional features", ""])
    for feature in manifest.get("features", []):
        details = ", ".join(f"{k}={v}" for k, v in feature.items() if k not in {"type", "description"})
        lines.append(f"- {feature.get('type', 'feature')}: {feature.get('description', '')}" + (f" ({details})" if details else ""))
    lines.extend(["", "## Assumptions", ""])
    lines.extend(f"- {v}" for v in manifest.get("assumptions", []))
    lines.extend(["", "## Warnings", ""])
    lines.extend(f"- {v}" for v in manifest.get("warnings", []))
    lines.extend(
        [
            "",
            "## Validation",
            "",
            f"- Watertight by edge count: {'yes' if mesh_data['watertight_by_edge_count'] else 'no'}",
            f"- Boundary edges: {mesh_data['boundary_edges']}",
            f"- Non-manifold edges: {mesh_data['nonmanifold_edges']}",
            "- Visual inspection of the exported geometry is still required.",
            "",
        ]
    )
    spec_path = base / "MODEL_SPEC.md"
    spec_path.write_text("\n".join(lines))
    return spec_path
