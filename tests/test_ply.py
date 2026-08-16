import struct
from pathlib import Path

import pytest

from polyforge.geometry import inspect as mesh_inspect
from polyforge.geometry import ply


def _write_tetrahedron_ply(path: Path, fmt: str = "binary_little_endian"):
    vertices = [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (0.0, 10.0, 0.0), (0.0, 0.0, 10.0)]
    faces = [(0, 1, 2), (0, 3, 1), (0, 2, 3), (1, 3, 2)]
    header = (
        f"ply\nformat {fmt} 1.0\nelement vertex {len(vertices)}\n"
        "property float x\nproperty float y\nproperty float z\n"
        f"element face {len(faces)}\nproperty list uchar int vertex_indices\nend_header\n"
    ).encode("ascii")
    if fmt == "ascii":
        lines = []
        for v in vertices:
            lines.append(f"{v[0]} {v[1]} {v[2]}")
        for f in faces:
            lines.append(f"3 {f[0]} {f[1]} {f[2]}")
        path.write_bytes(header + ("\n".join(lines) + "\n").encode("ascii"))
    else:
        body = b"".join(struct.pack("<3f", *v) for v in vertices)
        body += b"".join(struct.pack("<Biii", 3, *f) for f in faces)
        path.write_bytes(header + body)
    return vertices, faces


def test_read_mesh_binary(tmp_path):
    path = tmp_path / "tet.ply"
    vertices, faces = _write_tetrahedron_ply(path)
    read_vertices, read_faces = ply.read_mesh(path)
    assert read_vertices == vertices
    assert read_faces == faces


def test_read_mesh_ascii(tmp_path):
    path = tmp_path / "tet_ascii.ply"
    vertices, faces = _write_tetrahedron_ply(path, fmt="ascii")
    read_vertices, read_faces = ply.read_mesh(path)
    assert read_vertices == vertices
    assert read_faces == faces


def test_convert_produces_watertight_stl(tmp_path):
    ply_path = tmp_path / "tet.ply"
    _write_tetrahedron_ply(ply_path)
    stl_path = tmp_path / "tet.stl"
    ply.convert(ply_path, stl_path)

    result = mesh_inspect.inspect(stl_path)
    assert result["triangles"] == 4
    assert result["watertight_by_edge_count"]
    assert result["boundary_edges"] == 0
    assert result["nonmanifold_edges"] == 0
    assert [round(v, 2) for v in result["bounds_mm"]["size"]] == [10.0, 10.0, 10.0]
    assert round(result["absolute_volume_mm3"], 2) == round(1000 / 6, 2)


def test_convert_raises_on_empty_mesh(tmp_path):
    ply_path = tmp_path / "empty.ply"
    header = "ply\nformat binary_little_endian 1.0\nelement vertex 0\nproperty float x\nproperty float y\nproperty float z\nelement face 0\nproperty list uchar int vertex_indices\nend_header\n"
    ply_path.write_bytes(header.encode("ascii"))
    with pytest.raises(ValueError, match="no faces"):
        ply.convert(ply_path, tmp_path / "empty.stl")


def test_fan_triangulates_ngon_faces(tmp_path):
    # a single square face (4 indices) should fan-triangulate into 2 triangles
    vertices = [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 10.0, 0.0), (0.0, 10.0, 0.0)]
    path = tmp_path / "quad.ply"
    header = (
        "ply\nformat binary_little_endian 1.0\nelement vertex 4\n"
        "property float x\nproperty float y\nproperty float z\n"
        "element face 1\nproperty list uchar int vertex_indices\nend_header\n"
    ).encode("ascii")
    body = b"".join(struct.pack("<3f", *v) for v in vertices)
    body += struct.pack("<Biiii", 4, 0, 1, 2, 3)
    path.write_bytes(header + body)

    read_vertices, read_faces = ply.read_mesh(path)
    assert read_vertices == vertices
    assert read_faces == [(0, 1, 2), (0, 2, 3)]
