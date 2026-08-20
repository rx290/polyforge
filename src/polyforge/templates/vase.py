from .base import BMESH_PRIMITIVES, Param, Template, blender_macro, freecad_macro, register


def _generate(p: dict) -> str:
    return f"""// PolyForge template: vase
// units: millimetres
//
// Low-poly faceted vase: a jittered N-sided polygon cross-section, stacked
// through many thin height slices via linear_extrude's own twist+scale, not
// rotate_extrude (can't vary twist by height or do a multi-bulge profile)
// and not a hand-rolled polyhedron (real winding-order risk) --
// linear_extrude's scale/twist are native OpenSCAD operations, so the
// result is guaranteed manifold. The SAME jittered cross-section (not
// re-randomized per slice) is reused at every height, just uniformly scaled
// to that slice's radius -- that's what gives continuous vertical facets
// rather than per-slice noise.
//
// The profile itself is 5 diameter control points (base/25%/waist/75%/rim)
// blended with smoothstep (3u^2-2u^3) between adjacent points, sampled at
// `profile_slices` height steps -- found live that blending only the 4
// literal control-point segments directly (one linear_extrude per segment)
// leaves a visible sharp "necking" ring at every control point, since two
// straight scale ramps meeting at a point have mismatched slopes there.
// Smoothstep's derivative is zero at both ends of each blend, so consecutive
// segments meet slope-matched instead of kinked; sampling it at many thin
// slices (rather than one linear_extrude per control point) is what actually
// turns that per-point smoothness into a visibly smooth overall curve.

/* [Overall] */
vase_height = {p['vase_height']};
num_sides = {p['num_sides']};        // low-poly facet count (try 5-10)
facet_jitter = {p['facet_jitter']};  // 0 = perfect regular polygon; up to ~0.4 for a chunky irregular look
random_seed = {p['random_seed']};    // change this for a different random facet pattern at the same jitter
profile_slices = {p['profile_slices']};  // height steps the profile curve is sampled at; higher = smoother curve, slower render

/* [Profile -- diameters at 5 evenly-spaced height fractions: base, 25%, waist (50%), 75%, rim] */
d_base = {p['d_base']};
d_q1 = {p['d_q1']};
d_waist = {p['d_waist']};
d_q3 = {p['d_q3']};
d_rim = {p['d_rim']};

/* [Twist] */
total_twist_deg = {p['total_twist_deg']};   // spiral rotation from base to rim, spread evenly across all slices

/* [Wall / base] */
wall_thickness = {p['wall_thickness']};
base_thickness = {p['base_thickness']};
drainage_hole_d = {p['drainage_hole_d']};  // 0 = no hole

/* [Quality] */
eps = 0.02;

outer_diameters = [d_base, d_q1, d_waist, d_q3, d_rim];
inner_diameters = [for (d = outer_diameters) max(d - 2 * wall_thickness, 0.6)];
max_outer_d = max(outer_diameters);

assert(num_sides >= 3, "num_sides must be at least 3");
assert(profile_slices >= 4, "profile_slices must be at least 4");
assert(facet_jitter >= 0 && facet_jitter < 1, "facet_jitter must be between 0 and 1 (0.4 or less looks best)");
assert(min(outer_diameters) > 0, "all profile diameters must be positive");
assert(base_thickness > 0 && base_thickness < vase_height, "base_thickness must be positive and less than vase_height");
assert(wall_thickness > 0 && 2 * wall_thickness < min(outer_diameters), "wall_thickness is too large for the narrowest profile diameter");
assert(drainage_hole_d == 0 || drainage_hole_d < min(inner_diameters), "drainage_hole_d must be smaller than the narrowest interior diameter");

facet_offsets = rands(1 - facet_jitter, 1 + facet_jitter, num_sides, random_seed);

function facet_points(r) =
    [for (i = [0 : num_sides - 1])
        let (a = 360 * i / num_sides, rr = r * facet_offsets[i])
        [rr * cos(a), rr * sin(a)]];

module facet_ring(r) {{
    polygon(facet_points(r));
}}

function smoothstep(u) = u * u * (3 - 2 * u);

// Radius at height fraction t (0..1), across the 4 control-point intervals
// of `diam` (a 5-entry diameter list), smoothstep-blended within each one.
function radius_at(t, diam) =
    let (
        tt = min(max(t, 0), 1),
        seg = min(floor(tt * 4), 3),
        u = tt * 4 - seg,
        us = smoothstep(u),
        r0 = diam[seg] / 2,
        r1 = diam[seg + 1] / 2
    )
    r0 * (1 - us) + r1 * us;

module profile_slice(r_start, r_end, slice_height, slice_twist) {{
    linear_extrude(height = slice_height, twist = slice_twist, scale = r_end / max(r_start, eps))
        facet_ring(r_start);
}}

module profile_stack(diameters) {{
    n = profile_slices;
    slice_height = vase_height / n;
    slice_twist = total_twist_deg / n;
    for (i = [0 : n - 1])
        // Each slice is pre-rotated by the twist accumulated so far, so its
        // own local 0-degree start lines up with the previous slice's
        // finishing rotation instead of snapping back to 0 and kinking.
        translate([0, 0, i * slice_height])
            rotate([0, 0, i * slice_twist])
                profile_slice(radius_at(i / n, diameters), radius_at((i + 1) / n, diameters), slice_height, slice_twist);
}}

module vase_outer() {{
    profile_stack(outer_diameters);
}}

module inner_full() {{
    rim_r = inner_diameters[4] / 2;
    union() {{
        profile_stack(inner_diameters);
        // pokes a hair through the rim so the top is genuinely cut open,
        // not just brought flush with the outer surface
        translate([0, 0, vase_height - eps])
            cylinder(h = eps * 2, r = rim_r, $fn = num_sides);
    }}
}}

module vase_inner() {{
    // crops the cavity off below base_thickness rather than re-deriving a
    // shorter inner profile there, so the inner shape stays an exact,
    // uniformly-shrunk copy of the outer at every height (no separate
    // compression that would misalign the waist/bulge between them)
    intersection() {{
        inner_full();
        translate([-max_outer_d, -max_outer_d, base_thickness])
            cube([2 * max_outer_d, 2 * max_outer_d, vase_height * 2]);
    }}
}}

module drainage_hole() {{
    if (drainage_hole_d > 0)
        translate([0, 0, -eps])
            cylinder(h = base_thickness + 2 * eps, d = drainage_hole_d, $fn = 24);
}}

difference() {{
    vase_outer();
    vase_inner();
    drainage_hole();
}}
"""


