"""4-servo biped (Otto-style kinematics, original design): walks on feet or rolls on wheels, sized around real parts.

- body: open-top box. The two hip servos hang shaft-down through pockets in the floor (yaw joints); a battery
  shelf sits on 45 degree rails above them, an electronics deck (controller + PCA9685 + optional regulator / IMU on
  their real hole patterns) on a second pair of rails above the battery; the ultrasonic sensor looks out of the
  front wall; switch and USB slot at the back; floor slots let the ankle leads in.
- leg (x2): a servo cradle (robot/mounts.py) holding the ankle servo with its shaft forward (roll joint), with the
  hip horn pocket on its top face, right above the ankle axis.
- foot (x2): sole + upright with the ankle horn pocket. wheel (x2): disc on the same horn, for roll mode.
- deck, shelf, lid, 2 cable clips.

Spec keys: controller, driver, regulator, imu, battery, sensor, servo, switch (library keys; old keys such as
"servo_sg90" or "battery_4aa" still work).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from . import catalog, mounts as M, wiring as W
from .catalog import SCREWS
from .mounts import CLEAR, box, size_class, teardrop, vhole

ALIASES = {"servo_sg90": "sg90", "servo_mg996r": "mg996r", "battery_4aa": "battery_4aa_holder",
           "battery_18650_2s": "battery_18650_2s_holder", "esp32_devkitc": "esp32_devkitc_v4", "rpi4": "rpi4b",
           "arduino_uno": "arduino_uno_r3", "l298n": "l298n_module"}


def _k(key):
    return ALIASES.get(key, key)


def _rail(length, x_face, z_top, side, depth=3.0):
    """45 degree rail on a side wall (runs along y). side=+1: wall at +x, rail sticks out towards -x."""
    import build123d as b
    prof = b.Polygon((x_face, z_top - depth), (x_face - side * depth, z_top), (x_face, z_top), align=None)
    return b.extrude(b.Plane.XZ * prof, amount=length / 2, both=True)


def _dims(key):
    p = catalog.get(key)
    d = p["dims"]
    h = (d.get("height_top") or 10.0) + (d.get("thickness") or 0.0 if p["category"] in ("sbc", "mcu", "driver", "sensor") else 0.0)
    return float(d["length"]), float(d["width"]), float(h)


def build_biped(spec: dict, out: Path) -> dict:
    import build123d as b
    from .builder import layout
    from .quadruped import _render_assembly, bom_markdown, frame, servo_dummy

    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    s = catalog.servo(_k(spec.get("servo", "sg90")))
    cls = size_class(s)
    sen_key = _k(spec.get("sensor", "hc_sr04"))
    bat_key = _k(spec.get("battery", "battery_4aa"))
    deck_keys = [_k(spec.get("controller", "arduino_nano"))] + [_k(spec[k]) for k in ("driver", "regulator", "imu") if spec.get(k)]
    wall, floor = 2.0, 2.0
    sen = catalog.get(sen_key)
    sen_L, sen_W, _ = _dims(sen_key)
    sen_depth = float(sen["dims"].get("height_top") or 15.0) + 1.0
    eye_d = float(sen["mech"].get("eye_d", 16.0)); eye_sp = float(sen["mech"].get("eye_spacing", 26.0))
    bat_L, bat_W, bat_H = _dims(bat_key)

    # hip servos: inverted in the floor, long side along x, shafts at the outer ends
    tab_out = (s.tab_span - s.L) / 2
    g = s.tab_span - s.L + 4.0                          # gap between the two servos' inner ends
    x_o = g / 2 + s.L                                   # outer end of the right-hand (+x) servo body
    servo_up = s.tab_z + s.tab_t                        # servo body height above the floor top
    z_bat = floor + servo_up + 1.5                      # battery shelf rails
    shelf_t = 2.4
    # electronics deck: pack the boards, grow the body until they fit
    deck_y_min = max(bat_W + 4, 40.0)
    best = None
    for dy in [deck_y_min + 4 * i for i in range(12)]:   # deeper deck vs wider body: keep the smallest box
        pl_, Ld_, Wd_ = layout(deck_keys, {}, 2.0, 4.0, dy)
        width = max(2 * (g / 2 + s.L + (s.tab_span - s.L) / 2) + 2, bat_L + 6.6, Ld_ + 2.0)
        depth = sen_depth + max(Wd_, dy) + 2
        score = width * depth + 0.6 * depth * depth        # a deep body tips over the feet front-to-back
        if best is None or score < best[0]:
            best = (score, pl_, Ld_, Wd_)
    _, placed, Ld, Wd = best
    inner_x = max(2 * (x_o + tab_out) + 2, bat_L + 2 * CLEAR + 6.0, Ld + 2.0, sen_L + 2.0)
    deck_y = max(Wd, bat_W + 4)
    inner_y = sen_depth + max(deck_y, bat_W + 2 * CLEAR + 4, s.W + 12) + 2.0
    z_deck = z_bat + shelf_t + bat_H + 1.5
    tallest = max(_dims(k)[2] + max((catalog.board(k).bottom if catalog.get(k)["category"] != "battery" else 0) + 1.5, 4.0)
                  for k in deck_keys)
    inner_z = z_deck + 2.4 + tallest + 3.0 - floor
    X, Y, Z = inner_x + 2 * wall, inner_y + 2 * wall, floor + inner_z
    body = box(X, Y, Z) - box(inner_x, inner_y, inner_z + 1, 0, 0, floor)
    hips = []
    for side in (1, -1):
        cx = side * (x_o - s.L / 2)
        body -= box(s.L + 2 * CLEAR, s.W + 2 * CLEAR, floor, cx, 0, 0)
        for hx, hy in s.holes:
            body -= vhole(max(s.hole_d * 0.8, 1.6), floor, side * (x_o - hx), -s.W / 2 + hy, 0)
        hips.append({"side": side, "shaft": [side * (x_o - s.shaft_x), -s.W / 2 + s.shaft_y]})
        body -= box(4.0, 9.0, floor, side * (x_o + tab_out - 4), s.W / 2 + 7.0, 0)      # ankle lead slot
    # rails: battery shelf and deck
    rail_len = inner_y - sen_depth - 2
    rail_y = inner_y / 2 - rail_len / 2 - 1
    for z_top in (z_bat, z_deck):
        for side in (1, -1):
            body += b.Pos(0, rail_y, 0) * _rail(rail_len, side * inner_x / 2 + side * 0.01, z_top, side)
    # sensor: transducers through the front wall, centred on the sensor zone height
    z_eye = min(z_deck + 2.4 + sen_W / 2, Z - eye_d / 2 - 3)
    for dx in (-eye_sp / 2, eye_sp / 2):
        body -= b.Pos(dx, -Y / 2 + wall / 2, z_eye) * teardrop(eye_d + 2 * CLEAR, wall + 2)
    # back wall: USB slot at deck height and the power switch
    body -= box(14.0, wall + 2, 9.0, 0, Y / 2 - wall / 2, z_deck + 2.4)
    sw = catalog.get(_k(spec.get("switch", "switch_ss12d00")))
    swL, swW = float(sw["dims"]["length"]), float(sw["dims"]["width"])
    body -= box(swL + 0.4, wall + 2, swW + 0.4, inner_x / 2 - swL - 6, Y / 2 - wall / 2, z_bat + 2)

    # battery shelf (strap slots) and electronics deck (standoffs on real hole patterns)
    shelf = box(inner_x - 0.8, rail_len - 0.6, shelf_t)
    for sx in (-1, 1):
        shelf -= box(3.0, min(21.0, rail_len - 8), shelf_t, sx * bat_L / 4, 0, 0)
    deck = box(inner_x - 0.8, rail_len - 0.6, 2.4)
    deck -= box(12.0, 6.0, 2.4, 0, -(rail_len - 0.6) / 2 + 5, 0)                     # cable pass
    deck_meta = []
    for pl in placed:
        p = pl.spec
        cx = -Ld / 2 + pl.x + p["size"][0] / 2
        cy = -deck_y / 2 + pl.y + p["size"][1] / 2
        tray, tm = M.board_tray(pl.key, base_holes=False, plate=2.4, margin=1.0)
        deck += b.Pos(cx, cy, 0) * tray
        deck_meta.append({"part": pl.key, "mount": tm.get("mode"), "at": [round(cx, 1), round(cy, 1)]})
    lid = box(X, Y, wall) + (box(inner_x - 0.5, inner_y - 0.5, 3.0, 0, 0, wall) - box(inner_x - 3.7, inner_y - 3.7, 3.0, 0, 0, wall))

    # leg: cradle for the ankle servo + hip horn pocket on its top face
    leg_wall = 4.0
    leg, cm = M.servo_cradle(s, wall=leg_wall)
    sx_c = cm["shaft_xy"][0]
    outer_y = s.W + 2 * CLEAR + 2 * leg_wall
    y_top = outer_y / 2
    zc = cm["height"] / 2
    horn = "arm" if cls == "micro" else "disc"
    pocket = b.Rot(90, 0, 0) * M._horn_pocket(s, 1.7, horn, arm_angle=90.0)   # into the wall (-y), arm along +z
    leg -= b.Pos(sx_c, y_top + 0.01, zc) * pocket
    leg -= b.Pos(sx_c, y_top - leg_wall / 2, zc) * teardrop(SCREWS[s.horn_screw]["head"] + 1.0, leg_wall + 2)
    leg -= b.Pos(sx_c, y_top + 0.5, zc) * b.Rot(90, 0, 0) * M._horn_screw_holes(s, leg_wall + 1, horn, arm_angle=90.0)

    # foot: sole + upright with the ankle horn pocket facing back (+y)
    sole_t, up_t = 3.0, 4.0
    drop = outer_y / 2 + 4.0                            # ankle axis to the sole top (room for +/-30 degree roll)
    up_h = drop + (20.6 / 2 if cls == "standard" else 15.5 + 2.3) + 4.0
    sole_w, sole_len = max(40.0, cm["height"] + 16), max(50.0, s.tab_span + 20)
    foot = box(sole_w, sole_len, sole_t, 0, sole_len / 2 - up_t, 0)
    foot += box(max(18.0, s.spline_od + 14), up_t, up_h + sole_t, 0, -up_t / 2, 0)
    ax_z = sole_t + drop
    fp = b.Rot(-90, 0, 0) * M._horn_pocket(s, 1.7, horn, arm_angle=90.0)               # extrudes along +y
    foot -= b.Pos(0, -0.01 - 1.6 + 0.01, ax_z) * fp
    foot -= b.Pos(0, -up_t / 2, ax_z) * teardrop(SCREWS[s.horn_screw]["head"] + 1.0, up_t + 2)
    foot -= b.Pos(0, -up_t - 0.5, ax_z) * b.Rot(-90, 0, 0) * M._horn_screw_holes(s, up_t + 1, horn, arm_angle=90.0)
    # wheel for roll mode (continuous-rotation servos), O-ring groove as a tyre
    wheel_r = drop + 6.0
    wheel = b.Cylinder(wheel_r, 8, align=(b.Align.CENTER, b.Align.CENTER, b.Align.MIN))
    wheel -= b.Pos(0, 0, 8 - 1.6) * M._horn_pocket(s, 1.7, horn)
    wheel -= vhole(SCREWS[s.horn_screw]["head"] + 1.0, 8, 0, 0, 0)
    wheel -= M._horn_screw_holes(s, 8, horn)
    wheel -= b.Pos(0, 0, 3) * (b.Cylinder(wheel_r + 1, 2, align=(b.Align.CENTER, b.Align.CENTER, b.Align.MIN))
                               - b.Cylinder(wheel_r - 1.5, 2, align=(b.Align.CENTER, b.Align.CENTER, b.Align.MIN)))
    ankle_bundle = W.bundle(servos=1, servo_class=cls)
    clip, clip_meta = W.cable_clip(max(4.0, W.rules()["servo_cables"][cls]["flat"][0]))

    # ---------------- assembly: body raised so the soles stand on z = 0
    sdum = servo_dummy(s)
    spline_dz = floor + servo_up - s.shaft_top           # spline tip relative to the body bottom
    leg_top_to_axis = y_top                              # ankle axis sits y_top below the leg's top face
    Bz = sole_t + drop + leg_top_to_axis - 0.1 - spline_dz
    asm_p, asm_b = [b.Pos(0, 0, Bz) * body, b.Pos(0, rail_y, Bz + z_bat) * shelf, b.Pos(0, rail_y, Bz + z_deck) * deck,
                    b.Pos(0, 0, Bz + Z + wall) * b.Rot(180, 0, 0) * lid], []
    clashes = []
    for h in hips:
        side = h["side"]
        xs, ys = h["shaft"]
        zt = Bz + spline_dz
        hip_servo = frame((-1, 0, 0), (0, 0, -1), (x_o, -s.W / 2, Bz + floor + servo_up)) * sdum
        if side < 0:
            hip_servo = b.mirror(hip_servo, b.Plane.YZ)
        O = (xs - sx_c, ys + zc, zt + 0.1 - y_top)
        leg_loc = frame((1, 0, 0), (0, -1, 0), O)
        leg_p = leg_loc * leg
        ankle_servo = leg_loc * b.Pos(-s.L / 2, -s.W / 2, cm["floor"]) * sdum
        y_ka = O[1] - cm["floor"] - s.shaft_top
        foot_p = b.Pos(xs, y_ka - 1.5 + 1.6, O[2] - ax_z) * foot
        asm_p += [leg_p, foot_p]; asm_b += [hip_servo, ankle_servo]
        for n1, a1, n2, a2 in (("body", asm_p[0], "leg", leg_p), ("leg", leg_p, "hip_servo", hip_servo),
                               ("foot", foot_p, "ankle_servo", ankle_servo), ("foot", foot_p, "leg", leg_p),
                               ("body", asm_p[0], "hip_servo", hip_servo)):
            i = a1 & a2
            v = sum(x.volume for x in i.solids()) if i else 0.0
            if v > 1.0:
                clashes.append({"a": n1, "b": n2, "side": side, "mm3": round(v, 1)})
    _render_assembly(asm_p, asm_b, out / "assembly.png", f"Biped, {s.label}, " + ", ".join(deck_keys))

    printable = {"body": (body, {"outer_mm": [round(X, 1), round(Y, 1), round(Z, 1)]}), "lid": (lid, {}),
                 "battery_shelf": (shelf, {}), "electronics_deck": (deck, {"boards": deck_meta}),
                 "leg": (leg, cm), "foot": (foot, {}), "wheel": (wheel, {}), "cable_clip": (clip, clip_meta)}
    res = M.export_checked(printable, out / "print", sheet_title=f"biped ({s.label}) printable parts")
    # legacy file names used by earlier tests and docs
    for n in ("leg", "foot", "wheel"):
        for side in ("left", "right"):
            for ext in ("stl", "step"):
                src = out / "print" / f"{n}.{ext}"
                (out / f"{n}_{side}.{ext}").write_bytes(src.read_bytes())
    for n in ("body", "lid"):
        for ext in ("stl", "step"):
            (out / f"{n}.{ext}").write_bytes((out / "print" / f"{n}.{ext}").read_bytes())

    fits = {
        "battery_on_shelf": bat_L + 2 * CLEAR <= inner_x and bat_W <= rail_len and z_bat + shelf_t + bat_H <= z_deck,
        "boards_on_deck": Ld <= inner_x - 0.8 and Wd <= rail_len,
        "sensor_behind_front": sen_L <= inner_x and z_eye + eye_d / 2 < Z,
        "hip_pockets_do_not_touch": g >= s.tab_span - s.L + 2,
        "deck_clears_tallest_board": z_deck + 2.4 + tallest <= Z,
        "no_assembly_clashes": not clashes,
    }
    loop = W.service_loop(120, ankle_bundle)
    run = loop + y_top + cm["height"] + 40 + inner_y / 2
    lead = 245.0 if cls == "micro" else 300.0
    bom = [{"qty": 4, "item": s.label, "note": "hips and ankles; continuous-rotation versions for wheel mode"}]
    for k in deck_keys + [bat_key, sen_key, sw["key"]]:
        p = catalog.get(k)
        bom.append({"qty": 1, "item": p["label"], "note": "" if p.get("verified") else "generic clone: measure before printing"})
    bom += [{"qty": 1, "item": "5 V 3 A buck (MP1584 / LM2596) if the battery is above 6 V", "note": "servos and logic"},
            {"qty": 8, "item": "servo tab self-tapping screws (come with the servos)", "note": ""},
            {"qty": 2, "item": "O-rings for the wheels, about %d mm inner diameter" % round(2 * wheel_r - 3), "note": "tyres"},
            {"qty": 2 if run > lead else 0, "item": "servo extension leads 10 to 15 cm", "note": "ankle servos"},
            {"qty": 8, "item": "M2.5 or M2 screws for the boards", "note": "standoffs take self-tapping or heat-set inserts"}]
    report = {"type": "biped", "servo": s.key, "body_mm": [round(X, 1), round(Y, 1), round(Z, 1)],
              "inner_mm": [round(inner_x, 1), round(inner_y, 1), round(inner_z, 1)], "fits": fits, "clashes": clashes,
              "deck": deck_meta, "print_checks": {k: v["check"]["ok"] for k, v in res.items()},
              "print_counts": {"body": 1, "lid": 1, "battery_shelf": 1, "electronics_deck": 1, "leg": 2, "foot": 2, "wheel": 2, "cable_clip": 2},
              "wiring": {"ankle_service_loop_mm": loop, "ankle_run_mm": round(run), "servo_lead_mm": lead},
              "bom": bom, "files": list(printable),
              "warnings": [f"{catalog.get(k)['label']}: unverified dimensions, measure and override"
                           for k in [s.key, sen_key, bat_key, *deck_keys] if not catalog.get(k).get("verified")]}
    (out / "report.json").write_text(json.dumps(report, indent=1))
    (out / "BOM.md").write_text(bom_markdown(report))
    (out / "ASSEMBLY.md").write_text(biped_notes(report, s))
    return report


def biped_notes(r, s):
    w = r["wiring"]
    return f"""# Assembly notes: biped ({s.label})

