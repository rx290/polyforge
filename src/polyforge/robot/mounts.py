"""Parametric, support-free mounts for real robot parts (build123d).

Every generator returns a build123d Part already in its PRINT pose: flat face on z = 0, nothing that needs
support (horizontal holes are teardrops, ledges are short, ceilings are short bridges). `export_checked()` writes
STL + STEP, runs printcheck.check_mesh on the STL and draws a contact sheet, so a bad part is caught, not shipped.

Parts take library keys (see robot/parts/*.json) or the normalised catalog.Board / catalog.Servo objects.

Generators
- standoff, board_tray (screw / heat-set insert / self-tap / snap clips), enclosure + enclosure_lid
- servo_cradle (holds a servo by its tabs, bottom joint pattern, optional hollow-axis wire channel)
- servo_u_bracket (wraps the servo between horn and an idler pivot; hollow pivot option for wires)
- hollow_pivot (printed flanged tube: the idler axle that wires pass through), horn_coupler, servo_l_joint
- nema_mount, byj_mount, gear_motor_mount (N20 tunnel, TT plate, JGA25 face, 130/180 saddle)
- battery_tray (strap slots + holder screw holes), module_mount (alias of board_tray)
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from . import catalog
from .catalog import SCREWS

CLEAR = 0.3          # printed clearance around bought parts
WALL = 2.4           # default wall for brackets
# bolt pattern shared by servo cradles, U-brackets, couplers and L-joints, per servo size class: (dx, dy, screw)
JOINT_PATTERN = {"micro": (20.0, 10.0, "M3"), "standard": (24.0, 16.0, "M3")}


def _b3d():
    import build123d as b
    return b


def size_class(s) -> str:
    return "micro" if s.L < 30 else "standard"


# ------------------------------------------------------------------ primitives

def _extrude_fused(sk, amount, both=False):
    """Extrude every face of a sketch and fuse the solids (sketch '+' can leave overlapping faces unfused)."""
    b = _b3d()
    out = None
    for f in sk.faces():
        e = b.extrude(f, amount=amount, both=both, dir=(0, 0, 1))   # XY sketches only; polygon winding varies
        out = e if out is None else out + e
    return out


def teardrop(d, length, axis="y"):
    """Horizontal hole with a 45 degree roof so it prints without support. Centred on the origin."""
    b = _b3d()
    r = d / 2.0; c = r * math.sqrt(0.5)
    sk = b.Circle(r) + b.Polygon((c, c), (0, r * math.sqrt(2)), (-c, c), (0, 0), align=None)
    solid = _extrude_fused(sk, length / 2.0, both=True)          # profile in XY, axis along Z
    solid = b.Rot(90, 0, 0) * solid                              # axis along Y, roof towards +Z
    if axis == "x":
        solid = b.Rot(0, 0, 90) * solid
    elif axis == "z":
        raise ValueError("vertical holes do not need a teardrop")
    return solid


def vhole(d, depth, x=0.0, y=0.0, z=0.0):
    """Vertical cylinder from z upwards (use as a cutter)."""
    b = _b3d()
    return b.Pos(x, y, z) * b.Cylinder(d / 2.0, depth, align=(b.Align.CENTER, b.Align.CENTER, b.Align.MIN))


def vslot(d, travel, depth, x=0.0, y=0.0, z=0.0):
    """Vertical slot (oblong hole) along x: holes that forgive the 1 to 2 mm spread between servo clones."""
    b = _b3d()
    if travel <= 0.01:
        return vhole(d, depth, x, y, z)
    return b.Pos(x, y, z) * b.extrude(b.SlotCenterToCenter(travel, d), amount=depth)


def box(lx, ly, lz, x=0.0, y=0.0, z=0.0, center_xy=True):
    b = _b3d()
    al = (b.Align.CENTER, b.Align.CENTER, b.Align.MIN) if center_xy else (b.Align.MIN, b.Align.MIN, b.Align.MIN)
    return b.Pos(x, y, z) * b.Box(lx, ly, lz, align=al)


def rounded_plate(lx, ly, t, r=3.0):
    b = _b3d()
    r = max(0.1, min(r, lx / 2 - 0.1, ly / 2 - 0.1))
    return b.extrude(b.RectangleRounded(lx, ly, r), amount=t)


def hexagon(across_flats, depth, x=0.0, y=0.0, z=0.0):
    b = _b3d()
    return b.Pos(x, y, z) * b.extrude(b.RegularPolygon(across_flats / math.sqrt(3), 6), amount=depth)


def screw_hole(screw, kind, depth, x, y, z=0.0):
    """kind: 'clear' (bolt passes), 'tap' (self-tapping into plastic), 'insert' (heat-set insert from the top,
    tap hole below), 'insert_low' (insert pressed in from the bottom face, for bolts that come from below)."""
    s = SCREWS[screw]
    if kind == "insert_low":
        d, ins = s["insert"]
        ins = min(ins, depth - 0.8)
        return vhole(d, ins, x, y, z) + vhole(s["tap"], depth, x, y, z)
    if kind == "insert":
        d, ins = s["insert"]
        cut = vhole(d, ins + 0.5, x, y, z + depth - ins)
        cut += vhole(s["tap"], depth, x, y, z)
        return cut
    return vhole(s[kind], depth, x, y, z)


def joint_holes(cls, depth, z=0.0, kind="clear", plane="xy"):
    """Cutters for the shared 4-bolt joint pattern centred on the origin."""
    b = _b3d()
    dx, dy, sc = JOINT_PATTERN[cls]
    cut = None
    for sx in (-1, 1):
        for sy in (-1, 1):
            h = screw_hole(sc, kind, depth, sx * dx / 2, sy * dy / 2, z)
            cut = h if cut is None else cut + h
    if plane == "xz":    # holes along y (vertical wall in the print pose), as teardrops
        cut = None
        for sx in (-1, 1):
            for sz in (-1, 1):
                h = b.Pos(sx * dx / 2, 0, sz * dy / 2) * teardrop(SCREWS[sc][kind], depth)
                cut = h if cut is None else cut + h
    return cut


def _as_board(b):
    return b if isinstance(b, catalog.Board) else catalog.board(b)


def _as_servo(s):
    return s if isinstance(s, catalog.Servo) else catalog.servo(s)


# ------------------------------------------------------------------ boards and modules

def standoff(screw="M2.5", height=6.0, kind="insert", base_d=None):
    """Single round standoff with a flared foot (flare is a 45 degree cone, so it prints upright)."""
    b = _b3d()
    s = SCREWS[screw]
    od = max(s["insert"][0] + 3.2, s["head"] + 1.0) if kind == "insert" else s["tap"] + 3.4
    base_d = base_d or od + 4
    body = b.Cylinder(od / 2, height, align=(b.Align.CENTER, b.Align.CENTER, b.Align.MIN))
    flare_h = (base_d - od) / 2
    body += b.Cone(base_d / 2, od / 2, flare_h, align=(b.Align.CENTER, b.Align.CENTER, b.Align.MIN))
    body -= screw_hole(screw, kind, height, 0, 0)
    return body


def board_tray(board, fix="insert", standoff_h=None, plate=2.4, margin=5.0, base_holes=True, overrides=None):
    """Flat tray with standoffs on the board's real hole pattern; snap clips when the board has no holes.

    fix: 'insert' (heat-set insert bosses), 'tap' (self-tapping), 'clear' (bolt + nut trap under the plate).
    Origin: tray centre; the board's lower-left corner sits at (-L/2, -W/2).
    """
    bd = board if isinstance(board, catalog.Board) else catalog.board(board, overrides)
    sh = standoff_h if standoff_h is not None else max(bd.bottom + 1.5, 4.0)
    L, W = bd.L + 2 * margin, bd.W + 2 * margin
    tray = rounded_plate(L, W, plate, r=3.0)
    ox, oy = -bd.L / 2, -bd.W / 2
    meta = {"part": bd.key, "standoff_h": sh, "fix": fix, "screws": {}}
    if bd.holes and bd.hole_d >= 1.5:
        sc = bd.screw if bd.screw in SCREWS else catalog.screw_for_hole(bd.hole_d)
        s = SCREWS[sc]
        od = (s["insert"][0] + 3.2) if fix == "insert" else (s["tap"] + 3.4 if fix == "tap" else s["clear"] + 3.0)
        for hx, hy in bd.holes:
            x, y = ox + hx, oy + hy
            tray += vhole(od, sh, x, y, plate)
            if fix == "clear":
                tray -= vhole(s["clear"], plate + sh, x, y, 0)
                tray -= hexagon(s["nut"] + 0.4, min(2.4, plate + sh - 1.2), x, y, 0)
            else:
                tray -= screw_hole(sc, fix, plate + sh, x, y, 0)
        meta["screws"][sc] = len(bd.holes)
        meta["mode"] = "standoffs"
    else:
        # no holes: rest pads at the corners and snap clips on the long edges
        for cx in (ox + 3, ox + bd.L - 3):
            for cy in (oy + 3, oy + bd.W - 3):
                tray += box(5, 5, sh, cx, cy, plate)
        n = 2 if bd.L > 40 else 1
        xs = [ox + bd.L * (i + 1) / (n + 1) for i in range(n)]
        for x in xs:
            for side in (-1, 1):
                tray += snap_clip(sh + bd.T, side, x, side * (bd.W / 2 + CLEAR), plate)
        meta["mode"] = "snap clips"
    # cable slot and tray-to-robot holes
    if not bd.holes:
        tray -= box(12, 4, plate, 0, 0, 0)
    if base_holes:
        for sx in (-1, 1):
            tray -= vhole(SCREWS["M3"]["clear"], plate, sx * (L / 2 - 3.0), 0, 0)
        meta["screws"]["M3 (tray to robot)"] = 2
    return tray, meta


def snap_clip(height, side, x, y_inner, z0, width=6.0, beam=1.6, lip=1.0):
    """Cantilever snap clip standing on z0. side=+1 puts the beam at +y with the hook pointing to -y.

    The hook has a 45 degree lead-in on top and a 1 mm flat ledge underneath (short ledge, prints fine).
    """
    b = _b3d()
    yb = y_inner + side * beam / 2
    clip = box(width, beam, height + lip + 1.2, x, yb, z0)
    # hook: triangle prism profile in the y-z plane (flat underside at board top, 45 degree slope above)
    prof = b.Plane.YZ * b.Polygon((0, 0), (-side * lip, 0), (0, lip * 1.4), align=None)   # (y, z) profile
    hook = b.extrude(prof, amount=width / 2, both=True)                                     # width along x
    clip += b.Pos(x, y_inner, z0 + height + 0.2) * hook
    return clip


def module_mount(key, **kw):
    return board_tray(key, **kw)


def _keepout_cut(ko, ox, oy, zt, inner, wall, pad=1.0):
    """Cutter through the enclosure wall for one connector keepout (board frame -> enclosure frame)."""
    x0, y0, z0, x1, y1, z1 = (float(v) for v in ko["box"])
    face = ko.get("face", "top")
    X0, X1, Y0, Y1 = ox + x0 - pad, ox + x1 + pad, oy + y0 - pad, oy + y1 + pad
    Z0, Z1 = zt + z0 - pad, zt + z1 + pad
    ix, iy = inner
    big = wall + 4
    if face == "-x":
        return box(big, Y1 - Y0, Z1 - Z0, -ix / 2 - big / 2 + 1, (Y0 + Y1) / 2, Z0)
    if face == "+x":
        return box(big, Y1 - Y0, Z1 - Z0, ix / 2 + big / 2 - 1, (Y0 + Y1) / 2, Z0)
    if face == "-y":
        return box(X1 - X0, big, Z1 - Z0, (X0 + X1) / 2, -iy / 2 - big / 2 + 1, Z0)
    if face == "+y":
        return box(X1 - X0, big, Z1 - Z0, (X0 + X1) / 2, iy / 2 + big / 2 - 1, Z0)
    return None


def enclosure(board, wall=2.0, floor=2.0, clear=1.0, fix="insert", standoff_h=None, headroom=3.0, overrides=None):
    """Open-top box with standoffs and a hole in the wall for every side connector keepout.

    Returns (base, lid, meta). The lid prints upside down (plate on the bed, lip up) and gets a slot over every
    keepout reached from the top (GPIO header, camera cable) plus vent slots.
    """
    bd = board if isinstance(board, catalog.Board) else catalog.board(board, overrides)
    sh = standoff_h if standoff_h is not None else max(bd.bottom + 1.5, 4.0)
    ix, iy = bd.L + 2 * clear, bd.W + 2 * clear
    zt = floor + sh + bd.T                       # PCB top face height in the enclosure
    iz = sh + bd.T + bd.top + headroom
    X, Y = ix + 2 * wall, iy + 2 * wall
    base = rounded_plate(X, Y, floor + iz, r=wall + 1) - box(ix, iy, iz + 1, 0, 0, floor)
    ox, oy = -bd.L / 2, -bd.W / 2
    tray_meta = {"screws": {}}
    if bd.holes and bd.hole_d >= 1.5:
        sc = bd.screw if bd.screw in SCREWS else catalog.screw_for_hole(bd.hole_d)
        s = SCREWS[sc]
        od = (s["insert"][0] + 3.2) if fix == "insert" else s["tap"] + 3.4
        for hx, hy in bd.holes:
            base += vhole(od, sh, ox + hx, oy + hy, floor)
            base -= screw_hole(sc, fix, sh + floor - 0.6, ox + hx, oy + hy, 0.6)
        tray_meta["screws"][sc] = len(bd.holes)
    else:
        for cx in (ox + 3, ox + bd.L - 3):
            for cy in (oy + 3, oy + bd.W - 3):
                base += box(5, 5, sh, cx, cy, floor)
        tray_meta["note"] = "no mounting holes: board rests on pads and is held by the lid"
    cuts = []
    top_kos = []
    for ko in bd.keepouts:
        c = _keepout_cut(ko, ox, oy, zt, (ix, iy), wall)
        if c is not None:
            base -= c; cuts.append(ko["name"])
        elif ko.get("face") == "top":
            top_kos.append(ko)
    # lid: plate + locating lip, vents, slots for top connectors
    lip_t = 1.6
    lid = rounded_plate(X, Y, 2.0, r=wall + 1)
    lid += box(ix - 2 * 0.25, iy - 2 * 0.25, 4.0, 0, 0, 2.0) - box(ix - 2 * 0.25 - 2 * lip_t, iy - 2 * 0.25 - 2 * lip_t, 4.0, 0, 0, 2.0)
    for ko in top_kos:
        x0, y0, _, x1, y1, _ = (float(v) for v in ko["box"])
        # lid is printed flipped about x: board y maps to -y
        lid -= box(x1 - x0 + 2, y1 - y0 + 2, 6.0, ox + (x0 + x1) / 2, -(oy + (y0 + y1) / 2), 0)
    nvent = max(2, int(ix // 12))
    for i in range(nvent):
        vx = -ix / 2 + ix * (i + 0.5) / nvent
        vent = box(2.0, iy * 0.35, 2.0, vx, 0, 0)
        if all(abs(vx - (ox + (float(k["box"][0]) + float(k["box"][3])) / 2)) > (float(k["box"][3]) - float(k["box"][0])) / 2 + 3 for k in top_kos):
            lid -= vent
    meta = {"part": bd.key, "outer_mm": [round(X, 1), round(Y, 1), round(floor + iz + 2, 1)], "wall_cutouts": cuts,
            "lid_slots": [k["name"] for k in top_kos], **tray_meta}
    return base, lid, meta


# ------------------------------------------------------------------ servos

def _horn_pocket(s, depth, kind=None, arm_angle=0.0):
    """2D-extruded horn-shaped pocket (in XY, from z=0 up). kind: disc | arm | cross. Centred on the shaft."""
    b = _b3d()
    cls = size_class(s)
    kind = kind or ("cross" if cls == "micro" else "disc")
    hub = s.spline_od + 2.6
    if kind == "disc":
        d = 20.6 if cls == "standard" else 14.6
        return b.extrude(b.Circle(d / 2 + CLEAR), amount=depth)
    arm_len, tip = (15.5, 4.0) if cls == "micro" else (22.0, 6.0)
    def arm(angle):
        sk = b.Circle(hub / 2 + CLEAR) + b.Pos(arm_len, 0) * b.Circle(tip / 2 + CLEAR)
        hr, tr = (hub / 2 + CLEAR) * 0.97, (tip / 2 + CLEAR) * 0.97     # just inside the circles: clean union
        sk += b.Polygon((0, hr), (arm_len, tr), (arm_len, -tr), (0, -hr), align=None)
        return b.Rot(0, 0, angle) * sk
    sk = arm(arm_angle) if kind == "arm" else arm(0) + arm(90) + arm(180) + arm(270)
    return _extrude_fused(sk, depth)


def _horn_screw_holes(s, depth, kind=None, arm_angle=0.0):
    """Small pilot holes where the horn's own holes are (screws go from the horn into the printed part)."""
    cls = size_class(s)
    kind = kind or ("cross" if cls == "micro" else "disc")
    if kind == "disc":
        r = 7.0 if cls == "standard" else 5.0
        angles = (45, 135, 225, 315)
    else:
        r = 9.0 if cls == "micro" else 12.0
        angles = (0, 90, 180, 270) if kind == "cross" else (arm_angle,)
    cut = None
    for a in angles:
        h = vhole(1.5 if cls == "micro" else 2.0, depth, r * math.cos(math.radians(a)), r * math.sin(math.radians(a)), 0)
        cut = h if cut is None else cut + h
    return cut


