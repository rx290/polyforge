from .base import BMESH_PRIMITIVES, Param, Template, blender_macro, freecad_macro, register

# Section shape codes, shared by every backend below (kept numeric, not a
# string enum, so every param stays a plain float -- the same numeric shape
# all other templates' params use, and what the GUI's slider/number-input
# rendering already expects). 0=cylinder (holds the section's start
# diameter constant, its own end_d is ignored), 1=cone (straight linear
# taper), 2=taper (eased/smooth taper, no visible "necking" at the section's
# ends -- the default), 3=bulge (an eased S-curve through a THIRD diameter,
# peak_d, at the section's own midpoint -- one shape that covers both an
# hourglass waist, peak_d < both ends, and a globe/dome bulge, peak_d >
# both ends, since it's just the sign of that difference).
SECTION_CYLINDER, SECTION_CONE, SECTION_TAPER, SECTION_BULGE = 0, 1, 2, 3


def _generate(p: dict) -> str:
    return f"""// PolyForge template: vase
// units: millimetres
//
// A general parametric vase/planter: 4 profile sections, each independently
// a cylinder, a straight cone, an eased taper, or a bulge (hourglass waist
// or globe/dome, depending on which way its own peak diameter goes) --
// covers most real vase silhouettes (straight, tapered, hourglass, bulb/
// globe, stepped-neck) as sequences of these 4 primitives, not just one
// fixed 5-point curve. An optional low-poly faceted look (num_sides small,
// facet_jitter > 0) is still available but no longer the only look --
// num_sides high (e.g. 48+) with facet_jitter=0 gives an effectively smooth
// body instead. A revolved-profile generator (this one and every site it
// was researched against) can only ever produce shapes symmetric around
// the vertical axis -- an actual creature/skull silhouette needs real
// generative 3D synthesis, a different technology entirely, not a richer
// profile system.
//
// Built on stacked linear_extrude(twist=, scale=) -- not rotate_extrude
// (can't vary twist by height or do a multi-bulge profile) and not a
// hand-rolled polyhedron (real winding-order risk) -- linear_extrude's
// scale/twist are native OpenSCAD operations, so the result is guaranteed
// manifold. The SAME jittered cross-section (not re-randomized per slice)
// is reused at every height, just uniformly scaled to that slice's radius,
// optionally further modulated by a textured-base wave near the floor --
// that's what gives continuous vertical facets rather than per-slice noise.

/* [Overall] */
vase_height = {p['vase_height']};
d_base = {p['d_base']};              // diameter at the very bottom (section 1's start)
num_sides = {p['num_sides']};        // facet count around the circumference (try 5-10 for low-poly, 48+ for near-smooth)
facet_jitter = {p['facet_jitter']};  // 0 = perfect regular polygon; up to ~0.4 for a chunky irregular low-poly look
random_seed = {p['random_seed']};    // change this for a different random facet pattern at the same jitter
profile_slices = {p['profile_slices']};  // height steps the profile curve is sampled at; higher = smoother curve, slower render

/* [Section 1 -- shape: 0=cylinder 1=cone 2=taper(eased) 3=bulge] */
s1_type = {p['s1_type']};
s1_end_d = {p['s1_end_d']};
s1_peak_d = {p['s1_peak_d']};        // only used when s1_type=3 (bulge)
s1_height_frac = {p['s1_height_frac']};  // share of vase_height (normalized against all 4, doesn't need to sum to 1 itself)

/* [Section 2] */
s2_type = {p['s2_type']};
s2_end_d = {p['s2_end_d']};
s2_peak_d = {p['s2_peak_d']};
s2_height_frac = {p['s2_height_frac']};

/* [Section 3] */
s3_type = {p['s3_type']};
s3_end_d = {p['s3_end_d']};
s3_peak_d = {p['s3_peak_d']};
s3_height_frac = {p['s3_height_frac']};

/* [Section 4 -- ends at the rim] */
s4_type = {p['s4_type']};
s4_end_d = {p['s4_end_d']};
s4_peak_d = {p['s4_peak_d']};
s4_height_frac = {p['s4_height_frac']};

/* [Twist] */
total_twist_deg = {p['total_twist_deg']};   // spiral rotation from base to rim, spread proportionally across all 4 sections

/* [Wall / base] */
wall_thickness = {p['wall_thickness']};
base_thickness = {p['base_thickness']};
drainage_hole_d = {p['drainage_hole_d']};  // 0 = no hole

/* [Holder ring -- an optional raised ring/lip at a chosen height, e.g. to seat a candle cup or a bulb-holder fitting] */
holder_ring_d = {p['holder_ring_d']};       // ring cross-section diameter; 0 = disabled
holder_ring_height_frac = {p['holder_ring_height_frac']};  // 0..1 up the vase

/* [Textured base -- an optional repeating wave pattern low on the wall, fading out by base_texture_height_frac] */
base_texture_amplitude = {p['base_texture_amplitude']};  // 0 = disabled; fraction of local radius, try 0.05-0.15
base_texture_frequency = {p['base_texture_frequency']};  // repeating bumps around the circumference
base_texture_height_frac = {p['base_texture_height_frac']};  // how far up the texture reaches before fading out

/* [Quality] */
eps = 0.02;

s_type = [s1_type, s2_type, s3_type, s4_type];
s_end_d = [s1_end_d, s2_end_d, s3_end_d, s4_end_d];
s_peak_d = [s1_peak_d, s2_peak_d, s3_peak_d, s4_peak_d];
s_start_d = [d_base, s1_end_d, s2_end_d, s3_end_d];
s_height_frac_raw = [s1_height_frac, s2_height_frac, s3_height_frac, s4_height_frac];
frac_sum = s_height_frac_raw[0] + s_height_frac_raw[1] + s_height_frac_raw[2] + s_height_frac_raw[3];
s_height_frac = [for (f = s_height_frac_raw) f / frac_sum];
s_t_start = [0, s_height_frac[0], s_height_frac[0] + s_height_frac[1], s_height_frac[0] + s_height_frac[1] + s_height_frac[2]];

all_diameters = concat([d_base], s_end_d, s_peak_d);

assert(num_sides >= 3, "num_sides must be at least 3");
assert(profile_slices >= 4, "profile_slices must be at least 4");
assert(facet_jitter >= 0 && facet_jitter < 1, "facet_jitter must be between 0 and 1 (0.4 or less looks best)");
assert(min(all_diameters) > 0, "all profile/peak diameters must be positive");
assert(min(s_height_frac_raw) > 0, "every section's height_frac must be positive");
assert(base_thickness > 0 && base_thickness < vase_height, "base_thickness must be positive and less than vase_height");
assert(wall_thickness > 0 && 2 * wall_thickness < min(all_diameters), "wall_thickness is too large for the narrowest profile/peak diameter");
assert(drainage_hole_d == 0 || drainage_hole_d < min(all_diameters) - 2 * wall_thickness, "drainage_hole_d must be smaller than the narrowest interior diameter");
assert(holder_ring_height_frac >= 0 && holder_ring_height_frac <= 1, "holder_ring_height_frac must be between 0 and 1");
assert(base_texture_amplitude >= 0 && base_texture_amplitude < 0.5, "base_texture_amplitude must be between 0 and 0.5");
assert(base_texture_height_frac > 0 && base_texture_height_frac <= 1, "base_texture_height_frac must be between 0 and 1");

facet_offsets = rands(1 - facet_jitter, 1 + facet_jitter, num_sides, random_seed);

function ease(u) = (1 - cos(180 * u)) / 2;  // OpenSCAD's cos() takes degrees natively

// r0/r1/rp are radii (not diameters) for whichever section `type` picks out.
function section_radius(u, r0, r1, rp, type) =
    type == 0 ? r0 :
    type == 1 ? r0 + (r1 - r0) * u :
    type == 3 ? (u <= 0.5 ? r0 + (rp - r0) * ease(2 * u) : rp + (r1 - rp) * ease(2 * (u - 0.5))) :
    r0 + (r1 - r0) * ease(u);

function which_section(t) =
    t < s_t_start[1] ? 0 :
    t < s_t_start[2] ? 1 :
    t < s_t_start[3] ? 2 : 3;

// The bare profile's radius at height fraction t (0..1), before the
// optional holder-ring bump -- see wall_offset() below for how the inner
// cavity reuses THIS (not the bumped outer_radius_at) so the ring doesn't
// dent inward into the cavity, and so the cavity stays an exact,
// uniformly-shrunk copy of the profile at every height (no separate
// compression that would misalign the waist/bulge between them, the same
// real bug class the original 5-point version's own crop step was written
// to avoid).
function base_outer_radius_at(t) =
    let (
        tt = min(max(t, 0), 1),
        idx = which_section(tt),
        t0 = s_t_start[idx],
        frac = s_height_frac[idx],
        u = frac > 0 ? min(max((tt - t0) / frac, 0), 1) : 0,
        r0 = s_start_d[idx] / 2,
        r1 = s_end_d[idx] / 2,
        rp = s_peak_d[idx] / 2
    )
    section_radius(u, r0, r1, rp, s_type[idx]);

// The holder ring is a smooth local bump added straight onto the outer
// profile -- not a separate torus unioned in afterward. Found live (via
// the Blender backend, whose bmesh boolean modifier is the least robust of
// the three) that a separately-built torus, even carefully positioned to
// stay embedded in the wall, still produced a handful of non-manifold
// edges once unioned: the vase's own faceted/jittered surface isn't a
// perfect circle, so a smooth torus overlaps it unevenly around the
// circumference, and Blender's mesh boolean is fragile to that unevenness
// in a way FreeCAD's B-rep boolean and OpenSCAD's CGAL boolean weren't.
// Building the bump directly into the same ring-stacked profile this whole
// shell is already made from needs no boolean operation for this feature
// at all, so there's nothing left to be fragile.
ring_half_frac = holder_ring_d <= 0 ? 0 : min(max((holder_ring_d / 2) / vase_height, 0.01), 0.15);

function ring_bump(t) =
    holder_ring_d <= 0 ? 0 :
    let (
        dt = min(abs(t - holder_ring_height_frac) / ring_half_frac, 1)
    )
    (holder_ring_d / 2) * (1 - ease(dt));

function outer_radius_at(t) = base_outer_radius_at(t) + ring_bump(t);

function wall_offset(r) = max(r - wall_thickness, 0.3);

// The textured-base wave's multiplier at a given facet angle and height
// fraction, fading to 1 (no effect) by base_texture_height_frac -- a fixed
// small fade band (not a fraction of the textured region itself) keeps the
// transition predictable regardless of how tall that region is.
function texture_factor(angle_deg, t) =
    base_texture_amplitude <= 0 ? 1 :
    let (
        raw = 1 + base_texture_amplitude * sin(base_texture_frequency * angle_deg),
        fade_width = min(0.03, base_texture_height_frac / 2),
        fade = t <= base_texture_height_frac - fade_width ? 1
             : t >= base_texture_height_frac ? 0
             : (base_texture_height_frac - t) / fade_width
    )
    1 + (raw - 1) * fade;

function facet_points(r, t) =
    [for (i = [0 : num_sides - 1])
        let (a = 360 * i / num_sides, rr = r * facet_offsets[i] * texture_factor(a, t))
        [rr * cos(a), rr * sin(a)]];

module facet_ring(r, t) {{
    polygon(facet_points(r, t));
}}

module profile_slice(r_start, r_end, t_start, slice_height, slice_twist) {{
    linear_extrude(height = slice_height, twist = slice_twist, scale = r_end / max(r_start, eps))
        facet_ring(r_start, t_start);
}}

module profile_stack(is_inner) {{
    n = profile_slices;
    slice_height = vase_height / n;
    slice_twist = total_twist_deg / n;
    for (i = [0 : n - 1]) {{
        t0 = i / n;
        t1 = (i + 1) / n;
        r0 = is_inner ? wall_offset(base_outer_radius_at(t0)) : outer_radius_at(t0);
        r1 = is_inner ? wall_offset(base_outer_radius_at(t1)) : outer_radius_at(t1);
        // Each slice is pre-rotated by the twist accumulated so far, so its
        // own local 0-degree start lines up with the previous slice's
        // finishing rotation instead of snapping back to 0 and kinking.
        translate([0, 0, i * slice_height])
            rotate([0, 0, i * slice_twist])
                profile_slice(r0, r1, t0, slice_height, slice_twist);
    }}
}}

module vase_outer() {{
    profile_stack(false);
}}

module inner_full() {{
    rim_r = wall_offset(base_outer_radius_at(1));
    union() {{
        profile_stack(true);
        // pokes a hair through the rim so the top is genuinely cut open,
        // not just brought flush with the outer surface
        translate([0, 0, vase_height - eps])
            cylinder(h = eps * 2, r = rim_r, $fn = num_sides);
    }}
}}

module vase_inner() {{
    max_outer_d = max(all_diameters);
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
        f"d_base = {p['d_base']}\n"
        f"num_sides = {p['num_sides']}\n"
        f"facet_jitter = {p['facet_jitter']}\n"
        f"random_seed = {p['random_seed']}\n"
        f"profile_slices = {p['profile_slices']}\n"
        f"s1_type = {p['s1_type']}\n"
        f"s1_end_d = {p['s1_end_d']}\n"
        f"s1_peak_d = {p['s1_peak_d']}\n"
        f"s1_height_frac = {p['s1_height_frac']}\n"
        f"s2_type = {p['s2_type']}\n"
        f"s2_end_d = {p['s2_end_d']}\n"
        f"s2_peak_d = {p['s2_peak_d']}\n"
        f"s2_height_frac = {p['s2_height_frac']}\n"
        f"s3_type = {p['s3_type']}\n"
        f"s3_end_d = {p['s3_end_d']}\n"
        f"s3_peak_d = {p['s3_peak_d']}\n"
        f"s3_height_frac = {p['s3_height_frac']}\n"
        f"s4_type = {p['s4_type']}\n"
        f"s4_end_d = {p['s4_end_d']}\n"
        f"s4_peak_d = {p['s4_peak_d']}\n"
        f"s4_height_frac = {p['s4_height_frac']}\n"
        f"total_twist_deg = {p['total_twist_deg']}\n"
        f"wall_thickness = {p['wall_thickness']}\n"
        f"base_thickness = {p['base_thickness']}\n"
        f"drainage_hole_d = {p['drainage_hole_d']}\n"
        f"holder_ring_d = {p['holder_ring_d']}\n"
        f"holder_ring_height_frac = {p['holder_ring_height_frac']}\n"
        f"base_texture_amplitude = {p['base_texture_amplitude']}\n"
        f"base_texture_frequency = {p['base_texture_frequency']}\n"
        f"base_texture_height_frac = {p['base_texture_height_frac']}\n\n"
        "s_type = [s1_type, s2_type, s3_type, s4_type]\n"
        "s_end_d = [s1_end_d, s2_end_d, s3_end_d, s4_end_d]\n"
        "s_peak_d = [s1_peak_d, s2_peak_d, s3_peak_d, s4_peak_d]\n"
        "s_start_d = [d_base, s1_end_d, s2_end_d, s3_end_d]\n"
        "s_height_frac_raw = [s1_height_frac, s2_height_frac, s3_height_frac, s4_height_frac]\n"
        "frac_sum = sum(s_height_frac_raw)\n"
        "s_height_frac = [f / frac_sum for f in s_height_frac_raw]\n"
        "s_t_start = [0, s_height_frac[0], s_height_frac[0] + s_height_frac[1], s_height_frac[0] + s_height_frac[1] + s_height_frac[2]]\n"
        "all_diameters = [d_base] + s_end_d + s_peak_d\n\n"
        'assert num_sides >= 3, "num_sides must be at least 3"\n'
        'assert profile_slices >= 4, "profile_slices must be at least 4"\n'
        'assert 0 <= facet_jitter < 1, "facet_jitter must be between 0 and 1"\n'
        'assert min(all_diameters) > 0, "all profile/peak diameters must be positive"\n'
        'assert min(s_height_frac_raw) > 0, "every section\'s height_frac must be positive"\n'
        'assert 0 < base_thickness < vase_height, "base_thickness must be positive and less than vase_height"\n'
        'assert wall_thickness > 0 and 2 * wall_thickness < min(all_diameters), "wall_thickness is too large for the narrowest profile/peak diameter"\n'
        'assert drainage_hole_d == 0 or drainage_hole_d < min(all_diameters) - 2 * wall_thickness, "drainage_hole_d must be smaller than the narrowest interior diameter"\n'
        'assert 0 <= holder_ring_height_frac <= 1, "holder_ring_height_frac must be between 0 and 1"\n'
        'assert holder_ring_d * 0.2 <= wall_thickness, "holder_ring_d is too large for wall_thickness -- its embedded inward portion would reach past the wall into the hollow interior"\n'
        'assert 0 <= base_texture_amplitude < 0.5, "base_texture_amplitude must be between 0 and 0.5"\n'
        'assert 0 < base_texture_height_frac <= 1, "base_texture_height_frac must be between 0 and 1"'
    )


# Shared by both the FreeCAD and Blender generators below: the same
# section/ease/radius math as the OpenSCAD version above, just in plain
# Python instead of OpenSCAD's language -- kept as one string pasted into
# both macros (matching how box.py's generators each embed their own small
# self-contained helpers) rather than importing a private polyforge module,
# so each generated file stays independently editable.
_PROFILE_MATH_PY = """def ease(u):
    return (1 - math.cos(math.pi * u)) / 2


