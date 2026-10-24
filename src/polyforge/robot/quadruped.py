"""12-servo quadruped (SpotMicro-like layout, original design), sized around real parts from the library.

Layout per leg: the hip (roll) servo sits in the body end wall with its shaft pointing forward/back; a horn coupler
on the hip horn carries an L joint, the L joint carries the shoulder (pitch) servo cradle; the femur hangs from the
shoulder horn and carries the knee servo cradle on its inner face; the tibia hangs from the knee horn. All printed
parts come from robot/mounts.py (cradle, coupler, L joint) plus the femur, tibia, body and lid made here.

Everything is built twice: once in its print pose (exported, print-checked) and once placed in the assembly
(rendered, and checked for collisions between printed parts and the bought parts).

Spec keys (all optional):
  servo: "mg996r" | "sg90" | any servo key        controller: "rpi_zero_2w" | "esp32_devkitc_v4" | any board key
  driver: "pca9685"   regulator: "lm2596_module"   imu: "mpu6050"   battery: "lipo_2s_2200" | any battery key
  femur, tibia: lengths in mm (default from servo size)   stance: [shoulder_deg, knee_deg]
  shell: true for a chamfered character shell on the lid    switch: "switch_kcd1_rocker"
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from . import catalog, mounts as M, wiring as W
from .catalog import SCREWS
from .mounts import CLEAR, JOINT_PATTERN, box, size_class, teardrop, vhole


def _b3d():
    import build123d as b
    return b


def frame(X, Z, origin):
    """Location that maps local x/z axes to world directions X/Z and the local origin to `origin`."""
    import build123d as b
    from OCP.gp import gp_Ax3, gp_Dir, gp_Pnt, gp_Trsf
    t = gp_Trsf()
    t.SetTransformation(gp_Ax3(gp_Pnt(*origin), gp_Dir(*Z), gp_Dir(*X)), gp_Ax3())
    return b.Location(t)


def servo_dummy(s):
    """Bought servo as a solid in its own frame (body, tabs, spline) for renders and collision checks."""
    b = _b3d()
    body = box(s.L, s.W, s.H, center_xy=False)
    tab0 = (s.L - s.tab_span) / 2
    body += b.Pos(tab0, 0, s.tab_z) * b.Box(s.tab_span, s.W, s.tab_t, align=(b.Align.MIN,) * 3)
    body += b.Pos(s.shaft_x, s.shaft_y, s.H) * b.Cylinder(s.spline_od / 2, s.shaft_top - s.H, align=(b.Align.CENTER, b.Align.CENTER, b.Align.MIN))
    return body


def limb(s, length, thickness, width, joint_x=None, channel=None, foot=False):
    """Femur or tibia in its print pose: flat beam, horn pocket on top at x = 0, joint pattern (clear holes) at
    joint_x for the next cradle, optional closed cable tunnel with exits on the top face, optional foot end."""
    b = _b3d()
    cls = size_class(s)
    horn = "arm" if cls == "micro" else "disc"
    end_r = width / 2 + (3.0 if foot else 0.0)
    sk = b.Circle(width / 2) + b.Pos(length, 0) * b.Circle(end_r) + \
        b.Polygon((0, width / 2 * 0.98), (length, end_r * 0.98), (length, -end_r * 0.98), (0, -width / 2 * 0.98), align=None)
    beam = M._extrude_fused(sk, thickness)
    beam -= b.Pos(0, 0, thickness - 1.6) * M._horn_pocket(s, 1.7, horn, arm_angle=0.0)
    beam -= vhole(SCREWS[s.horn_screw]["head"] + 1.0, thickness, 0, 0, 0)
    beam -= M._horn_screw_holes(s, thickness, horn, arm_angle=0.0)
    if joint_x is not None:
        beam -= b.Pos(joint_x, 0, 0) * M.joint_holes(cls, thickness, 0, kind="clear")
    meta = {"length": length, "thickness": thickness, "width": round(width, 1)}
    if channel:
        cw, ch = channel
        x0 = (15.5 + 6 if horn == "arm" else 14.0)
        x1 = (joint_x - JOINT_PATTERN[cls][0] / 2 - 5) if joint_x else length - 8
        if x1 - x0 > 10:
            zc = 1.2 + ch / 2
            beam -= b.Pos((x0 + x1) / 2, 0, zc) * W.channel_cutter(x1 - x0, cw, ch, axis="x", roof=False)
            for xe in (x0, x1):                       # exits up through the top face
                beam -= box(6.0, cw, thickness, xe + (3.0 if xe == x0 else -3.0), 0, 1.2)
            meta["channel"] = [cw, ch, round(x1 - x0, 1)]
    if foot:
        beam -= b.Pos(length + end_r - 6, 0, thickness / 2) * teardrop(3.0, 12.5, axis="x")     # rubber foot screw
        meta["foot"] = "M3 rubber bumper or heat-shrink pad screwed into the tip"
    return beam, meta


def _parts_of(spec):
    s = catalog.servo(spec.get("servo", "mg996r"))
    keys = {k: spec.get(k, d) for k, d in (("controller", "rpi_zero_2w"), ("driver", "pca9685"),
                                           ("regulator", "lm2596_module"), ("imu", "mpu6050"),
                                           ("battery", "lipo_2s_2200" if size_class(s) == "standard" else "battery_18650_2s_holder"))}
    return s, {k: v for k, v in keys.items() if v}


def build_quadruped(spec: dict, out: Path) -> dict:
    b = _b3d()
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    s, elec = _parts_of(spec)
    cls = size_class(s)
    std = cls == "standard"
    wall, end_wall, floor = 3.0, 5.0, 3.0
    L1 = float(spec.get("femur", 105.0 if std else 55.0))
    L2 = float(spec.get("tibia", 115.0 if std else 60.0))
    th_sh, th_kn = spec.get("stance", [25.0, -55.0])
    warnings = []

    # ---------------- electronics layout (shelf packing, reused from the rover builder)
    from .builder import layout
    from .library import part as legacy_part
    gap_min = 16.0
    zone = s.tab_z + 6.0                                 # servo body inside each end
    w0 = max(2 * (s.W + 2 * CLEAR) + gap_min, max(legacy_part(k)["size"][1] for k in elec.values()) + 8)
    best = None
    for w_try in [w0 + 5 * i for i in range(30)]:        # widest-first packing; keep the most SpotMicro-like box
        pl_, Le_, We_ = layout(list(elec.values()), {}, 4.0, 6.0, w_try)
        wi = max(w_try, We_)
        aspect = (Le_ + 2 * zone + 2 * end_wall) / (wi + 2 * wall)
        score = abs(aspect - float(spec.get("aspect", 2.2))) + (Le_ + 2 * zone) * wi / 1e5
        if best is None or score < best[0]:
            best = (score, pl_, Le_, wi)
    _, placed, Le, inner_w = best
    gap_mid = inner_w - 2 * (s.W + 2 * CLEAR) - 2.0      # hip servos sit against the side walls
    inner_l = Le + 2 * zone
    tall = max((legacy_part(k)["size"][2] + 6.0) for k in elec.values())
    inner_h = max(s.L + 2 * CLEAR + 10.0, tall, s.tab_span + 6.0 - floor)
    X = inner_l + 2 * end_wall
    Y = inner_w + 2 * wall
    Z = floor + inner_h
    Xw = X / 2                                           # front wall outer face (world x)

    # ---------------- body (print pose = assembly pose: floor on the bed, body centred on x/y)
    body = box(X, Y, Z) - box(inner_l, inner_w, inner_h + 1, 0, 0, floor)
    Zs = floor + (inner_h - s.L) / 2                     # hip servo body bottom (servo x = 0 end)
    y_in = gap_mid / 2                                   # inner face of the left hip servo
    hips = {}
    for fx in (1, -1):                                   # front, back
        for fy in (1, -1):                               # left, right
            yc = fy * (y_in + s.W / 2)
            body -= box(end_wall + 2, s.W + 2 * CLEAR, s.L + 2 * CLEAR, fx * (Xw - end_wall / 2), yc, Zs - CLEAR)
            for hx, hy in s.holes:                       # tab screws go into the end wall (horizontal, teardrop)
                y = fy * (y_in + s.W - hy) if fy > 0 else -(y_in + s.W - hy)
                body -= b.Pos(fx * (Xw - end_wall / 2), y, Zs + hx) * teardrop(max(s.hole_d * 0.8, 1.6), end_wall + 2, axis="x")
            hips[(fx, fy)] = {"axis_y": fy * (y_in + s.W - s.shaft_y), "axis_z": Zs + s.shaft_x}
        # cable slot between the two hip servos: leg cables enter the body here (roof is a short bridge)
        body -= box(end_wall + 2, min(gap_mid - 4, 20.0), 6.0, fx * (Xw - end_wall / 2), 0, Zs + s.L - 8)
    if Zs + max(hx for hx, _ in s.holes) + 3 > Z:
        warnings.append("hip servo tab holes are close to the top edge; check wall height")
    # electronics on the floor: standoffs / clips from the tray generator, battery strap slots
    elec_meta = []
    ex0 = -inner_l / 2 + zone
    ey0 = -inner_w / 2
    for pl in placed:
        p = pl.spec
        cx = ex0 + pl.x + p["size"][0] / 2 - 4.0
        cy = ey0 + pl.y + p["size"][1] / 2
        key = pl.key
        cat = catalog.get(key).get("category")
        if cat == "battery":
            for sx in (-1, 1):
                body -= box(3.0, 22.0, floor, cx + sx * p["size"][0] / 4, cy, 0)
            body += box(p["size"][0] + 2 * CLEAR + 4, 2.0, 6.0, cx, cy - p["size"][1] / 2 - CLEAR - 1, floor - 0.01) \
                + box(p["size"][0] + 2 * CLEAR + 4, 2.0, 6.0, cx, cy + p["size"][1] / 2 + CLEAR + 1, floor - 0.01)
            elec_meta.append({"part": key, "mount": "strap + rails", "at": [round(cx, 1), round(cy, 1)]})
        else:
            tray, tm = M.board_tray(key, base_holes=False, plate=2.4)
            body += b.Pos(cx, cy, floor - 2.4) * tray
            elec_meta.append({"part": key, "mount": tm.get("mode"), "at": [round(cx, 1), round(cy, 1)]})
    # lid screw bosses in the corners (heat-set inserts from the top)
    boss_d = SCREWS["M3"]["insert"][0] + 3.6
    for sx in (-1, 1):
        for sy in (-1, 1):
            bx, by = sx * (inner_l / 2 - zone - boss_d / 2 + 2.0), sy * (inner_w / 2 - boss_d / 2)
            body += box(boss_d, boss_d, inner_h - 4.0, bx, by, floor - 0.01)
            body -= M.screw_hole("M3", "insert", inner_h - 4.0, bx, by, floor)
    # lid: plate + lip, vents, switch cut-out, shell holes
    lid = box(X, Y, 2.4) + (box(inner_l - 0.5, inner_w - 0.5, 4.0, 0, 0, 2.4) - box(inner_l - 3.7, inner_w - 3.7, 4.0, 0, 0, 2.4))
    for sx in (-1, 1):
        for sy in (-1, 1):
            bx, by = sx * (inner_l / 2 - zone - boss_d / 2 + 2.0), sy * (inner_w / 2 - boss_d / 2)
            lid -= box(boss_d + 1.0, boss_d + 1.0, 4.0, bx, by, 2.4)           # lip clears the bosses
            lid -= vhole(SCREWS["M3"]["clear"], 2.4, bx, by, 0)
    sw = catalog.get(spec.get("switch", "switch_kcd1_rocker"))
    lid -= box(sw["dims"]["length"] + 0.4, sw["dims"]["width"] + 0.4, 2.4, -inner_l / 2 + zone + 16, 0, 0)
    for i in range(5):
        lid -= box(2.0, inner_w * 0.4, 2.4, inner_l * (i - 2) / 7 + 10, 0, 0)

    # ---------------- leg parts (print pose) and their placement (front-left leg, mirrored for the others)
    dx_j, dy_j, _ = JOINT_PATTERN[cls]
    coupler, cmeta = M.horn_coupler(s)
    ljoint, lmeta = M.servo_l_joint(s)
    cradle, crmeta = M.servo_cradle(s)
    leg_t = 7.0 if std else 5.0
    leg_w = max(dy_j + 10.0, s.spline_od + 16.0, 14.0)
    knee_bundle = W.bundle(servos=1, servo_class=cls)
    ch = W.channel_size(knee_bundle, pass_connector=False)
    sx_c = crmeta["shaft_xy"][0]                         # shaft x in the cradle frame (negative: near -x end)
    femur, fmeta = limb(s, L1, leg_t, leg_w, joint_x=L1 + sx_c, channel=ch)
    tibia, tmeta = limb(s, L2, leg_t, leg_w * 0.85, foot=True)

    # coupler print frame: horn centre at (hx, 0), pocket face z = 4 (towards the servo), joint at jx
    c_len = cmeta["length"]
    horn_t = 2.5 if std else 2.0
    pocket_r = (20.6 / 2 if std else 7.0 / 2) + 3
    hx = -c_len / 2 + pocket_r
    jx = hx + max(pocket_r, 15.5 + 3.0 if cls == "micro" else 0) + dx_j / 2 + 4
    S = (Xw - s.tab_z) + s.shaft_top                     # hip spline top (world x) for the front-left leg
    hy, hz = hips[(1, 1)]["axis_y"], hips[(1, 1)]["axis_z"]
    Xc = S + 1.5 + 2.4                                   # coupler back face
    loc_coupler = frame((0, 0, -1), (-1, 0, 0), (Xc, hy, hz)) * b.Pos(-hx, 0, 0)
    zj = hz - (jx - hx)
    lt = 4.0
    leg_l = lmeta["leg"]
    x_ref = leg_l / 2 - lt + 2
    loc_l = frame((0, -1, 0), (1, 0, 0), (Xc, hy, zj)) * b.Pos(-x_ref, 0, 0)
    y_l2 = hy + (x_ref + lt)                             # outer face of the L joint's upright leg
    x_c = Xc + leg_l / 2 + 2                             # upright leg hole-pattern centre (world x)
    loc_cradle_sh = frame((0, 0, 1), (0, 1, 0), (x_c, y_l2, zj))
    floor_c = crmeta["floor"]
    z_s = zj + sx_c                                      # shoulder axis height
    y_sp = y_l2 + floor_c + s.shaft_top                  # shoulder spline top (world y)
    y_fp = y_sp + 1.5 - 1.6                              # femur pocket face (inner face)
    loc_femur = frame((0, 0, -1), (0, -1, 0), (x_c, y_fp + leg_t, z_s))
    z_k = z_s - L1
    loc_cradle_kn = frame((0, 0, 1), (0, -1, 0), (x_c, y_fp, z_k - sx_c))
    y_kp = y_fp - floor_c - s.shaft_top                  # knee spline top (world y)
    loc_tibia = frame((0, 0, -1), (0, 1, 0), (x_c, y_kp - 1.5 + 1.6 - leg_t, z_k))
    # servo dummies: hip in the wall, shoulder in its cradle, knee in its cradle
    loc_servo_hip = frame((0, 0, 1), (1, 0, 0), (Xw - s.tab_z, y_in + s.W, Zs))
    # cradle frame: servo lower-left-bottom at (-L/2, -W/2, floor)
    loc_servo_in_cradle = b.Pos(-s.L / 2, -s.W / 2, floor_c)

    sdum = servo_dummy(s)
    ax_sh = b.Axis((x_c, 0, z_s), (0, 1, 0))
    ax_kn_local = (x_c, z_k)

    def place_leg():
        """Front-left leg in the assembly at the stance angles: (printed parts, bought parts)."""
        printed = {"coupler": loc_coupler * coupler, "l_joint": loc_l * ljoint, "cradle_shoulder": loc_cradle_sh * cradle}
        bought = {"servo_hip": loc_servo_hip * sdum, "servo_shoulder": loc_cradle_sh * loc_servo_in_cradle * sdum}
        lower_printed = {"femur": loc_femur * femur, "cradle_knee": loc_cradle_kn * cradle}
        lower_bought = {"servo_knee": loc_cradle_kn * loc_servo_in_cradle * sdum}
        tib = {"tibia": loc_tibia * tibia}
        kax = b.Axis((ax_kn_local[0], 0, ax_kn_local[1]), (0, 1, 0))
        tib = {k: v.rotate(kax, th_kn) for k, v in tib.items()}
        lower_printed.update(tib)
        lower_printed = {k: v.rotate(ax_sh, th_sh) for k, v in lower_printed.items()}
        lower_bought = {k: v.rotate(ax_sh, th_sh) for k, v in lower_bought.items()}
        printed.update(lower_printed); bought.update(lower_bought)
        return printed, bought

    fl_printed, fl_bought = place_leg()

    def mirrored(shape, fx, fy):
        if fy < 0:
            shape = b.mirror(shape, b.Plane.XZ)
        if fx < 0:
            shape = b.mirror(shape, b.Plane.YZ)
        return shape

    legs = {}
    for fx, fname in ((1, "front"), (-1, "back")):
        for fy, sname in ((1, "left"), (-1, "right")):
            legs[f"{fname}_{sname}"] = ({k: mirrored(v, fx, fy) for k, v in fl_printed.items()},
                                        {k: mirrored(v, fx, fy) for k, v in fl_bought.items()})

    # ---------------- collision checks in the assembly
    def overlap(a, c):
        try:
            i = a & c
            return sum(x.volume for x in i.solids()) if i else 0.0
        except Exception:                                  # noqa: BLE001
            return -1.0
    clashes = []
    pr, bo = legs["front_left"]
    pairs = [("body", body, k, v) for k, v in pr.items()] + \
            [(k1, v1, k2, v2) for k1, v1 in pr.items() for k2, v2 in bo.items()
             if not (k1 == "cradle_shoulder" and k2 == "servo_shoulder") and not (k1 == "cradle_knee" and k2 == "servo_knee")] + \
            [("femur", pr["femur"], "tibia", pr["tibia"]), ("cradle_shoulder", pr["cradle_shoulder"], "femur", pr["femur"]),
             ("tibia", pr["tibia"], "cradle_shoulder", pr["cradle_shoulder"])]
    for n1, a, n2, c in pairs:
        v = overlap(a, c)
        if v > 1.0:
            clashes.append({"a": n1, "b": n2, "mm3": round(v, 1)})
    hip_clear = overlap(body, bo["servo_hip"])
    if hip_clear > 1.0:
        clashes.append({"a": "body", "b": "servo_hip", "mm3": round(hip_clear, 1)})

    # ---------------- wiring: cable lengths and service loops
    loops = {"hip_roll": W.service_loop(90, W.bundle(servos=2, servo_class=cls)),
             "shoulder_pitch": W.service_loop(180, knee_bundle)}
    run_knee = L1 + loops["shoulder_pitch"] + loops["hip_roll"] + 60 + Le / 2
    run_shoulder = loops["hip_roll"] + 60 + Le / 2
    lead = 245.0 if cls == "micro" else 300.0
    ext = [n for n, r in (("knee", run_knee), ("shoulder", run_shoulder)) if r > lead]

    # ---------------- export printable parts (print pose) + assembly preview
    lidp = lid
    printable = {"body": (body, {"outer_mm": [round(X, 1), round(Y, 1), round(Z, 1)], "electronics": elec_meta}),
                 "lid": (lidp, {"switch": sw["key"]}),
                 "hip_coupler": (coupler, cmeta), "l_joint": (ljoint, lmeta), "servo_cradle": (cradle, crmeta),
                 "femur": (femur, fmeta), "tibia": (tibia, tmeta)}
    if spec.get("shell"):
        printable["character_shell"] = character_shell(X, Y, inner_l - 2 * zone + 4.0, inner_w, boss_d)
    res = M.export_checked(printable, out / "print", sheet_title=f"quadruped ({s.label}) printable parts")
    counts = {"body": 1, "lid": 1, "hip_coupler": 4, "l_joint": 4, "servo_cradle": 8, "femur": 4, "tibia": 4,
              "character_shell": 1}
    lid_placed = b.Pos(0, 0, Z + 2.4) * b.Rot(180, 0, 0) * lid          # lip down into the body
    assembly = [body, lid_placed] + [v for pr_, bo_ in legs.values() for v in pr_.values()]
    if "character_shell" in printable:
        assembly.append(b.Pos(0, 0, Z + 2.4) * printable["character_shell"][0])
    bought_all = [v for pr_, bo_ in legs.values() for v in bo_.values()]
    _render_assembly(assembly, bought_all, out / "assembly.png", f"Quadruped, {s.label}, stance {th_sh:.0f}/{th_kn:.0f} deg")
    try:
        b.export_step(b.Compound(children=assembly + bought_all), str(out / "assembly.step"))
    except Exception:                                      # noqa: BLE001
        pass
    bom = quadruped_bom(s, elec, sw, ext, cls)
    report = {"type": "quadruped", "servo": s.key, "femur": L1, "tibia": L2,
              "body_mm": [round(X, 1), round(Y, 1), round(Z, 1)], "inner_mm": [round(inner_l, 1), round(inner_w, 1), round(inner_h, 1)],
              "electronics": elec_meta, "print_checks": {k: v["check"]["ok"] for k, v in res.items()},
              "print_counts": {k: counts[k] for k in printable}, "clashes": clashes,
              "wiring": {"knee_channel_mm": ch, "service_loops_mm": loops, "run_knee_mm": round(run_knee), "run_shoulder_mm": round(run_shoulder),
                         "servo_lead_mm": lead, "extensions_needed": ext},
              "warnings": warnings + [f"{catalog.get(k)['label']}: unverified dimensions, measure and override"
                                      for k in [s.key, *elec.values()] if not catalog.get(k).get("verified")],
              "bom": bom}
    (out / "report.json").write_text(json.dumps(report, indent=1))
    (out / "BOM.md").write_text(bom_markdown(report))
    (out / "ASSEMBLY.md").write_text(quadruped_notes(report, s))
    return report


def character_shell(X, Y, inner_l, inner_w, boss_d, wall_h=None, t=2.0):
    """Cover that bolts onto the lid: straight walls and a 45 degree hipped roof (prints upright, rim on the bed,
    no flat ceiling to support), a bolting flange on the bed and two teardrop eye sockets at the front."""
    b = _b3d()
    wall_h = wall_h if wall_h is not None else max(12.0, Y * 0.2)
    roof = Y / 2 - 0.5
    outer = box(X, Y, wall_h) + b.Pos(0, 0, wall_h) * b.extrude(b.Rectangle(X, Y), amount=roof, taper=45)
    ri = roof - t * 1.414
    inner = box(X - 2 * t, Y - 2 * t, wall_h + 0.01, 0, 0, -0.01) + \
        b.Pos(0, 0, wall_h) * b.extrude(b.Rectangle(X - 2 * t, Y - 2 * t), amount=max(ri, 1.0), taper=45)
    shell = outer - inner
    fl = 2.4
    shell += box(X, Y, fl) - box(inner_l - 2 * boss_d - 4, inner_w - 2 * boss_d - 4, fl)
    for sx in (-1, 1):
        for sy in (-1, 1):
            shell -= vhole(SCREWS["M3"]["clear"], fl, sx * (inner_l / 2 - boss_d / 2), sy * (inner_w / 2 - boss_d / 2), 0)
    eye_d = min(Y * 0.14, wall_h * 0.6)                 # teardrop apex stays below the roof line
    for sy in (-1, 1):
        shell -= b.Pos(X / 2 - t / 2, sy * Y * 0.2, wall_h * 0.5) * teardrop(eye_d, 3 * t, axis="x")
    return shell, {"height": round(wall_h + roof, 1), "note": "prints upright, rim on the bed; the eyes look forward"}


def _render_assembly(printed, bought, png, title):
    import trimesh
    from PIL import Image, ImageDraw

    from .printcheck import render_view
    import build123d as b
    tmp = Path(png).with_suffix(".tmp.stl")
    meshes = []
    for group, color in ((printed, (90, 150, 220)), (bought, (60, 60, 60))):
        b.export_stl(b.Compound(children=group), str(tmp), tolerance=0.1, angular_tolerance=0.3)
        meshes.append((trimesh.load(tmp, force="mesh"), color))
    tmp.unlink(missing_ok=True)
    combo = trimesh.util.concatenate([m for m, _ in meshes])
    colors = []
    for m, c in meshes:
        colors += [c] * len(m.faces)
    size = 520
    sheet = Image.new("RGB", (size * 2, size * 2 + 30), (255, 255, 255))
    for i, (az, el) in enumerate(((-60, 25), (-90, 0), (0, 0), (-90, 90))):
        sheet.paste(_render_colored(combo, colors, az, el, size), ((i % 2) * size, (i // 2) * size + 30))
    ImageDraw.Draw(sheet).text((10, 8), title + "  (blue = printed, dark = bought servos)", fill=(0, 0, 0))
    sheet.save(png)


def _render_colored(mesh, colors, az, el, size):
    import numpy as np
    from PIL import Image, ImageDraw

    from .printcheck import _view_matrix
    R = _view_matrix(az, el)
    v = mesh.vertices @ R.T
    tri = v[mesh.faces]
    n = mesh.face_normals @ R.T
    vis = n[:, 2] > 0
    cols = np.array(colors, dtype=float)[vis]
    tri, n = tri[vis], n[vis]
    img = Image.new("RGB", (size, size), (250, 250, 248))
    lo, hi = v[:, :2].min(0), v[:, :2].max(0)
    scale = size * 0.9 / max(float((hi - lo).max()), 1e-6)
    off = np.array([size / 2, size / 2]) - (lo + hi) / 2 * scale
    light = np.array([0.35, 0.45, 0.82]); light /= np.linalg.norm(light)
    shade = 0.35 + 0.65 * np.clip(n @ light, 0, 1)
    pts = tri[:, :, :2] * scale + off
    pts[:, :, 1] = size - pts[:, :, 1]
    d = ImageDraw.Draw(img)
    for i in np.argsort(tri[:, :, 2].mean(1)):
        c = tuple(int(x) for x in np.clip(cols[i] * shade[i], 0, 255))
        d.polygon([tuple(p) for p in pts[i]], fill=c, outline=c)
    return img


# ---------------------------------------------------------------- BOM and notes

def quadruped_bom(s, elec, sw, ext, cls):
    std = cls == "standard"
    bom = [
        {"qty": 12, "item": s.label, "note": "buy 13: one spare. Metal-gear MG996R or SG90/MG90S are stocked by most electronics shops (Hall Road, Lahore) and Pakistani online robotics stores"},
        {"qty": 12, "item": "servo horns that came with the servos", "note": ("round 25T disc horn" if std else "single-arm horn")},
    ]
    for role, key in elec.items():
        p = catalog.get(key)
        bom.append({"qty": 1, "item": p["label"], "note": role + ("" if p.get("verified") else " (generic clone: measure before printing)")})
    bom += [
        {"qty": 1, "item": sw["label"], "note": "main power switch in the lid"},
        {"qty": 1, "item": "servo power buck converter, 5 to 6 V, " + ("10 A or more (XL4016-class 8 A minimum)" if std else "5 A"),
         "note": "servos must NOT run from the logic regulator: " + ("12 x MG996R can pull over 10 A when the robot stands up" if std else "12 micro servos pull 3 to 5 A")},
        {"qty": 1, "item": "XT60 (2S LiPo) or JST-XH lead + 16 AWG silicone wire for the servo rail", "note": "short, thick power runs"},
        {"qty": len(ext) * 4, "item": "servo extension leads (male-female, 15 to 30 cm)", "note": "for " + ", ".join(ext) + " servos" if ext else "not needed"},
        {"qty": 28, "item": "M3 x 4 or x 5 heat-set inserts", "note": "8 cradles x 4 inside the joint pattern minus the femur side + lid bosses; buy a pack of 50"},
        {"qty": 48, "item": "M3 x 10 cap screws", "note": "joint patterns (coupler-L joint, L joint-cradle, femur-knee cradle)"},
        {"qty": 8, "item": "M3 x 8 screws", "note": "lid and electronics trays"},
        {"qty": 4, "item": "M3 rubber bumpers or heat-shrink pads", "note": "feet"},
        {"qty": 1, "item": "hook-and-loop strap 20 mm", "note": "battery"},
        {"qty": 10, "item": "zip ties 3 mm", "note": "service loops at hips and shoulders"},
    ]
    return bom


def bom_markdown(r):
    lines = [f"# Bill of materials: {r['type']} ({r['servo']})", "", "## Bought parts", "", "| Qty | Item | Note |", "|---|---|---|"]
    lines += [f"| {x['qty']} | {x['item']} | {x['note']} |" for x in r["bom"] if x["qty"]]
    lines += ["", "## Printed parts", "", "| Qty | Part | Print check |", "|---|---|---|"]
    lines += [f"| {r['print_counts'].get(k, 1)} | {k}.stl | {'OK' if ok else 'CHECK'} |" for k, ok in r["print_checks"].items()]
    if r.get("warnings"):
        lines += ["", "## Measure before printing", ""] + [f"- {w}" for w in r["warnings"]]
    return "\n".join(lines) + "\n"


def quadruped_notes(r, s):
    w = r["wiring"]
    return f"""# Assembly notes: quadruped ({s.label})

