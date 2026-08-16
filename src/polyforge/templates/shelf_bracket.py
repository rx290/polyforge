from .base import BMESH_PRIMITIVES, Param, Template, blender_macro, freecad_macro, register


def _generate(p: dict) -> str:
    return f"""// PolyForge template: shelf_bracket
// units: millimetres
// L-profile wall shelf: a vertical back plate (against the wall, with mounting
// holes) fused to a horizontal shelf plate, spanning the shelf width in X.
// Hole placement is expressed as fractions of shelf_width/back_height so it
// stays valid for any override of those dimensions.

/* [Primary dimensions] */
shelf_width = {p['shelf_width']};   // X, length of the shelf
shelf_depth = {p['shelf_depth']};   // Y, how far the shelf sticks out from the wall
back_height = {p['back_height']};   // Z, height of the vertical wall plate
thickness = {p['thickness']};       // plate thickness

/* [Mounting holes, through the back plate] */
hole_diameter = {p['hole_diameter']};
hole_count = {p['hole_count']};
hole_margin_fraction = {p['hole_margin_fraction']};   // end margin, as a fraction of shelf_width
hole_z_fraction = {p['hole_z_fraction']};             // hole row height, as a fraction of back_height
hole_margin = shelf_width * hole_margin_fraction;
hole_z = back_height * hole_z_fraction;

/* [Quality] */
$fn = $preview ? 32 : 96;
eps = 0.01;

assert(shelf_depth > thickness, "shelf_depth must exceed thickness");
assert(back_height > thickness, "back_height must exceed thickness");
assert(hole_count >= 1, "hole_count must be at least 1");
assert(hole_margin_fraction > 0 && hole_margin_fraction < 0.5, "hole_margin_fraction must be between 0 and 0.5");
assert(hole_z_fraction > 0 && hole_z_fraction < 1, "hole_z_fraction must be between 0 and 1");
assert(hole_diameter < thickness * 4, "hole_diameter looks implausibly large for this plate thickness");

module back_plate() {{
    cube([shelf_width, thickness, back_height]);
}}

module shelf_plate() {{
    cube([shelf_width, shelf_depth, thickness]);
}}

module mounting_holes() {{
    step = (hole_count > 1) ? (shelf_width - 2 * hole_margin) / (hole_count - 1) : 0;
    for (i = [0 : hole_count - 1]) {{
        x = hole_margin + i * step;
        translate([x, -eps, hole_z])
            rotate([-90, 0, 0])
                cylinder(h = thickness + 2 * eps, d = hole_diameter);
    }}
}}

difference() {{
    union() {{
        back_plate();
        shelf_plate();
    }}
    mounting_holes();
}}
"""


def _generate_freecad(p: dict) -> str:
    param_lines = (
        f"shelf_width = {p['shelf_width']}\n"
        f"shelf_depth = {p['shelf_depth']}\n"
        f"back_height = {p['back_height']}\n"
        f"thickness = {p['thickness']}\n"
        f"hole_diameter = {p['hole_diameter']}\n"
        f"hole_count = {p['hole_count']}\n"
        f"hole_margin_fraction = {p['hole_margin_fraction']}\n"
        f"hole_z_fraction = {p['hole_z_fraction']}\n"
        "hole_margin = shelf_width * hole_margin_fraction\n"
        "hole_z = back_height * hole_z_fraction\n\n"
        'assert shelf_depth > thickness, "shelf_depth must exceed thickness"\n'
        'assert back_height > thickness, "back_height must exceed thickness"\n'
        'assert hole_count >= 1, "hole_count must be at least 1"\n'
        'assert 0 < hole_margin_fraction < 0.5, "hole_margin_fraction must be between 0 and 0.5"\n'
        'assert 0 < hole_z_fraction < 1, "hole_z_fraction must be between 0 and 1"\n'
        'assert hole_diameter < thickness * 4, "hole_diameter looks implausibly large for this plate thickness"'
    )
    body = """back_plate = Part.makeBox(shelf_width, thickness, back_height)
shelf_plate = Part.makeBox(shelf_width, shelf_depth, thickness)
shape = back_plate.fuse(shelf_plate)

step = (shelf_width - 2 * hole_margin) / (hole_count - 1) if hole_count > 1 else 0
for i in range(hole_count):
    x = hole_margin + i * step
    hole = Part.makeCylinder(
        hole_diameter / 2, thickness + 2 * eps,
        FreeCAD.Vector(x, -eps, hole_z), FreeCAD.Vector(0, 1, 0),
    )
    shape = shape.cut(hole)"""
    return freecad_macro("shelf_bracket", param_lines, body)