def section_radius(u, r0, r1, rp, section_type):
    if section_type == 0:
        return r0
    if section_type == 1:
        return r0 + (r1 - r0) * u
    if section_type == 3:
        if u <= 0.5:
            return r0 + (rp - r0) * ease(2 * u)
        return rp + (r1 - rp) * ease(2 * (u - 0.5))
    return r0 + (r1 - r0) * ease(u)


def which_section(t):
    if t < s_t_start[1]:
        return 0
    if t < s_t_start[2]:
        return 1
    if t < s_t_start[3]:
        return 2
    return 3


def base_outer_radius_at(t):
    tt = min(max(t, 0.0), 1.0)
    idx = which_section(tt)
    t0 = s_t_start[idx]
    frac = s_height_frac[idx]
    u = min(max((tt - t0) / frac, 0.0), 1.0) if frac > 0 else 0.0
    r0, r1, rp = s_start_d[idx] / 2.0, s_end_d[idx] / 2.0, s_peak_d[idx] / 2.0
    return section_radius(u, r0, r1, rp, s_type[idx])


# The holder ring is a smooth local bump added straight onto the outer
# profile -- not a separate torus unioned in afterward. See the matching
# comment in the OpenSCAD generator: a separately-built torus, even
# carefully positioned to stay embedded in the wall, still produced a
# handful of non-manifold edges once unioned in Blender specifically (the
# least robust of the three booleans here) -- the vase's own faceted/
# jittered surface isn't a perfect circle, so a smooth torus overlaps it
# unevenly around the circumference. Building the bump directly into the
# same ring-stacked profile needs no boolean operation for this feature at
# all, so there's nothing left to be fragile.
ring_half_frac = min(max((holder_ring_d / 2) / vase_height, 0.01), 0.15) if holder_ring_d > 0 else 0.0


