from .base import BMESH_PRIMITIVES, Param, Template, blender_macro, freecad_macro, register


def _generate(p: dict) -> str:
    return f"""// PolyForge template: l_bracket
// units: millimetres
// A right-angle corner/mending bracket joining two perpendicular surfaces:
// a horizontal flange (holes drilled downward through it) fused to a
// vertical flange (holes drilled through it toward the wall), spanning the
// bracket width in X. Hole placement is expressed as fractions of
// width/flange_a/flange_b so it stays valid for any override of those
// dimensions.

/* [Primary dimensions] */
width = {p['width']};           // X, length of the bracket
flange_a = {p['flange_a']};     // Y, length of the horizontal flange
flange_b = {p['flange_b']};     // Z, length of the vertical flange
thickness = {p['thickness']};

/* [Holes, one row per flange] */
hole_diameter = {p['hole_diameter']};
holes_per_flange = {p['holes_per_flange']};
hole_margin_fraction = {p['hole_margin_fraction']};   // end margin, as a fraction of width
hole_offset_fraction = {p['hole_offset_fraction']};   // hole row position along each flange, as a fraction of that flange's length
hole_margin = width * hole_margin_fraction;
offset_a = flange_a * hole_offset_fraction;
offset_b = flange_b * hole_offset_fraction;

/* [Quality] */
$fn = $preview ? 32 : 96;
eps = 0.01;

assert(flange_a > thickness, "flange_a must exceed thickness");
assert(flange_b > thickness, "flange_b must exceed thickness");
assert(holes_per_flange >= 1, "holes_per_flange must be at least 1");
assert(hole_margin_fraction > 0 && hole_margin_fraction < 0.5, "hole_margin_fraction must be between 0 and 0.5");
assert(hole_offset_fraction > 0 && hole_offset_fraction < 1, "hole_offset_fraction must be between 0 and 1");
assert(offset_a > thickness + hole_diameter / 2, "hole_offset_fraction places holes too close to the bend on flange_a");
assert(offset_b > thickness + hole_diameter / 2, "hole_offset_fraction places holes too close to the bend on flange_b");
assert(offset_a < flange_a - hole_diameter / 2, "hole_offset_fraction runs off the end of flange_a");
assert(offset_b < flange_b - hole_diameter / 2, "hole_offset_fraction runs off the end of flange_b");
assert(hole_diameter < thickness * 5, "hole_diameter looks implausibly large for this plate thickness");

module horizontal_flange() {{
    cube([width, flange_a, thickness]);
}}

module vertical_flange() {{
    cube([width, thickness, flange_b]);
}}

module hole_positions() {{
    step = (holes_per_flange > 1) ? (width - 2 * hole_margin) / (holes_per_flange - 1) : 0;
    for (i = [0 : holes_per_flange - 1])
        translate([hole_margin + i * step, 0, 0])
            children();
}}

module horizontal_flange_holes() {{
    hole_positions()
        translate([0, offset_a, -eps])
            cylinder(h = thickness + 2 * eps, d = hole_diameter);
}}

module vertical_flange_holes() {{
    hole_positions()
        translate([0, -eps, offset_b])
            rotate([-90, 0, 0])
                cylinder(h = thickness + 2 * eps, d = hole_diameter);
}}

difference() {{
    union() {{
        horizontal_flange();
        vertical_flange();
    }}
    horizontal_flange_holes();
    vertical_flange_holes();
}}
"""


def _generate_freecad(p: dict) -> str:
    param_lines = (
        f"width = {p['width']}\n"
        f"flange_a = {p['flange_a']}\n"
        f"flange_b = {p['flange_b']}\n"
        f"thickness = {p['thickness']}\n"
        f"hole_diameter = {p['hole_diameter']}\n"
        f"holes_per_flange = {p['holes_per_flange']}\n"
        f"hole_margin_fraction = {p['hole_margin_fraction']}\n"
        f"hole_offset_fraction = {p['hole_offset_fraction']}\n"
        "hole_margin = width * hole_margin_fraction\n"
        "offset_a = flange_a * hole_offset_fraction\n"
        "offset_b = flange_b * hole_offset_fraction\n\n"
        'assert flange_a > thickness, "flange_a must exceed thickness"\n'
        'assert flange_b > thickness, "flange_b must exceed thickness"\n'
        'assert holes_per_flange >= 1, "holes_per_flange must be at least 1"\n'
        'assert 0 < hole_margin_fraction < 0.5, "hole_margin_fraction must be between 0 and 0.5"\n'
        'assert 0 < hole_offset_fraction < 1, "hole_offset_fraction must be between 0 and 1"\n'
        'assert offset_a > thickness + hole_diameter / 2, "hole_offset_fraction places holes too close to the bend on flange_a"\n'
        'assert offset_b > thickness + hole_diameter / 2, "hole_offset_fraction places holes too close to the bend on flange_b"\n'
        'assert offset_a < flange_a - hole_diameter / 2, "hole_offset_fraction runs off the end of flange_a"\n'
        'assert offset_b < flange_b - hole_diameter / 2, "hole_offset_fraction runs off the end of flange_b"\n'
        'assert hole_diameter < thickness * 5, "hole_diameter looks implausibly large for this plate thickness"'
    )
    body = """horizontal_flange = Part.makeBox(width, flange_a, thickness)
vertical_flange = Part.makeBox(width, thickness, flange_b)
shape = horizontal_flange.fuse(vertical_flange)

step = (width - 2 * hole_margin) / (holes_per_flange - 1) if holes_per_flange > 1 else 0
for i in range(holes_per_flange):
    x = hole_margin + i * step
    horizontal_hole = Part.makeCylinder(
        hole_diameter / 2, thickness + 2 * eps,
        FreeCAD.Vector(x, offset_a, -eps), FreeCAD.Vector(0, 0, 1),
    )
    vertical_hole = Part.makeCylinder(
        hole_diameter / 2, thickness + 2 * eps,
        FreeCAD.Vector(x, -eps, offset_b), FreeCAD.Vector(0, 1, 0),
    )
    shape = shape.cut(horizontal_hole).cut(vertical_hole)"""
    return freecad_macro("l_bracket", param_lines, body)