def servo_cradle(servo, floor=3.0, wall=2.4, hollow_axis=False, channel_d=None, wire_slot=True):
    """Holds a servo by its tabs. Print pose: floor on the bed, servo drops in from the top.

    Frame: the servo body's lower-left-bottom corner is at (-L/2, -W/2, floor), shaft at x = shaft_x - L/2.
    The floor carries the shared joint pattern (heat-set inserts) and a tapped idler hole on the shaft axis.
    hollow_axis: thicker floor with a wire groove from the cradle end to a bore on the shaft axis; press the
    hollow_pivot tube into that bore and the wires leave through the joint axis instead of a loop outside.
    """
    s = _as_servo(servo)
    cls = size_class(s)
    ch = channel_d or (5.0 if cls == "micro" else 7.0)
    if hollow_axis:
        floor = max(floor, ch + 2.4)
    ox, oy = -s.L / 2, -s.W / 2
    tab_lo = s.L / 2 - s.tab_span / 2
    outer_x = s.tab_span + 2.0
    outer_y = s.W + 2 * CLEAR + 2 * wall
    H = floor + s.tab_z
    body = box(outer_x, outer_y, H)
    body -= box(s.L + 2 * CLEAR, s.W + 2 * CLEAR, s.tab_z + 1, 0, 0, floor)
    for hx, hy in s.holes:     # tab screws (self-tap into the end blocks), slotted: clones differ by 1 to 2 mm
        body -= vslot(max(s.hole_d * 0.8, 1.6), 0.0 if s.verified else 2.0, 10.0, ox + hx, oy + hy, H - 10.0)
    sx = ox + s.shaft_x
    body -= joint_holes(cls, floor, 0, kind="insert_low") if not hollow_axis else joint_holes(cls, floor, 0, kind="clear")
    if wire_slot:      # cable exit at the end opposite the shaft, open from the top
        far = ox + s.L if s.shaft_x < s.L / 2 else ox
        body -= box(wall + 3, 6.0 if cls == "micro" else 8.0, s.tab_z + 1, far + math.copysign(wall / 2 + 1, far), 0, floor + 2.0)
    meta = {"servo": s.key, "floor": floor, "shaft_xy": [round(sx, 2), round(oy + s.shaft_y, 2)], "height": H,
            "screws": {"self-tap tab screws": len(s.holes), "M3 x 4 heat-set inserts": 4}}
    if hollow_axis:
        bore = ch + 3.2                       # hollow_pivot tube outer diameter press fit
        body -= vhole(bore, floor, sx, oy + s.shaft_y, 0)
        # groove under the floor from the axis to the cradle end (open to the bed, ceiling is a short bridge)
        gx0 = sx; gx1 = ox - 2 * wall - 2 if s.shaft_x < s.L / 2 else ox + s.L + 2 * wall + 2
        body -= box(abs(gx1 - gx0), ch, ch, (gx0 + gx1) / 2, oy + s.shaft_y, 0)
        meta["hollow_axis"] = {"bore_d": bore, "channel_d": ch}
        meta["screws"].pop("M3 x 4 heat-set inserts"); meta["screws"]["M3 bolts through floor"] = 4
    else:
        body -= screw_hole("M3", "insert_low", floor, sx, oy + s.shaft_y, 0)
        meta["idler"] = "M3 heat-set insert on the shaft axis under the servo (shoulder screw or M3 bolt as axle)"
    return body, meta