def ring_bump(t):
    if holder_ring_d <= 0:
        return 0.0
    dt = min(abs(t - holder_ring_height_frac) / ring_half_frac, 1.0)
    return (holder_ring_d / 2) * (1 - ease(dt))


def outer_radius_at(t):
    return base_outer_radius_at(t) + ring_bump(t)


def wall_offset(r):
    return max(r - wall_thickness, 0.3)


def texture_factor(angle_deg, t):
    if base_texture_amplitude <= 0:
        return 1.0
    raw = 1 + base_texture_amplitude * math.sin(math.radians(base_texture_frequency * angle_deg))
    fade_width = min(0.03, base_texture_height_frac / 2)
    if t <= base_texture_height_frac - fade_width:
        fade = 1.0
    elif t >= base_texture_height_frac:
        fade = 0.0
    else:
        fade = (base_texture_height_frac - t) / fade_width
    return 1 + (raw - 1) * fade


_rng = random.Random(random_seed)
facet_offsets = [_rng.uniform(1 - facet_jitter, 1 + facet_jitter) for _ in range(num_sides)]


def ring_points(r, angle_offset_deg, t):
    ao = math.radians(angle_offset_deg)
    pts = []
    for i in range(num_sides):
        a_deg = 360.0 * i / num_sides
        a = math.radians(a_deg)
        rr = r * facet_offsets[i] * texture_factor(a_deg, t)
        x, y = rr * math.cos(a), rr * math.sin(a)
        pts.append((x * math.cos(ao) - y * math.sin(ao), x * math.sin(ao) + y * math.cos(ao)))
    return pts"""


def _generate_freecad(p: dict) -> str:
    param_lines = _freecad_param_lines(p)
    body = f"""import math
