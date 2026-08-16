from .base import Param, Template, blender_macro, freecad_macro, register


def _generate(p: dict) -> str:
    return f"""// PolyForge template: box
// units: millimetres

/* [Primary dimensions] */
width = {p['width']};
depth = {p['depth']};
height = {p['height']};
wall = {p['wall']};
corner_r = {p['corner_radius']};

/* [Quality] */
$fn = $preview ? 32 : 96;
eps = 0.01;

assert(width > 2 * corner_r, "width is too small for corner_radius");
assert(depth > 2 * corner_r, "depth is too small for corner_radius");
assert(wall > 0 && wall * 2 < min(width, depth), "wall is too thick for width/depth");
assert(height > wall, "height must exceed the floor thickness (wall)");

module rounded_rect(size, r) {{
    hull()
        for (dx = [-1, 1], dy = [-1, 1])
            translate([dx * (size[0] / 2 - r), dy * (size[1] / 2 - r), 0])
                circle(r = r);
}}

module box_outer() {{
    linear_extrude(height = height)
        rounded_rect([width, depth], corner_r);
}}

module box_cavity() {{
    inner_r = max(corner_r - wall, 0.1);
    translate([0, 0, wall])
        linear_extrude(height = height)
            rounded_rect([width - 2 * wall, depth - 2 * wall], inner_r);
}}

difference() {{
    box_outer();
    box_cavity();
}}
"""


def _generate_freecad(p: dict) -> str:
    param_lines = (
        f"width = {p['width']}\n"
        f"depth = {p['depth']}\n"
        f"height = {p['height']}\n"
        f"wall = {p['wall']}\n"
        f"corner_r = {p['corner_radius']}\n\n"
        'assert width > 2 * corner_r, "width is too small for corner_radius"\n'
        'assert depth > 2 * corner_r, "depth is too small for corner_radius"\n'
        'assert wall > 0 and wall * 2 < min(width, depth), "wall is too thick for width/depth"\n'
        'assert height > wall, "height must exceed the floor thickness (wall)"'
    )
    body = """def vertical_edges(box):
    return [
        e for e in box.Edges
        if e.BoundBox.XLength < 1e-6 and e.BoundBox.YLength < 1e-6 and e.BoundBox.ZLength > 1e-6
    ]

def rounded_box(w, d, h, r, base=FreeCAD.Vector(0, 0, 0)):
    box = Part.makeBox(w, d, h, base)
    if r <= 0:
        return box
    return box.makeFillet(r, vertical_edges(box))

outer = rounded_box(width, depth, height, corner_r)
inner_r = max(corner_r - wall, 0.1)
inner = rounded_box(width - 2 * wall, depth - 2 * wall, height, inner_r, FreeCAD.Vector(wall, wall, wall))
shape = outer.cut(inner)"""
    return freecad_macro("box", param_lines, body)


def _generate_blender(p: dict) -> str:
    param_lines = (
        f"width = {p['width']}\n"
        f"depth = {p['depth']}\n"
        f"height = {p['height']}\n"
        f"wall = {p['wall']}\n"
        f"corner_r = {p['corner_radius']}\n\n"
        'assert width > 2 * corner_r, "width is too small for corner_radius"\n'
        'assert depth > 2 * corner_r, "depth is too small for corner_radius"\n'
        'assert wall > 0 and wall * 2 < min(width, depth), "wall is too thick for width/depth"\n'
        'assert height > wall, "height must exceed the floor thickness (wall)"'
    )
    body = """def rounded_rect_points(w, d, r, segs=16):
    if r <= 1e-6:
        return [(-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, d / 2), (-w / 2, d / 2)]
    centers = [
        (w / 2 - r, d / 2 - r), (-(w / 2 - r), d / 2 - r),
        (-(w / 2 - r), -(d / 2 - r)), (w / 2 - r, -(d / 2 - r)),
    ]
    starts = [0, 90, 180, 270]
    pts = []
    for (cx, cy), start in zip(centers, starts):
        for i in range(segs + 1):
            a = math.radians(start + 90 * i / segs)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def extrude_solid(points, h, name):
    bm = bmesh.new()
    verts = [bm.verts.new((x, y, 0.0)) for x, y in points]
    bm.verts.ensure_lookup_table()
    face = bm.faces.new(verts)
    bmesh.ops.recalc_face_normals(bm, faces=[face])
    ret = bmesh.ops.extrude_face_region(bm, geom=[face])
    extruded_verts = [v for v in ret['geom'] if isinstance(v, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=extruded_verts, vec=(0, 0, h))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name + "_mesh")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


inner_r = max(corner_r - wall, 0.1)
outer = extrude_solid(rounded_rect_points(width, depth, corner_r), height, "box_outer")
inner = extrude_solid(rounded_rect_points(width - 2 * wall, depth - 2 * wall, inner_r), height, "box_inner")
inner.location.z = wall

cut = outer.modifiers.new(name="cut", type='BOOLEAN')
cut.operation = 'DIFFERENCE'
cut.object = inner
cut.solver = 'EXACT'

bpy.context.view_layer.objects.active = outer
bpy.ops.object.modifier_apply(modifier=cut.name)
bpy.data.objects.remove(inner, do_unlink=True)

result_obj = outer"""
    return blender_macro("box", param_lines, body)


TEMPLATE = register(
    Template(
        key="box",
        title="Open-top box / enclosure",
        keywords=("box", "enclosure", "case", "container", "tray", "housing"),
        params=[
            Param("width", 60, description="overall X"),
            Param("depth", 40, description="overall Y"),
            Param("height", 30, description="overall Z"),
            Param("wall", 2.5, description="wall and floor thickness"),
            Param("corner_radius", 3, description="outer corner radius"),
        ],
        generate=_generate,
        generate_freecad=_generate_freecad,
        generate_blender=_generate_blender,
        description="A simple open-top rectangular enclosure with rounded corners and a solid floor.",
    )
)
