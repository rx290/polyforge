from .base import BMESH_PRIMITIVES, Param, Template, blender_macro, freecad_macro, register


def _generate(p: dict) -> str:
    return f"""// PolyForge template: standoff_mount
// units: millimetres
// A flat plate with a rectangular grid of cylindrical standoffs, each with a
// through screw hole, for mounting a PCB or panel.

/* [Plate] */
plate_width = {p['plate_width']};
plate_depth = {p['plate_depth']};
plate_thickness = {p['plate_thickness']};

/* [Standoff grid] */
columns = {p['columns']};
rows = {p['rows']};
margin_x = {p['margin_x']};       // distance from plate edge to the nearest standoff center, X
margin_y = {p['margin_y']};       // distance from plate edge to the nearest standoff center, Y
standoff_height = {p['standoff_height']};
standoff_diameter = {p['standoff_diameter']};
hole_diameter = {p['hole_diameter']};

/* [Quality] */
$fn = $preview ? 32 : 96;
eps = 0.01;

assert(columns >= 1 && rows >= 1, "columns and rows must each be at least 1");
assert(plate_width > 2 * margin_x || columns == 1, "margin_x is too large for plate_width");
assert(plate_depth > 2 * margin_y || rows == 1, "margin_y is too large for plate_depth");
assert(hole_diameter < standoff_diameter, "hole_diameter must be smaller than standoff_diameter");
assert(standoff_diameter < min(plate_width, plate_depth), "standoff_diameter is too large for the plate");

module plate() {{
    cube([plate_width, plate_depth, plate_thickness]);
}}

module standoff_centers() {{
    x_step = (columns > 1) ? (plate_width - 2 * margin_x) / (columns - 1) : 0;
    y_step = (rows > 1) ? (plate_depth - 2 * margin_y) / (rows - 1) : 0;
    for (c = [0 : columns - 1], r = [0 : rows - 1])
        translate([margin_x + c * x_step, margin_y + r * y_step, 0])
            children();
}}

module standoffs() {{
    standoff_centers()
        cylinder(h = plate_thickness + standoff_height, d = standoff_diameter);
}}

module standoff_holes() {{
    standoff_centers()
        translate([0, 0, -eps])
            cylinder(h = plate_thickness + standoff_height + 2 * eps, d = hole_diameter);
}}

difference() {{
    union() {{
        plate();
        standoffs();
    }}
    standoff_holes();
}}
"""


def _generate_freecad(p: dict) -> str:
    param_lines = (
        f"plate_width = {p['plate_width']}\n"
        f"plate_depth = {p['plate_depth']}\n"
        f"plate_thickness = {p['plate_thickness']}\n"
        f"columns = {int(p['columns'])}\n"
        f"rows = {int(p['rows'])}\n"
        f"margin_x = {p['margin_x']}\n"
        f"margin_y = {p['margin_y']}\n"
        f"standoff_height = {p['standoff_height']}\n"
        f"standoff_diameter = {p['standoff_diameter']}\n"
        f"hole_diameter = {p['hole_diameter']}\n\n"
        'assert columns >= 1 and rows >= 1, "columns and rows must each be at least 1"\n'
        'assert plate_width > 2 * margin_x or columns == 1, "margin_x is too large for plate_width"\n'
        'assert plate_depth > 2 * margin_y or rows == 1, "margin_y is too large for plate_depth"\n'
        'assert hole_diameter < standoff_diameter, "hole_diameter must be smaller than standoff_diameter"\n'
        'assert standoff_diameter < min(plate_width, plate_depth), "standoff_diameter is too large for the plate"'
    )
    body = """plate = Part.makeBox(plate_width, plate_depth, plate_thickness)
shape = plate

x_step = (plate_width - 2 * margin_x) / (columns - 1) if columns > 1 else 0
y_step = (plate_depth - 2 * margin_y) / (rows - 1) if rows > 1 else 0
centers = [
    (margin_x + c * x_step, margin_y + r * y_step)
    for c in range(columns)
    for r in range(rows)
]

for cx, cy in centers:
    standoff = Part.makeCylinder(
        standoff_diameter / 2, plate_thickness + standoff_height,
        FreeCAD.Vector(cx, cy, 0), FreeCAD.Vector(0, 0, 1),
    )
    shape = shape.fuse(standoff)

for cx, cy in centers:
    hole = Part.makeCylinder(
        hole_diameter / 2, plate_thickness + standoff_height + 2 * eps,
        FreeCAD.Vector(cx, cy, -eps), FreeCAD.Vector(0, 0, 1),
    )
    shape = shape.cut(hole)"""
    return freecad_macro("standoff_mount", param_lines, body)