Body {r['body_mm'][0]} x {r['body_mm'][1]} x {r['body_mm'][2]} mm. Print in PLA+ or PETG, 3 walls, 25 percent infill.
Every part prints as exported without supports (print/contact_sheet.png, print/checks.json).

1. Centre all four servos (90 degrees / 1500 us) before fitting any horn.
2. Hip servos: drop them into the floor pockets from inside the body, shaft pointing down, screw the tabs into the
   floor. The ankle leads come in through the slots beside the pockets.
3. Legs: put the ankle servo in the leg cradle (shaft to the front), screw its tabs. Press the hip horn into the
   pocket on top of the leg (horn screws from the horn side) and push the leg onto the hip spline, foot pointing
   forward; fit the horn screw through the access hole.
4. Feet: horn into the upright's pocket, onto the ankle spline with the sole level. For roll mode swap the feet for
   the wheels (continuous-rotation servos) and fit O-rings as tyres.
5. Leave a {w['ankle_service_loop_mm']:.0f} mm loop in each ankle lead at the hip and hold it with the printed clip;
   the run is about {w['ankle_run_mm']} mm against a {w['servo_lead_mm']:.0f} mm lead.
6. Battery: strap it onto the battery shelf, slide the shelf onto the lower rails.
7. Deck: screw the controller and PCA9685 onto their standoffs, wire the servos to channels 0 to 3, slide the deck onto
   the upper rails. The sensor clips behind the front wall with its transducers in the eye holes.
8. Power through the back switch. Lid on.
"""
