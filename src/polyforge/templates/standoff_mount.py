from .base import Param, Template, register


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
        description="A base plate with a grid of standoffs and through-holes for mounting a PCB or panel.",
    )
)
