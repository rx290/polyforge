"""Dependency-free PLY mesh reading and STL writing.

OpenMVS's ReconstructMesh writes triangle meshes as binary PLY. Rather than
pull in trimesh as a new hard dependency just for this one conversion, this
reads the subset of PLY actually needed (vertex x/y/z, face vertex_indices)
with a real header parser, matching the project's existing dependency-free
style (see inspect.py's hand-rolled binary STL parser).
"""

from __future__ import annotations

import struct
from pathlib import Path

_SCALAR_SIZES = {
    "char": 1, "int8": 1, "uchar": 1, "uint8": 1,
    "short": 2, "int16": 2, "ushort": 2, "uint16": 2,
    "int": 4, "int32": 4, "uint": 4, "uint32": 4, "float": 4, "float32": 4,
    "double": 8, "float64": 8, "int64": 8, "uint64": 8,
}
_SCALAR_STRUCT = {
    "char": "b", "int8": "b", "uchar": "B", "uint8": "B",
    "short": "h", "int16": "h", "ushort": "H", "uint16": "H",
    "int": "i", "int32": "i", "uint": "I", "uint32": "I",
    "float": "f", "float32": "f", "double": "d", "float64": "d",
    "int64": "q", "uint64": "Q",
}


def _parse_header(f):
    line = f.readline().strip()
    if line != b"ply":
        raise ValueError("not a PLY file (missing 'ply' magic)")
    fmt = None
    elements = []  # list of (name, count, properties) where properties is list of dicts
    current = None
    while True:
        line = f.readline()
        if not line:
            raise ValueError("PLY header ended without 'end_header'")
        line = line.strip()
        if line == b"end_header":
            break
        parts = line.split()
        if not parts:
            continue
        keyword = parts[0]
        if keyword == b"format":
            fmt = parts[1].decode("ascii")
        elif keyword == b"element":
            current = {"name": parts[1].decode("ascii"), "count": int(parts[2]), "properties": []}
            elements.append(current)
        elif keyword == b"property":
            if parts[1] == b"list":
                current["properties"].append({
                    "list": True,
                    "count_type": parts[2].decode("ascii"),
                    "value_type": parts[3].decode("ascii"),
                    "name": parts[4].decode("ascii"),
                })
            else:
                current["properties"].append({
                    "list": False,
                    "type": parts[1].decode("ascii"),
                    "name": parts[2].decode("ascii"),
                })
    if fmt is None:
        raise ValueError("PLY header missing 'format' line")
    return fmt, elements


def _read_binary_element(f, byte_order, element):
    little = byte_order == "binary_little_endian"
    prefix = "<" if little else ">"
    rows = []
    for _ in range(element["count"]):
        row = {}
        for prop in element["properties"]:
            if prop["list"]:
                (count,) = struct.unpack(prefix + _SCALAR_STRUCT[prop["count_type"]], f.read(_SCALAR_SIZES[prop["count_type"]]))
                value_fmt = _SCALAR_STRUCT[prop["value_type"]]
                value_size = _SCALAR_SIZES[prop["value_type"]]
                values = struct.unpack(prefix + value_fmt * count, f.read(value_size * count))
                row[prop["name"]] = values
            else:
                (value,) = struct.unpack(prefix + _SCALAR_STRUCT[prop["type"]], f.read(_SCALAR_SIZES[prop["type"]]))
                row[prop["name"]] = value
        rows.append(row)
    return rows


def _read_ascii_element(f, element):
    rows = []
    for _ in range(element["count"]):
        line = f.readline().split()
        row = {}
        pos = 0
        for prop in element["properties"]:
            if prop["list"]:
                count = int(line[pos])
                pos += 1
                caster = float if prop["value_type"] in ("float", "float32", "double", "float64") else int
                row[prop["name"]] = tuple(caster(v) for v in line[pos:pos + count])
                pos += count
            else:
                caster = float if prop["type"] in ("float", "float32", "double", "float64") else int
                row[prop["name"]] = caster(line[pos])
                pos += 1
        rows.append(row)
    return rows


def read_mesh(path: Path):
    """Read a PLY file's vertex positions and triangle faces.

    Returns (vertices, faces): vertices is a list of (x, y, z) tuples, faces
    is a list of (i, j, k) vertex-index tuples. Non-triangular face records
    are fan-triangulated (the same assumption OpenMVS's own writer satisfies
    for manifold meshes).
    """
    path = Path(path)
    with path.open("rb") as f:
        fmt, elements = _parse_header(f)
        vertices = []
        faces = []
        for element in elements:
            if fmt == "ascii":
                rows = _read_ascii_element(f, element)
            elif fmt in ("binary_little_endian", "binary_big_endian"):
                rows = _read_binary_element(f, fmt, element)
            else:
                raise ValueError(f"unsupported PLY format: {fmt}")
            if element["name"] == "vertex":
                vertices = [(row["x"], row["y"], row["z"]) for row in rows]
            elif element["name"] == "face":
                index_key = next(p["name"] for p in element["properties"] if p["list"])
                for row in rows:
                    idx = row[index_key]
                    for i in range(1, len(idx) - 1):
                        faces.append((idx[0], idx[i], idx[i + 1]))
    return vertices, faces


def write_stl(path: Path, vertices, faces) -> None:
    """Write a binary STL from vertex positions and triangle vertex-index faces."""
    path = Path(path)
    with path.open("wb") as f:
        f.write(b"\x00" * 80)
        f.write(struct.pack("<I", len(faces)))
        for a, b, c in faces:
            va, vb, vc = vertices[a], vertices[b], vertices[c]
            ux, uy, uz = vb[0] - va[0], vb[1] - va[1], vb[2] - va[2]
            vx, vy, vz = vc[0] - va[0], vc[1] - va[1], vc[2] - va[2]
            nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
            length = (nx * nx + ny * ny + nz * nz) ** 0.5
            if length > 0:
                nx, ny, nz = nx / length, ny / length, nz / length
            f.write(struct.pack("<12fH", nx, ny, nz, *va, *vb, *vc, 0))


def convert(ply_path: Path, stl_path: Path) -> None:
    vertices, faces = read_mesh(ply_path)
    if not faces:
        raise ValueError(f"PLY has no faces to convert: {ply_path}")
    write_stl(stl_path, vertices, faces)