def hollow_pivot(servo, length=None, channel_d=None):
    """Printed flanged tube: press it into the cradle floor bore; the U-bracket idler arm turns on it and the
    wires pass through its bore. Print pose: flange down."""
    s = _as_servo(servo)
    cls = size_class(s)
    ch = channel_d or (5.0 if cls == "micro" else 7.0)
    od = ch + 3.2
    length = length or (ch + 2.4) + 3.0 + 1.0
    b = _b3d()
    tube = b.Cylinder(od / 2 + 2.5, 1.6, align=(b.Align.CENTER, b.Align.CENTER, b.Align.MIN))
    tube += vhole(od, length, 0, 0, 0)
    tube -= vhole(ch, length + 2, 0, 0, -1)
    # retaining groove for a printed clip ring
    tube -= vhole(od + 2, 0.8, 0, 0, length - 1.6) - vhole(od - 0.8, 0.8, 0, 0, length - 1.6)
    return tube, {"od": od, "bore": ch, "length": length}


def servo_u_bracket(servo, wall=None, hollow_axis=False, horn=None, clearance=0.6):
    """U-bracket: one arm bolts to the horn, the other turns on the idler axis under the cradle.

    Print pose: the base (with the joint pattern) is on the bed, both arms stand up; horn pocket and idler hole
    are horizontal and printed as teardrop / short-ledge features.
    Geometry follows servo_cradle(): the gap between the arms holds cradle floor + servo + horn.
    """
    b = _b3d()
    s = _as_servo(servo)
    cls = size_class(s)
    t = wall or (3.0 if cls == "micro" else 4.0)
    floor = 3.0 if not hollow_axis else max(3.0, (5.0 if cls == "micro" else 7.0) + 2.4)
    horn_t = 2.0 if cls == "micro" else 2.5
    gap = floor + s.shaft_top + horn_t + clearance + 0.5             # cradle bottom to horn face
    # reach: distance from the shaft axis to the base, clears the cradle end + tab blocks while rotating
    far_end = max(s.shaft_x, s.L - s.shaft_x) + (s.tab_span - s.L) / 2 + 1.0
    near_end = min(s.shaft_x, s.L - s.shaft_x) + (s.tab_span - s.L) / 2 + 1.0
    half_w = (s.W + 2 * CLEAR + 4.8) / 2
    R = math.hypot(near_end, half_w) + 2.0
    width = s.W + 2 * CLEAR + 4.8 + 2.0
    arm_len = R + (s.spline_od / 2 + 12.0)
    # print pose: base plate on the bed (x along arm length = up), arms are vertical walls at y = +/-(gap/2 + t/2)
    base = box(width, gap + 2 * t, t)        # x = bracket width, y = across the arms
    arms = None
    for side in (-1, 1):
        a = box(width, t, arm_len, 0, side * (gap / 2 + t / 2), 0)
        arms = a if arms is None else arms + a
    u = base + arms
    # round the arm tips around the axis (axis is horizontal along y at z = R)
    horn = horn or ("arm" if cls == "micro" else "disc")
    tip_r = width / 2
    # single-arm horns point away from the base, so the arm plates run on past the axis to hold the whole horn
    ext = (15.5 + 2.0 + 2.5 if cls == "micro" else 22.0 + 3.0 + 3.0) if horn == "arm" else tip_r
    top_c = R + max(ext - tip_r, 0.0)
    tip = b.Pos(0, 0, top_c) * b.Rot(90, 0, 0) * b.Cylinder(tip_r, gap + 2 * t + 2)
    keep = box(width + 2, gap + 2 * t + 2, top_c) + tip
    arms = None
    for side in (-1, 1):
        a = box(width, t, top_c + tip_r, 0, side * (gap / 2 + t / 2), 0)
        arms = a if arms is None else arms + a
    u = (base + arms) & keep
    # horn arm (+y): horn-shaped pocket on the inner face, centre hole for the horn screw/driver
    pocket = _horn_pocket(s, 1.6, horn, arm_angle=90.0)
    pocket = b.Rot(90, 0, 0) * pocket                       # pocket now extends along -y
    u -= b.Pos(0, gap / 2 + 1.6, R) * pocket
    u -= b.Pos(0, gap / 2 + t / 2, R) * teardrop(SCREWS[s.horn_screw]["head"] + 1.0, t + 2)
    hs = _horn_screw_holes(s, t + 2, horn, arm_angle=-90.0)
    u -= b.Pos(0, gap / 2 - 1, R) * b.Rot(-90, 0, 0) * hs
    # idler arm (-y): bearing hole on the axis
    if hollow_axis:
        od = (5.0 if cls == "micro" else 7.0) + 3.2
        u -= b.Pos(0, -(gap / 2 + t / 2), R) * teardrop(od + 0.4, t + 2)
        # wire groove on the outer face of the idler arm, down to the base, then out under the base
        ch = 5.0 if cls == "micro" else 7.0
        u -= box(ch, ch / 2 + 0.5, R, 0, -(gap / 2 + t) + (ch / 2 + 0.5) / 2 - 0.01, 0)
    else:
        u -= b.Pos(0, -(gap / 2 + t / 2), R) * teardrop(SCREWS["M3"]["clear"], t + 2)
    # base joint pattern (rotated so the long spacing runs across the arms)
    u -= b.Rot(0, 0, 90) * joint_holes(cls, t, 0, kind="clear") if gap + 2 * t > JOINT_PATTERN[cls][0] + 7 \
        else joint_holes(cls, t, 0, kind="clear")
    meta = {"servo": s.key, "gap": round(gap, 2), "axis_height": round(R, 2), "arm_t": t, "width": round(width, 1),
            "rotation_clear_radius": round(R, 2), "screws": {"M3 x 10 (joint)": 4, "horn screws": 4,
                                                            "M3 shoulder screw or bolt (idler)": 0 if hollow_axis else 1}}
    return u, meta


