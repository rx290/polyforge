"""A small 4-servo biped (walk on feet, or roll on wheels like the "ninja" walkers), sized around real parts.

Original design in the spirit of the open Otto-style walkers, not a copy of any of their files:
- body: open-top box; the ultrasonic sensor's two transducers look out through the front, the hip servos hang
  through pockets in the floor (shaft down), the controller and battery sit inside, USB slot at the back
- lid: drop-in lid with a lip
- leg (x2): a block whose top takes the hip servo horn and whose side pocket holds the ankle servo
- foot (x2) and wheel (x2): both take the ankle servo horn, so you swap walk and roll modes
Spec: {"controller": "arduino_nano", "battery": "battery_4aa", "sensor": "hc_sr04", "servo": "servo_sg90"}
"""
from __future__ import annotations

import json
from pathlib import Path

from .library import part

CLEAR = 0.3   # print clearance around bought parts


def build_biped(spec: dict, out: Path) -> dict:
    from build123d import Align, Box, Cylinder, Pos, Rot, export_step, export_stl

    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    ov = spec.get("overrides", {})
    ctrl, bat, sen, srv = (part(spec.get(k, d), ov) for k, d in (("controller", "arduino_nano"), ("battery", "battery_4aa"),
                                                                 ("sensor", "hc_sr04"), ("servo", "servo_sg90")))
    wall = spec.get("wall", 2.0)
    C = (Align.CENTER, Align.CENTER, Align.MIN)
    sl, sw, sh = srv["size"]
    # inner space: battery flat on the floor between the hip servos, controller standing at the back, sensor at the front
    inner_x = max(bat["size"][0], sen["size"][0], 2 * sl + 12) + 2 * CLEAR
    inner_y = sen["size"][2] + bat["size"][1] * 0 + ctrl["size"][1] + 24.0          # sensor depth + controller + cable room
    inner_y = max(inner_y, bat["size"][1] + 2 * CLEAR)
    inner_z = max(sh - srv["tab_z"] + bat["size"][2] + 6, sen["size"][1] + 10)
    X, Y, Z = inner_x + 2 * wall, inner_y + 2 * wall, inner_z + wall
    body = Box(X, Y, Z, align=C) - Pos(0, 0, wall) * Box(inner_x, inner_y, inner_z, align=C)
    # front eyes: two transducer holes, centred on the sensor
    eye_z = wall + inner_z - sen["size"][1] / 2 - 4
    for dx in (-sen["eye_spacing"] / 2, sen["eye_spacing"] / 2):
        body -= Pos(dx, -Y / 2, eye_z) * Rot(90, 0, 0) * Cylinder(sen["eye_d"] / 2 + CLEAR, 2 * wall + 2)
    # hip servos: body pocket through the floor, shaft hanging down, tabs resting on the floor with screw holes
    hips = [-(sl / 2 + 4), sl / 2 + 4]
    for hx in hips:
        body -= Pos(hx, 0, 0) * Box(sl + 2 * CLEAR, sw + 2 * CLEAR, wall, align=C)
        for tx in (-srv["tab_span"] / 2 + 2.4, srv["tab_span"] / 2 - 2.4):
            body -= Pos(hx + tx, 0, 0) * Cylinder(srv["hole_d"] / 2 * 0.9, wall, align=C)
    # battery shelf: the hip servos stick up through the floor, so the battery rests on two rails above them
    shelf_z = wall + (sh - srv["tab_z"]) + 1.0
    for sy in (-inner_y / 2, inner_y / 2 - 4):
        body += Pos(0, sy + 2, shelf_z - 3) * Box(inner_x, 4, 3, align=C)
    # USB slot at the back for the controller
    body -= Pos(0, Y / 2, wall + 4) * Box(14, 2 * wall + 2, 9, align=(Align.CENTER, Align.CENTER, Align.MIN))

    lid = Box(X, Y, wall, align=C) + Pos(0, 0, -3) * (Box(inner_x - 2 * CLEAR, inner_y - 2 * CLEAR, 3, align=C)
                                                     - Box(inner_x - 2 * CLEAR - 3, inner_y - 2 * CLEAR - 3, 3, align=C))
    lid = Pos(0, 0, 3) * lid

    # leg: block; top socket for the hip horn hub, side pocket for the ankle servo (shaft outward along x)
    lx, ly, lz = sw + 2 * wall + 2 * CLEAR + 4, sl + 2 * wall + 2 * CLEAR, sh + wall + 6
    leg = Box(lx, ly, lz, align=C)
    leg -= Pos(0, 0, lz - 4) * Cylinder(srv["horn_hub_d"] / 2 + CLEAR, 4, align=C)
    leg -= Pos(0, 0, lz - 12) * Cylinder(1.0, 12, align=C)                       # horn screw
    leg -= Pos(0, 0, 0) * Box(sw + 2 * CLEAR, sl + 2 * CLEAR, sh + CLEAR, align=C)   # ankle servo pocket from below
    # foot: plate + upright with the ankle horn socket
    foot = Box(48, 30, 4, align=C) + Pos(0, 0, 4) * Box(10, 20, 14, align=C)
    foot -= Pos(0, 0, 18 - 4) * Cylinder(srv["horn_hub_d"] / 2 + CLEAR, 4, align=C)
    # wheel: disc with a hub socket and a tyre groove, for continuous-rotation servos
    wheel = Cylinder(22, 8, align=C) - Pos(0, 0, 4) * Cylinder(srv["horn_hub_d"] / 2 + CLEAR, 4, align=C)
    wheel -= Pos(0, 0, 3) * (Cylinder(23, 2, align=C) - Cylinder(21, 2, align=C))   # O-ring groove as a tyre

    parts = {"body": body, "lid": lid, "leg_left": leg, "leg_right": leg, "foot_left": foot, "foot_right": foot,
             "wheel_left": wheel, "wheel_right": wheel}
    for name, shp in parts.items():
        export_stl(shp, str(out / f"{name}.stl")); export_step(shp, str(out / f"{name}.step"))
    fits = {   # every bought part must fit its space
        "battery_on_shelf_above_servos": bat["size"][0] + 2 * CLEAR <= inner_x and bat["size"][1] + 2 * CLEAR <= inner_y
                                        and shelf_z + bat["size"][2] <= wall + inner_z,
        "sensor_behind_front": sen["size"][0] <= inner_x and sen["size"][1] + 4 <= inner_z,
        "controller_inside": ctrl["size"][0] <= inner_x and ctrl["size"][1] <= inner_y,
        "hip_pockets_do_not_touch": hips[1] - hips[0] >= sl + 2 * CLEAR + 2,
        "ankle_pocket_clears_servo": lx > sw + 2 * CLEAR and ly > sl + 2 * CLEAR and lz > sh + CLEAR,
    }
    report = {"body_mm": [round(X, 1), round(Y, 1), round(Z, 1)], "inner_mm": [round(inner_x, 1), round(inner_y, 1), round(inner_z, 1)],
              "fits": fits, "bom": [ctrl["label"], bat["label"], sen["label"], f"4 x {srv['label']}"],
              "warnings": [f"{p['label']}: measure yours" for p in (ctrl, bat, sen, srv) if p.get("verify")],
              "files": list(parts)}
    (out / "report.json").write_text(json.dumps(report, indent=1))
    return report
