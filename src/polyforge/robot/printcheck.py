"""Print checks and preview renders for generated robot parts (no GPU, no OpenGL needed).

check_mesh(): watertight, one body, positive volume, sits on the bed, and the 45 degree rule: every face that
points down more than 45 degrees from vertical must be on the bed, a short bridge between two walls, or a small
ledge next to a wall. Anything else is reported as unsupported area.

render_views() / contact_sheet(): flat-shaded orthographic views drawn with a numpy z-sort and PIL, so this runs
headless on any machine.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np

COS45 = math.cos(math.radians(45.0))


def _components(face_ids, adjacency):
    """Connected groups of the given faces (scipy only, no networkx)."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components

    idx = {f: i for i, f in enumerate(face_ids)}
    keep = np.isin(adjacency[:, 0], face_ids) & np.isin(adjacency[:, 1], face_ids)
    a = adjacency[keep]
    rows = np.array([idx[f] for f in a[:, 0]], dtype=int)
    cols = np.array([idx[f] for f in a[:, 1]], dtype=int)
    g = coo_matrix((np.ones(len(rows)), (rows, cols)), shape=(len(face_ids), len(face_ids)))
    n, labels = connected_components(g, directed=False)
    return [face_ids[labels == k] for k in range(n)]


def _ray_hits(pts, dirs, segs):
    """Distance from each point along each 2D direction to the nearest segment (inf if none)."""
    if not len(segs):
        return np.full((len(pts), len(dirs)), np.inf)
    a, b = segs[:, 0, :], segs[:, 1, :]
    e = b - a                                                   # (S, 2)
    out = np.full((len(pts), len(dirs)), np.inf)
    for j, d in enumerate(dirs):
        den = d[0] * e[:, 1] - d[1] * e[:, 0]                   # (S,)
        ok = np.abs(den) > 1e-9
        w = a[None, :, :] - pts[:, None, :]                     # (P, S, 2)
        t = (w[..., 0] * e[None, :, 1] - w[..., 1] * e[None, :, 0]) / np.where(ok, den, 1)[None, :]
        u = (w[..., 0] * d[1] - w[..., 1] * d[0]) / np.where(ok, den, 1)[None, :]
        hit = ok[None, :] & (t > -1e-6) & (u >= -1e-6) & (u <= 1 + 1e-6)
        out[:, j] = np.where(hit, t, np.inf).min(1)
    return out


def _seg_dist(pts, segs):
    if not len(segs):
        return np.full(len(pts), np.inf)
    a, b = segs[None, :, 0, :], segs[None, :, 1, :]
    ab = b - a
    t = np.clip(((pts[:, None, :] - a) * ab).sum(-1) / np.maximum((ab * ab).sum(-1), 1e-12), 0, 1)
    proj = a + t[..., None] * ab
    return np.linalg.norm(pts[:, None, :] - proj, axis=-1).min(1)


def check_mesh(mesh, bridge_max: float = 25.0, ledge_max: float = 3.0, bed_tol: float = 0.05,
               max_unsupported_mm2: float = 6.0, overhang_deg: float = 45.0) -> dict:
    """Return a dict of checks; `ok` is True when the part prints as is (in its exported orientation).

    A face steeper than `overhang_deg` that is not on the bed is fine when every point of it is either within
    `ledge_max` of an anchored edge (an edge whose neighbouring face runs downwards, i.e. a wall holds it up) or
    sits on a bridge: anchored edges on both sides along one direction, no more than `bridge_max` apart.
    """
    import trimesh

    m = mesh if isinstance(mesh, trimesh.Trimesh) else trimesh.load(mesh, force="mesh")
    res = {"watertight": bool(m.is_watertight), "bodies": int(m.body_count), "volume_mm3": round(float(m.volume), 1),
           "extents": [round(float(e), 2) for e in m.extents]}
    zmin = float(m.bounds[0][2])
    res["on_bed"] = abs(zmin) < 0.01
    normals, centers = m.face_normals, m.triangles_center
    limit = -math.sin(math.radians(90.0 - overhang_deg))
    down = normals[:, 2] < limit - 1e-6
    on_bed = centers[:, 2] < zmin + bed_tol
    cand = np.where(down & ~on_bed)[0]
    bad_area, regions = 0.0, []
    if len(cand):
        adj, adj_edges = m.face_adjacency, m.face_adjacency_edges
        verts = m.vertices
        angles = np.linspace(0, np.pi, 8, endpoint=False)
        dirs = np.stack([np.cos(angles), np.sin(angles)], 1)
        dirs = np.concatenate([dirs, -dirs])
        for comp in _components(cand, adj):
            in_comp = np.zeros(len(m.faces), bool); in_comp[comp] = True
            border = in_comp[adj[:, 0]] ^ in_comp[adj[:, 1]]
            anchors = []
            for (f0, f1), (v0, v1) in zip(adj[border], adj_edges[border]):
                other = f1 if in_comp[f0] else f0
                mid_z = (verts[v0][2] + verts[v1][2]) / 2
                # the neighbour runs down (a wall holds this edge) or the edge sits on the bed
                if centers[other][2] < mid_z - 1e-4 or mid_z < zmin + bed_tol:
                    anchors.append([verts[v0][:2], verts[v1][:2]])
            anchors = np.array(anchors, dtype=float).reshape(-1, 2, 2)
            sub = m.submesh([comp], append=True, repair=False)
            area = float(sub.area)
            n = int(min(4000, max(30, area * 2)))
            pts = np.asarray(trimesh.sample.sample_surface_even(sub, n, radius=None)[0])[:, :2] if area > 0.5 \
                else sub.triangles_center[:, :2]
            if not len(pts):
                pts = sub.triangles_center[:, :2]
            near = _seg_dist(pts, anchors) <= ledge_max
            hits = _ray_hits(pts, dirs, anchors)
            k = len(angles)
            bridged = ((hits[:, :k] + hits[:, k:]) <= bridge_max).any(1)
            good = near | bridged
            frac_bad = 1.0 - float(good.mean())
            if frac_bad > 0:
                a_bad = frac_bad * area
                bad_area += a_bad
                regions.append({"area": round(a_bad, 1), "z": round(float(sub.bounds[0][2]), 1),
                                "center": [round(float(v), 1) for v in sub.centroid]})
    res["unsupported_mm2"] = round(bad_area, 1)
    res["unsupported_regions"] = sorted(regions, key=lambda r: -r["area"])[:5]
    res["supports_free"] = bad_area <= max_unsupported_mm2
    res["ok"] = res["watertight"] and res["bodies"] == 1 and res["volume_mm3"] > 0 and res["on_bed"] and res["supports_free"]
    res["problems"] = [msg for bad, msg in (
        (not res["watertight"], "mesh is not watertight"),
        (res["bodies"] != 1, f"{res['bodies']} separate shells (loose piece or sealed internal void)"),
        (not res["on_bed"], "lowest point is not on z = 0"),
        (not res["supports_free"], f"{res['unsupported_mm2']} mm2 of overhang needs support")) if bad]
    return res