def horn_coupler(servo, thickness=4.0, horn=None, length=None):
    """Flat plate with a horn pocket on one end and the joint pattern on the other: bolt any printed limb to a
    servo horn. Print pose: flat, pocket facing up."""
    s = _as_servo(servo)
    cls = size_class(s)
    dx, dy, _ = JOINT_PATTERN[cls]
    pocket_r = (20.6 / 2 if cls == "standard" else 7.0 / 2) + 3
    length = length or pocket_r + dx + 10 + (15.5 if cls == "micro" else 0)
    width = max(dy + 9, s.spline_od + 14, 2 * pocket_r if horn == "disc" else 0)
    plate = rounded_plate(length + pocket_r, width, thickness, r=width / 2 - 0.2)
    b = _b3d()
    hx = -(length + pocket_r) / 2 + pocket_r
    horn = horn or ("arm" if cls == "micro" else "disc")     # micro single arm points along the coupler
    plate -= b.Pos(hx, 0, thickness - 1.6) * _horn_pocket(s, 1.7, horn)
    plate -= vhole(SCREWS[s.horn_screw]["head"] + 1.0, thickness, hx, 0, 0)
    plate -= b.Pos(hx, 0, 0) * _horn_screw_holes(s, thickness, horn)
    jx = hx + max(pocket_r, 15.5 + 3.0 if horn == "arm" else 0) + dx / 2 + 4
    plate -= b.Pos(jx, 0, 0) * joint_holes(cls, thickness, 0, kind="insert_low")    # bolts come from the back
    return plate, {"servo": s.key, "length": round(length + pocket_r, 1)}