Body {r['body_mm'][0]} x {r['body_mm'][1]} x {r['body_mm'][2]} mm, femur {r['femur']} mm, tibia {r['tibia']} mm.
Print everything in PETG or PLA+, 3 walls, 30 percent infill; cradles and femurs at 40 percent. Every part prints in
the pose it was exported in, without supports (see print/contact_sheet.png and print/checks.json).

1. Heat-set the inserts: 4 in the floor of every servo cradle (from below), 4 in the body corner bosses.
2. Electronics: screw the controller, PCA9685 and regulator onto their standoffs in the body floor; strap the
   battery between its rails. Set the regulator to 5.0 V for the logic BEFORE connecting the controller.
3. Centre all 12 servos (1500 us pulse from the PCA9685) before fitting any horn.
4. Hip servos: push each one through its end-wall pocket from inside the body, shaft outwards, and screw the
   tabs into the wall. Leg cables go back into the body through the slot between the two hip servos.
5. Hip coupler: fit the horn into the coupler pocket (horn screws from the horn side), then onto the hip spline
   pointing straight down, horn screw through the centre hole.
6. L joint: bolt its flat leg to the coupler (4 x M3 x 10), the upright leg points outwards.
7. Shoulder cradle: drop a servo in (shaft away from the floor), screw the tabs, bolt the cradle floor onto the L
   joint's upright leg so the shaft points outwards.