def to_print_pose(mesh):
    """Move a mesh so its lowest point sits on z = 0 and it is centred on x/y (does not rotate)."""
    b = mesh.bounds
    mesh.apply_translation([-(b[0][0] + b[1][0]) / 2, -(b[0][1] + b[1][1]) / 2, -b[0][2]])
    return mesh


# ---------------------------------------------------------------- rendering

VIEWS = {   # name: (azimuth deg, elevation deg)
    "front": (-90.0, 0.0), "right": (0.0, 0.0), "top": (-90.0, 90.0), "iso": (-55.0, 30.0),
}


def _view_matrix(az, el):
    a, e = math.radians(az), math.radians(el)
    d = np.array([math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)])   # direction to the camera
    up = np.array([0.0, 0.0, 1.0]) if abs(el) < 89 else np.array([0.0, 1.0, 0.0])
    r = np.cross(up, d); r /= np.linalg.norm(r)
    u = np.cross(d, r)
    return np.stack([r, u, d])


def render_view(mesh, az, el, size=360, color=(90, 150, 220), bg=(250, 250, 248)):
    from PIL import Image, ImageDraw

    R = _view_matrix(az, el)
    v = mesh.vertices @ R.T
    tri = v[mesh.faces]
    n = mesh.face_normals @ R.T
    vis = n[:, 2] > 0
    tri, n = tri[vis], n[vis]
    img = Image.new("RGB", (size, size), bg)
    if not len(tri):
        return img
    lo, hi = v[:, :2].min(0), v[:, :2].max(0)
    scale = (size * 0.86) / max(float((hi - lo).max()), 1e-6)
    off = np.array([size / 2, size / 2]) - (lo + hi) / 2 * scale
    order = np.argsort(tri[:, :, 2].mean(1))
    light = np.array([0.35, 0.45, 0.82]); light /= np.linalg.norm(light)
    shade = 0.35 + 0.65 * np.clip(n @ light, 0, 1)
    draw = ImageDraw.Draw(img)
    pts = tri[:, :, :2] * scale + off
    pts[:, :, 1] = size - pts[:, :, 1]
    base = np.array(color, dtype=float)
    for i in order:
        c = tuple(int(x) for x in np.clip(base * shade[i], 0, 255))
        draw.polygon([tuple(p) for p in pts[i]], fill=c, outline=c)
    return img


def render_views(mesh, size=300, color=(90, 150, 220)):
    """2 x 2 sheet: front, right, top, iso."""
    from PIL import Image

    sheet = Image.new("RGB", (size * 2, size * 2), (250, 250, 248))
    for i, (name, (az, el)) in enumerate(VIEWS.items()):
        sheet.paste(render_view(mesh, az, el, size, color), ((i % 2) * size, (i // 2) * size))
    return sheet


def contact_sheet(items, out_png, cell=260, cols=4, title=None):
    """items: list of (label, mesh, ok_flag or None). Draws an iso view per part with its label and size."""
    from PIL import Image, ImageDraw

    rows = max(1, math.ceil(len(items) / cols))
    top = 34 if title else 0
    sheet = Image.new("RGB", (cell * cols, cell * rows + top), (255, 255, 255))
    draw = ImageDraw.Draw(sheet)
    if title:
        draw.text((10, 10), title, fill=(20, 20, 20))
    for i, (label, mesh, ok) in enumerate(items):
        color = (90, 150, 220) if ok in (None, True) else (220, 110, 90)
        img = render_view(mesh, *VIEWS["iso"], size=cell - 30, color=color)
        x, y = (i % cols) * cell, (i // cols) * cell + top
        sheet.paste(img, (x + 15, y + 2))
        ext = mesh.extents
        tag = "" if ok is None else ("  OK" if ok else "  CHECK")
        draw.text((x + 8, y + cell - 26), f"{label}{tag}", fill=(20, 20, 20))
        draw.text((x + 8, y + cell - 13), f"{ext[0]:.0f} x {ext[1]:.0f} x {ext[2]:.0f} mm", fill=(90, 90, 90))
    Path(out_png).parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_png)
    return out_png