def servo_l_joint(servo, thickness=4.0):
    """90 degree L plate with the joint pattern on both legs (servo-to-servo cross joints, pan-tilt).
    The long pattern spacing runs across the legs (y) on both legs. Print pose: one leg on the bed, the other
    standing up with teardrop holes; a 45 degree gusset joins them."""
    b = _b3d()
    s = _as_servo(servo)
    cls = size_class(s)
    dx, dy, _ = JOINT_PATTERN[cls]
    leg = dy + 14.0
    width = dx + 10.0
    plate = box(leg, width, thickness, leg / 2 - thickness, 0, 0)
    wall = box(thickness, width, leg, -thickness / 2, 0, 0)
    gusset = b.extrude(b.Polygon((0, 0), (6, 0), (0, 6), align=None), amount=width / 2 - 1, both=True)
    gusset = b.Pos(0, 0, thickness) * b.Rot(90, 0, 0) * gusset
    lj = plate + wall + gusset
    lj -= b.Pos(leg / 2 - thickness + 2, 0, 0) * b.Rot(0, 0, 90) * joint_holes(cls, thickness, 0, kind="clear")
    lj -= _wall_joint(cls, thickness, leg)
    return lj, {"servo": s.key, "leg": leg, "width": width}


def _wall_joint(cls, thickness, leg):
    b = _b3d()
    dx, dy, sc = JOINT_PATTERN[cls]
    cut = None
    for sy in (-1, 1):
        for sz in (-1, 1):
            h = b.Pos(-thickness / 2, sy * dx / 2, leg / 2 + 2 + sz * dy / 2) * teardrop(SCREWS[sc]["clear"], thickness + 2, axis="x")
            cut = h if cut is None else cut + h
    return cut


