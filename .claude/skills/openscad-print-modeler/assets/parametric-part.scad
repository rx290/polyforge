// Parametric OpenSCAD starter for dimensioned FDM parts.
// Units: millimetres

/* [Primary dimensions] */
part_x = 60;
part_y = 40;
part_z = 8;
corner_r = 3;

/* [Functional features] */
hole_d = 3.4;
hole_edge_x = 8;
hole_edge_y = 8;

/* [Quality] */
preview_fn = 32;
render_fn = 96;
$fn = $preview ? preview_fn : render_fn;
eps = 0.01;

assert(part_x > 2 * corner_r, "part_x is too small for corner_r");
assert(part_y > 2 * corner_r, "part_y is too small for corner_r");
assert(hole_edge_x > hole_d / 2, "hole is too close to X edge");
assert(hole_edge_y > hole_d / 2, "hole is too close to Y edge");

module rounded_profile(size = [part_x, part_y], r = corner_r) {
    offset(r = r)
        square([size.x - 2 * r, size.y - 2 * r], center = true);
}

module primary_body() {
    linear_extrude(height = part_z)
        rounded_profile();
}

module additive_features() {
    // Add bosses, ribs, or locating features here.
}

module subtractive_features() {
    for (x = [-part_x / 2 + hole_edge_x, part_x / 2 - hole_edge_x])
        for (y = [-part_y / 2 + hole_edge_y, part_y / 2 - hole_edge_y])
            translate([x, y, -eps])
                cylinder(d = hole_d, h = part_z + 2 * eps);
}

difference() {
    union() {
        primary_body();
        additive_features();
    }
    subtractive_features();
}