def _generate_blender(p: dict) -> str:
    param_lines = (
        f"plate_width = {p['plate_width']}\n"
        f"plate_depth = {p['plate_depth']}\n"
        f"plate_thickness = {p['plate_thickness']}\n"
        f"columns = {int(p['columns'])}\n"
        f"rows = {int(p['rows'])}\n"
        f"margin_x = {p['margin_x']}\n"
        f"margin_y = {p['margin_y']}\n"
        f"standoff_height = {p['standoff_height']}\n"
        f"standoff_diameter = {p['standoff_diameter']}\n"
        f"hole_diameter = {p['hole_diameter']}\n\n"
        'assert columns >= 1 and rows >= 1, "columns and rows must each be at least 1"\n'
        'assert plate_width > 2 * margin_x or columns == 1, "margin_x is too large for plate_width"\n'
        'assert plate_depth > 2 * margin_y or rows == 1, "margin_y is too large for plate_depth"\n'
        'assert hole_diameter < standoff_diameter, "hole_diameter must be smaller than standoff_diameter"\n'
        'assert standoff_diameter < min(plate_width, plate_depth), "standoff_diameter is too large for the plate"'
    )
    body = f"""{BMESH_PRIMITIVES}

result_obj = make_box(plate_width, plate_depth, plate_thickness, (0, 0, 0), "plate")

x_step = (plate_width - 2 * margin_x) / (columns - 1) if columns > 1 else 0
y_step = (plate_depth - 2 * margin_y) / (rows - 1) if rows > 1 else 0
centers = [
    (margin_x + c * x_step, margin_y + r * y_step)
    for c in range(columns)
    for r in range(rows)
]

for i, (cx, cy) in enumerate(centers):
    standoff = make_cylinder(standoff_diameter / 2, plate_thickness + standoff_height, (cx, cy, 0), 'Z', f"standoff_{{i}}")
    result_obj = boolean(result_obj, standoff, 'UNION')

for i, (cx, cy) in enumerate(centers):
    hole = make_cylinder(hole_diameter / 2, plate_thickness + standoff_height + 2 * eps, (cx, cy, -eps), 'Z', f"hole_{{i}}")
    result_obj = boolean(result_obj, hole, 'DIFFERENCE')"""
    return blender_macro("standoff_mount", param_lines, body)


TEMPLATE = register(
    Template(
        key="standoff_mount",
        title="Standoff mounting plate",
        keywords=("standoff", "standoff mount", "board mount", "pcb mount", "mounting plate", "mount plate"),
        params=[
            Param("plate_width", 80, description="X, overall plate width"),
            Param("plate_depth", 60, description="Y, overall plate depth"),
            Param("plate_thickness", 3, description="base plate thickness"),
            Param("columns", 2, description="standoffs across X"),
            Param("rows", 2, description="standoffs across Y"),
            Param("margin_x", 8, description="edge-to-center margin, X"),
            Param("margin_y", 8, description="edge-to-center margin, Y"),
            Param("standoff_height", 6, description="standoff height above the plate"),
            Param("standoff_diameter", 6, description="standoff outer diameter"),
            Param("hole_diameter", 2.5, description="through screw hole diameter (M2.5 clearance)"),
        ],
        generate=_generate,
        generate_freecad=_generate_freecad,
        generate_blender=_generate_blender,
        description="A base plate with a grid of standoffs and through-holes for mounting a PCB or panel.",
    )
)