# ------------------------------------------------------------------ motors

def nema_mount(key="nema17", thickness=5.0, overrides=None):
    """L bracket: base on the bed with two slotted M4 holes, vertical face with the pilot and 4 motor holes,
    45 degree gussets at both sides."""
    b = _b3d()
    p = catalog.get(key)
    m = p.get("mech") or {}
    face = float(m.get("face") or p["dims"]["length"])
    spacing = float(m.get("hole_spacing") or (31.0 if face > 40 else 26.0))
    pilot = float(m.get("pilot_d") or 22.0) + 0.6
    w = face + 2 * thickness + 8
    h = face + thickness
    depth = 30.0
    base = box(w, depth, thickness, 0, depth / 2, 0)
    wall = box(w, thickness, h, 0, thickness / 2, 0)
    g = b.extrude(b.Plane.YZ * b.Polygon((0, 0), (depth - thickness, 0), (0, depth - thickness), align=None),
                  amount=thickness / 2, both=True)             # 45 degree triangle in the y-z plane
    br = base + wall
    for sx in (-1, 1):
        br += b.Pos(sx * (w / 2 - thickness / 2), thickness, thickness) * g
    cz = thickness + face / 2
    br -= b.Pos(0, thickness / 2, cz) * teardrop(pilot, thickness + 2)
    for dx in (-spacing / 2, spacing / 2):
        for dz in (-spacing / 2, spacing / 2):
            br -= b.Pos(dx, thickness / 2, cz + dz) * teardrop(SCREWS["M3"]["clear"], thickness + 2)
    for sx in (-1, 1):
        br -= b.Pos(sx * (face / 2 - 6), depth * 0.6, 0) * b.extrude(b.SlotCenterToCenter(8, SCREWS["M4"]["clear"]).rotate(b.Axis.Z, 90), amount=thickness)
    return br, {"motor": p["key"], "face": face, "hole_spacing": spacing, "screws": {"M3 x 8 (motor)": 4, "M4 (base)": 2}}