8. Femur: horn into the pocket, onto the shoulder spline hanging straight down. Bolt a knee cradle (servo inside,
   shaft pointing to the body centre line) onto the femur's inner face with 4 x M3 x 10 into its inserts.
9. Thread the knee servo lead through the femur channel (exits face the servo side) before closing the cradle.
10. Tibia: horn in pocket, onto the knee spline pointing down, rubber pad in the tip.
11. Wiring: leave a {w['service_loops_mm']['shoulder_pitch']:.0f} mm service loop at every shoulder and
    {w['service_loops_mm']['hip_roll']:.0f} mm at every hip (zip-tie the loop to the L joint, never across the axis).
    Knee runs are about {w['run_knee_mm']} mm, shoulder runs {w['run_shoulder_mm']} mm against a {w['servo_lead_mm']:.0f} mm stock lead:
    {'add extension leads for the ' + ', '.join(w['extensions_needed']) + ' servos.' if w['extensions_needed'] else 'stock leads reach.'}
12. Power: battery to the switch to the servo buck (servo rail on the PCA9685 V+ terminal) and, separately, to the
    logic regulator. Common ground between everything.
13. Calibrate each joint's zero in software, then try the stance ({r['femur']:.0f}/{r['tibia']:.0f} mm legs) with the robot on a stand.
"""