def _generate_blender(p: dict) -> str:
    param_lines = (
        f"shelf_width = {p['shelf_width']}\n"
        f"shelf_depth = {p['shelf_depth']}\n"
        f"back_height = {p['back_height']}\n"
        f"thickness = {p['thickness']}\n"
        f"hole_diameter = {p['hole_diameter']}\n"
        f"hole_count = {int(p['hole_count'])}\n"
        f"hole_margin_fraction = {p['hole_margin_fraction']}\n"
        f"hole_z_fraction = {p['hole_z_fraction']}\n"
        "hole_margin = shelf_width * hole_margin_fraction\n"
        "hole_z = back_height * hole_z_fraction\n\n"
        'assert shelf_depth > thickness, "shelf_depth must exceed thickness"\n'
        'assert back_height > thickness, "back_height must exceed thickness"\n'
        'assert hole_count >= 1, "hole_count must be at least 1"\n'
        'assert 0 < hole_margin_fraction < 0.5, "hole_margin_fraction must be between 0 and 0.5"\n'
        'assert 0 < hole_z_fraction < 1, "hole_z_fraction must be between 0 and 1"\n'
        'assert hole_diameter < thickness * 4, "hole_diameter looks implausibly large for this plate thickness"'
    )
    body = f"""{BMESH_PRIMITIVES}

back_plate = make_box(shelf_width, thickness, back_height, (0, 0, 0), "back_plate")
shelf_plate = make_box(shelf_width, shelf_depth, thickness, (0, 0, 0), "shelf_plate")
result_obj = boolean(back_plate, shelf_plate, 'UNION')

step = (shelf_width - 2 * hole_margin) / (hole_count - 1) if hole_count > 1 else 0
for i in range(hole_count):
    x = hole_margin + i * step
    hole = make_cylinder(hole_diameter / 2, thickness + 2 * eps, (x, -eps, hole_z), 'Y', f"hole_{{i}}")
    result_obj = boolean(result_obj, hole, 'DIFFERENCE')"""
    return blender_macro("shelf_bracket", param_lines, body)


TEMPLATE = register(
    Template(
        key="shelf_bracket",
        title="Wall-mounted L-profile shelf",
        keywords=("shelf", "wall shelf", "wall-mounted shelf", "ledge", "floating shelf"),
        params=[
            Param("shelf_width", 200, description="X, length of the shelf"),
            Param("shelf_depth", 120, description="Y, how far the shelf sticks out"),
            Param("back_height", 60, description="Z, height of the wall-side plate"),
            Param("thickness", 5, description="plate thickness"),
            Param("hole_diameter", 4.5, description="mounting hole diameter (M4 clearance)"),
            Param("hole_count", 2, description="number of mounting holes"),
            Param("hole_margin_fraction", 0.1, unit="", description="end margin as a fraction of shelf_width"),
            Param("hole_z_fraction", 0.5, unit="", description="hole row height as a fraction of back_height"),
        ],
        generate=_generate,
        generate_freecad=_generate_freecad,
        generate_blender=_generate_blender,
        description="A wall-mounted shelf: an L-shaped profile with mounting holes through the back plate.",
    )
)