def byj_mount(key="28byj_48", thickness=4.0):
    """Flat plate for the 28BYJ-48: ears on the real 35 mm spacing, clearance for the offset shaft boss."""
    p = catalog.get(key)
    m = p.get("mech") or {}
    body_d = float(m.get("body_d") or 28.0)
    ear = float(m.get("ear_hole_spacing") or 35.0)
    off = float(m.get("shaft_offset") or 8.0)
    boss = float(m.get("boss_d") or 9.0) + 1.0
    plate = rounded_plate(ear + 12, body_d + 8, thickness, r=5)
    for sx in (-1, 1):
        plate -= vhole(SCREWS["M3"]["clear"] + 0.8, thickness, sx * ear / 2, 0, 0)
    plate -= vhole(boss, thickness, 0, off, 0)
    for sx in (-1, 1):
        plate -= vhole(SCREWS["M3"]["clear"], thickness, sx * (ear / 2 - 8), -(body_d / 2 - 1), 0)
    return plate, {"motor": p["key"], "ear_spacing": ear, "shaft_offset": off}


def gear_motor_mount(key, thickness=3.0):
    """Mount for the common small DC gear motors. Picks a style by motor family:
    n20: tunnel clamp the gearbox slides into; tt: upright plate on the two through holes;
    jga25: face plate on the gearbox screw holes; 130/180 cans: open saddle with zip-tie slots."""
    b = _b3d()
    p = catalog.get(key)
    m, d = p.get("mech") or {}, p["dims"]
    k = p["key"]
    if "n20" in k:
        gw, gh = float(d.get("width") or 12.0), float(d.get("height_top") or 10.0)
        L = 12.0
        blk = box(gw + 2 * thickness + 10, L, gh + thickness + 0.4, 0, 0, 0)
        blk -= box(gw + 0.4, L + 2, gh + 0.4, 0, 0, 0)
        for sx in (-1, 1):
            blk -= vhole(SCREWS["M2"]["clear"], gh + thickness, sx * (gw / 2 + thickness + 2.5), 0, 0)
        return blk, {"motor": k, "style": "tunnel clamp"}
    if "tt" in k:
        # TT gearbox: two M3 bolts pass through the gearbox parallel to the shaft, a 4 mm nub locates it.
        # Plate sits against the nub side, below the shaft; face_holes are [x, z] from the shaft axis.
        fh = [tuple(map(float, h)) for h in (m.get("face_holes") or [[-8.8, -20.6], [8.8, -20.6]])]
        low = [h for h in fh if h[1] < 0] or fh
        nub = (m.get("nub") or {}).get("pos", [0.0, -11.2])
        zmin = min(z for _, z in low) - 6.0
        ztop = float(nub[1]) + 4.5
        w = max(x for x, _ in low) - min(x for x, _ in low) + 14
        h = ztop - zmin
        plate = box(w, thickness, h, 0, 0, 0) + box(w, 16.0, thickness, 0, 8.0 - thickness / 2, 0)
        for x, z in low:
            plate -= b.Pos(x, 0, z - zmin) * teardrop(SCREWS["M3"]["clear"], thickness + 2)
        plate -= b.Pos(float(nub[0]), 0, float(nub[1]) - zmin) * teardrop(4.4, thickness + 2)
        for sx in (-1, 1):
            plate -= vhole(SCREWS["M3"]["clear"], thickness, sx * (w / 2 - 3.5), 10, 0)
        return plate, {"motor": k, "style": "upright plate", "shaft_above_base": round(-zmin, 1),
                       "screws": {"M3 x 30 through the gearbox": len(low), "M3 (base)": 2}}
    if "jga25" in k:
        fh = [tuple(map(float, h)) for h in (m.get("face_holes") or [[-8.5, 0], [8.5, 0]])]
        dia = float(m.get("can_d") or 25.0)
        boss = 8.0
        w, h = dia + 12, dia / 2 + thickness + 14
        plate = box(w, thickness, h + dia / 2) + box(w, 20, thickness, 0, 10 - thickness / 2, 0)
        cz = h
        plate -= b.Pos(0, 0, cz) * teardrop(boss, thickness + 2)
        for x, y in fh:
            plate -= b.Pos(x, 0, cz + y) * teardrop(SCREWS["M3"]["clear"], thickness + 2)
        for sx in (-1, 1):
            plate -= vhole(SCREWS["M3"]["clear"], thickness, sx * (w / 2 - 4), 12, 0)
        return plate, {"motor": k, "style": "face plate"}
    # round cans (130 / 180) and anything else: open saddle
    dia = float(m.get("can_d") or d.get("width") or 20.0)
    L = 18.0
    sad = box(dia + 2 * thickness + 10, L, dia / 2 + thickness)
    sad -= b.Pos(0, 0, dia / 2 + thickness) * b.Rot(90, 0, 0) * b.Cylinder(dia / 2 + CLEAR, L + 2)
    for sx in (-1, 1):
        sad -= box(2.5, 5.0, dia, sx * (dia / 2 + thickness / 2 + 1.5), 0, 0)      # zip-tie slots
        sad -= vhole(SCREWS["M3"]["clear"], 2 * thickness, sx * (dia / 2 + thickness + 3.5), 0, 0)
    return sad, {"motor": k, "style": "saddle + zip ties"}