def _generate_blender(p: dict) -> str:
    param_lines = (
        f"width = {p['width']}\n"
        f"flange_a = {p['flange_a']}\n"
        f"flange_b = {p['flange_b']}\n"
        f"thickness = {p['thickness']}\n"
        f"hole_diameter = {p['hole_diameter']}\n"
        f"holes_per_flange = {int(p['holes_per_flange'])}\n"
        f"hole_margin_fraction = {p['hole_margin_fraction']}\n"
        f"hole_offset_fraction = {p['hole_offset_fraction']}\n"
        "hole_margin = width * hole_margin_fraction\n"
        "offset_a = flange_a * hole_offset_fraction\n"
        "offset_b = flange_b * hole_offset_fraction\n\n"
        'assert flange_a > thickness, "flange_a must exceed thickness"\n'
        'assert flange_b > thickness, "flange_b must exceed thickness"\n'
        'assert holes_per_flange >= 1, "holes_per_flange must be at least 1"\n'
        'assert 0 < hole_margin_fraction < 0.5, "hole_margin_fraction must be between 0 and 0.5"\n'
        'assert 0 < hole_offset_fraction < 1, "hole_offset_fraction must be between 0 and 1"\n'
        'assert offset_a > thickness + hole_diameter / 2, "hole_offset_fraction places holes too close to the bend on flange_a"\n'
        'assert offset_b > thickness + hole_diameter / 2, "hole_offset_fraction places holes too close to the bend on flange_b"\n'
        'assert offset_a < flange_a - hole_diameter / 2, "hole_offset_fraction runs off the end of flange_a"\n'
        'assert offset_b < flange_b - hole_diameter / 2, "hole_offset_fraction runs off the end of flange_b"\n'
        'assert hole_diameter < thickness * 5, "hole_diameter looks implausibly large for this plate thickness"'
    )
    body = f"""{BMESH_PRIMITIVES}

horizontal_flange = make_box(width, flange_a, thickness, (0, 0, 0), "horizontal_flange")
vertical_flange = make_box(width, thickness, flange_b, (0, 0, 0), "vertical_flange")
result_obj = boolean(horizontal_flange, vertical_flange, 'UNION')

step = (width - 2 * hole_margin) / (holes_per_flange - 1) if holes_per_flange > 1 else 0
for i in range(holes_per_flange):
    x = hole_margin + i * step
    horizontal_hole = make_cylinder(hole_diameter / 2, thickness + 2 * eps, (x, offset_a, -eps), 'Z', f"h_hole_{{i}}")
    result_obj = boolean(result_obj, horizontal_hole, 'DIFFERENCE')
    vertical_hole = make_cylinder(hole_diameter / 2, thickness + 2 * eps, (x, -eps, offset_b), 'Y', f"v_hole_{{i}}")
    result_obj = boolean(result_obj, vertical_hole, 'DIFFERENCE')"""
    return blender_macro("l_bracket", param_lines, body)


TEMPLATE = register(
    Template(
        key="l_bracket",
        title="Right-angle corner bracket",
        keywords=("l bracket", "l-bracket", "corner bracket", "mending bracket", "angle bracket", "corner brace"),
        params=[
            Param("width", 40, description="X, length of the bracket"),
            Param("flange_a", 30, description="Y, length of the horizontal flange"),
            Param("flange_b", 30, description="Z, length of the vertical flange"),
            Param("thickness", 4, description="plate thickness"),
            Param("hole_diameter", 4.5, description="hole diameter (M4 clearance)"),
            Param("holes_per_flange", 2, description="holes in each flange"),
            Param("hole_margin_fraction", 0.2, unit="", description="end margin as a fraction of width"),
            Param("hole_offset_fraction", 0.5, unit="", description="hole row position along each flange, as a fraction of its length"),
        ],
        generate=_generate,
        generate_freecad=_generate_freecad,
        generate_blender=_generate_blender,
        description="A right-angle bracket joining two perpendicular surfaces, with holes in both flanges.",
    )
)