import random

{_PROFILE_MATH_PY}


def ring_wire(r, angle_offset_deg, z, t):
    pts = [FreeCAD.Vector(x, y, z) for x, y in ring_points(r, angle_offset_deg, t)]
    pts.append(pts[0])
    return Part.makePolygon(pts)


def loft_profile(is_inner, extra_top=0.0):
    # ruled=True forces straight lines between corresponding points of
    # consecutive ring profiles (matching linear_extrude's own straight
    # interpolation in the OpenSCAD version) instead of FreeCAD's default
    # smoothed B-spline loft, which would round off the profile's own
    # control points instead of just its facets.
    wires = []
    for i in range(profile_slices + 1):
        t = i / profile_slices
        r = wall_offset(outer_radius_at(t)) if is_inner else outer_radius_at(t)
        z = t * vase_height
        twist = t * total_twist_deg
        wires.append(ring_wire(r, twist, z, t))
    if extra_top > 0:
        r_top = wall_offset(outer_radius_at(1.0)) if is_inner else outer_radius_at(1.0)
        wires.append(ring_wire(r_top, total_twist_deg, vase_height + extra_top, 1.0))
    return Part.makeLoft(wires, True, True, False)


outer = loft_profile(False)
inner_full = loft_profile(True, extra_top=eps)
max_outer_d = max(all_diameters)
crop_box = Part.makeBox(max_outer_d * 4, max_outer_d * 4, vase_height * 2, FreeCAD.Vector(-max_outer_d * 2, -max_outer_d * 2, base_thickness))
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