# ------------------------------------------------------------------ power

def battery_tray(key, floor=2.4, wall=2.0, strap_w=20.0):
    """Tray with low walls, two strap slots for a hook-and-loop strap, and the holder's own screw holes."""
    p = catalog.get(key)
    d, h = p["dims"], p.get("holes") or {}
    L, W, H = float(d["length"]), float(d["width"]), float(d.get("height_top") or d.get("thickness") or 15.0)
    ix, iy = L + 2 * CLEAR, W + 2 * CLEAR
    wall_h = min(H * 0.5, 10.0)
    t = rounded_plate(ix + 2 * wall + 2 * 6, iy + 2 * wall, floor, r=3)
    t += box(ix + 2 * wall, iy + 2 * wall, floor + wall_h) - box(ix, iy, wall_h + 1, 0, 0, floor)
    for sx in (-1, 1):
        t -= box(3.0, min(strap_w + 1, iy - 4), floor, sx * (ix / 4), 0, 0)
        t -= vhole(SCREWS["M3"]["clear"], floor, sx * (ix / 2 + wall + 3), 0, 0)
    # wire exit notch at one end
    t -= box(wall + 2, 8, wall_h + 1, ix / 2 + wall / 2, 0, floor + 2)
    for hx, hy in h.get("positions") or []:
        t -= vhole(SCREWS["M3"]["clear"], floor, -L / 2 + float(hx), -W / 2 + float(hy), 0)
    return t, {"battery": p["key"], "inner": [round(ix, 1), round(iy, 1)], "strap": f"{strap_w:.0f} mm hook-and-loop"}


# ------------------------------------------------------------------ export + check

def export_checked(parts: dict, out_dir, sheet_title=None, tolerance=0.02):
    """parts: {name: Part or (Part, meta)}. Writes STL/STEP, runs check_mesh, contact sheet + checks.json."""
    import trimesh

    from build123d import export_step, export_stl

    from .printcheck import check_mesh, contact_sheet, render_views

    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    results, sheet = {}, []
    for name, val in parts.items():
        shape, meta = (val if isinstance(val, tuple) else (val, {}))
        bb = shape.bounding_box()
        from build123d import Pos
        shape = Pos(0, 0, -bb.min.Z) * shape                     # lowest point on the bed
        stl = out / f"{name}.stl"
        export_stl(shape, str(stl), tolerance=tolerance, angular_tolerance=0.2)
        export_step(shape, str(out / f"{name}.step"))
        mesh = trimesh.load(stl, force="mesh")
        chk = check_mesh(mesh)
        results[name] = {"check": chk, "meta": meta, "stl": str(stl)}
        render_views(mesh, size=260, color=(90, 150, 220) if chk["ok"] else (220, 110, 90)).save(out / f"{name}.png")
        sheet.append((name, mesh, chk["ok"]))
    contact_sheet(sheet, out / "contact_sheet.png", title=sheet_title)
    (out / "checks.json").write_text(json.dumps(results, indent=1, default=str))
    return results