def _freecad_param_lines(p: dict) -> str:
    return (
        f"vase_height = {p['vase_height']}\n"
        f"num_sides = {p['num_sides']}\n"
        f"facet_jitter = {p['facet_jitter']}\n"
        f"random_seed = {p['random_seed']}\n"
        f"profile_slices = {p['profile_slices']}\n"
        f"d_base = {p['d_base']}\n"
        f"d_q1 = {p['d_q1']}\n"
        f"d_waist = {p['d_waist']}\n"
        f"d_q3 = {p['d_q3']}\n"
        f"d_rim = {p['d_rim']}\n"
        f"total_twist_deg = {p['total_twist_deg']}\n"
        f"wall_thickness = {p['wall_thickness']}\n"
        f"base_thickness = {p['base_thickness']}\n"
        f"drainage_hole_d = {p['drainage_hole_d']}\n\n"
        "outer_diameters = [d_base, d_q1, d_waist, d_q3, d_rim]\n"
        "inner_diameters = [max(d - 2 * wall_thickness, 0.6) for d in outer_diameters]\n\n"
        'assert num_sides >= 3, "num_sides must be at least 3"\n'
        'assert profile_slices >= 4, "profile_slices must be at least 4"\n'
        'assert 0 <= facet_jitter < 1, "facet_jitter must be between 0 and 1"\n'
        'assert min(outer_diameters) > 0, "all profile diameters must be positive"\n'
        'assert 0 < base_thickness < vase_height, "base_thickness must be positive and less than vase_height"\n'
        'assert wall_thickness > 0 and 2 * wall_thickness < min(outer_diameters), "wall_thickness is too large for the narrowest profile diameter"\n'
        'assert drainage_hole_d == 0 or drainage_hole_d < min(inner_diameters), "drainage_hole_d must be smaller than the narrowest interior diameter"'
    )


