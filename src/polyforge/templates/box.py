from .base import Param, Template, register


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
        description="A simple open-top rectangular enclosure with rounded corners and a solid floor.",
    )
)
