"""Dependency-free STL geometry and topology inspection."""

from __future__ import annotations

import math
import struct
from collections import Counter
from pathlib import Path


def _binary_triangles(data: bytes):
    count = struct.unpack_from("<I", data, 80)[0]
    expected = 84 + count * 50
    if expected != len(data):
        raise ValueError("not a canonical binary STL")
    for i in range(count):
        values = struct.unpack_from("<12fH", data, 84 + i * 50)
        yield (values[3:6], values[6:9], values[9:12])


def _ascii_triangles(data: bytes):
    vertices = []
    for raw in data.decode("utf-8", errors="replace").splitlines():
        fields = raw.strip().split()
        if len(fields) == 4 and fields[0].lower() == "vertex":
            vertices.append(tuple(float(v) for v in fields[1:]))
    if not vertices or len(vertices) % 3:
        raise ValueError("ASCII STL has no complete triangles")
    for i in range(0, len(vertices), 3):
        yield tuple(vertices[i : i + 3])


def load_triangles(path: Path):
    data = path.read_bytes()
    if len(data) >= 84:
        try:
            return list(_binary_triangles(data)), "binary"
        except ValueError:
            pass
    return list(_ascii_triangles(data)), "ascii"


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def inspect(path: Path, tolerance: float = 1e-5):
    triangles, encoding = load_triangles(path)
    points = [v for tri in triangles for v in tri]
    mins = [min(v[i] for v in points) for i in range(3)]
    maxs = [max(v[i] for v in points) for i in range(3)]
    area = 0.0
    signed_volume = 0.0
    degenerate = 0
    edges = Counter()

    def key(v):
        return tuple(round(c / tolerance) for c in v)

    for a, b, c in triangles:
        cr = cross(sub(b, a), sub(c, a))
        tri_area = 0.5 * math.sqrt(dot(cr, cr))
        area += tri_area
        if tri_area <= tolerance * tolerance:
            degenerate += 1
        signed_volume += dot(a, cross(b, c)) / 6.0
        ka, kb, kc = key(a), key(b), key(c)
        edges.update((tuple(sorted((ka, kb))), tuple(sorted((kb, kc))), tuple(sorted((kc, ka)))))

    boundary = sum(1 for uses in edges.values() if uses == 1)
    nonmanifold = sum(1 for uses in edges.values() if uses > 2)
    return {
        "file": str(path.resolve()),
        "encoding": encoding,
        "bytes": path.stat().st_size,
        "triangles": len(triangles),
        "bounds_mm": {"min": mins, "max": maxs, "size": [maxs[i] - mins[i] for i in range(3)]},
        "surface_area_mm2": area,
        "signed_volume_mm3": signed_volume,
        "absolute_volume_mm3": abs(signed_volume),
        "degenerate_triangles": degenerate,
        "boundary_edges": boundary,
        "nonmanifold_edges": nonmanifold,
        "watertight_by_edge_count": boundary == 0 and nonmanifold == 0,
        "vertex_merge_tolerance_mm": tolerance,
    }


def markdown(result: dict) -> str:
    size = result["bounds_mm"]["size"]
    return "\n".join(
        [
            "# Mesh report",
            "",
            f"- File: `{result['file']}`",
            f"- Encoding: {result['encoding']}",
            f"- Overall size (X × Y × Z): {size[0]:.3f} × {size[1]:.3f} × {size[2]:.3f} mm",
            f"- Triangles: {result['triangles']:,}",
            f"- Surface area: {result['surface_area_mm2']:.3f} mm²",
            f"- Absolute signed volume: {result['absolute_volume_mm3']:.3f} mm³",
            f"- Degenerate triangles: {result['degenerate_triangles']}",
            f"- Boundary edges: {result['boundary_edges']}",
            f"- Non-manifold edges: {result['nonmanifold_edges']}",
            f"- Watertight by edge count: {'yes' if result['watertight_by_edge_count'] else 'no'}",
            "",
            "Topology counts use tolerance-rounded vertices. Hole diameters and semantic "
            "features must be verified from the parametric source or model manifest.",
            "",
        ]
    )