# Shared by both the FreeCAD and Blender generators below: the same
# radius_at(t)/smoothstep/jittered-facet-offsets math as the OpenSCAD
# version above, just in plain Python instead of OpenSCAD's language --
# kept as one string pasted into both macros (matching how box.py's
# generators each embed their own small self-contained helpers) rather than
# importing a private polyforge module, so each generated file stays
# independently editable.
_PROFILE_MATH_PY = """def smoothstep(u):
    return u * u * (3 - 2 * u)


def radius_at(t, diam):
    tt = min(max(t, 0.0), 1.0)
    seg = min(int(tt * 4), 3)
    u = tt * 4 - seg
    us = smoothstep(u)
    r0, r1 = diam[seg] / 2.0, diam[seg + 1] / 2.0
    return r0 * (1 - us) + r1 * us


_rng = random.Random(random_seed)
facet_offsets = [_rng.uniform(1 - facet_jitter, 1 + facet_jitter) for _ in range(num_sides)]


def ring_points(r, angle_offset_deg):
    ao = math.radians(angle_offset_deg)
    pts = []
    for i in range(num_sides):
        a = math.radians(360.0 * i / num_sides)
        rr = r * facet_offsets[i]
        x, y = rr * math.cos(a), rr * math.sin(a)
        pts.append((x * math.cos(ao) - y * math.sin(ao), x * math.sin(ao) + y * math.cos(ao)))
    return pts"""


def _generate_freecad(p: dict) -> str:
    param_lines = _freecad_param_lines(p)
    body = f"""import math
import random

{_PROFILE_MATH_PY}


def ring_wire(r, angle_offset_deg, z):
    pts = [FreeCAD.Vector(x, y, z) for x, y in ring_points(r, angle_offset_deg)]
    pts.append(pts[0])
    return Part.makePolygon(pts)


def loft_profile(diameters, extra_top=0.0):
    # ruled=True forces straight lines between corresponding points of
    # consecutive ring profiles (matching linear_extrude's own straight
    # interpolation in the OpenSCAD version) instead of FreeCAD's default
    # smoothed B-spline loft, which would round off the profile's own
    # control points instead of just its facets.
    wires = []
    for i in range(profile_slices + 1):
        t = i / profile_slices
        r = radius_at(t, diameters)
        z = t * vase_height
        twist = t * total_twist_deg
        wires.append(ring_wire(r, twist, z))
    if extra_top > 0:
        r_top = radius_at(1.0, diameters)
        wires.append(ring_wire(r_top, total_twist_deg, vase_height + extra_top))
    return Part.makeLoft(wires, True, True, False)


outer = loft_profile(outer_diameters)
inner_full = loft_profile(inner_diameters, extra_top=eps)
crop_box = Part.makeBox(4000, 4000, vase_height * 2, FreeCAD.Vector(-2000, -2000, base_thickness))
inner = inner_full.common(crop_box)
shape = outer.cut(inner)

if drainage_hole_d > 0:
    hole = Part.makeCylinder(drainage_hole_d / 2, base_thickness + 2 * eps, FreeCAD.Vector(0, 0, -eps))
    shape = shape.cut(hole)"""
    return freecad_macro("vase", param_lines, body)