def build_shell(is_inner, name, extra_top=0.0):
    bm = bmesh.new()
    rings = []
    for i in range(profile_slices + 1):
        t = i / profile_slices
        r = wall_offset(outer_radius_at(t)) if is_inner else outer_radius_at(t)
        z = t * vase_height
        twist = t * total_twist_deg
        ring = [bm.verts.new((x, y, z)) for x, y in ring_points(r, twist, t)]
        rings.append(ring)
    if extra_top > 0:
        r_top = wall_offset(outer_radius_at(1.0)) if is_inner else outer_radius_at(1.0)
        top_ring = [bm.verts.new((x, y, vase_height + extra_top)) for x, y in ring_points(r_top, total_twist_deg, 1.0)]
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


outer = build_shell(False, "vase_outer")
inner = build_shell(True, "vase_inner", extra_top=eps)

# crop the inner shell's own mesh to only the part above base_thickness,
# via a boolean intersection with a crop box, before it ever touches the
# outer shell -- mirrors the OpenSCAD/FreeCAD versions' own crop step.
max_outer_d = max(all_diameters)
crop = bpy.data.objects.new("crop", bpy.data.meshes.new("crop_mesh"))
bpy.context.collection.objects.link(crop)
crop_bm = bmesh.new()
bmesh.ops.create_cube(crop_bm, size=1.0)
bmesh.ops.scale(crop_bm, vec=(max_outer_d * 4.0, max_outer_d * 4.0, vase_height), verts=crop_bm.verts)
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
        title="Parametric vase / planter",
        keywords=("vase", "planter", "pot", "flower vase", "low poly vase", "faceted vase", "twisted vase", "bulb vase", "hourglass vase"),
        params=[
            Param("d_base", 70, description="diameter at the base"),
            Param("vase_height", 150, description="overall height"),
            Param("s1_end_d", 55, description="section 1's ending diameter (bottom quarter)"),
            Param("s1_type", SECTION_TAPER, unit="", description="section 1 shape: 0=cylinder 1=cone 2=taper(eased) 3=bulge"),
            Param("s1_peak_d", 62, description="section 1's mid-section peak diameter, only used if s1_type=3"),
            Param("s1_height_frac", 0.25, unit="", description="section 1's share of the overall height"),
            Param("s2_end_d", 45, description="section 2's ending diameter (the waist, by default)"),
            Param("s2_type", SECTION_TAPER, unit="", description="section 2 shape: 0=cylinder 1=cone 2=taper(eased) 3=bulge"),
            Param("s2_peak_d", 50, description="section 2's mid-section peak diameter, only used if s2_type=3"),
            Param("s2_height_frac", 0.25, unit="", description="section 2's share of the overall height"),
            Param("s3_end_d", 65, description="section 3's ending diameter"),
            Param("s3_type", SECTION_TAPER, unit="", description="section 3 shape: 0=cylinder 1=cone 2=taper(eased) 3=bulge"),
            Param("s3_peak_d", 55, description="section 3's mid-section peak diameter, only used if s3_type=3"),
            Param("s3_height_frac", 0.25, unit="", description="section 3's share of the overall height"),
            Param("s4_end_d", 60, description="section 4's ending diameter -- the rim"),
            Param("s4_type", SECTION_TAPER, unit="", description="section 4 shape: 0=cylinder 1=cone 2=taper(eased) 3=bulge"),
            Param("s4_peak_d", 62, description="section 4's mid-section peak diameter, only used if s4_type=3"),
            Param("s4_height_frac", 0.25, unit="", description="section 4's share of the overall height"),
            Param("num_sides", 7, unit="", description="facet count around the circumference (try 5-10 for low-poly, 48+ for near-smooth)"),
            Param("facet_jitter", 0.12, unit="", description="0 = perfect regular polygon, up to ~0.4 for a chunky irregular low-poly look"),
            Param("random_seed", 1, unit="", description="change for a different random facet pattern at the same jitter"),
            Param("profile_slices", 24, unit="", description="height steps the profile curve is sampled at; higher = smoother, slower render"),
            Param("total_twist_deg", 120, unit="deg", description="spiral rotation from base to rim"),
            Param("wall_thickness", 2.4, description="shell wall thickness"),
            Param("base_thickness", 4, description="solid base thickness"),
            Param("drainage_hole_d", 0, description="drainage hole diameter in the base; 0 = no hole"),
            Param("holder_ring_d", 0, description="an optional raised ring/lip's own cross-section diameter (e.g. to seat a candle cup or bulb-holder fitting); 0 = disabled"),
            Param("holder_ring_height_frac", 0.95, unit="", description="where the holder ring sits, 0..1 up the vase"),
            Param("base_texture_amplitude", 0, unit="", description="an optional repeating wave texture near the base; 0 = disabled, try 0.05-0.15"),
            Param("base_texture_frequency", 8, unit="", description="repeating bumps around the circumference, if base_texture_amplitude > 0"),
            Param("base_texture_height_frac", 0.25, unit="", description="how far up the textured region reaches before fading out"),
        ],
        generate=_generate,
        generate_freecad=_generate_freecad,
        generate_blender=_generate_blender,
        description=(
            "A general parametric vase/planter: 4 independently-shaped profile sections (cylinder, "
            "cone, eased taper, or bulge/hourglass), an optional low-poly faceted look, spiral twist, "
            "an optional holder ring, and an optional textured base. Prints in any mode (not "
            "vase-mode-dependent) thanks to a real wall thickness and solid base."
        ),
    )
)