def _generate_blender(p: dict) -> str:
    param_lines = _freecad_param_lines(p)
    body = f"""import random

{BMESH_PRIMITIVES}


{_PROFILE_MATH_PY}


def build_shell(diameters, name, extra_top=0.0):
    bm = bmesh.new()
    rings = []
    for i in range(profile_slices + 1):
        t = i / profile_slices
        r = radius_at(t, diameters)
        z = t * vase_height
        twist = t * total_twist_deg
        ring = [bm.verts.new((x, y, z)) for x, y in ring_points(r, twist)]
        rings.append(ring)
    if extra_top > 0:
        r_top = radius_at(1.0, diameters)
        top_ring = [bm.verts.new((x, y, vase_height + extra_top)) for x, y in ring_points(r_top, total_twist_deg)]
        rings.append(top_ring)
    bm.verts.ensure_lookup_table()

    n = num_sides
    for a, b in zip(rings, rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new([a[i], a[j], b[j], b[i]])

    # Both ends capped -- this needs to be a genuinely closed solid for the
    # boolean ops below to behave (matching Part.makeLoft(solid=True) in the
    # FreeCAD version, which caps both ends automatically); the vase's own
    # open top only emerges afterward, from subtracting a cavity that pokes
    # a hair past this shell's top cap, not from leaving this mesh open.
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))

    mesh = bpy.data.meshes.new(name + "_mesh")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


outer = build_shell(outer_diameters, "vase_outer")
inner = build_shell(inner_diameters, "vase_inner", extra_top=eps)

# crop the inner shell's own mesh to only the part above base_thickness,
# via a boolean intersection with a crop box, before it ever touches the
# outer shell -- mirrors the OpenSCAD/FreeCAD versions' own crop step.
crop = bpy.data.objects.new("crop", bpy.data.meshes.new("crop_mesh"))
bpy.context.collection.objects.link(crop)
crop_bm = bmesh.new()
bmesh.ops.create_cube(crop_bm, size=1.0)
bmesh.ops.scale(crop_bm, vec=(4000.0, 4000.0, vase_height), verts=crop_bm.verts)
bmesh.ops.translate(crop_bm, vec=(0.0, 0.0, base_thickness + vase_height / 2.0), verts=crop_bm.verts)
crop_bm.to_mesh(crop.data)
crop_bm.free()

boolean(inner, crop, 'INTERSECT')
boolean(outer, inner, 'DIFFERENCE')

if drainage_hole_d > 0:
    hole = make_cylinder(drainage_hole_d / 2, base_thickness + 2 * eps, (0, 0, -eps), 'Z', "drainage_hole")
    boolean(outer, hole, 'DIFFERENCE')

result_obj = outer"""
    return blender_macro("vase", param_lines, body)


TEMPLATE = register(
    Template(
        key="vase",
        title="Low-poly faceted vase",
        keywords=("vase", "planter", "pot", "flower vase", "low poly vase", "faceted vase", "twisted vase"),
        params=[
            Param("d_base", 70, description="diameter at the base"),
            Param("vase_height", 150, description="overall height"),
            Param("d_rim", 60, description="diameter at the rim (top)"),
            Param("d_q1", 55, description="diameter at 25% height"),
            Param("d_waist", 45, description="diameter at 50% height (the waist)"),
            Param("d_q3", 65, description="diameter at 75% height"),
            Param("num_sides", 7, unit="", description="low-poly facet count around the circumference"),
            Param("facet_jitter", 0.12, unit="", description="0 = perfect regular polygon, up to ~0.4 for a chunky irregular low-poly look"),
            Param("random_seed", 1, unit="", description="change for a different random facet pattern at the same jitter"),
            Param("profile_slices", 24, unit="", description="height steps the profile curve is sampled at; higher = smoother, slower render"),
            Param("total_twist_deg", 120, unit="deg", description="spiral rotation from base to rim"),
            Param("wall_thickness", 2.4, description="shell wall thickness"),
            Param("base_thickness", 4, description="solid base thickness"),
            Param("drainage_hole_d", 0, description="drainage hole diameter in the base; 0 = no hole"),
        ],
        generate=_generate,
        generate_freecad=_generate_freecad,
        generate_blender=_generate_blender,
        description=(
            "A hollow, low-poly faceted vase: a 5-point diameter profile (base/25%/waist/75%/rim), "
            "smoothstep-blended and revolved with a jittered N-sided cross-section, with an optional "
            "spiral twist. Prints in any mode (not vase-mode-dependent) thanks to a real wall "
            "thickness and solid base."
        ),
    )
)
